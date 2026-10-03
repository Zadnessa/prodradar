"""Первый срез контрактов общих каталогов без БД, Telegram и секретов."""

import asyncio
import json
from pathlib import Path
import re
import sys

import aiohttp
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from parsers.tls import source_ssl_context

TARGETS = {
    'alfa': ('https://job.alfabank.ru/api/vacancies', {'take': 200, 'skip': 0}),
    'vk': ('https://team.vk.company/career/api/v2/vacancies/', {'limit': 100, 'offset': 0}),
    'wildberries': ('https://career.rwb.ru/crm-api/api/v1/pub/vacancies', {'limit': 200, 'offset': 0}),
    'ozon': ('https://job-api.ozon.ru/v2/vacancy', {'meta.limit': 100, 'meta.page': 1}),
    'sber': ('https://rabota.sber.ru/public/app-candidate-public-api-gateway/api/v1/publications', {'skip': 0, 'take': 200}),
    'x5': ('https://rabota.x5.ru/public/api/vacancies/vacancies/', {'page': 1, 'page_size': 100}),
    'tochka': ('https://hr.tochka.com/api/v2/hr/vacancies/', {'page': 1}),
    'yandex': ('https://yandex.ru/jobs/api/publications', {'page_size': 100}),
    'avito': ('https://career.avito.com/vacancies/', {'action': 'filter'}),
    'kontur': ('https://kontur.ru/career/vacancies', {}),
}


def describe(value, depth=0):
    if depth > 2:
        return type(value).__name__
    if isinstance(value, dict):
        return {k: describe(v, depth + 1) for k, v in value.items() if k not in {'description', 'html'}}
    if isinstance(value, list):
        return {'length': len(value), 'first_schema': describe(value[0], depth + 1) if value else None}
    if isinstance(value, (int, bool)) or value is None:
        return value
    return str(value)[:180] if re.search(r'count|total|page|limit|offset|next|previous', str(value), re.I) else type(value).__name__


async def main():
    async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=45)) as session:
        for name, (url, params) in TARGETS.items():
            try:
                headers = {**config.REQUEST_HEADERS, 'Referer': url, 'X-Requested-With': 'XMLHttpRequest'}
                async with session.get(url, params=params, headers=headers, ssl=source_ssl_context(url)) as response:
                    response.raise_for_status()
                    body = await response.text()
                    try:
                        payload = json.loads(body)
                    except json.JSONDecodeError:
                        payload = {'html': body}
                report = {'source': name, 'schema': describe(payload)}
                rows = []
                def walk(value):
                    if isinstance(value, dict):
                        title = value.get('title') or value.get('name')
                        if isinstance(title, str) and re.search(r'проект|project|развити|develop|партн|partner|delivery|scrum|монетизац|moneti|growth', title, re.I):
                            rows.append({k: v for k, v in value.items() if k in {'id', 'name', 'title', 'profAreas', 'professionalRoles', 'direction', 'directions', 'category', 'department', 'businessLineId', 'vacancy_categories'}})
                        for child in value.values():
                            walk(child)
                    elif isinstance(value, list):
                        for child in value:
                            walk(child)
                walk(payload)
                report['role_samples'] = rows[:45]
                if payload.get('html'):
                    soup = BeautifulSoup(payload['html'], 'html.parser')
                    report['html_links'] = [{'text': a.get_text(' ', strip=True)[:140], 'href': a.get('href')} for a in soup.find_all('a', href=True) if re.search(r'vacanc|direction|project|развит|проект', a.get('href', '') + a.get_text(), re.I)][:70]
            except Exception as exc:
                report = {'source': name, 'error': type(exc).__name__, 'http_status': getattr(exc, 'status', None)}
            print('::notice title=role-catalog-' + name + '::' + json.dumps(report, ensure_ascii=False, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
