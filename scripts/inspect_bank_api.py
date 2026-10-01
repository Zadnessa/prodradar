"""Read-only проверка структуры банковских API и актуальных фильтров."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

import aiohttp
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from parsers.tls import source_ssl_context


def structure(value, depth=0):
    if depth > 5:
        return type(value).__name__
    if isinstance(value, dict):
        return {key: structure(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        return {'length': len(value), 'sample': [structure(item, depth + 1) for item in value[:2]]}
    # Только публичные идентификаторы/названия фильтров и вакансий в sample ниже.
    return type(value).__name__


async def inspect():
    result = {}
    async with aiohttp.ClientSession(trust_env=True, headers=config.REQUEST_HEADERS,
                                    timeout=aiohttp.ClientTimeout(total=30)) as session:
        url = 'https://www.tbank.ru/pfpjobs/papi/getVacancies'
        for name, filters in [('current_direction', {'direction': ['it']}),
                              ('unfiltered', {}),
                              ('current_filter', {'tcareer_it_profession': ['product-management']})]:
            payload = {'filters': filters, 'pagination': {'limit': 100, 'offset': 0}}
            body = None
            for attempt in range(3):
                async with session.post(url, json=payload, ssl=source_ssl_context(url)) as response:
                    if response.status == 429 and attempt < 2:
                        await response.read()
                        await asyncio.sleep(10 * (attempt + 1))
                        continue
                    if response.status != 200:
                        result[name] = {'status': response.status}
                        break
                    body = await response.json()
                    break
            if body is None:
                continue
            detail = body.get('payload') or {}
            vacancies = detail.get('vacancies') or []
            result[name] = {'structure': structure(body), 'resultCode': body.get('resultCode'),
                            'nextPagination': detail.get('nextPagination'),
                            'vacancies': [{key: item.get(key) for key in ('title', 'seoSlug', 'urlSlug', 'tags')}
                                          for item in vacancies]}
            print(json.dumps({'request': name, 'count': len(vacancies), 'keys': list(body)}, ensure_ascii=False))
            await asyncio.sleep(5)
        html_url = 'https://www.tbank.ru/career/it/'
        async with session.get(html_url, ssl=source_ssl_context(html_url)) as response:
            if response.status == 200:
                soup = BeautifulSoup(await response.text(), 'html.parser')
                result['page'] = {'script_ids': [tag.get('id') for tag in soup.select('script[id]')],
                                  'json_scripts': [structure(json.loads(tag.string or '{}'))
                                                   for tag in soup.select('script[type="application/json"]')],
                                  'vacancy_links': [{'url': a.get('href'), 'text': a.get_text(' ', strip=True)}
                                                    for a in soup.select('a[href*="/vacancy/"]')][:100]}
                state_tag = soup.find('script', id='__TRAMVAI_STATE__')
                if state_tag:
                    stores = json.loads(state_tag.string or '{}').get('stores') or {}
                    result['page']['public_filters'] = stores.get('filtersStore')
                    result['page']['public_pagination'] = (stores.get('vacanciesStore') or {}).get('nextPagination')
            else:
                result['page'] = {'status': response.status}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asyncio.run(inspect()), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
