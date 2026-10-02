"""Переотбор существующей TEST-ленты без рассылки и сброса истории.

По умолчанию только dry run. --apply атомарно меняет актуальный snapshot,
если заголовки и описания не изменились между чтением и записью.
"""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def selection_plan(rows):
    from database.supabase_client import compute_content_hash
    from delivery.roles import apply_selection, classify
    result = []
    for row in rows:
        decision = classify(row)
        updated = apply_selection(dict(row), decision)
        result.append({'id': row['id'], 'title': row['title'], 'description': row.get('description'),
                       'is_active': decision['status'] == 'selected',
                       'role_families': decision['families'], 'selection_version': decision['version'],
                       'content_hash': compute_content_hash(updated),
                       'company': row['company'], 'decision': decision})
    return result


def update_sql(plan):
    def literal(value):
        return 'NULL' if value is None else "'" + str(value).replace("'", "''") + "'"
    if not plan or len({r['id'] for r in plan}) != len(plan):
        raise ValueError('Пустой или дублирующийся план')
    values = ',\n'.join('(' + ','.join([
        literal(r['id']), literal(r['title']),
        literal(hashlib.md5(r['description'].encode('utf-8')).hexdigest() if r['description'] is not None else None),
        'true' if r['is_active'] else 'false',
        'ARRAY[' + ','.join(literal(f) for f in r['role_families']) + ']::text[]',
        literal(r['selection_version']), literal(r['content_hash']),
        literal(json.dumps({k: v for k, v in r['decision'].items() if k != 'native_groups'})) + '::jsonb']) + ')' for r in plan)
    # role_families в TEST имеет тип text[]. Снимок защищён от конкурентного cron.
    # MD5 здесь только индикатор смены публичного описания, не секрет/подпись.
    # Полные body в SQL превышают лимит Management API; native groups сохраняются.
    return f"""WITH proposed(id,title,description_hash,is_active,families,version,hash,decision) AS (
      VALUES {values}
    ), matching AS (
      SELECT p.* FROM proposed p JOIN public.vacancies v ON v.id=p.id
      WHERE v.selection_profile='project_bizdev' AND v.is_active=true
        AND v.title=p.title AND md5(v.description) IS NOT DISTINCT FROM p.description_hash
    ), changed AS (
      UPDATE public.vacancies v SET is_active=p.is_active, role_families=p.families,
        selection_version=p.version, content_hash=p.hash,
        source_json=jsonb_set(coalesce(v.source_json,'{{}}'::jsonb),'{{selection}}',
          coalesce(v.source_json->'selection','{{}}'::jsonb)||p.decision,true)
      FROM matching p WHERE v.id=p.id AND (SELECT count(*) FROM matching)={len(plan)}
      RETURNING v.id
    ) SELECT count(*) AS changed FROM changed"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from runtime_profiles import select_profile, verify_bot
    profile = select_profile('test')
    verify_bot(profile)
    from database.supabase_client import SupabaseService
    db = SupabaseService()
    db._guard_pool()
    rows = []
    while True:
        page = db._vacancies_select(db._vacancy_columns()).eq('is_active', True).order('id').range(
            len(rows), len(rows) + 999).execute().data or []
        rows.extend(page)
        if len(page) < 1000:
            break
    plan = selection_plan(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    if args.apply:
        import requests
        token = os.environ['SUPABASE_ACCESS_TOKEN']
        logging.disable(logging.CRITICAL)
        response = requests.post(f"https://api.supabase.com/v1/projects/{profile['project_ref']}/database/query",
                                 headers={'Authorization': f'Bearer {token}'},
                                 json={'query': update_sql(plan)}, timeout=90)
        response.raise_for_status()
        if response.json() != [{'changed': len(plan)}]:
            raise RuntimeError('Snapshot изменился; переотбор не применён')
    print(json.dumps({'applied': args.apply, 'snapshot': len(plan),
                      'retained': sum(r['is_active'] for r in plan),
                      'excluded': [{'id': r['id'], 'title': r['title']} for r in plan if not r['is_active']]},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
