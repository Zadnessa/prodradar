"""Защита активных deployment при очистке Function Storage."""

import unittest
from unittest.mock import patch

from scripts.vercel_storage import ORIGINAL, TEST, all_pages, apply_plan, plan


def deployment(uid, project=TEST, created=1, target="production", state="READY"):
    return dict(uid=uid, projectId=project, created=created, target=target, state=state)


class StorageTests(unittest.TestCase):
    def test_aliases_targets_rollbacks_and_original_production_are_protected(self):
        snapshot = dict(aliases=[{"deployment": {"id": "alias"}}], targets=["target"],
                        deployments=[deployment("current", created=3),
                                     deployment("rollback", created=2), deployment("old-test"),
                                     deployment("old-original", project=ORIGINAL),
                                     deployment("alias", target=None), deployment("target", target=None),
                                     deployment("old-preview", project=ORIGINAL, target=None),
                                     deployment("building", target=None, state="BUILDING")])
        result = plan(snapshot)
        self.assertEqual({d["uid"] for d in result["candidates"]}, {"old-test", "old-preview"})

    def test_pagination_reads_every_page(self):
        calls = []
        def fetch(path, query):
            calls.append(dict(query))
            return {"items": [len(calls)], "pagination": {"next": 9 if len(calls) == 1 else None}}
        self.assertEqual(all_pages("/items", "items", fetch=fetch), [1, 2])
        self.assertEqual(calls[1]["until"], 9)

    def test_invalid_or_repeated_pagination_blocks_cleanup(self):
        for response in [{"items": []}, {"items": [], "pagination": {"next": 1}}]:
            with self.assertRaises(RuntimeError):
                all_pages("/items", "items", fetch=lambda *args: response)

    def test_new_alias_cancels_deletion_during_refresh(self):
        old = deployment("candidate", target=None)
        initial = plan(dict(aliases=[], targets=[], deployments=[old]))
        def fetch(path, params=None, method="GET"):
            self.assertEqual(method, "GET")
            if path == "/v4/aliases":
                return {"aliases": [{"deployment": {"id": "candidate"}}], "pagination": {"next": None}}
            if path.startswith("/v9/projects/"):
                return {"id": path.split("/")[-1], "targets": {}}
            return {"deployments": [old] if params["projectId"] == TEST else [],
                    "pagination": {"next": None}}
        self.assertEqual(apply_plan(initial, fetch), [])

    def test_alias_added_between_two_deletions_protects_second_deployment(self):
        rows = [deployment('first', target=None), deployment('second', target=None)]
        before = dict(aliases=[], targets=[], deployments=rows)
        after = dict(aliases=[{'deployment': {'id': 'second'}}], targets=[], deployments=[rows[1]])
        calls = []
        def fetch(path, params=None, method='GET'):
            calls.append((path, method))
            return {'projectId': TEST, 'target': None}
        with patch('scripts.vercel_storage.inventory', side_effect=[before, after]) as refresh:
            self.assertEqual(apply_plan(plan(before), fetch), ['first'])
        self.assertEqual(refresh.call_count, 2)
        self.assertEqual([path for path, method in calls if method == 'DELETE'],
                         ['/v13/deployments/first'])

    def test_failed_refresh_never_starts_deletion(self):
        initial = {"candidates": [{"uid": "candidate", "projectId": TEST}]}
        calls = []
        def fetch(path, params=None, method="GET"):
            calls.append(method)
            raise RuntimeError("HTTP 403")
        with self.assertRaises(RuntimeError):
            apply_plan(initial, fetch)
        self.assertEqual(calls, ["GET"])


if __name__ == "__main__":
    unittest.main()
