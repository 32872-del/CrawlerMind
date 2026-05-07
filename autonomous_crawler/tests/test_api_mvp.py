from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from autonomous_crawler.api import app as app_module
from autonomous_crawler.api.app import (
    create_app,
    _count_active_jobs,
    _get_job,
    _jobs,
    _jobs_lock,
    _max_active_jobs,
    _register_job,
    _try_register_job,
    _update_job,
)


class FastAPIMVPTests(unittest.TestCase):
    def setUp(self) -> None:
        # Clear the in-memory job registry between tests
        with _jobs_lock:
            _jobs.clear()

    def test_post_crawl_returns_immediately_with_running_status(self) -> None:
        """POST /crawl should return before the workflow finishes."""
        with patch("autonomous_crawler.api.app.run_crawl_workflow") as mock_wf, patch(
            "autonomous_crawler.api.app.save_crawl_result"
        ) as mock_save:
            # Make the workflow slow so we can verify the response comes first
            def slow_workflow(**kwargs):
                time.sleep(0.5)
                return {
                    "task_id": "test",
                    "status": "completed",
                    "extracted_data": {"items": [{"title": "A"}], "item_count": 1, "confidence": 1.0},
                    "validation_result": {"is_valid": True},
                }

            mock_wf.side_effect = slow_workflow
            mock_save.return_value = "test-id"

            client = TestClient(create_app())
            response = client.post(
                "/crawl",
                json={"user_goal": "collect products", "target_url": "mock://catalog"},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "running")
            self.assertIn("task_id", payload)
            self.assertEqual(payload["item_count"], 0)
            self.assertFalse(payload["is_valid"])

    def test_get_crawl_returns_running_task_from_registry(self) -> None:
        """GET /crawl/{task_id} should show a running task before it completes."""
        with patch("autonomous_crawler.api.app.run_crawl_workflow") as mock_wf, patch(
            "autonomous_crawler.api.app.save_crawl_result"
        ) as mock_save:
            block_event = __import__("threading").Event()

            def blocking_workflow(**kwargs):
                block_event.wait(timeout=5)
                return {
                    "status": "completed",
                    "extracted_data": {"items": [], "item_count": 0, "confidence": 0},
                    "validation_result": {"is_valid": False},
                }

            mock_wf.side_effect = blocking_workflow
            mock_save.return_value = "test-id"

            client = TestClient(create_app())
            post_resp = client.post(
                "/crawl",
                json={"user_goal": "test", "target_url": "https://example.com"},
            )
            task_id = post_resp.json()["task_id"]

            # While the background thread is blocked, GET should return running
            get_resp = client.get(f"/crawl/{task_id}")
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.json()["status"], "running")
            self.assertEqual(get_resp.json()["task_id"], task_id)

            # Unblock the workflow so the thread can finish cleanly
            block_event.set()
            time.sleep(0.3)

    def test_background_completion_persists_result(self) -> None:
        """When background workflow completes, result should be persisted."""
        with patch("autonomous_crawler.api.app.run_crawl_workflow") as mock_wf, patch(
            "autonomous_crawler.api.app.save_crawl_result"
        ) as mock_save:
            mock_wf.return_value = {
                "status": "completed",
                "extracted_data": {"items": [{"title": "A"}, {"title": "B"}], "item_count": 2, "confidence": 1.0},
                "validation_result": {"is_valid": True},
            }
            mock_save.return_value = "persisted-id"

            client = TestClient(create_app())
            post_resp = client.post(
                "/crawl",
                json={"user_goal": "test", "target_url": "mock://catalog"},
            )
            task_id = post_resp.json()["task_id"]

            # Wait for background thread to finish
            time.sleep(0.5)

            # Should have persisted
            mock_save.assert_called_once()

            # In-memory registry should show completed
            get_resp = client.get(f"/crawl/{task_id}")
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.json()["status"], "completed")
            self.assertEqual(get_resp.json()["item_count"], 2)
            self.assertTrue(get_resp.json()["is_valid"])

    def test_background_exception_becomes_queryable_failed_task(self) -> None:
        """If the workflow raises, the task should be queryable as failed."""
        with patch("autonomous_crawler.api.app.run_crawl_workflow") as mock_wf, patch(
            "autonomous_crawler.api.app.save_crawl_result"
        ):
            mock_wf.side_effect = RuntimeError("workflow crashed")

            client = TestClient(create_app())
            post_resp = client.post(
                "/crawl",
                json={"user_goal": "test", "target_url": "https://example.com"},
            )
            task_id = post_resp.json()["task_id"]

            # Wait for background thread to fail
            time.sleep(0.5)

            get_resp = client.get(f"/crawl/{task_id}")
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.json()["status"], "failed")
            self.assertIn("workflow crashed", get_resp.json()["error"])

    def test_get_crawl_returns_404_for_unknown_task(self) -> None:
        with patch("autonomous_crawler.api.app.load_crawl_result", return_value=None):
            client = TestClient(create_app())
            response = client.get("/crawl/nonexistent")

        self.assertEqual(response.status_code, 404)

    def test_history_endpoint_returns_persisted_items(self) -> None:
        with patch(
            "autonomous_crawler.api.app.list_crawl_results",
            return_value=[{"task_id": "task-1", "status": "completed"}],
        ):
            client = TestClient(create_app())
            response = client.get("/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["task_id"], "task-1")

    def test_get_crawl_falls_back_to_persisted_result(self) -> None:
        """If task is not in memory registry, should fall back to SQLite."""
        with patch("autonomous_crawler.api.app.load_crawl_result") as mock_load:
            mock_load.return_value = {
                "task_id": "old-task",
                "status": "completed",
                "item_count": 5,
                "is_valid": True,
                "items": [],
            }
            client = TestClient(create_app())
            response = client.get("/crawl/old-task")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["item_count"], 5)


