"""Проверки приоритетов и успешной доставки нового test-среза."""
import unittest
from unittest.mock import MagicMock, patch

from bot import simple_flow
from database.supabase_client import SupabaseService, compute_content_hash
from delivery.roles import classify, apply_selection
from delivery.ranking import rank_vacancies


class RoleTests(unittest.TestCase):
    def test_project_titles_do_not_require_monetization_or_industry(self):
        for title in ['Project Manager', 'Руководитель строительных проектов', 'Менеджер проектов внедрения',
                      'Program Manager', 'Менеджер коммерческих проектов', 'Delivery Manager']:
            with self.subTest(title=title):
                self.assertIn('project', classify({'title': title})['families'])
        self.assertEqual(classify({'title': 'Product Manager', 'description': 'монетизация, проекты'})['status'], 'rejected')

    def test_native_group_and_description_cannot_select_ambiguous_title(self):
        decision = classify({'title': 'Менеджер по развитию', 'description': 'управление проектами',
                             'source_json': {'category': 'Управление проектами'}})
        self.assertEqual(decision['status'], 'review')
        self.assertEqual(decision['families'], [])

    def test_bizdev_is_second_tier_even_with_monetization(self):
        project = apply_selection({'id': 'p', 'title': 'Project Manager'}, classify({'title': 'Project Manager'}))
        bizdev = apply_selection({'id': 'b', 'title': 'Business Development Manager', 'description': 'монетизация'},
                                classify({'title': 'Business Development Manager'}))
        with patch('config.VACANCY_PROFILE', 'project_bizdev'):
            self.assertEqual([v['id'] for v in rank_vacancies([bizdev, project], [], lambda _: 999)], ['p', 'b'])

    def test_selection_version_changes_hash_but_description_does_not(self):
        vacancy = apply_selection({'title': 'Project Manager'}, classify({'title': 'Project Manager'}))
        initial = compute_content_hash(vacancy)
        vacancy['description'] = 'монетизация'
        self.assertEqual(compute_content_hash(vacancy), initial)
        vacancy['selection_version'] = 'next'
        self.assertNotEqual(compute_content_hash(vacancy), initial)

    def test_product_projection_does_not_request_test_columns(self):
        db = SupabaseService.__new__(SupabaseService)
        db.client = MagicMock()
        with patch('config.VACANCY_PROFILE', 'product'):
            self.assertNotIn('selection_profile', db._vacancy_columns())
            db._vacancies_select('id')
            db.client.table.return_value.select.return_value.eq.assert_not_called()
        with patch('config.VACANCY_PROFILE', 'project_bizdev'):
            self.assertIn('role_families', db._vacancy_columns())
            db._vacancies_select('id')
            db.client.table.return_value.select.return_value.eq.assert_called_with('selection_profile', 'project_bizdev')


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.get_user.return_value = {'filters': {'cities': ['Москва'], 'strict_mode': True,
                                                   'excluded_companies': ['Muted']}}
        self.db.get_enabled_companies.return_value = [{'name': 'Example', 'slug': 'example'}]
        self.items = [{'id': 'p', 'title': 'Project Manager', 'company': 'Example', 'role_families': ['project'],
                       'url': 'https://example.com/1', 'city': 'Казань'},
                      {'id': 'b', 'title': 'Business Development Manager', 'company': 'Example',
                       'role_families': ['bizdev'], 'url': 'https://example.com/2'}]
        self.db.get_undelivered_vacancies.return_value = self.items

    def test_start_immediately_delivers_project_without_onboarding_or_bizdev(self):
        with patch('bot.simple_flow.send_message', return_value={'message_id': 1}) as send:
            simple_flow.handle_simple_message(1, '/start', 'test', self.db)
        texts = [call.args[1] for call in send.call_args_list]
        self.assertTrue(any('Project Manager' in t for t in texts))
        self.assertFalse(any('Business Development Manager' in t for t in texts))
        self.db.update_onboarding_step.assert_called_once_with(1, None)
        self.db.mark_delivered.assert_called_once_with(1, ['p'], source='simple')
        self.db.clear_delivery_history.assert_not_called()

    def test_bizdev_requires_explicit_button(self):
        with patch('bot.simple_flow.send_message', return_value={'message_id': 1}):
            simple_flow.handle_simple_callback('sm:more:bizdev', 1, 2, self.db)
        self.db.mark_delivered.assert_called_once_with(1, ['b'], source='simple')

    def test_failed_send_does_not_mark_vacancy(self):
        with patch('bot.simple_flow.send_message', return_value=None):
            simple_flow.show_vacancies(1, self.db)
        self.db.mark_delivered.assert_not_called()

    def test_previous_success_survives_later_exception(self):
        self.db.get_undelivered_vacancies.return_value = [dict(self.items[0], id=str(i)) for i in range(2)]
        with patch('bot.simple_flow.send_message', side_effect=[{'message_id': 1}, RuntimeError('offline')]):
            with self.assertRaises(RuntimeError):
                simple_flow.show_vacancies(1, self.db)
        self.db.mark_delivered.assert_called_once_with(1, ['0'], source='simple')

    def test_grade_filter_applies_after_all_pages_are_read(self):
        first = [dict(self.items[0], id=str(i), grade='Junior') for i in range(1000)]
        self.db.get_undelivered_vacancies.side_effect = [first, [dict(self.items[0], id='senior', grade='Senior')]]
        self.db.get_user.return_value = {'filters': {'grades': ['Senior']}}
        with patch('bot.simple_flow.send_message', return_value={'message_id': 1}):
            simple_flow.show_vacancies(1, self.db)
        self.db.mark_delivered.assert_called_once_with(1, ['senior'], source='simple')

    def test_grade_setting_preserves_mute_and_delivery_history(self):
        with patch('bot.simple_flow.edit_message'):
            simple_flow.handle_simple_callback('sm:grade:2', 1, 2, self.db)
        filters = self.db.update_user_filters.call_args.args[1]
        self.assertEqual(filters['grades'], ['Senior'])
        self.assertEqual(filters['excluded_companies'], ['Muted'])
        self.db.clear_delivery_history.assert_not_called()

