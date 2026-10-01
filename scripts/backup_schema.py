"""Снимок прикладной SQL-схемы public через Supabase Management API.

Не заменяет pg_dump всей платформы: auth/storage и внутренние схемы Supabase
не входят в копию. Неподдерживаемые объекты останавливают выгрузку.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import requests


CATALOG_QUERIES = {
    "tables": """SELECT c.relname AS name, c.relkind,
        c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
        ORDER BY c.relname""",
    "columns": """SELECT c.relname AS table_name, a.attname AS name,
        format_type(a.atttypid,a.atttypmod) AS type, a.attnotnull AS not_null,
        pg_get_expr(d.adbin,d.adrelid) AS default_expr,
        a.attidentity AS identity, a.attgenerated AS generated,
        CASE WHEN a.attidentity<>'' THEN pg_get_serial_sequence(
            format('%I.%I',n.nspname,c.relname),a.attname) END AS identity_sequence
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND c.relkind IN ('r','p')
        AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""",
    "sequences": """SELECT s.schemaname,s.sequencename,s.sequenceowner,s.data_type,
        s.start_value::text,s.min_value::text,s.max_value::text,
        s.increment_by::text,s.cycle,s.cache_size::text,s.last_value::text,
        d.refobjid::regclass::text AS owned_table,
        a.attname AS owned_column, d.deptype
        FROM pg_sequences s JOIN pg_namespace n ON n.nspname=s.schemaname
        JOIN pg_class c ON c.relnamespace=n.oid AND c.relname=s.sequencename
        LEFT JOIN pg_depend d ON d.objid=c.oid AND d.classid='pg_class'::regclass
            AND d.refclassid='pg_class'::regclass AND d.deptype IN ('a','i')
        LEFT JOIN pg_attribute a ON a.attrelid=d.refobjid AND a.attnum=d.refobjsubid
        WHERE s.schemaname='public' ORDER BY s.sequencename""",
    "constraints": """SELECT c.conrelid::regclass::text AS table_name,
        c.conname AS name, c.contype AS type, pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
        WHERE n.nspname='public' ORDER BY (c.contype='f'),c.conname""",
    "indexes": """SELECT i.indexdef AS definition FROM pg_indexes i
        JOIN pg_class c ON c.relname=i.indexname AND c.relnamespace='public'::regnamespace
        WHERE i.schemaname='public' AND NOT EXISTS
        (SELECT 1 FROM pg_constraint x WHERE x.conindid=c.oid) ORDER BY i.indexname""",
    "policies": "SELECT * FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname",
    "functions": """SELECT pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p WHERE p.pronamespace='public'::regnamespace
        AND p.prokind IN ('f','p') ORDER BY p.proname,p.oid""",
    "triggers": """SELECT pg_get_triggerdef(t.oid) AS definition, t.tgenabled AS enabled
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        WHERE c.relnamespace='public'::regnamespace AND NOT t.tgisinternal
        ORDER BY c.relname,t.tgname""",
    "grants": """SELECT c.relname AS name, c.relkind,
        CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,
        x.privilege_type AS privilege, x.is_grantable
        FROM pg_class c CROSS JOIN LATERAL aclexplode(c.relacl) x
        WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','S')
        ORDER BY c.relname,grantee,privilege""",
    "default_grants": """SELECT pg_get_userbyid(d.defaclrole) AS owner,
        d.defaclobjtype AS type,
        CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,
        x.privilege_type AS privilege,x.is_grantable
        FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) x
        WHERE d.defaclnamespace='public'::regnamespace
        ORDER BY owner,type,grantee,privilege""",
    "schema_grants": """SELECT CASE WHEN x.grantee=0 THEN 'PUBLIC'
        ELSE pg_get_userbyid(x.grantee) END AS grantee,
        x.privilege_type AS privilege,x.is_grantable
        FROM pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) x
        WHERE n.nspname='public' ORDER BY grantee,privilege""",
    "unsupported_types": """SELECT typname FROM pg_type t
        WHERE t.typnamespace='public'::regnamespace AND t.typtype IN ('e','d','r')""",
    "extensions": """SELECT e.extname,e.extversion,n.nspname FROM pg_extension e
        JOIN pg_namespace n ON n.oid=e.extnamespace ORDER BY e.extname""",
}


def ident(value):
    return '"' + value.replace('"', '""') + '"'


def role(value):
    return 'PUBLIC' if value == 'PUBLIC' else ident(value)


def relation(value):
    # Имена из pg_catalog текущего приложения простые; сложные не угадываем.
    parts = value.split('.')
    if any('"' in part for part in parts):
        raise ValueError('Неподдерживаемое составное имя')
    return '.'.join(ident(part) for part in parts)


def render_schema(catalog):
    if catalog['unsupported_types'] or any(t['relkind'] != 'r' for t in catalog['tables']):
        raise ValueError('Для нестандартных типов/таблиц требуется pg_dump')
    if any(c['generated'] for c in catalog['columns']):
        raise ValueError('Для generated columns требуется pg_dump')
    if any(t['enabled'] != 'O' for t in catalog['triggers']):
        raise ValueError('Неподдерживаемый режим триггера')
    statements = ['BEGIN;', 'SET search_path = public, pg_catalog;']
    for seq in catalog['sequences']:
        if seq['deptype'] != 'i':
            statements.append(f'CREATE SEQUENCE public.{ident(seq["sequencename"])} '
                              f'AS {seq["data_type"]} START {seq["start_value"]} '
                              f'INCREMENT {seq["increment_by"]} MINVALUE {seq["min_value"]} '
                              f'MAXVALUE {seq["max_value"]} CACHE {seq["cache_size"]} '
                              f'{"CYCLE" if seq["cycle"] else "NO CYCLE"};')
    for table in catalog['tables']:
        columns = []
        for col in catalog['columns']:
            if col['table_name'] != table['name']:
                continue
            value = f'{ident(col["name"])} {col["type"]}'
            if col['identity']:
                seq = next(s for s in catalog['sequences']
                           if s['owned_table'].removeprefix('public.') == table['name']
                           and s['owned_column'] == col['name'])
                value += (' GENERATED ' + ('ALWAYS' if col['identity'] == 'a' else 'BY DEFAULT')
                          + ' AS IDENTITY (SEQUENCE NAME ' + relation(col['identity_sequence'])
                          + f' START WITH {seq["start_value"]} INCREMENT BY {seq["increment_by"]}'
                          + f' MINVALUE {seq["min_value"]} MAXVALUE {seq["max_value"]}'
                          + f' CACHE {seq["cache_size"]}'
                          + (' CYCLE)' if seq['cycle'] else ' NO CYCLE)'))
            elif col['default_expr'] is not None:
                value += ' DEFAULT ' + col['default_expr']
            if col['not_null']:
                value += ' NOT NULL'
            columns.append(value)
        statements.append(f'CREATE TABLE public.{ident(table["name"])} (\n  '
                          + ',\n  '.join(columns) + '\n);')
    for seq in catalog['sequences']:
        if seq['deptype'] == 'a':
            statements.append(f'ALTER SEQUENCE public.{ident(seq["sequencename"])} OWNED BY '
                              f'{relation(seq["owned_table"])}.{ident(seq["owned_column"])};')
    statements.extend(row['definition'].rstrip(';') + ';' for row in catalog['functions'])
    for constraint in catalog['constraints']:
        statements.append(f'ALTER TABLE {relation(constraint["table_name"])} ADD CONSTRAINT '
                          f'{ident(constraint["name"])} {constraint["definition"]};')
    statements.extend(row['definition'].rstrip(';') + ';' for row in catalog['indexes'])
    statements.extend(row['definition'].rstrip(';') + ';' for row in catalog['triggers'])
    for table in catalog['tables']:
        if table['rls']:
            statements.append(f'ALTER TABLE public.{ident(table["name"])} ENABLE ROW LEVEL SECURITY;')
        if table['force_rls']:
            statements.append(f'ALTER TABLE public.{ident(table["name"])} FORCE ROW LEVEL SECURITY;')
    for policy in catalog['policies']:
        roles = policy['roles']
        if isinstance(roles, str):
            roles = roles.strip('{}').split(',')
        value = (f'CREATE POLICY {ident(policy["policyname"])} ON public.{ident(policy["tablename"])} '
                 f'AS {policy["permissive"]} FOR {policy["cmd"]} TO '
                 + ', '.join(role(r) for r in roles))
        if policy['qual'] is not None:
            value += f' USING ({policy["qual"]})'
        if policy['with_check'] is not None:
            value += f' WITH CHECK ({policy["with_check"]})'
        statements.append(value + ';')
    # Сбрасываем наследованные гранты перед точным восстановлением ACL.
    grantees = {'PUBLIC', 'anon', 'authenticated', 'service_role'}
    grantees.update(g['grantee'] for g in catalog['grants'])
    for obj in catalog['tables'] + [{'name': s['sequencename']} for s in catalog['sequences']]:
        statements.append(f'REVOKE ALL ON public.{ident(obj["name"])} FROM '
                          + ', '.join(role(r) for r in sorted(grantees)) + ';')
    for grant in catalog['grants']:
        statements.append(f'GRANT {grant["privilege"]} ON public.{ident(grant["name"])} '
                          f'TO {role(grant["grantee"])}'
                          + (' WITH GRANT OPTION;' if grant['is_grantable'] else ';'))
    for grant in catalog['schema_grants']:
        statements.append(f'GRANT {grant["privilege"]} ON SCHEMA public TO {role(grant["grantee"])}'
                          + (' WITH GRANT OPTION;' if grant['is_grantable'] else ';'))
    object_types = {'r': 'TABLES', 'S': 'SEQUENCES', 'f': 'FUNCTIONS'}
    for grant in catalog['default_grants']:
        statements.append(f'ALTER DEFAULT PRIVILEGES FOR ROLE {role(grant["owner"])} '
                          f'IN SCHEMA public GRANT {grant["privilege"]} '
                          f'ON {object_types[grant["type"]]} TO {role(grant["grantee"])}'
                          + (' WITH GRANT OPTION;' if grant['is_grantable'] else ';'))
    statements.append('COMMIT;')
    return '\n'.join(statements) + '\n'


def backup_schema(destination, project_ref, token):
    destination = Path(destination)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Один statement даёт согласованный MVCC-снимок каталога.
    query = 'SELECT json_build_object(' + ','.join(
        "'" + name + "',COALESCE((SELECT json_agg(x) FROM (" + sql + ") x),'[]'::json)"
        for name, sql in CATALOG_QUERIES.items()) + ') AS catalog'
    response = requests.post(f'https://api.supabase.com/v1/projects/{project_ref}/database/query',
                             headers={'Authorization': f'Bearer {token}'},
                             json={'query': query}, timeout=90)
    response.raise_for_status()
    catalog = response.json()[0]['catalog']
    schema = render_schema(catalog)
    files = {'catalog.json': json.dumps(catalog, ensure_ascii=False, indent=2) + '\n',
             'schema.sql': schema}
    hashes = {}
    for name, content in files.items():
        path = destination / name
        path.write_text(content)
        path.chmod(0o600)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'project_ref': project_ref,
                'scope': 'public: таблицы, sequences, constraints, indexes, RLS, policies, ACL, functions, triggers',
                'excluded': 'auth, storage, внутренние схемы и роли платформы Supabase; данные отдельно',
                'complete': True, 'files': hashes,
                'objects': {name: len(rows) for name, rows in catalog.items()}}
    path = destination / 'manifest.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    path.chmod(0o600)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--project-ref', required=True)
    args = parser.parse_args()
    try:
        manifest = backup_schema(args.destination, args.project_ref, os.environ['SUPABASE_ACCESS_TOKEN'])
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_type': type(exc).__name__}))
        return 1
    print(json.dumps({'ok': True, 'objects': manifest['objects'], 'files': manifest['files']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
