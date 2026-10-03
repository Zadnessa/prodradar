"""Первый scheduled запуск, ручной режим и изоляция test расписания."""

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

WORKFLOW = Path('.github/workflows/schedule_test.yml')


def run_gate(event, requested, now):
    text = WORKFLOW.read_text()
    start = text.index("          python - <<'PY'\n") + len("          python - <<'PY'\n")
    end = text.index('\n          PY', start)
    script = '\n'.join(line[10:] for line in text[start:end].splitlines())

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz or timezone.utc)

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / 'output'
        with patch('datetime.datetime', Clock), patch.dict(os.environ, {
            'EVENT_NAME': event, 'COLLECT_NOW': str(requested).lower(), 'GITHUB_OUTPUT': str(output),
        }):
            exec(compile(script, str(WORKFLOW), 'exec'), {})
        return output.read_text()


class ScheduleTests(unittest.TestCase):
    def test_schedule_cannot_start_today_or_before_tomorrow_ten_moscow(self):
        for now in [datetime(2026, 10, 2, 16, tzinfo=timezone.utc),
                    datetime(2026, 10, 3, 6, 59, tzinfo=timezone.utc)]:
            with self.subTest(now=now):
                self.assertEqual(run_gate('schedule', False, now), 'collect=false\n')

    def test_first_and_following_scheduled_runs_collect(self):
        for now in [datetime(2026, 10, 3, 7, tzinfo=timezone.utc),
                    datetime(2026, 10, 3, 16, tzinfo=timezone.utc),
                    datetime(2027, 1, 1, 7, tzinfo=timezone.utc)]:
            with self.subTest(now=now):
                self.assertEqual(run_gate('schedule', False, now), 'collect=true\n')

    def test_default_manual_verification_never_collects(self):
        self.assertEqual(run_gate('workflow_dispatch', False, datetime(2027, 1, 1, tzinfo=timezone.utc)), 'collect=false\n')

    def test_explicit_manual_collect_is_allowed_now(self):
        self.assertEqual(run_gate('workflow_dispatch', True, datetime(2026, 10, 2, tzinfo=timezone.utc)), 'collect=true\n')

    def test_collector_uses_live_test_branch_and_shared_concurrency(self):
        text = WORKFLOW.read_text()
        self.assertIn("cron: '0 7 * * *'", text)
        self.assertIn("cron: '0 16 * * *'", text)
        self.assertEqual(text.count('environment: prodradar-test'), 2)
        self.assertEqual(text.count('ref: codex/restore-test-bot'), 2)
        self.assertIn('group: prodradar-test-collector', text)
        self.assertIn('--profile test collect --project-ref jmsdxgylyjxwdwmdrmxw', text)
        self.assertNotIn('--use-source-pool', text)
        self.assertNotIn('RADAR_SOURCE_POOL_ONLY', text)
        self.assertNotIn('ykbtejjedefibdgyfgov', text)

    def test_only_keepalive_can_write_and_cannot_read_test_secrets(self):
        text = WORKFLOW.read_text()
        collector, keepalive = text.split('\n  keepalive:', 1)
        self.assertNotIn('contents: write', collector)
        self.assertIn('contents: write', keepalive)
        self.assertNotIn('secrets.', keepalive)
        self.assertNotIn('environment:', keepalive)
        self.assertIn('2592000', keepalive)
        self.assertIn('git add .github/test-schedule-heartbeat', keepalive)