class PoolStoreTests(unittest.TestCase):
    def setUp(self):
        self.db = SupabaseService.__new__(SupabaseService)
        self.db.client = MagicMock()

    def test_incomplete_batch_never_commits_and_cleans_stage(self):
        self.db.client.table.return_value.insert.return_value.execute.side_effect = RuntimeError('timeout')
        with patch.object(self.db, '_guard_pool'), self.assertRaises(RuntimeError):
            self.db.store_source_pool('example', [{'id': '1', 'title': 'Project Manager', 'url': 'https://example.com'}], {})
        self.db.client.rpc.assert_not_called()
        self.db.client.table.return_value.delete.assert_called_once()

    def test_duplicate_ids_are_rejected_before_any_write(self):
        v = {'id': '1', 'title': 'Project Manager', 'url': 'https://example.com'}
        with patch.object(self.db, '_guard_pool'), self.assertRaises(ValueError):
            self.db.store_source_pool('example', [v, v], {})
        self.db.client.table.assert_not_called()

    def test_large_catalog_commits_once_after_all_batches(self):
        with patch.object(self.db, '_guard_pool'):
            self.db.store_source_pool('example', [{'id': str(i), 'title': 'Project Manager',
                                                  'url': 'https://example.com'} for i in range(201)], {})
        self.assertEqual(self.db.client.table.return_value.insert.call_count, 3)
        self.db.client.rpc.assert_called_once()
        self.assertEqual(self.db.client.rpc.call_args.args[0], 'commit_source_pool')
        self.assertEqual(self.db.client.rpc.call_args.args[1]['p_expected'], 201)

class EmpiricalRoleTests(unittest.TestCase):
    def test_manually_audited_titles_have_at_least_95_percent_recall_and_precision(self):
        import json
        from pathlib import Path
        from scripts.evaluate_role_slice import evaluate
        gold = json.loads(Path('tests/fixtures/project_bizdev_gold.json').read_text())
        report, _ = evaluate([], gold)
        for split, families in report['metrics'].items():
            for family, metrics in families.items():
                with self.subTest(split=split, family=family):
                    if metrics['recall'] is not None:
                        self.assertGreaterEqual(metrics['recall'], .95, metrics['errors'])
                        self.assertGreaterEqual(metrics['precision'], .95, metrics['errors'])

    def test_project_in_hr_domain_is_not_excluded(self):
        self.assertEqual(classify({'title': 'Менеджер проектов (HR Tech)'})['families'], ['project'])

    def test_bizdev_does_not_match_business_process_development(self):
        self.assertNotIn('bizdev', classify({'title': 'Менеджер по развитию бизнес-процессов'})['families'])

