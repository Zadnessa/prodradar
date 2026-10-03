"""Идемпотентная подготовка схемы project/bizdev только в test БД."""

import os
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.collect_test import check_target

PROJECT_REF = 'jmsdxgylyjxwdwmdrmxw'


def main():
    if os.getenv('PRODRADAR_PROFILE') != 'test':
        raise ValueError('Нужен явный test профиль')
    check_target(PROJECT_REF)
    base = f'https://api.supabase.com/v1/projects/{PROJECT_REF}'
    headers = {'Authorization': 'Bearer ' + os.environ['SUPABASE_ACCESS_TOKEN']}
    response = requests.get(base, headers=headers, timeout=30)
    response.raise_for_status()
    if response.json().get('id') != PROJECT_REF:
        raise ValueError('Чужой проект')
    sql = (Path(__file__).resolve().parents[1] / 'database/role_pool.sql').read_text()
    response = requests.post(base + '/database/query', headers=headers, json={'query': sql}, timeout=60)
    if not response.ok:
        raise RuntimeError(f'Подготовка схемы: HTTP {response.status_code}')
    print('Test схема source_pool и метаданных ролей готова; production не изменён')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