class JobRegistryTests(unittest.TestCase):
    """Unit tests for the in-memory job registry helpers."""

    def setUp(self) -> None:
        with _jobs_lock:
            _jobs.clear()

    def test_register_and_get_job(self) -> None:
        _register_job("abc", "goal", "https://example.com")
        job = _get_job("abc")
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "running")
        self.assertEqual(job["task_id"], "abc")

    def test_update_job(self) -> None:
        _register_job("abc", "goal", "https://example.com")
        _update_job("abc", status="completed", item_count=5)
        job = _get_job("abc")
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["item_count"], 5)

    def test_get_nonexistent_job_returns_none(self) -> None:
        self.assertIsNone(_get_job("nonexistent"))


class ConcurrencyLimitTests(unittest.TestCase):
    """Tests for the active job concurrency guard."""

    def setUp(self) -> None:
        with _jobs_lock:
            _jobs.clear()

    def _make_client(self) -> TestClient:
        return TestClient(create_app())

    def _blocking_workflow(self, block_event: "threading.Event"):
        def _wf(**kwargs):
            block_event.wait(timeout=10)
            return {
                "status": "completed",
                "extracted_data": {"items": [], "item_count": 0, "confidence": 0},
                "validation_result": {"is_valid": False},
            }
        return _wf

    @patch("autonomous_crawler.api.app.save_crawl_result")
    @patch("autonomous_crawler.api.app.run_crawl_workflow")
    def test_accepted_when_below_limit(self, mock_wf, mock_save) -> None:
        """POST /crawl should succeed when active jobs < limit."""
        block = threading.Event()
        mock_wf.side_effect = self._blocking_workflow(block)
        mock_save.return_value = "ok"

        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "2"}, clear=False):
            client = self._make_client()
            resp = client.post(
                "/crawl",
                json={"user_goal": "test", "target_url": "https://example.com"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "running")

            block.set()
            time.sleep(0.3)

    @patch("autonomous_crawler.api.app.save_crawl_result")
    @patch("autonomous_crawler.api.app.run_crawl_workflow")
    def test_rejected_when_at_limit(self, mock_wf, mock_save) -> None:
        """POST /crawl should return 429 when active jobs == limit."""
        block = threading.Event()
        mock_wf.side_effect = self._blocking_workflow(block)
        mock_save.return_value = "ok"

        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "1"}, clear=False):
            client = self._make_client()

            # First request fills the slot
            resp1 = client.post(
                "/crawl",
                json={"user_goal": "first", "target_url": "https://example.com"},
            )
            self.assertEqual(resp1.status_code, 200)

            # Second request should be rejected
            resp2 = client.post(
                "/crawl",
                json={"user_goal": "second", "target_url": "https://example.com"},
            )
            self.assertEqual(resp2.status_code, 429)
            self.assertIn("too many active jobs", resp2.json()["detail"])

            block.set()
            time.sleep(0.3)

    @patch("autonomous_crawler.api.app.save_crawl_result")
    @patch("autonomous_crawler.api.app.run_crawl_workflow")
    def test_completed_jobs_do_not_count_as_active(self, mock_wf, mock_save) -> None:
        """After a job completes, it should free up a slot."""
        mock_wf.return_value = {
            "status": "completed",
            "extracted_data": {"items": [], "item_count": 0, "confidence": 0},
            "validation_result": {"is_valid": False},
        }
        mock_save.return_value = "ok"

        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "1"}, clear=False):
            client = self._make_client()

            # Fill the slot
            resp1 = client.post(
                "/crawl",
                json={"user_goal": "first", "target_url": "https://example.com"},
            )
            self.assertEqual(resp1.status_code, 200)

            # Wait for the background thread to complete
            time.sleep(0.5)

            # Slot should be free now
            resp2 = client.post(
                "/crawl",
                json={"user_goal": "second", "target_url": "https://example.com"},
            )
            self.assertEqual(resp2.status_code, 200)

    @patch("autonomous_crawler.api.app.save_crawl_result")
    @patch("autonomous_crawler.api.app.run_crawl_workflow")
    def test_failed_jobs_do_not_count_as_active(self, mock_wf, mock_save) -> None:
        """After a job fails, it should free up a slot."""
        mock_wf.side_effect = RuntimeError("boom")
        mock_save.return_value = "ok"

        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "1"}, clear=False):
            client = self._make_client()

            # Fill the slot with a job that will fail
            resp1 = client.post(
                "/crawl",
                json={"user_goal": "first", "target_url": "https://example.com"},
            )
            self.assertEqual(resp1.status_code, 200)

            # Wait for the background thread to fail
            time.sleep(0.5)

            # Slot should be free now
            resp2 = client.post(
                "/crawl",
                json={"user_goal": "second", "target_url": "https://example.com"},
            )
            self.assertEqual(resp2.status_code, 200)

    def test_count_active_jobs_counts_only_running(self) -> None:
        """_count_active_jobs should not count completed or failed jobs."""
        _register_job("a", "g", "https://x.com")
        _register_job("b", "g", "https://x.com")
        _update_job("b", status="completed")
        _register_job("c", "g", "https://x.com")
        _update_job("c", status="failed")

        self.assertEqual(_count_active_jobs(), 1)

    def test_try_register_job_is_atomic_limit_gate(self) -> None:
        """_try_register_job should check active count and register under one lock."""
        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "1"}, clear=False):
            self.assertTrue(_try_register_job("a", "g", "https://x.com"))
            self.assertFalse(_try_register_job("b", "g", "https://x.com"))
            self.assertIsNone(_get_job("b"))

    def test_max_active_jobs_reads_env_var(self) -> None:
        """_max_active_jobs should read from CLM_MAX_ACTIVE_JOBS env var."""
        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "7"}, clear=False):
            self.assertEqual(_max_active_jobs(), 7)

    def test_max_active_jobs_defaults_to_4(self) -> None:
        """_max_active_jobs should default to 4 when env var is not set."""
        env = {k: v for k, v in __import__("os").environ.items() if k != "CLM_MAX_ACTIVE_JOBS"}
        with patch.dict("os.environ", env, clear=True):
            self.assertEqual(_max_active_jobs(), 4)

    def test_max_active_jobs_falls_back_on_invalid(self) -> None:
        """_max_active_jobs should fall back to 4 on invalid env var."""
        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "not-a-number"}, clear=False):
            self.assertEqual(_max_active_jobs(), 4)

    def test_max_active_jobs_falls_back_on_zero(self) -> None:
        """_max_active_jobs should fall back to 4 on zero."""
        with patch.dict("os.environ", {"CLM_MAX_ACTIVE_JOBS": "0"}, clear=False):
            self.assertEqual(_max_active_jobs(), 4)


if __name__ == "__main__":
    unittest.main()
