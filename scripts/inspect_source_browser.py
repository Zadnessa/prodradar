"""Read-only DevTools-диагностика фирменных страниц через Chromium.

Отчёт содержит только пути запросов, имена параметров/заголовков/cookies,
HTTP-статусы и структуру JSON. Значения токенов и cookies не сохраняются.
"""

import argparse
import asyncio
import json
import os
import re
from pathlib import Path
import sys
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


TARGETS = {
    'alfa': 'https://job.alfabank.ru/vacancies',
    'tbank': 'https://www.tbank.ru/career/it/',
    'tochka': 'https://hr.tochka.com/vacancies/catalog/',
    'domclick': 'https://career.domclick.ru/vacancies',
    'domclick_team': 'https://team.domclick.ru/',
    'dodo': 'https://dodoteam.ru/vacancies',
    'kuper': 'https://team.kuper.ru/vacancies',
    'mtslink': 'https://job.mts-link.ru/vacancies/',
}


def url_metadata(url):
    parts = urlsplit(url)
    return {'url': f'{parts.scheme}://{parts.netloc}{parts.path}',
            'query_keys': sorted(parse_qs(parts.query, keep_blank_values=True))}


async def inspect_sources(names):
    results = {}
    async with async_playwright() as playwright:
        proxy = os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')
        browser = await playwright.chromium.launch(headless=True,
                    **({'proxy': {'server': proxy}} if proxy else {}))
        semaphore = asyncio.Semaphore(3)

        async def inspect(name):
            async with semaphore:
                context = await browser.new_context(user_agent=config.REQUEST_HEADERS['User-Agent'], locale='ru-RU')
                page = await context.new_page()
                network = []
                pending = set()
                result = {'page': TARGETS[name], 'network': network}

                async def response_received(response):
                    request = response.request
                    if request.resource_type not in ('xhr', 'fetch', 'document'):
                        return
                    item = {**url_metadata(response.url), 'status': response.status,
                            'method': request.method, 'type': request.resource_type,
                            'request_header_names': sorted(request.headers),
                            'content_type': response.headers.get('content-type', '')}
                    network.append(item)
                    if 'json' in item['content_type']:
                        try:
                            payload = await response.json()
                            item['json_type'] = type(payload).__name__
                            if isinstance(payload, dict):
                                item['json_keys'] = sorted(payload)
                                result_payload = payload.get('result')
                                if isinstance(result_payload, dict):
                                    item['result_keys'] = sorted(result_payload)
                                elif isinstance(result_payload, list):
                                    item['result_length'] = len(result_payload)
                            elif isinstance(payload, list):
                                item['list_length'] = len(payload)
                        except Exception:
                            item['json_unreadable'] = True

                def on_response(response):
                    task = asyncio.create_task(response_received(response))
                    pending.add(task)
                    task.add_done_callback(pending.discard)

                page.on('response', on_response)
                def request_failed(request):
                    if request.resource_type in ('xhr', 'fetch', 'document'):
                        failure = request.failure or ''
                        match = re.fullmatch(r'net::[A-Z0-9_]+', failure)
                        network.append({**url_metadata(request.url), 'type': request.resource_type,
                                        'failure': failure if match else 'request_failed'})
                page.on('requestfailed', request_failed)
                try:
                    response = await page.goto(TARGETS[name], timeout=25000, wait_until='domcontentloaded')
                    result['page_status'] = response.status if response else None
                    await asyncio.sleep(8)
                    html = await page.content()
                    result['html_length'] = len(html)
                    result['cookie_names'] = sorted({c['name'] for c in await context.cookies()})
                    soup = BeautifulSoup(html, 'html.parser')
                    result['title'] = soup.title.get_text(strip=True) if soup.title else None
                    links = [urljoin(page.url, a['href']) for a in soup.select('a[href]')
                             if '/vacanc' in a['href'] or '/vakans' in a['href']]
                    result['vacancy_links'] = [url_metadata(url) for url in dict.fromkeys(links)][:12]
                    if links:
                        # Переход по первой карточке даёт detail-запрос без кликов/форм.
                        same_host = [url for url in links if urlsplit(url).netloc == urlsplit(page.url).netloc
                                     and urlsplit(url).path.rstrip('/') != urlsplit(page.url).path.rstrip('/')]
                        if same_host:
                            await page.goto(same_host[0], timeout=25000, wait_until='domcontentloaded')
                            await asyncio.sleep(3)
                except Exception as exc:
                    # Playwright exception text может включить URL с реквизитами.
                    result['error_type'] = type(exc).__name__
                finally:
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    results[name] = result
                    await context.close()
                print(json.dumps({'source': name, 'page_status': result.get('page_status'),
                                  'network_requests': len(network), 'error_type': result.get('error_type')}), flush=True)

        await asyncio.gather(*(inspect(name) for name in names))
        await browser.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', nargs='+', choices=TARGETS, default=list(TARGETS))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(inspect_sources(args.sources))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
