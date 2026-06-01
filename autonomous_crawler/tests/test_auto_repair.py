"""Tests for the failure diagnosis and auto-repair loop."""
from __future__ import annotations

import unittest
from typing import Any

from autonomous_crawler.runners.auto_repair import (
    AutoRepairLoop,
    AutoRepairLoopResult,
    DiagnosisReport,
    FailureCategory,
    FailureDiagnoser,
    FailureDiagnosis,
)


class TestFailureDiagnoser(unittest.TestCase):
    """Test FailureDiagnoser classification logic."""

    def setUp(self) -> None:
        self.diagnoser = FailureDiagnoser()

    def test_no_records_detected(self) -> None:
        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                },
            },
        }
        report = self.diagnoser.diagnose(job=job)
        self.assertTrue(report.has_failures)
        categories = [d.category for d in report.diagnoses]
        self.assertIn(FailureCategory.NO_RECORDS, categories)

    def test_access_blocked_detected(self) -> None:
        job = {
            "status": "failed",
            "error_log": ["HTTP 403 Forbidden", "Rate limit exceeded (429)"],
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "failure_buckets": {"http_blocked": 5},
                },
            },
        }
        report = self.diagnoser.diagnose(job=job)
        categories = [d.category for d in report.diagnoses]
        self.assertIn(FailureCategory.ACCESS_BLOCKED, categories)

    def test_challenge_detected(self) -> None:
        job = {
            "status": "failed",
            "error_log": ["CAPTCHA challenge detected by Cloudflare"],
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "failure_buckets": {"challenge_like": 3, "captcha": 2},
                },
            },
        }
        report = self.diagnoser.diagnose(job=job)
        categories = [d.category for d in report.diagnoses]
        self.assertIn(FailureCategory.ACCESS_CHALLENGE, categories)

    def test_empty_html_detected(self) -> None:
        execution_result = {
            "status": "executed",
            "visited_urls": ["https://example.com"],
            "raw_html": {},
        }
        report = self.diagnoser.diagnose(
            job={"status": "completed"},
            execution_result=execution_result,
        )
        categories = [d.category for d in report.diagnoses]
        self.assertIn(FailureCategory.EMPTY_HTML, categories)

    def test_selector_miss_detected(self) -> None:
        execution_result = {
            "status": "executed",
            "engine_result": {
                "selector_results": [
                    {"name": "title", "match_count": 0},
                    {"name": "price", "match_count": 0},
                    {"name": "image", "match_count": 3},
                ],
            },
        }
        report = self.diagnoser.diagnose(
            job={"status": "completed"},
            execution_result=execution_result,
        )
        categories = [d.category for d in report.diagnoses]
        self.assertIn(FailureCategory.SELECTOR_MISS, categories)

    def test_healthy_when_records_present(self) -> None:
        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 50,
                    "quality_indicator": "pass",
                },
            },
        }
        report = self.diagnoser.diagnose(job=job)
        self.assertEqual(report.overall_health, "healthy")
        self.assertFalse(report.has_failures)

    def test_quality_fail_detected(self) -> None:
        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 10,
                    "quality_indicator": "fail",
                    "quality": {
                        "missing_fields": ["price", "image_urls"],
                    },
                },
            },
        }
        report = self.diagnoser.diagnose(job=job)
        categories = [d.category for d in report.diagnoses]
        self.assertIn(FailureCategory.QUALITY_FAIL, categories)

    def test_multiple_failures_diagnosed(self) -> None:
        job = {
            "status": "failed",
            "error_log": ["HTTP 403 Forbidden", "CAPTCHA challenge detected"],
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                    "failure_buckets": {
                        "http_blocked": 3,
                        "challenge_like": 2,
                    },
                },
            },
        }
        report = self.diagnoser.diagnose(job=job)
        self.assertGreaterEqual(report.critical_count, 2)
        self.assertEqual(report.overall_health, "critical")

    def test_diagnosis_report_serializable(self) -> None:
        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                },
            },
        }
        report = self.diagnoser.diagnose(job=job)
        d = report.to_dict()
        self.assertIn("diagnoses", d)
        self.assertIn("overall_health", d)
        self.assertIn("auto_repairable", d)
        # Should be JSON-serializable
        import json
        json.dumps(d)


class TestAutoRepairLoop(unittest.TestCase):
    """Test AutoRepairLoop orchestration."""

    def test_converges_on_healthy(self) -> None:
        """Loop should stop immediately if job is already healthy."""
        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 50,
                    "quality_indicator": "pass",
                },
            },
        }
        loop = AutoRepairLoop(max_cycles=3)
        result = loop.run(
            job=job,
            profile={"name": "test"},
            target_url="https://example.com",
        )
        self.assertTrue(result.converged)
        self.assertEqual(result.total_cycles, 1)
        self.assertEqual(result.final_health, "healthy")

    def test_runs_multiple_cycles_on_failure(self) -> None:
        """Loop should run multiple cycles when failures persist."""
        call_count = 0

        def mock_executor(**kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {
                    "status": "completed",
                    "profile_run": {
                        "product_stats": {
                            "records_saved": 0,
                            "quality_indicator": "fail",
                        },
                    },
                }
            return {
                "status": "completed",
                "profile_run": {
                    "product_stats": {
                        "records_saved": 20,
                        "quality_indicator": "pass",
                    },
                },
            }

        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                },
            },
        }
        loop = AutoRepairLoop(max_cycles=5)
        result = loop.run(
            job=job,
            profile={"name": "test", "target_fields": ["title"]},
            target_url="https://example.com",
            executor_fn=mock_executor,
        )
        self.assertGreater(result.total_cycles, 1)

    def test_stops_at_max_cycles(self) -> None:
        """Loop should stop at max cycles even if not converged."""
        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                },
            },
        }
        loop = AutoRepairLoop(max_cycles=2)
        result = loop.run(
            job=job,
            profile={"name": "test"},
            target_url="https://example.com",
        )
        self.assertLessEqual(result.total_cycles, 2)

    def test_result_serializable(self) -> None:
        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                },
            },
        }
        loop = AutoRepairLoop(max_cycles=1)
        result = loop.run(
            job=job,
            profile={"name": "test"},
            target_url="https://example.com",
        )
        d = result.to_dict()
        self.assertIn("total_cycles", d)
        self.assertIn("converged", d)
        import json
        json.dumps(d)


class TestFailureDiagnosis(unittest.TestCase):
    """Test FailureDiagnosis data class."""

    def test_to_dict(self) -> None:
        d = FailureDiagnosis(
            category=FailureCategory.NO_RECORDS,
            severity="critical",
            evidence="Zero records",
            affected_fields=["title", "price"],
            repair_actions=["repair_selectors"],
            confidence=0.9,
        )
        result = d.to_dict()
        self.assertEqual(result["category"], "no_records")
        self.assertEqual(result["severity"], "critical")
        self.assertAlmostEqual(result["confidence"], 0.9)


class TestFailureCategory(unittest.TestCase):
    """Test FailureCategory enum."""

    def test_all_categories_have_repair_map(self) -> None:
        from autonomous_crawler.runners.auto_repair import REPAIR_ACTION_MAP
        for cat in FailureCategory:
            if cat == FailureCategory.UNKNOWN:
                continue
            self.assertIn(
                cat, REPAIR_ACTION_MAP,
                f"Category {cat.value} missing from REPAIR_ACTION_MAP",
            )


if __name__ == "__main__":
    unittest.main()
