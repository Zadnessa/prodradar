"""Регрессии изоляции профиля до импорта config и любого запуска команды."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def run_profile(self, code, overrides=None):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(('TEST_', 'PROD_', 'PRODRADAR_PROFILE'))}
        env.update({
            'SUPABASE_URL': 'https://original.invalid',
            'SUPABASE_KEY': 'original-key',
            'TELEGRAM_BOT_TOKEN': 'original-token',
            'REDIRECT_BASE_URL': 'original.invalid',
            **(overrides or {}),
        })
        return subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env,
                              capture_output=True, text=True)

    def test_missing_test_or_prod_values_never_fall_back_or_mutate_environment(self):
        for profile in ('test', 'prod'):
            result = self.run_profile(f'''
import os
from runtime_profiles import select_profile
before = dict(os.environ)
try:
    select_profile({profile!r})
except ValueError:
    assert dict(os.environ) == before
else:
    raise AssertionError('Missing credentials accepted')
assert 'config' not in __import__('sys').modules
''')
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_database_ref_is_rejected_before_imports(self):
        result = self.run_profile('''
from runtime_profiles import select_profile
try:
    select_profile('test')
except ValueError:
    pass
else:
    raise AssertionError('Original database accepted')
''', {'TEST_SUPABASE_URL': 'https://ykbtejjedefibdgyfgov.supabase.co',
      'TEST_SUPABASE_KEY': 'test-key', 'TEST_TELEGRAM_BOT_TOKEN': 'test-token'})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_profiles_select_only_their_credentials_and_redirect_before_config(self):
        for name, prefix, ref, bot, redirect in (
            ('test', 'TEST', 'jmsdxgylyjxwdwmdrmxw', 'ProdRadar_bot', 'prodradar-test.vercel.app'),
            ('prod', 'PROD', 'ykbtejjedefibdgyfgov', 'findproductjob_bot', 'prodradar.vercel.app'),
        ):
            result = self.run_profile(f'''
import json, os
from runtime_profiles import select_profile
p = select_profile({name!r})
import config
print(json.dumps([config.SUPABASE_URL, config.SUPABASE_KEY,
                  os.environ['TELEGRAM_BOT_TOKEN'], os.environ['REDIRECT_BASE_URL'], p['bot']]))
try:
    select_profile({name!r})
except RuntimeError:
    pass
else:
    raise AssertionError('Switch after config import accepted')
''', {f'{prefix}_SUPABASE_URL': f'https://{ref}.supabase.co/',
      f'{prefix}_SUPABASE_KEY': 'profile-key', f'{prefix}_TELEGRAM_BOT_TOKEN': 'profile-token'})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             [f'https://{ref}.supabase.co', 'profile-key', 'profile-token', redirect, bot])

    def test_wrong_bot_identity_is_rejected(self):
        result = self.run_profile('''
from unittest.mock import patch
from runtime_profiles import verify_bot, PROFILES
with patch('bot.telegram_api._post', return_value={'is_bot': True, 'username': 'findproductjob_bot'}):
    try:
        verify_bot(PROFILES['test'])
    except ValueError:
        pass
    else:
        raise AssertionError('Original bot accepted')
''')
        self.assertEqual(result.returncode, 0, result.stderr)
