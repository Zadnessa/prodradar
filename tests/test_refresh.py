"""Регрессии контрактов источников и полноты резервной выгрузки."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aiohttp

from parsers.twogis import TwoGisParser
from parsers.lamoda import LamodaParser
from parsers.kontur import KonturParser
from parsers.hh import HHParser
from scripts.backup_database import backup_database


class Response:
    def __init__(self, data=None, text='', status=200):
        self.data, self.body, self.status = data, text, status
        self.url = 'https://example.com/vacancies'

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self, **kwargs):
        return self.data

    async def text(self):
        return self.body

    def raise_for_status(self):
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status, message='Ошибка API')


class Session:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


class ParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_twogis_reads_every_page_and_uses_api_fields(self):
        def item(raw_id):
            return {'id': raw_id, 'title': ' Менеджер продукта ', 'isRemote': True,
                    'direction': {'slug': 'product'}, 'city': None}
        session = Session(Response({'items': [item(1)], 'totalPages': 2, 'totalItems': 2}),
                          Response({'items': [item(2)], 'totalPages': 2, 'totalItems': 2}))
        result = await TwoGisParser().parse(session, set(), {})
        self.assertEqual([v['id'] for v in result], ['2gis_1', '2gis_2'])
        self.assertEqual(result[0]['title'], 'Менеджер продукта')
        self.assertEqual(result[0]['url'], 'https://job.2gis.ru/vacancies/product/1')
        self.assertEqual(result[0]['work_format'], 'Удалёнка')
        self.assertEqual(session.calls[1][1]['params']['page'], 2)

    async def test_twogis_incomplete_collection_raises(self):
        session = Session(Response({'items': [], 'totalPages': 1, 'totalItems': 10}))
        with self.assertRaises(ValueError):
            await TwoGisParser().parse(session, set(), {})

    async def test_twogis_enrichment_preserves_existing_fields_and_full_text(self):
        description = 'Полный текст ' * 700
        vacancy = {'id': '2gis_574', 'city': 'Москва', 'description': ''}
        session = Session(Response({'description': '<p>' + description + '</p>', 'city': {'name': 'Казань'}}))
        await TwoGisParser().enrich(session, vacancy)
        self.assertEqual(vacancy['city'], 'Москва')
        self.assertEqual(vacancy['description'], description.strip())
        await TwoGisParser().enrich(Session(Response({'description': '<p>Короткий</p>'})), vacancy)
        self.assertEqual(vacancy['description'], description.strip())

    async def test_lamoda_never_leaks_raw_id_even_without_enrichment(self):
        session = Session(Response({'data': [{'id': 2906, 'slug': 'product', 'name': 'Product Manager'}],
                                    'meta': {'total': 1, 'limit': 100}}),
                          Response({'data': {'attributes': {'duties': '<p>Полное описание</p>'}}}))
        parser = LamodaParser()
        vacancy = (await parser.parse(session, set(), {}))[0]
        self.assertFalse(any(key.startswith('_') for key in vacancy))
        with patch('parsers.lamoda.asyncio.sleep', return_value=None):
            await parser.enrich(session, vacancy)
        self.assertTrue(session.calls[-1][0].endswith('/2906'))
        self.assertEqual(vacancy['description'], 'Полное описание')

    async def test_kontur_title_does_not_include_location_or_format(self):
        html = '''<a href="/career/vacancies/5837" class="vacancy">
        <span class="vacancy__title">Менеджер продукта, middle+</span>
        <div class="vacancy__description"><span>Екатеринбург</span><span>Удалённо</span></div></a>'''
        vacancy = (await KonturParser().parse(Session(Response(text=html)), set(), {}))[0]
        self.assertEqual(vacancy['title'], 'Менеджер продукта')
        self.assertEqual(vacancy['grade'], 'middle+')
        self.assertEqual(vacancy['city'], 'Екатеринбург')
        self.assertEqual(vacancy['work_format'], 'Удалённо')

    async def test_hh_oauth_error_after_successful_page_never_returns_partial_list(self):
        session = Session(Response({'items': [{'id': '1', 'name': 'Product Manager'}], 'pages': 2}),
                          Response({'errors': [{'type': 'oauth_error'}]}, status=403))
        with patch('parsers.hh_base.asyncio.sleep', return_value=None):
            with self.assertRaises(aiohttp.ClientResponseError):
                await HHParser().parse(session, set(), {})

    async def test_hh_captcha_is_reported_as_error(self):
        parser = HHParser()
        with self.assertRaises(aiohttp.ClientResponseError):
            await parser.parse(Session(Response({'errors': [{'type': 'captcha_required'}]}, status=403)), set(), {})
        self.assertTrue(parser.captcha_hit)


class BackupTests(unittest.TestCase):
    def test_export_bounds_new_events_and_verifies_every_page(self):
        class RestResponse:
            def __init__(self, body, headers=None):
                self.body, self.headers = body, headers or {}
            def json(self):
                return self.body
            def raise_for_status(self):
                pass

        class RestSession:
            headers = {}
            def mount(self, *args):
                pass
            def close(self):
                pass
            def get(self, url, params=None, headers=None, **kwargs):
                if url.endswith('/rest/v1/'):
                    return RestResponse({'definitions': {'user_events': {'properties': {'id': {}, 'event': {}}}}})
                if params.get('order') == 'id.desc':
                    return RestResponse([{'id': 3}])
                self_outer.assertEqual(params.get('id'), 'lte.3')
                if headers:
                    return RestResponse([], {'Content-Range': '0-0/3'})
                rows = [{'id': n, 'event': 'test'} for n in range(1, 5) if n <= 3]
                offset, limit = params['offset'], params['limit']
                return RestResponse(rows[offset:offset + limit])

        self_outer = self
        with tempfile.TemporaryDirectory() as tmp, patch('scripts.backup_database.requests.Session', RestSession), \
                patch('scripts.backup_database.TABLE_KEYS', {'user_events': 'id'}):
            target = Path(tmp) / 'snapshot'
            report = backup_database(target, 'https://example.com', 'test-key', page_size=2)
            self.assertTrue(report['complete'])
            self.assertEqual(report['tables']['user_events']['rows'], 3)
            data = (target / 'user_events.ndjson').read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), report['tables']['user_events']['sha256'])
            self.assertEqual(len(data.splitlines()), 3)


if __name__ == '__main__':
    unittest.main()