class AblationTests(unittest.TestCase):
    def test_adding_role_guards_does_not_remove_any_audited_project(self):
        import json
        from pathlib import Path
        from scripts.role_filter_ablation import ablate
        gold = json.loads(Path('tests/fixtures/project_bizdev_gold.json').read_text())
        report = ablate([], gold)
        for stage in report['stages'][2:4]:
            self.assertFalse(stage['target_losses_vs_previous'], stage)
        self.assertFalse(report['stages'][4]['missed_targets'])
        self.assertTrue(any(v['family'] == 'project' for v in report['stages'][5]['missed_targets']))

    def test_relaxing_grade_and_mute_restores_vacancies_without_changing_roles(self):
        from delivery.filters import filter_vacancies_for_user
        records = [{'id': 'senior', 'title': 'Руководитель R&D проектов в HR', 'grade': 'Senior', 'company': 'Сбер'},
                   {'id': 'junior', 'title': 'Менеджер проектов (стажёр)', 'grade': 'Junior', 'company': 'Ozon'},
                   {'id': 'unknown', 'title': 'Project Manager', 'grade': None, 'company': 'Ozon'}]
        with patch('config.SIMPLE_BOT_FLOW', True):
            strict = filter_vacancies_for_user(records, {'grades': ['Senior'], 'excluded_companies': ['Ozon']})
            no_mute = filter_vacancies_for_user(records, {'grades': ['Senior']})
            relaxed = filter_vacancies_for_user(records, {})
            restored = filter_vacancies_for_user(relaxed, {'grades': ['Senior'], 'excluded_companies': ['Ozon']})
        self.assertEqual([v['id'] for v in strict], ['senior'])
        self.assertEqual({v['id'] for v in no_mute}, {'senior', 'unknown'})
        self.assertEqual({v['id'] for v in relaxed}, {'senior', 'junior', 'unknown'})
        self.assertEqual(restored, strict)
        self.assertTrue(all('project' in classify(v)['families'] for v in relaxed))

class ReplayTests(unittest.TestCase):
    def test_replay_is_explicit_and_does_not_clear_or_rewrite_history(self):
        db = MagicMock()
        db.get_user.return_value = {'filters': {}}
        db.get_enabled_companies.return_value = [{'name': 'Example'}]
        db.get_active_vacancies_for_filter_check.return_value = [
            {'id':'seen', 'title':'Project Manager', 'company':'Example', 'role_families':['project'], 'url':'https://example.com'}]
        with patch('bot.simple_flow.send_message', return_value={'message_id':1}):
            simple_flow.handle_simple_callback('sm:seen:project:0', 1, 2, db)
        db.mark_delivered.assert_not_called()
        db.clear_delivery_history.assert_not_called()
        db.get_undelivered_vacancies.assert_not_called()

class SemanticAliasTests(unittest.TestCase):
    def test_verified_alias_requires_company_title_and_both_duty_quotes(self):
        import json
        from pathlib import Path
        from delivery.role_aliases import ALIASES
        gold = json.loads(Path('tests/fixtures/project_bizdev_gold.json').read_text())
        for alias in ALIASES:
            row = next(r for r in gold['rows'] if r['title'] == alias['title'] and r.get('company') == alias['company'])
            with self.subTest(alias=alias['id']):
                self.assertEqual(set(classify(row)['families']), set(alias['families']))
                self.assertNotIn('company_alias:' + alias['id'], classify(dict(row, company='Other company'))['rules'])
                self.assertNotIn('company_alias:' + alias['id'], classify(dict(row, description='Опыт работы с проектами. Знание Jira.'))['rules'])
                first_quote = alias['evidence']['quotes'][0]
                self.assertNotIn('company_alias:' + alias['id'], classify(dict(row, description=first_quote))['rules'])

    def test_generic_product_and_warehouse_operations_stay_out(self):
        for vacancy in [
            {'company':'Ozon','title':'Менеджер по развитию продукта (курьерская доставка)',
             'description':'Discovery, интервью, продуктовые фичи, метрики и бэклог'},
            {'company':'Ozon','title':'Руководитель отдела по оптимизации потерь ( СЦ Радищево)',
             'description':'Организация подразделения склада, инвентаризация, утилизация и KPI'},
            {'company':'VK','title':'Ассистент команды','description':'Календарь, встречи и документооборот'},
            {'company':'VK','title':'Кадровый резерв МАХ','description':'Задачи зависят от будущей роли'}]:
            self.assertNotEqual(classify(vacancy)['status'], 'selected')

