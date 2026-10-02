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
