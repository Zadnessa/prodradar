"""Проверки вычитки: продающий PM не возвращается после live enrichment."""
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, MagicMock

from delivery.roles import classify, normalized_description, resolve_role
from delivery.role_exclusions import EXCLUSIONS


def audit_rows():
    return json.loads(Path('tests/fixtures/role_precision_audit.json').read_text())['rows']


class PrecisionTests(unittest.TestCase):
    def test_reviewed_snapshot_and_exact_duty_evidence(self):
        rows = audit_rows()
        by_id = {r['id']: r for r in rows}
        self.assertEqual(len(rows), 374)
        for row in rows:
            with self.subTest(id=row['id']):
                self.assertEqual(classify(row)['status'] == 'selected', row['retain'])
        for rule in EXCLUSIONS:
            for evidence in rule['evidence']:
                body = normalized_description(by_id[evidence['id']]['description'])
                self.assertTrue(all(normalized_description(q) in body for q in evidence['quotes']), evidence)

    def test_clients_are_not_a_global_blacklist(self):
        for title in ['Менеджер проектов для клиентов', 'Project Manager — Customer Projects']:
            self.assertIn('project', classify({'title': title, 'description': 'Продажи клиентам. Управление сроками и бюджетом проектов.'})['families'])

    def test_company_title_and_duties_all_required(self):
        for rule in EXCLUSIONS:
            vacancy = {'company': rule['company'], 'title': rule['title'],
                       'description': ' '.join(rule['evidence_groups'][0])}
            self.assertTrue(any(r.startswith('duty_guard:') for r in classify(vacancy)['excluded_by']))
            for field, value in [('company', 'Другая компания'), ('title', 'Project Manager'),
                                 ('description', 'Реализовывать клиентские проекты: сроки, бюджет, координация команд.')]:
                self.assertFalse(any(r.startswith('duty_guard:') for r in classify(dict(vacancy, **{field: value}))['excluded_by']))

    def test_each_sales_guard_preserves_all_confirmed_projects(self):
        from scripts.role_filter_ablation import variants
        positives = [r for r in audit_rows() if r['retain']]
        for stage, classifier in variants()[5:8]:
            for row in positives:
                with self.subTest(stage=stage, id=row['id']):
                    self.assertEqual(classifier(row)['status'], 'selected')

    def test_sql_is_atomic_scoped_and_does_not_touch_users_or_history(self):
        from scripts.reselect_test_roles import update_sql
        plan = [{'id': 'x', 'title': "Проект 'клиент'", 'description': "договор 'A'",
                 'is_active': False, 'role_families': [], 'selection_version': 'v6', 'content_hash': 'hash', 'decision': {}}]
        sql = update_sql(plan)
        self.assertIn("Проект ''клиент''", sql)
        self.assertIn("selection_profile='project_bizdev'", sql)
        self.assertIn('(SELECT count(*) FROM matching)=1', sql)
        self.assertIn('md5(v.description) IS NOT DISTINCT FROM p.description_hash', sql)
        self.assertNotIn('users', sql)
        self.assertNotIn('user_vacancy_delivery', sql)
        with self.assertRaises(ValueError):
            update_sql(plan + plan)


class PrecisionEnrichmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_title_is_checked_against_detail_before_selection(self):
        negative = next(r for r in audit_rows() if not r['retain'] and r['kind'] == 'sales_account')
        vacancy = {'id': 'new_id', 'company': negative['company'], 'title': negative['title']}
        async def enrich(_session, row):
            row['description'] = negative['description']
        parser = MagicMock(enrich=AsyncMock(side_effect=enrich))
        self.assertNotEqual((await resolve_role(None, vacancy, parser))['status'], 'selected')
        parser.enrich.assert_awaited_once()

    async def test_unavailable_detail_keeps_risky_title_in_review(self):
        rule = EXCLUSIONS[0]
        vacancy = {'company': rule['company'], 'title': rule['title']}
        parser = MagicMock(enrich=AsyncMock())
        self.assertEqual((await resolve_role(None, vacancy, parser))['status'], 'review')

    async def test_confirmed_negative_description_does_not_fetch_again(self):
        row = next(r for r in audit_rows() if not r['retain'])
        parser = MagicMock(enrich=AsyncMock())
        self.assertNotEqual((await resolve_role(None, dict(row), parser))['status'], 'selected')
        parser.enrich.assert_not_awaited()
