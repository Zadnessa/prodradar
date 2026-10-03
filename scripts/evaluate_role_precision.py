"""Эффект точечных ограничений на вычитанной старой выдаче, отдельно от recall."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery.roles import classify, VERSION
from scripts.role_filter_ablation import variants


def evaluate(audit):
    rows = audit['rows']
    stages = []
    for name, classifier in variants()[4:8]:
        selected = {r['id'] for r in rows if classifier(r)['status'] == 'selected'}
        stages.append({'step': name, 'selected': len(selected),
                       'known_noise_retained': sum(r['audit_decision'] == 'drop' and r['id'] in selected for r in rows),
                       'confirmed_target_losses': [r['id'] for r in rows if r['retain'] and r['id'] not in selected],
                       'mixed_commercial_retained': [r['id'] for r in rows if r['audit_decision'] == 'review' and r['id'] in selected]})
    kept = [r for r in rows if classify(r)['status'] == 'selected']
    mixed = [r for r in rows if r['audit_decision'] == 'review']
    return {'version': VERSION, 'method': audit['method'], 'before_count': len(rows),
            'after_count': len(kept), 'removed_by_kind': dict(Counter(r['kind'] for r in rows if not r['retain'])),
            'families_after': dict(Counter(f for r in kept for f in classify(r)['families'])),
            'potential_target_loss_if_all_mixed_are_relevant': len(mixed) / (len(kept) + len(mixed)),
            'stages': stages, 'mixed_ids': [r['id'] for r in mixed],
            'excluded': [{'id': r['id'], 'company': r['company'], 'title': r['title'],
                          'kind': r['kind'], 'evidence': r['evidence']} for r in rows if not r['retain']]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(json.loads(Path('tests/fixtures/role_precision_audit.json').read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('before_count', 'after_count', 'removed_by_kind', 'families_after')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
