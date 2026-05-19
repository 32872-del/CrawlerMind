"""Recovery smoke tests: prove durable jobs survive registry reopen."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.storage.batch_registry import BatchRegistry


class RegistryRecoverySmokeTests(unittest.TestCase):
    """Prove that jobs registered in one session are visible after reopen."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "recovery_test.sqlite3"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_running_job_survives_reopen(self) -> None:
        reg1 = BatchRegistry(self.db)
        reg1.register("job-1", "profile_run", {
            "user_goal": "scrape shoes",
            "target_url": "https://shop.example",
            "run_id": "run-abc",
            "profile_name": "shoe-shop",
        })
        reg1.register("job-2", "crawl", {
            "user_goal": "scrape books",
            "target_url": "https://books.example",
        })
        reg1.mark_status("job-2", "completed")

        # Simulate restart: new instance, same DB
        reg2 = BatchRegistry(self.db)

        # job-1 should be findable and still running
        job1 = reg2.get("job-1")
        self.assertIsNotNone(job1)
        self.assertEqual(job1["status"], "running")
        self.assertEqual(job1["kind"], "profile_run")
        self.assertEqual(job1["user_goal"], "scrape shoes")
        self.assertEqual(job1["profile_name"], "shoe-shop")

        # job-2 should be completed
        job2 = reg2.get("job-2")
        self.assertIsNotNone(job2)
        self.assertEqual(job2["status"], "completed")

    def test_recover_running_finds_stale_jobs(self) -> None:
        reg1 = BatchRegistry(self.db)
        reg1.register("stale-1", "profile_run")
        reg1.register("stale-2", "crawl")
        reg1.register("done-1", "crawl")
        reg1.mark_status("done-1", "completed")

        reg2 = BatchRegistry(self.db)
        running = reg2.recover_running()
        task_ids = [j["task_id"] for j in running]
        self.assertIn("stale-1", task_ids)
        self.assertIn("stale-2", task_ids)
        self.assertNotIn("done-1", task_ids)

    def test_recover_then_mark_failed(self) -> None:
        """Simulate the startup recovery flow: find stale, mark failed."""
        reg1 = BatchRegistry(self.db)
        reg1.register("j1", "profile_run", {"run_id": "r1"})
        reg1.register("j2", "crawl")

        reg2 = BatchRegistry(self.db)
        stale = reg2.recover_running()
        self.assertEqual(len(stale), 2)

        for job in stale:
            reg2.mark_status(job["task_id"], "failed")
            reg2.update(job["task_id"], error="recovered from prior crash", error_code="CRASH_RECOVERY")

        # Verify all marked failed
        j1 = reg2.get("j1")
        self.assertEqual(j1["status"], "failed")
        self.assertEqual(j1["error_code"], "CRASH_RECOVERY")

        # No more stale jobs
        self.assertEqual(len(reg2.recover_running()), 0)

    def test_list_jobs_after_recovery(self) -> None:
        """Jobs should be listable after recovery with correct status."""
        reg1 = BatchRegistry(self.db)
        reg1.register("j1", "profile_run")
        reg1.register("j2", "crawl")
        reg1.mark_status("j2", "completed")

        reg2 = BatchRegistry(self.db)
        running = reg2.list_jobs(status="running")
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0]["task_id"], "j1")

        completed = reg2.list_jobs(status="completed")
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0]["task_id"], "j2")

    def test_job_data_preserved_across_reopen(self) -> None:
        """Custom fields in job_data survive reopen."""
        reg1 = BatchRegistry(self.db)
        reg1.register("j1", "profile_run", {
            "run_id": "run-42",
            "profile_name": "electronics",
            "custom_field": {"nested": "value"},
        })

        reg2 = BatchRegistry(self.db)
        job = reg2.get("j1")
        self.assertEqual(job["run_id"], "run-42")
        self.assertEqual(job["profile_name"], "electronics")
        self.assertEqual(job["custom_field"]["nested"], "value")

    def test_count_active_after_reopen(self) -> None:
        reg1 = BatchRegistry(self.db)
        reg1.register("j1", "crawl")
        reg1.register("j2", "crawl")
        reg1.register("j3", "crawl")
        reg1.mark_status("j1", "completed")

        reg2 = BatchRegistry(self.db)
        self.assertEqual(reg2.count_active(), 2)

    def test_try_register_respects_reopened_state(self) -> None:
        """try_register should count active jobs from prior session."""
        reg1 = BatchRegistry(self.db)
        for i in range(4):
            reg1.register(f"j{i}", "crawl")

        reg2 = BatchRegistry(self.db)
        # At capacity from prior session
        self.assertFalse(reg2.try_register("new-job", "crawl", max_active=4))

        # Free a slot
        reg2.mark_status("j0", "completed")
        self.assertTrue(reg2.try_register("new-job", "crawl", max_active=4))


if __name__ == "__main__":
    unittest.main()
