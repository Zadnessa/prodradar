"""Регрессии широкого каталога: короткие страницы не теряют вакансии."""

import unittest
import runpy
from unittest.mock import patch

from parsers.alfa import AlfaParser
from parsers.sber import SberParser
from parsers.wildberries import WildberriesParser
from parsers.vk import VKParser
from test_refresh import Response, Session


class BroadCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_alfa_broad_catalog_uses_actual_skip_and_no_product_group(self):
        session = Session(Response({}),
                          Response({'items': [{'id': '1', 'name': 'Менеджер проекта'}], 'total': 2}),
                          Response({'items': [{'id': '2', 'name': 'Business Development Manager'}], 'total': 2}))
        with patch('config.CAPTURE_ALL_ROLES', True):
            result = await AlfaParser().parse(session, set(), {})
        self.assertEqual(len(result), 2)
        self.assertEqual(session.calls[2][1]['params']['skip'], 1)
        self.assertNotIn('businessLine', session.calls[1][1]['params'])

    async def test_sber_broad_catalog_uses_actual_skip_and_requires_complete_total(self):
        def page(raw_id):
            return Response({'data': {'vacancies': [{'internalId': raw_id, 'title': 'Руководитель проектов'}], 'total': 2}})
        session = Session(page('1'), page('2'))
        with patch('config.CAPTURE_ALL_ROLES', True):
            result = await SberParser().parse(session, set(), {})
            with self.assertRaises(ValueError):
                await SberParser().parse(Session(page('1'), Response({'data': {'vacancies': [], 'total': 2}})), set(), {})
        self.assertEqual(len(result), 2)
        self.assertEqual(session.calls[1][1]['params']['skip'], 1)
        self.assertNotIn('profAreas', session.calls[0][1]['params'])

    async def test_wildberries_short_page_advances_by_items_and_not_requested_limit(self):
        def page(raw_id):
            return Response({'data': {'items': [{'id': raw_id, 'name': 'Project manager'}], 'range': {'count': 2}}})
        session = Session(page(1), page(2))
        with patch('config.CAPTURE_ALL_ROLES', True):
            result = await WildberriesParser().parse(session, set(), {})
            with self.assertRaises(ValueError):
                await WildberriesParser().parse(Session(page(1), page(1)), set(), {})
        self.assertEqual(len(result), 2)
        self.assertEqual(session.calls[1][1]['params']['offset'], 1)
        self.assertNotIn('direction_ids[]', session.calls[0][1]['params'])

    async def test_vk_broad_catalog_reaches_other_native_roles(self):
        session = Session(Response({'results': [{'id': 1, 'title': 'Менеджер проектов'}], 'count': 1, 'next': None}))
        with patch('config.CAPTURE_ALL_ROLES', True):
            result = await VKParser().parse(session, set(), {})
        self.assertEqual(result[0]['title'], 'Менеджер проектов')
        self.assertNotIn('tags', session.calls[0][1]['params'])


class PoolEntryPointTests(unittest.TestCase):
    def test_entry_point_resolves_script_package_under_runpy(self):
        with patch('scripts.collect_test.main', return_value=0) as main:
            with self.assertRaises(SystemExit) as exited:
                runpy.run_path('scripts/capture_role_pool.py', run_name='__main__')
        self.assertEqual(exited.exception.code, 0)
        main.assert_called_once_with()

class PoolPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_pool_mode_never_writes_or_sends_core_vacancies(self):
        from unittest.mock import MagicMock, AsyncMock
        import main
        db = MagicMock()
        db.get_enabled_companies.return_value = [{'name': 'Example', 'parser_name': 'example'}]
        db.get_city_mappings.return_value = {}
        parser = MagicMock()
        parser.parse = AsyncMock(return_value=[{'id': 'example_1', 'title': 'Project Manager', 'url': 'https://example.com/1'}])
        with patch('main.SupabaseService', return_value=db), patch.dict('main.PARSER_REGISTRY', {'example': lambda: parser}), \
             patch('main.fetch_browser_secrets', AsyncMock(return_value={})), patch('config.SOURCE_POOL_ONLY', True), \
             patch('config.CAPTURE_ALL_ROLES', True), patch('config.USE_SOURCE_POOL', False), patch('main.send_message') as send:
            await main.run()
        db.store_source_pool.assert_called_once()
        db.insert_vacancies.assert_not_called()
        db.get_existing_vacancy_hashes.assert_not_called()
        db.deactivate_missing_vacancies.assert_not_called()
        send.assert_not_called()

class AdditionalPaginationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ozon_deduplicates_overlap_but_rejects_repeated_page(self):
        from parsers.ozon import OzonParser
        def page(ids, number):
            return Response({'items': [{'internalUuid': str(i), 'hhId': i, 'title': 'Менеджер проекта',
                                       'vacancyType': 'external_vacancy'} for i in ids],
                             'meta': {'page': number, 'totalPages': 2, 'totalItems': 4}})
        with patch('config.CAPTURE_ALL_ROLES', True):
            parser = OzonParser()
            result = await parser.parse(Session(page([1, 2], 1), page([2, 3], 2)), set(), {})
            self.assertEqual(len(result), 3)
            self.assertEqual(parser._duplicate_count, 1)
            with self.assertRaises(ValueError):
                await parser.parse(Session(page([1, 2], 1), page([1, 2], 2)), set(), {})

    async def test_tbank_connection_reset_has_same_bounded_retry_budget(self):
        import aiohttp
        from parsers.tbank import TBankParser
        class ResetResponse(Response):
            async def __aenter__(self):
                raise aiohttp.ClientOSError(104, 'Connection reset by peer')
        session = Session(ResetResponse(), Response({'ok': True}))
        with patch('parsers.tbank.asyncio.sleep', return_value=None):
            self.assertEqual(await TBankParser()._request(session, 'get', 'https://www.tbank.ru/career/it/', as_json=True), {'ok': True})
        self.assertEqual(len(session.calls), 2)
