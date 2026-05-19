from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.storage.batch_registry import BatchRegistry


class RegistryCRUDTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_registry.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_register_and_get(self) -> None:
        reg = BatchRegistry(self.db)
        record = reg.register("j1", "crawl", {"user_goal": "test"})
        self.assertEqual(record["task_id"], "j1")
        self.assertEqual(record["status"], "running")
        fetched = reg.get("j1")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["task_id"], "j1")
        self.assertEqual(fetched["user_goal"], "test")

    def test_get_missing_returns_none(self) -> None:
        reg = BatchRegistry(self.db)
        self.assertIsNone(reg.get("nonexistent"))

    def test_update_merges_fields(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.update("j1", item_count=42, is_valid=True)
        data = reg.get("j1")
        self.assertEqual(data["item_count"], 42)
        self.assertTrue(data["is_valid"])

    def test_update_missing_is_noop(self) -> None:
        reg = BatchRegistry(self.db)
        reg.update("missing", foo="bar")  # should not raise

    def test_remove(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        self.assertTrue(reg.remove("j1"))
        self.assertIsNone(reg.get("j1"))

    def test_remove_missing_returns_false(self) -> None:
        reg = BatchRegistry(self.db)
        self.assertFalse(reg.remove("nonexistent"))

    def test_list_jobs_all(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.register("j2", "profile_run")
        jobs = reg.list_jobs()
        self.assertEqual(len(jobs), 2)

    def test_list_jobs_filter_by_kind(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.register("j2", "profile_run")
        reg.register("j3", "crawl")
        jobs = reg.list_jobs(kind="crawl")
        self.assertEqual(len(jobs), 2)

    def test_list_jobs_filter_by_status(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.register("j2", "crawl")
        reg.mark_status("j1", "completed")
        jobs = reg.list_jobs(status="running")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["task_id"], "j2")


class ConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_registry.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_try_register_below_capacity(self) -> None:
        reg = BatchRegistry(self.db)
        self.assertTrue(reg.try_register("j1", "crawl", max_active=4))

    def test_try_register_at_capacity(self) -> None:
        reg = BatchRegistry(self.db)
        for i in range(4):
            self.assertTrue(reg.try_register(f"j{i}", "crawl", max_active=4))
        self.assertFalse(reg.try_register("j4", "crawl", max_active=4))

    def test_try_register_capacity_frees_after_completion(self) -> None:
        reg = BatchRegistry(self.db)
        for i in range(4):
            reg.try_register(f"j{i}", "crawl", max_active=4)
        reg.mark_status("j0", "completed")
        self.assertTrue(reg.try_register("j4", "crawl", max_active=4))


class StatusTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_registry.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_mark_completed_sets_timestamp(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.mark_status("j1", "completed")
        data = reg.get("j1")
        self.assertEqual(data["status"], "completed")
        self.assertIsNotNone(data["completed_at"])

    def test_mark_failed_sets_timestamp(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.mark_status("j1", "failed")
        data = reg.get("j1")
        self.assertEqual(data["status"], "failed")
        self.assertIsNotNone(data["completed_at"])

    def test_mark_running_has_no_completed_at(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.mark_status("j1", "running")
        data = reg.get("j1")
        self.assertEqual(data["status"], "running")
        self.assertIsNone(data["completed_at"])


class CleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_registry.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cleanup_removes_old_completed(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.mark_status("j1", "completed")
        # With retention=0, everything should be cleaned
        removed = reg.cleanup_stale(retention_seconds=0)
        self.assertEqual(removed, 1)
        self.assertIsNone(reg.get("j1"))

    def test_cleanup_keeps_running(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        removed = reg.cleanup_stale(retention_seconds=0)
        self.assertEqual(removed, 0)
        self.assertIsNotNone(reg.get("j1"))

    def test_cleanup_keeps_recent_completed(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.mark_status("j1", "completed")
        removed = reg.cleanup_stale(retention_seconds=3600)
        self.assertEqual(removed, 0)


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_registry.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_recover_running_finds_stale_jobs(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.register("j2", "crawl")
        reg.mark_status("j2", "completed")

        # Simulate restart: new registry instance, same DB
        reg2 = BatchRegistry(self.db)
        running = reg2.recover_running()
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0]["task_id"], "j1")

    def test_recover_running_empty_when_none_stuck(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.mark_status("j1", "completed")

        reg2 = BatchRegistry(self.db)
        self.assertEqual(len(reg2.recover_running()), 0)


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test_registry.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_data_survives_reopen(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl", {"user_goal": "test", "item_count": 5})

        reg2 = BatchRegistry(self.db)
        data = reg2.get("j1")
        self.assertIsNotNone(data)
        self.assertEqual(data["user_goal"], "test")
        self.assertEqual(data["item_count"], 5)

    def test_count_active_survives_reopen(self) -> None:
        reg = BatchRegistry(self.db)
        reg.register("j1", "crawl")
        reg.register("j2", "crawl")
        reg.mark_status("j1", "completed")

        reg2 = BatchRegistry(self.db)
        self.assertEqual(reg2.count_active(), 1)


if __name__ == "__main__":
    unittest.main()
