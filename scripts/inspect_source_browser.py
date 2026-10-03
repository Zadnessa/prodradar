"""Read-only DevTools-диагностика фирменных страниц через Chromium.

Отчёт содержит только пути запросов, имена параметров/заголовков/cookies,
HTTP-статусы и структуру JSON. Значения токенов и cookies не сохраняются.
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
import sys
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from parsers.tls import CA_BUNDLE


def add_actions_browser_ca():
    """Временный пользовательский NSS trust только в одноразовом Actions runner."""
    if os.getenv('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('--source-ca допустим только в одноразовом GitHub Actions runner')
    database = Path.home() / '.pki' / 'nssdb'
    database.mkdir(parents=True, exist_ok=True)
    location = 'sql:' + str(database)
    nickname = 'ProductRadar official Russian root diagnostic'
    if not (database / 'cert9.db').exists():
        subprocess.run(['certutil', '-N', '--empty-password', '-d', location], check=True)
    if subprocess.run(['certutil', '-L', '-d', location, '-n', nickname],
                      capture_output=True).returncode == 0:
        raise RuntimeError('Диагностический сертификат уже существует; не перезаписываем')
    root = CA_BUNDLE.read_text().split('-----END CERTIFICATE-----', 1)[0] + '-----END CERTIFICATE-----\n'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pem') as certificate:
        certificate.write(root)
        certificate.flush()
        subprocess.run(['certutil', '-A', '-d', location, '-n', nickname,
                        '-t', 'C,,', '-i', certificate.name], check=True)
    return location, nickname


TARGETS = {
    'alfa': 'https://job.alfabank.ru/vacancies',
    'tbank': 'https://www.tbank.ru/career/it/',
    'tochka': 'https://hr.tochka.com/vacancies/catalog/',
    'domclick': 'https://career.domclick.ru/vacancies',
    'domclick_team': 'https://team.domclick.ru/',
    'dodo': 'https://dodoteam.ru/vacancies',
    'kuper': 'https://team.kuper.ru/vacancies',
    'mts': 'https://job.mts.ru/',
    'vk': 'https://team.vk.company/career/',
    'mtslink': 'https://job.mts-link.ru/vacancies/',
}


def url_metadata(url):
    parts = urlsplit(url)
    return {'url': f'{parts.scheme}://{parts.netloc}{parts.path}',
            'query_keys': sorted(parse_qs(parts.query, keep_blank_values=True))}


async def inspect_sources(names, probe_tbank_pagination=False, compare_http=False):
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
                if compare_http:
                    # Разные клиенты проверяют транспорт, а не повторяют один запрос.
                    import aiohttp
                    from curl_cffi.requests import AsyncSession
                    async with aiohttp.ClientSession(trust_env=True) as session:
                        try:
                            async with session.get(TARGETS[name], headers=config.REQUEST_HEADERS,
                                                   timeout=aiohttp.ClientTimeout(total=25)) as response:
                                result['http'] = {'status': response.status}
                                await response.read()
                        except Exception as exc:
                            result['http'] = {'error_type': type(exc).__name__}
                    async with AsyncSession(impersonate='chrome') as session:
                        try:
                            response = await session.get(TARGETS[name], headers=config.REQUEST_HEADERS, timeout=25)
                            result['chrome_http'] = {'status': response.status_code}
                        except Exception as exc:
                            result['chrome_http'] = {'error_type': type(exc).__name__}

                async def response_received(response):
                    request = response.request
                    if request.resource_type not in ('xhr', 'fetch', 'document'):
                        return
                    item = {**url_metadata(response.url), 'status': response.status,
                            'method': request.method, 'type': request.resource_type,
                            'request_header_names': sorted(request.headers),
                            'content_type': response.headers.get('content-type', '')}
                    network.append(item)
                    if '/getVacancies' in response.url:
                        try:
                            posted = request.post_data_json
                            item['post_data_keys'] = sorted(posted)
                            # Публичные параметры каталога; auth/csrf/session не сохраняются.
                            item['catalog_request'] = {key: posted[key] for key in ('filters', 'pagination')
                                                       if key in posted}
                        except Exception:
                            item['catalog_request_unreadable'] = True
                    if 'json' in item['content_type']:
                        try:
                            payload = await response.json()
                            item['json_type'] = type(payload).__name__
                            if isinstance(payload, dict):
                                item['json_keys'] = sorted(payload)
                                if '/getVacancies' in response.url and isinstance(payload.get('payload'), dict):
                                    item['catalog_count'] = len(payload['payload'].get('vacancies') or [])
                                    item['catalog_pagination'] = payload['payload'].get('nextPagination')
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
                    result['script_paths'] = [url_metadata(urljoin(page.url, script['src']))
                                              for script in soup.select('script[src]')][:30]
                    result['jsonld_present'] = bool(soup.select('script[type="application/ld+json"]'))
                    next_data = soup.find('script', id='__NEXT_DATA__')
                    if next_data:
                        try:
                            state = json.loads(next_data.string or '{}')
                            result['next_metadata'] = {'keys': sorted(state), 'has_build_id': bool(state.get('buildId')),
                                                       'page_props_keys': sorted((state.get('props') or {}).get('pageProps') or {})}
                        except (ValueError, TypeError):
                            result['next_metadata'] = {'invalid_json': True}
                    links = [urljoin(page.url, a['href']) for a in soup.select('a[href]')
                             if '/vacanc' in a['href'] or '/vakans' in a['href']]
                    result['vacancy_links'] = [url_metadata(url) for url in dict.fromkeys(links)][:12]
                    if name == 'tbank' and probe_tbank_pagination:
                        result['button_labels'] = [b.get_text(' ', strip=True) for b in soup.select('button')][:30]
                        # Пользователь разрешил диагностику через браузер и кнопки вакансий.
                        # Только чтение следующей страницы; формы отклика не используются.
                        more = page.get_by_role('button', name=re.compile(r'Показать (ещё|еще)'))
                        if await more.count():
                            # Первый одноимённый элемент раскрывает фильтры;
                            # последний под списком загружает вакансии.
                            await more.last.click(timeout=5000)
                            await asyncio.sleep(5)
                            result['pagination_clicked'] = True
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
    parser.add_argument('--compare-http', action='store_true', help='Сравнить обычный HTTP, Chrome TLS и Chromium')
    parser.add_argument('--probe-tbank-pagination', action='store_true',
                        help='Явная DevTools-диагностика одного POST по кнопке каталога, без выгрузки вакансий')
    parser.add_argument('--source-ca', action='store_true',
                        help='Временный официальный root CA для Chromium в Actions; TLS проверки сохранены')
    args = parser.parse_args()
    certificate = add_actions_browser_ca() if args.source_ca else None
    try:
        report = asyncio.run(inspect_sources(args.sources, args.probe_tbank_pagination, args.compare_http))
    finally:
        if certificate:
            location, nickname = certificate
            subprocess.run(['certutil', '-D', '-d', location, '-n', nickname], check=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for name, item in report.items():
        # Только публичные пути и схемы, без cookies/token values.
        compact = json.dumps(item, ensure_ascii=False, separators=(',', ':'))
        print(f'::notice title=source-inspection-{name}::{compact}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
