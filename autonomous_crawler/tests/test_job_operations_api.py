"""Tests for job list/detail/cancel API endpoints."""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from autonomous_crawler.api.app import create_app, _clear_jobs, _register_job, _update_job, _registry


class JobListEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        _clear_jobs()

    def test_list_jobs_empty(self) -> None:
        resp = self.client.get("/jobs")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["jobs"], [])

    def test_list_jobs_returns_registered(self) -> None:
        _register_job("j1", "scrape shoes", "https://shop.example", kind="crawl")
        _register_job("j2", "profile run", "https://profile.example", kind="profile_run")
        resp = self.client.get("/jobs")
        self.assertEqual(resp.status_code, 200)
        jobs = resp.json()["jobs"]
        self.assertEqual(len(jobs), 2)

    def test_list_jobs_filter_by_status(self) -> None:
        _register_job("j1", "g", "https://x.com")
        _register_job("j2", "g", "https://x.com")
        _update_job("j1", status="completed")
        resp = self.client.get("/jobs?status=running")
        self.assertEqual(resp.status_code, 200)
        jobs = resp.json()["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["task_id"], "j2")

    def test_list_jobs_filter_by_kind(self) -> None:
        _register_job("j1", "g", "https://x.com", kind="crawl")
        _register_job("j2", "g", "https://x.com", kind="profile_run")
        resp = self.client.get("/jobs?kind=crawl")
        self.assertEqual(resp.status_code, 200)
        jobs = resp.json()["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["kind"], "crawl")

    def test_list_jobs_limit(self) -> None:
        for i in range(10):
            _register_job(f"j{i}", "g", "https://x.com")
        resp = self.client.get("/jobs?limit=3")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["jobs"]), 3)

    def test_list_jobs_includes_timestamps(self) -> None:
        _register_job("j1", "g", "https://x.com")
        resp = self.client.get("/jobs")
        job = resp.json()["jobs"][0]
        self.assertIn("created_at", job)
        self.assertIn("updated_at", job)

    def test_list_jobs_includes_kind(self) -> None:
        _register_job("j1", "g", "https://x.com", kind="profile_run")
        resp = self.client.get("/jobs")
        job = resp.json()["jobs"][0]
        self.assertEqual(job["kind"], "profile_run")


class JobDetailEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        _clear_jobs()

    def test_get_job_detail(self) -> None:
        _register_job("j1", "scrape shoes", "https://shop.example", kind="crawl")
        resp = self.client.get("/jobs/j1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["task_id"], "j1")
        self.assertEqual(data["kind"], "crawl")
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["user_goal"], "scrape shoes")

    def test_get_job_detail_404(self) -> None:
        resp = self.client.get("/jobs/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_get_job_detail_includes_all_fields(self) -> None:
        _register_job("j1", "g", "https://x.com", kind="profile_run")
        _update_job("j1", run_id="run-42", profile_name="shoes")
        resp = self.client.get("/jobs/j1")
        data = resp.json()
        self.assertEqual(data["run_id"], "run-42")
        self.assertEqual(data["profile_name"], "shoes")


class JobCancelEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        _clear_jobs()

    def test_cancel_running_job(self) -> None:
        _register_job("j1", "g", "https://x.com")
        resp = self.client.post("/jobs/j1/cancel")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "cancelled")

        # Verify status changed
        detail = self.client.get("/jobs/j1")
        self.assertEqual(detail.json()["status"], "cancelled")

    def test_cancel_completed_job_409(self) -> None:
        _register_job("j1", "g", "https://x.com")
        _update_job("j1", status="completed")
        resp = self.client.post("/jobs/j1/cancel")
        self.assertEqual(resp.status_code, 409)
        self.assertIn("cannot cancel", resp.json()["detail"])

    def test_cancel_nonexistent_404(self) -> None:
        resp = self.client.post("/jobs/nonexistent/cancel")
        self.assertEqual(resp.status_code, 404)


class ProfileRunCancelEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        _clear_jobs()

    def test_cancel_running_profile_run(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        _update_job("j1", profile_name="shoes")
        resp = self.client.post("/profile-runs/j1/cancel")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "cancelled")

    def test_cancel_non_running_profile_run_409(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        _update_job("j1", status="completed")
        resp = self.client.post("/profile-runs/j1/cancel")
        self.assertEqual(resp.status_code, 409)

    def test_cancel_nonexistent_profile_run_404(self) -> None:
        resp = self.client.post("/profile-runs/nonexistent/cancel")
        self.assertEqual(resp.status_code, 404)


class ProfileRunPauseResumeEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        _clear_jobs()

    def test_pause_running_profile_run(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        resp = self.client.post("/profile-runs/j1/pause")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "pause_requested")

    def test_pause_non_running_409(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        _update_job("j1", status="completed")
        resp = self.client.post("/profile-runs/j1/pause")
        self.assertEqual(resp.status_code, 409)

    def test_resume_paused_profile_run(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        _update_job("j1", status="paused")
        resp = self.client.post("/profile-runs/j1/resume")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "running")

    def test_resume_non_paused_409(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        resp = self.client.post("/profile-runs/j1/resume")
        self.assertEqual(resp.status_code, 409)

    def test_pause_nonexistent_404(self) -> None:
        resp = self.client.post("/profile-runs/nonexistent/pause")
        self.assertEqual(resp.status_code, 404)


class ProfileRunDiagnosticsEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        _clear_jobs()
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        _clear_jobs()

    def test_profile_run_status_includes_diagnostics(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        _update_job("j1", profile_name="shoes", diagnostics={
            "bottlenecks": [{"key": "transport_pressure", "severity": "warn"}],
            "recommendation": {"code": "slow_down", "message_zh": "降速"},
        })
        resp = self.client.get("/profile-runs/j1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("diagnostics", data)
        self.assertEqual(data["diagnostics"]["recommendation"]["code"], "slow_down")

    def test_profile_run_status_without_diagnostics_omits_key(self) -> None:
        _register_job("j1", "profile-run:shoes", "https://x.com", kind="profile_run")
        resp = self.client.get("/profile-runs/j1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertNotIn("diagnostics", data)


if __name__ == "__main__":
    unittest.main()
