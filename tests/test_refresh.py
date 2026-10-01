"""Регрессии контрактов источников и полноты резервной выгрузки."""

import hashlib
import json
import os
import ssl
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import aiohttp

from parsers.twogis import TwoGisParser
from parsers.lamoda import LamodaParser
from parsers.kontur import KonturParser
from parsers.hh import HHParser
from parsers.mtslink import MtsLinkParser
from parsers.aviasales import AviasalesParser
from parsers.dodo import DodoParser
from parsers.domclick import DomClickParser
from parsers.tbank import TBankParser
from scripts.backup_database import backup_database
from scripts.backup_schema import render_schema
from scripts.collect_test import check_target
from parsers.tls import source_ssl_context


class SourceTLSVerificationTests(unittest.TestCase):
    def test_additional_source_ca_keeps_certificate_and_hostname_checks(self):
        context = source_ssl_context('https://job.alfabank.ru/api/vacancies')
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertGreater(context.cert_store_stats()['x509_ca'], 2)

    def test_additional_source_ca_does_not_apply_to_external_or_similar_hosts(self):
        for url in ('https://api.telegram.org', 'https://jmsdxgylyjxwdwmdrmxw.supabase.co',
                    'https://job.alfabank.ru.attacker.example', 'https://other.tbank.ru'):
            self.assertIs(source_ssl_context(url), True)


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

    async def text(self, **kwargs):
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

    post = get


class ParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_tbank_rate_limit_retries_same_page_and_keeps_complete_result(self):
        state = '<script id="__TRAMVAI_STATE__">' + json.dumps({'stores': {'environment': {
            'VACANCIES_PUBLIC_API': 'https://www.tbank.ru/pfpjobs/papi/'}}}) + '</script>'
        limited = Response(status=429)
        limited.headers = {'Retry-After': '40'}
        session = Session(Response(text=state), limited, Response({'resultCode': 'OK', 'payload': {
            'vacancies': [{'title': 'Product Manager', 'urlSlug': '1'}],
            'nextPagination': {'offset': 1, 'isFinished': True, 'totalCount': 1}}}))
        parser = TBankParser()
        with patch('parsers.tbank.asyncio.sleep', return_value=None) as sleep:
            result = await parser.parse(session, set(), {})
        self.assertEqual(len(result), 1)
        self.assertEqual(session.calls[1][1]['json'], session.calls[2][1]['json'])
        sleep.assert_awaited_once_with(40.0)
        self.assertEqual(parser._recovered_rate_limits, 1)

    async def test_tbank_full_description_includes_offer_and_preserves_fields(self):
        session = Session(Response(text='<h2>Описание</h2><p>Продукт</p>'
                                  '<h2>Обязанности</h2><p>Развивать</p>'
                                  '<h2>Требования</h2><p>Опыт</p>'
                                  '<h2>Мы предлагаем</h2><p>Условия работы</p>'))
        vacancy = {'url': 'https://www.tbank.ru/career/it/1/', 'description': 'Preview',
                   'city': 'Москва', 'grade': 'Senior'}
        with patch('parsers.tbank.asyncio.sleep', return_value=None):
            await TBankParser().enrich(session, vacancy)
        self.assertIn('Условия работы', vacancy['description'])
        self.assertEqual(vacancy['city'], 'Москва')
        self.assertEqual(vacancy['grade'], 'Senior')

    async def test_tbank_flat_pagination_reads_every_page_before_city_deduplication(self):
        def page(raw_id, offset, finished):
            return {'resultCode': 'OK', 'payload': {'vacancies': [
                {'title': 'Product Manager', 'urlSlug': raw_id, 'seoSlug': 'product-manager',
                 'regionId': raw_id}], 'nextPagination': {
                    'offset': offset, 'isFinished': finished, 'totalCount': 2}}}
        state = '<script id="__TRAMVAI_STATE__" type="application/json">' + json.dumps({
            'stores': {'environment': {'VACANCIES_PUBLIC_API': 'https://www.tbank.ru/pfpjobs/papi/'},
                       'filtersStore': {'direction': ['produkt-i-marketing'], 'cityId': ['default-city']}}}) + '</script>'
        session = Session(Response(text=state), Response(page('1', 1, False)), Response(page('2', 2, True)))
        with patch('parsers.tbank.asyncio.sleep', return_value=None):
            result = await TBankParser().parse(session, set(), {('tbank_region', '1'): 'Москва',
                                                               ('tbank_region', '2'): 'Казань'})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['city'], 'Москва, Казань')
        self.assertEqual(session.calls[2][1]['json']['pagination']['offset'], 1)
        query = session.calls[1][1]['json']['filters']['generatedGraphQL']
        self.assertEqual(query['status'], 'ACTIVE')
        self.assertNotIn('searchFiasIds', query)

    async def test_tbank_rejects_non_advancing_pagination_and_incomplete_total(self):
        for items, pagination in [([{'urlSlug': '1'}], {'offset': 0, 'isFinished': False, 'totalCount': 2}),
                                  ([], {'offset': 0, 'isFinished': True, 'totalCount': 2})]:
            state = '<script id="__TRAMVAI_STATE__">' + json.dumps({
                'stores': {'environment': {'VACANCIES_PUBLIC_API': 'https://www.tbank.ru/pfpjobs/papi/'}}}) + '</script>'
            session = Session(Response(text=state), Response({'resultCode': 'OK', 'payload': {
                'vacancies': items, 'nextPagination': pagination}}))
            with self.assertRaises(ValueError):
                await TBankParser().parse(session, set(), {})
    async def test_domclick_current_api_paginates_and_reads_full_detail_by_slug(self):
        def item(raw_id):
            return {'id': raw_id, 'slug': f'product-{raw_id}', 'title': ' Product Owner ',
                    'vacancycontent': {'work_format': ['REMOTE', 'HYBRID']},
                    'area': {'name': 'Москва'}}
        session = Session(Response({'success': True, 'result': [item(1)],
                                    'pagination': {'limit': 1, 'offset': 0, 'total': 2}}),
                          Response({'success': True, 'result': [item(2)],
                                    'pagination': {'limit': 1, 'offset': 1, 'total': 2}}),
                          Response({'success': True, 'result': {'vacancycontent': {
                                    'description': '<p>' + 'Полный текст ' * 600 + '</p>'}}}))
        parser = DomClickParser()
        result = await parser.parse(session, set(), {})
        self.assertEqual(len(result), 2)
        self.assertEqual(session.calls[1][1]['params']['offset'], 1)
        self.assertEqual(result[0]['title'], 'Product Owner')
        self.assertEqual(result[0]['work_format'], 'Удалёнка, Гибрид')
        await parser.enrich(session, result[0])
        self.assertIn('/api/v1/vacancy/detail/product-1/', session.calls[-1][0])
        self.assertGreater(len(result[0]['description']), 7000)
        self.assertEqual(result[0]['city'], 'Москва')

    async def test_domclick_incomplete_pagination_is_rejected(self):
        session = Session(Response({'success': True, 'result': [], 'pagination': {'total': 10}}))
        with self.assertRaises(ValueError):
            await DomClickParser().parse(session, set(), {})

    async def test_dodo_discovers_current_backend_and_keeps_it_for_detail(self):
        session = Session(Response(text='<script>window.__NUXT__={config:{public:{apiURL:"https://new-api.example"}}}</script>'),
                          Response({'data': [{'items': [{'id': 12, 'subspeciality': 'product',
                                                         'position': 'Product Manager'}]}]}),
                          Response({'data': {'page': {'content': [{'type': 'vacancy_text',
                                                                  'data': {'text': '<p>Полный текст</p>'}}]}}}))
        parser = DodoParser()
        vacancy = (await parser.parse(session, set(), {}))[0]
        with patch('parsers.dodo.asyncio.sleep', return_value=None):
            await parser.enrich(session, vacancy)
        self.assertEqual(session.calls[1][0], 'https://new-api.example/api/v1/vacancies')
        self.assertEqual(session.calls[2][0], 'https://new-api.example/api/v1/pages/vacancy/12')
        self.assertEqual(vacancy['url'], 'https://dodoteam.ru/vacancy?vacancyId=12')
        self.assertEqual(vacancy['description'], 'Полный текст')

    async def test_aviasales_does_not_use_the_obsolete_specialization_filter(self):
        session = Session(Response([{'id': 10, 'position': 'Product Manager', 'workPlace': None}]))
        result = await AviasalesParser().parse(session, set(), {})
        self.assertEqual(len(result), 1)
        self.assertNotIn('specializations', session.calls[0][0])

    async def test_mtslink_public_list_and_detail_need_no_bearer_or_stale_category(self):
        session = Session(Response([{'id': 12, 'position': 'Product Manager', 'hidden': False,
                                     'created': {'date': '2026-09-30 10:22:44.000000', 'timezone': '+03:00'}}]),
                          Response({'body': '<p>Полный текст</p>', 'requirements': '<p>Требования</p>'}))
        parser = MtsLinkParser()
        vacancy = (await parser.parse(session, set(), {}))[0]
        await parser.enrich(session, vacancy)
        self.assertEqual(vacancy['published_at'], '2026-09-30T10:22:44+03:00')
        self.assertIn('Требования', vacancy['description'])
        for _, options in session.calls:
            self.assertNotIn('Authorization', options['headers'])
            self.assertNotIn('params', options)

    async def test_hh_successful_but_incomplete_list_is_not_accepted(self):
        session = Session(Response({'items': [{'id': '1', 'name': 'Product Manager'}], 'pages': 1, 'found': 2}))
        with self.assertRaises(ValueError):
            await HHParser().parse(session, set(), {})

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
    def test_test_collector_rejects_original_database_before_api_calls(self):
        with patch('scripts.collect_test._post') as telegram, \
                patch('scripts.collect_test.SupabaseService') as database:
            with self.assertRaises(ValueError):
                check_target('ykbtejjedefibdgyfgov')
            telegram.assert_not_called()
            database.assert_not_called()

    def test_test_collector_rejects_original_bot_before_database_access(self):
        with patch.dict(os.environ, {'SUPABASE_URL': 'https://isolated.supabase.co'}), \
                patch('scripts.collect_test._post', return_value={'username': 'findproductjob_bot'}), \
                patch('scripts.collect_test.SupabaseService') as database:
            with self.assertRaises(ValueError):
                check_target('isolated')
            database.assert_not_called()

    def test_schema_export_keeps_bigint_identity_limits_and_private_rls(self):
        catalog = {name: [] for name in ('tables', 'columns', 'sequences', 'constraints', 'functions',
                                        'indexes', 'triggers', 'policies', 'grants', 'schema_grants',
                                        'default_grants', 'unsupported_types')}
        catalog['tables'] = [{'name': 'users', 'relkind': 'r', 'rls': True, 'force_rls': False}]
        catalog['columns'] = [{'table_name': 'users', 'name': 'id', 'type': 'bigint', 'not_null': True,
                               'default_expr': None, 'identity': 'a', 'generated': '',
                               'identity_sequence': 'public.users_id_seq'}]
        catalog['sequences'] = [{'sequencename': 'users_id_seq', 'deptype': 'i', 'owned_table': 'users',
                                 'owned_column': 'id', 'start_value': '1', 'increment_by': '1',
                                 'min_value': '1', 'max_value': '9223372036854775807', 'cache_size': '1',
                                 'cycle': False}]
        catalog['policies'] = [{'policyname': 'Service role only', 'tablename': 'users',
                                'permissive': 'PERMISSIVE', 'cmd': 'ALL', 'roles': '{service_role}',
                                'qual': 'true', 'with_check': 'true'}]
        sql = render_schema(catalog)
        self.assertIn('MAXVALUE 9223372036854775807', sql)
        self.assertIn('ENABLE ROW LEVEL SECURITY', sql)
        self.assertIn('TO "service_role" USING (true) WITH CHECK (true)', sql)
        self.assertNotIn('CREATE SEQUENCE', sql)
        catalog['tables'][0]['relkind'] = 'v'
        with self.assertRaises(ValueError):
            render_schema(catalog)

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