class NativeCohortTests(unittest.TestCase):
    def test_full_audited_native_groups_retain_targets_without_role_noise(self):
        import json
        from pathlib import Path
        from scripts.native_role_cohorts import evaluate_native_cohorts
        gold = json.loads(Path('tests/fixtures/native_role_cohorts.json').read_text())
        # Срезы пересекаются: не дублируем одну вакансию в исходном каталоге.
        pool = list({v['id']: v for rows in gold['cohorts'].values() for v in rows}.values())
        report = evaluate_native_cohorts(pool, gold)
        for name, row in report['cohorts'].items():
            with self.subTest(cohort=name):
                self.assertFalse(row['unaudited_ids'])
                self.assertFalse(row['missing_snapshot_ids'])
                for family, metric in row['metrics'].items():
                    self.assertFalse(metric['errors'], (family, metric))

    def test_new_native_member_is_unaudited_instead_of_automatic_target(self):
        import json
        from pathlib import Path
        from scripts.native_role_cohorts import evaluate_native_cohorts
        gold = json.loads(Path('tests/fixtures/native_role_cohorts.json').read_text())
        new = dict(gold['cohorts']['ozon_project_107'][0], id='new_native_id', title='Неизвестная роль')
        report = evaluate_native_cohorts([new], gold)['cohorts']['ozon_project_107']
        self.assertEqual(report['unaudited_ids'], ['new_native_id'])
        self.assertIsNone(report['metrics']['project']['recall'])

    def test_disabling_aliases_reveals_native_project_losses(self):
        import json
        from pathlib import Path
        from scripts.native_role_cohorts import evaluate_native_cohorts
        gold = json.loads(Path('tests/fixtures/native_role_cohorts.json').read_text())
        pool = list({v['id']: v for rows in gold['cohorts'].values() for v in rows}.values())
        report = evaluate_native_cohorts(pool, gold, lambda v: classify(v, enable_aliases=False))
        self.assertLess(report['cohorts']['vk_project_2261']['metrics']['project']['recall'], .95)
        self.assertLess(report['cohorts']['sber_project_specializations']['metrics']['project']['recall'], .95)

class LiveSemanticSelectionTests(unittest.IsolatedAsyncioTestCase):
    def test_shared_product_project_process_group_is_reviewed(self):
        from scripts.enrich_role_reviews import candidate
        self.assertTrue(candidate({'title':'Менеджер клиентского опыта', 'source_json': {
            'info':{'category':'Управление продуктами/проектами/процессами'}}}))
    async def test_empty_list_snippet_is_enriched_before_alias_filter(self):
        from unittest.mock import AsyncMock
        from delivery.roles import resolve_role
        vacancy = {'id':'mtslink_new', 'company':'МТС Линк', 'title':'Продюсер онлайн-трансляций', 'description':None}
        async def enrich(_session, row):
            row['description'] = 'Реализация проектов под ключ. Контроль исполнения бюджета.'
        parser = MagicMock(enrich=AsyncMock(side_effect=enrich))
        decision = await resolve_role(None, vacancy, parser)
        self.assertEqual(decision['families'], ['project'])
        parser.enrich.assert_awaited_once()

    async def test_verified_cached_description_does_not_repeat_detail_request(self):
        from unittest.mock import AsyncMock
        from delivery.roles import resolve_role
        vacancy = {'company':'МТС Линк', 'title':'Продюсер онлайн-трансляций',
                   'description':'Реализация проектов под ключ. Контроль исполнения бюджета.'}
        parser = MagicMock(enrich=AsyncMock())
        self.assertEqual((await resolve_role(None, vacancy, parser))['families'], ['project'])
        parser.enrich.assert_not_awaited()
