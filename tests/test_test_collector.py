"""Изоляция сборщика TEST и регрессия остановки после регистрации пользователя."""

import contextlib
import io
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from scripts.collect_test import TestTargetError, check_target, main


PROJECT = "jmsdxgylyjxwdwmdrmxw"
ENV = {"PRODRADAR_PROFILE": "test", "SUPABASE_URL": f"https://{PROJECT}.supabase.co"}
IDENTITY = {"is_bot": True, "username": "ProdRadar_bot"}


class TestCollectorTests(unittest.TestCase):
    def test_other_project_is_rejected_before_network_or_collection(self):
        with patch.dict(os.environ, ENV), patch("scripts.collect_test._post") as telegram:
            for project in (None, "", "ykbtejjedefibdgyfgov", "another-test"):
                with self.subTest(project=project), self.assertRaises(TestTargetError):
                    check_target(project)
            telegram.assert_not_called()

    def test_wrong_profile_or_url_is_rejected_before_network(self):
        for env in ({**ENV, "PRODRADAR_PROFILE": "prod"},
                    {**ENV, "PRODRADAR_PROFILE": ""},
                    {**ENV, "SUPABASE_URL": "https://another-test.supabase.co"}):
            with self.subTest(env=env), patch.dict(os.environ, env), \
                    patch("scripts.collect_test._post") as telegram:
                with self.assertRaises(TestTargetError):
                    check_target(PROJECT)
                telegram.assert_not_called()

    def test_original_bot_or_non_bot_is_rejected(self):
        for identity in (None, {"is_bot": True, "username": "findproductjob_bot"},
                         {"is_bot": False, "username": "ProdRadar_bot"}):
            with self.subTest(identity=identity), patch.dict(os.environ, ENV), \
                    patch("scripts.collect_test._post", return_value=identity):
                with self.assertRaises(TestTargetError):
                    check_target(PROJECT)

    def test_registered_test_users_do_not_prevent_collection(self):
        database = MagicMock()
        database.client.table.return_value.select.return_value.range.return_value.execute.return_value.data = [
            {"chat_id": 1}, {"chat_id": 2},
        ]
        with patch.dict(os.environ, {**ENV, "ADMIN_CHAT_ID": "1"}), \
                patch("scripts.collect_test._post", return_value=IDENTITY) as telegram, \
                patch("database.supabase_client.SupabaseService", return_value=database), \
                patch("scripts.collect_test.run", new_callable=AsyncMock) as collect, \
                patch("sys.argv", ["collect_test.py", "--project-ref", PROJECT]):
            self.assertEqual(main(), 0)
            collect.assert_awaited_once_with()
            telegram.assert_called_once_with("getMe", {}, allow_retry=False)
            database.client.table.assert_not_called()

    def test_target_error_reports_safe_specific_reason(self):
        with patch.dict(os.environ, ENV), \
                patch("scripts.collect_test.check_target", side_effect=TestTargetError("Нужен явный профиль test")), \
                patch("scripts.collect_test.run") as collect, \
                patch("sys.argv", ["collect_test.py", "--project-ref", PROJECT]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 1)
            self.assertIn("Нужен явный профиль test", output.getvalue())
            collect.assert_not_called()

    def test_client_exception_does_not_expose_credentials(self):
        with patch.dict(os.environ, ENV), \
                patch("scripts.collect_test.check_target", side_effect=RuntimeError("secret-token-in-url")), \
                patch("scripts.collect_test.run") as collect, \
                patch("sys.argv", ["collect_test.py", "--project-ref", PROJECT]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(), 1)
            self.assertIn("RuntimeError", output.getvalue())
            self.assertNotIn("secret-token-in-url", output.getvalue())
            collect.assert_not_called()
