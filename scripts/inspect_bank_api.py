"""Read-only проверка структуры банковских API и актуальных фильтров."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

import aiohttp

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
        for name, filters in [('current_filter', {'tcareer_it_profession': ['product-management']}),
                              ('unfiltered', {})]:
            payload = {'filters': filters, 'pagination': {'it': {'limit': 100, 'offset': 0}}}
            async with session.post(url, json=payload, ssl=source_ssl_context(url)) as response:
                response.raise_for_status()
                body = await response.json()
            detail = body.get('payload') or {}
            vacancies = detail.get('vacancies') or []
            result[name] = {'structure': structure(body), 'nextPagination': detail.get('nextPagination'),
                            'vacancies': [{key: item.get(key) for key in ('title', 'seoSlug', 'urlSlug', 'tags')}
                                          for item in vacancies]}
            print(json.dumps({'request': name, 'count': len(vacancies), 'keys': list(body)}, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asyncio.run(inspect()), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
