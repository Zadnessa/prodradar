"""Проверки границ автоматической настройки только тестового GitHub environment."""

import base64
import copy
import importlib.util
import unittest
from unittest.mock import patch

from scripts.prepare_test_github import encrypt_settings
from scripts.setup_test_github import ENVIRONMENT, PROJECT_REF, REPOSITORY, SetupError, apply_settings, validate_settings


class GithubSetupTests(unittest.TestCase):
    def setUp(self):
        self.public_key = {'key_id': 'test-key'}
        self.settings = {
            'repository': REPOSITORY, 'environment': ENVIRONMENT, 'key_id': 'test-key',
            'variables': {'SUPABASE_URL': f'https://{PROJECT_REF}.supabase.co', 'ADMIN_CHAT_ID': '123'},
            'secrets': {name: base64.b64encode(b'x' * 100).decode()
                        for name in ['SUPABASE_KEY', 'TELEGRAM_BOT_TOKEN']},
        }

    def test_foreign_target_original_database_new_key_and_extra_secrets_never_write(self):
        variants = []
        for key, value in [('repository', 'Other/repo'), ('environment', 'production'), ('key_id', 'changed')]:
            settings = copy.deepcopy(self.settings)
            settings[key] = value
            variants.append(settings)
        settings = copy.deepcopy(self.settings)
        settings['variables']['SUPABASE_URL'] = 'https://ykbtejjedefibdgyfgov.supabase.co'
        variants.append(settings)
        settings = copy.deepcopy(self.settings)
        settings['secrets']['OTHER_TOKEN'] = settings['secrets']['SUPABASE_KEY']
        variants.append(settings)
        for settings in variants:
            with self.subTest(settings=settings), \
                    patch('scripts.setup_test_github.get_public_key', return_value=self.public_key), \
                    patch('scripts.setup_test_github.api_request') as api:
                with self.assertRaises(SetupError):
                    apply_settings('dummy', settings)
                api.assert_not_called()

    def test_plaintext_secrets_are_rejected(self):
        self.settings['secrets']['SUPABASE_KEY'] = 'plaintext'
        with self.assertRaises(SetupError):
            validate_settings(self.settings, self.public_key)

    def test_setup_is_idempotent_and_updates_only_named_environment_settings(self):
        actual_variables = [{'name': key, 'value': value} for key, value in self.settings['variables'].items()]
        with patch('scripts.setup_test_github.get_public_key', return_value=self.public_key), \
                patch('scripts.setup_test_github.api_request', side_effect=[
                    {'variables': [{'name': 'SUPABASE_URL'}]}, None, None, None, None,
                    {'variables': actual_variables},
                    {'secrets': [{'name': name} for name in ['SUPABASE_KEY', 'TELEGRAM_BOT_TOKEN', 'HH_ACCESS_TOKEN']]},
                ]) as api:
            apply_settings('dummy', self.settings)
        mutations = [(args[0], args[1]) for args, _ in api.call_args_list if args[0] != 'GET']
        self.assertEqual(mutations, [('PUT', '/secrets/SUPABASE_KEY'), ('PUT', '/secrets/TELEGRAM_BOT_TOKEN'),
                                     ('PATCH', '/variables/SUPABASE_URL'), ('POST', '/variables')])

    @unittest.skipUnless(importlib.util.find_spec('nacl'), 'PyNaCl нужен только для подготовки пакета')
    def test_package_uses_github_sealed_box_and_contains_no_plaintext_secrets(self):
        from nacl.public import PrivateKey, SealedBox
        private = PrivateKey.generate()
        public = {**self.public_key, 'repository': REPOSITORY, 'environment': ENVIRONMENT,
                  'key': base64.b64encode(bytes(private.public_key)).decode()}
        settings = encrypt_settings(public, 'actual-database-secret', 'actual-test-bot-token', 123)
        box = SealedBox(private)
        self.assertEqual(box.decrypt(base64.b64decode(settings['secrets']['SUPABASE_KEY'])), b'actual-database-secret')
        self.assertEqual(box.decrypt(base64.b64decode(settings['secrets']['TELEGRAM_BOT_TOKEN'])), b'actual-test-bot-token')
        self.assertNotIn('actual-database-secret', str(settings))
        self.assertNotIn('actual-test-bot-token', str(settings))
