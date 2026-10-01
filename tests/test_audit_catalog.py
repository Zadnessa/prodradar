"""Аудит в Actions не должен получать доступ к БД или Telegram."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.audit_sources import audit_sources


class CatalogAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_catalog_audit_exports_full_product_description_without_database(self):
        class Parser:
            async def parse(self, session, existing_ids, city_mappings, browser_secrets=None):
                self.assert_mapping = city_mappings
                return [{'id': 'product', 'company': 'Компания', 'title': 'Product Manager',
                         'url': 'https://example.com/product', 'city': 'Город'},
                        {'id': 'other', 'company': 'Компания', 'title': 'Курьер',
                         'url': 'https://example.com/other'}]

            async def enrich(self, session, vacancy):
                vacancy['description'] = 'Полные задачи, требования и условия'

        catalog = {'companies': [{'name': 'Компания', 'parser_name': 'example', 'is_enabled': True}],
                   'city_mappings': [{'source': 'example', 'raw_value': 'Город', 'normalized': 'Москва'}]}
        with tempfile.TemporaryDirectory() as directory, \
                patch('scripts.audit_sources.SupabaseService', side_effect=AssertionError('Database access')), \
                patch.dict('scripts.audit_sources.PARSER_REGISTRY', {'example': Parser}):
            output = Path(directory) / 'vacancies.json'
            report = await audit_sources(['example'], use_browser=False, catalog=catalog,
                                         full_enrich_sources=['example'], vacancies_output=output)
            self.assertTrue(report['ok'])
            self.assertEqual(report['sources']['example']['product_count'], 1)
            exported = json.loads(output.read_text())['example']
            self.assertEqual(exported['raw_ids'], ['product', 'other'])
            self.assertEqual(exported['vacancies'][0]['description'], 'Полные задачи, требования и условия')
