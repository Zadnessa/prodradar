"""Регрессии широкого каталога: короткие страницы не теряют вакансии."""

import unittest
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
