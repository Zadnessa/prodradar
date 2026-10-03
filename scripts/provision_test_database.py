"""Восстановление схемы и двух справочников в пустой отдельный проект Supabase.

Пользователи, доставки, события и старые вакансии в тест не переносятся.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backup_schema import CATALOG_QUERIES, ident, role


ORIGINAL_PROJECT_REF = "ykbtejjedefibdgyfgov"


def preserve_platform_defaults(schema, source, target, current_user):
    """Платформенные ACL сохраняем только после точного сравнения с копией."""
    owners = {grant['owner'] for grant in source if grant['owner'] != current_user}
    for owner in owners:
        expected = [grant for grant in source if grant['owner'] == owner]
        actual = [grant for grant in target if grant['owner'] == owner]
        if expected != actual:
            raise ValueError('Default privileges платформенной роли не совпадают')
    prefixes = tuple(f'ALTER DEFAULT PRIVILEGES FOR ROLE {role(owner)} ' for owner in owners)
    return '\n'.join(line for line in schema.splitlines() if not line.startswith(prefixes))


def verify_files(directory, manifest_key):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if not manifest.get('complete'):
        raise ValueError('Резервная копия не завершена')
    entries = manifest[manifest_key]
    for name, metadata in entries.items():
        filename = name if manifest_key == 'files' else name + '.ndjson'
        expected = metadata if isinstance(metadata, str) else metadata['sha256']
        if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != expected:
            raise ValueError('SHA-256 файла не совпадает с манифестом')
    return manifest


def provision(project_ref, schema_directory, data_directory, token):
    if not project_ref or project_ref == ORIGINAL_PROJECT_REF:
        raise ValueError('Восстановление в исходный проект запрещено')
    schema_manifest = verify_files(schema_directory, 'files')
    data_manifest = verify_files(data_directory, 'tables')
    if schema_manifest['project_ref'] == project_ref:
        raise ValueError('Проект назначения совпадает с проектом резервной копии')
    session = requests.Session()
    session.headers['Authorization'] = f'Bearer {token}'
    base = f'https://api.supabase.com/v1/projects/{project_ref}'
    response = session.get(base, timeout=30)
    response.raise_for_status()
    if response.json()['id'] != project_ref:
        raise ValueError('Identity проекта не совпадает')

    def query(sql):
        response = session.post(base + '/database/query', json={'query': sql}, timeout=90)
        response.raise_for_status()
        return response.json()

    existing = query("SELECT tablename FROM pg_tables WHERE schemaname='public';")
    if existing:
        raise ValueError('Прикладная схема назначения не пуста; перезапись запрещена')
    schema = (schema_directory / 'schema.sql').read_text().strip()
    if not schema.startswith('BEGIN;') or not schema.endswith('COMMIT;'):
        raise ValueError('Неподдерживаемый формат schema.sql')
    catalog = json.loads((schema_directory / 'catalog.json').read_text())
    defaults = query(CATALOG_QUERIES['default_grants'])
    current_user = query('SELECT current_user AS name')[0]['name']
    schema = preserve_platform_defaults(schema, catalog['default_grants'], defaults, current_user)
    statements = [schema[:-len('COMMIT;')]]
    for table in ('companies', 'city_mappings'):
        path = data_directory / f'{table}.ndjson'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != data_manifest['tables'][table]['rows']:
            raise ValueError('Число строк справочника не совпадает')
        # JSON передаётся в SQL literal с удвоением одинарных кавычек.
        payload = json.dumps(rows, ensure_ascii=False).replace("'", "''")
        statements.append(f"INSERT INTO public.{ident(table)} OVERRIDING SYSTEM VALUE "
                          f"SELECT * FROM jsonb_populate_recordset(NULL::public.{ident(table)}, '{payload}'::jsonb);")
    statements.extend([
        "SELECT setval(pg_get_serial_sequence('public.city_mappings','id'), COALESCE(max(id),1), count(*)>0) FROM public.city_mappings;",
        "NOTIFY pgrst, 'reload schema';",
        'COMMIT;',
    ])
    # Вторая проверка внутри транзакции предотвращает гонку с другим provision.
    guard = """DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public')
        THEN RAISE EXCEPTION 'public is not empty'; END IF; END $$;"""
    statements[0] = statements[0].replace('BEGIN;', 'BEGIN;\n' + guard, 1)
    query('\n'.join(statements))
    if query(CATALOG_QUERIES['default_grants']) != catalog['default_grants']:
        raise ValueError('Default privileges после восстановления не совпадают')
    counts = query('SELECT ' + ','.join(
        f'(SELECT count(*) FROM public.{ident(table)}) AS {ident(table)}'
        for table in data_manifest['tables']))[0]
    for table, count in counts.items():
        expected = data_manifest['tables'][table]['rows'] if table in ('companies', 'city_mappings') else 0
        if count != expected:
            raise ValueError('Неожиданное число строк в восстановленном тестовом проекте')
    session.close()
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-ref', required=True)
    parser.add_argument('--schema-directory', type=Path, required=True)
    parser.add_argument('--data-directory', type=Path, required=True)
    args = parser.parse_args()
    try:
        counts = provision(args.project_ref, args.schema_directory, args.data_directory,
                           os.environ['SUPABASE_ACCESS_TOKEN'])
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps({'ok': True, 'project_ref': args.project_ref, 'counts': counts}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
