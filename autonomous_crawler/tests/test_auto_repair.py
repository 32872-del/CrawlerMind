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


# ------------------------------------------------------------------
# Tests for diagnose_and_repair() enhancements
# ------------------------------------------------------------------


class TestDiagnoseAndRepair(unittest.TestCase):
    """Test the diagnose_and_repair closed-loop function."""

    def test_healthy_job_returns_converged_immediately(self) -> None:
        """A healthy job should return converged=True with no repair actions."""
        from autonomous_crawler.runners.auto_repair import diagnose_and_repair

        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 50,
                    "quality_indicator": "pass",
                },
            },
        }
        result = diagnose_and_repair(
            job=job,
            profile={"name": "test"},
            target_url="https://example.com",
        )
        self.assertTrue(result["converged"])
        self.assertEqual(result["cycles_run"], 0)
        self.assertIsNone(result["repair_plan"])
        self.assertIn("before", result)
        self.assertIn("after", result)

    def test_failed_job_produces_repair_plan_and_delta(self) -> None:
        """A failed job should produce a repair plan with before/after delta."""
        from autonomous_crawler.runners.auto_repair import diagnose_and_repair

        job = {
            "status": "failed",
            "error_log": ["HTTP 403 Forbidden"],
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                    "failure_buckets": {"http_blocked": 5},
                },
            },
        }
        result = diagnose_and_repair(
            job=job,
            profile={"name": "test", "target_fields": ["title"]},
            target_url="https://example.com",
        )
        self.assertIn("diagnosis", result)
        self.assertIn("before", result)
        self.assertEqual(result["before"]["records_saved"], 0)
        self.assertEqual(result["before"]["health"], "critical")

    def test_before_snapshot_includes_field_coverage(self) -> None:
        """Before snapshot should include field_coverage from job progress."""
        from autonomous_crawler.runners.auto_repair import diagnose_and_repair

        job = {
            "status": "completed",
            "profile_run": {
                "product_stats": {
                    "records_saved": 10,
                    "quality_indicator": "fail",
                },
                "quality_summary": {
                    "field_completeness": {
                        "title": 1.0,
                        "price": 0.3,
                    },
                },
            },
        }
        result = diagnose_and_repair(
            job=job,
            profile={"name": "test"},
            target_url="https://example.com",
        )
        self.assertIn("field_coverage", result["before"])
        self.assertAlmostEqual(result["before"]["field_coverage"], 0.65, places=2)

    def test_repair_actions_sorted_by_cost(self) -> None:
        """Repair actions should be ordered cheapest first."""
        from autonomous_crawler.runners.auto_repair import (
            _generate_repair_actions,
            FailureDiagnoser,
            REPAIR_ACTION_COST,
        )

        job = {
            "status": "failed",
            "error_log": ["HTTP 403 Forbidden"],
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                    "failure_buckets": {"http_blocked": 5},
                },
            },
        }
        diagnoser = FailureDiagnoser()
        diagnosis = diagnoser.diagnose(job=job)
        actions = _generate_repair_actions(diagnosis.diagnoses, {"name": "test"}, job)

        # Filter out prepare_rerun
        repair_only = [a for a in actions if a.action != "prepare_rerun"]
        if len(repair_only) >= 2:
            costs = [REPAIR_ACTION_COST.get(a.action, 2) for a in repair_only]
            self.assertEqual(costs, sorted(costs),
                             f"Actions should be sorted by cost: {[(a.action, REPAIR_ACTION_COST.get(a.action)) for a in repair_only]}")

    def test_warning_severity_limits_actions(self) -> None:
        """Warning severity should cap actions at 3 and exclude costly repairs."""
        from autonomous_crawler.runners.auto_repair import (
            _generate_repair_actions,
            FailureDiagnosis,
            FailureCategory,
            REPAIR_ACTION_COST,
            SEVERITY_REPAIR_STRATEGY,
        )

        diagnoses = [
            FailureDiagnosis(
                category=FailureCategory.LOW_COVERAGE,
                severity="warning",
                evidence="coverage low",
                repair_actions=["probe_fields", "repair_selectors", "reanalyze_site"],
                confidence=0.6,
            ),
        ]
        actions = _generate_repair_actions(diagnoses, {"name": "test"}, {})
        repair_only = [a for a in actions if a.action != "prepare_rerun"]

        # warning strategy max_actions=3
        self.assertLessEqual(len(repair_only), 3)
        # warning strategy allow_costly_repairs=False (cost_limit=2)
        for a in repair_only:
            cost = REPAIR_ACTION_COST.get(a.action, 2)
            self.assertLessEqual(cost, 2,
                                 f"Warning severity should exclude costly action '{a.action}' (cost={cost})")

    def test_critical_severity_allows_costly_repairs(self) -> None:
        """Critical severity should allow cost 3+ actions like adjust_runtime."""
        from autonomous_crawler.runners.auto_repair import (
            _generate_repair_actions,
            FailureDiagnosis,
            FailureCategory,
            REPAIR_ACTION_COST,
        )

        diagnoses = [
            FailureDiagnosis(
                category=FailureCategory.ACCESS_BLOCKED,
                severity="critical",
                evidence="blocked",
                repair_actions=["inspect_access", "adjust_runtime"],
                confidence=0.9,
            ),
        ]
        actions = _generate_repair_actions(diagnoses, {"name": "test"}, {})
        repair_only = [a for a in actions if a.action != "prepare_rerun"]

        action_types = {a.action for a in repair_only}
        # Critical should include adjust_runtime (cost=3)
        self.assertIn("adjust_runtime", action_types)
        self.assertIn("inspect_access", action_types)

    def test_diagnosis_report_serializable_with_new_fields(self) -> None:
        """DiagnosisReport should still be JSON-serializable with new fields."""
        import json
        from autonomous_crawler.runners.auto_repair import FailureDiagnoser

        job = {
            "status": "failed",
            "error_log": ["HTTP 403"],
            "profile_run": {
                "product_stats": {
                    "records_saved": 0,
                    "quality_indicator": "fail",
                    "failure_buckets": {"http_blocked": 3},
                },
            },
        }
        diagnoser = FailureDiagnoser()
        report = diagnoser.diagnose(job=job)
        d = report.to_dict()
        json.dumps(d)


class TestRepairActionCost(unittest.TestCase):
    """Test REPAIR_ACTION_COST and SEVERITY_REPAIR_STRATEGY constants."""

    def test_all_repair_actions_have_cost(self) -> None:
        """Every action in REPAIR_ACTION_MAP should have a cost entry."""
        from autonomous_crawler.runners.auto_repair import (
            REPAIR_ACTION_MAP,
            REPAIR_ACTION_COST,
        )
        all_actions = set()
        for actions in REPAIR_ACTION_MAP.values():
            all_actions.update(actions)
        for action in all_actions:
            self.assertIn(
                action, REPAIR_ACTION_COST,
                f"Repair action '{action}' missing from REPAIR_ACTION_COST",
            )

    def test_severity_strategies_defined(self) -> None:
        """All three severity levels should have strategies."""
        from autonomous_crawler.runners.auto_repair import SEVERITY_REPAIR_STRATEGY
        self.assertIn("critical", SEVERITY_REPAIR_STRATEGY)
        self.assertIn("warning", SEVERITY_REPAIR_STRATEGY)
        self.assertIn("info", SEVERITY_REPAIR_STRATEGY)
        self.assertTrue(SEVERITY_REPAIR_STRATEGY["critical"]["allow_costly_repairs"])
        self.assertFalse(SEVERITY_REPAIR_STRATEGY["warning"]["allow_costly_repairs"])


class TestComputeRepairDelta(unittest.TestCase):
    """Test _compute_repair_delta helper."""

    def test_delta_shows_improvement(self) -> None:
        from autonomous_crawler.runners.auto_repair import _compute_repair_delta, DiagnosisReport

        before = {"records_saved": 0, "health": "critical", "field_coverage": 0.0}
        after = {"records_saved": 20, "health": "healthy", "field_coverage": 0.8}
        diagnosis = DiagnosisReport(diagnoses=[], overall_health="critical")
        execute_result = {
            "chain_evidence": {
                "actions_executed": [
                    {"action": "adjust_runtime", "ok": True, "summary": "switched mode"},
                ],
            },
        }
        delta = _compute_repair_delta(
            before=before, after=after, diagnosis=diagnosis, execute_result=execute_result,
        )
        self.assertTrue(delta["improved"])
        self.assertEqual(delta["records_delta"], 20)
        self.assertEqual(delta["health_delta"], 3)  # critical(0) -> healthy(3)
        self.assertEqual(delta["before_health"], "critical")
        self.assertEqual(delta["after_health"], "healthy")
        self.assertIn("adjust_runtime", delta["actions_taken"])

    def test_delta_shows_no_improvement(self) -> None:
        from autonomous_crawler.runners.auto_repair import _compute_repair_delta, DiagnosisReport

        before = {"records_saved": 0, "health": "critical", "field_coverage": 0.0}
        after = {"records_saved": 0, "health": "critical", "field_coverage": 0.0}
        diagnosis = DiagnosisReport(diagnoses=[], overall_health="critical")
        execute_result = {"chain_evidence": {"actions_executed": []}}
        delta = _compute_repair_delta(
            before=before, after=after, diagnosis=diagnosis, execute_result=execute_result,
        )
        self.assertFalse(delta["improved"])
        self.assertEqual(delta["records_delta"], 0)
        self.assertEqual(delta["health_delta"], 0)


class TestCountResolvedDiagnoses(unittest.TestCase):
    """Test _count_resolved_diagnoses helper."""

    def test_no_records_resolved_when_records_appear(self) -> None:
        from autonomous_crawler.runners.auto_repair import (
            _count_resolved_diagnoses,
            DiagnosisReport,
            FailureDiagnosis,
            FailureCategory,
        )

        diagnosis = DiagnosisReport(
            diagnoses=[
                FailureDiagnosis(
                    category=FailureCategory.NO_RECORDS,
                    severity="critical",
                    evidence="zero records",
                ),
            ],
        )
        resolved = _count_resolved_diagnoses(
            diagnosis=diagnosis, after_records=10, after_health="healthy",
        )
        self.assertEqual(resolved, 1)

    def test_no_records_not_resolved_when_still_zero(self) -> None:
        from autonomous_crawler.runners.auto_repair import (
            _count_resolved_diagnoses,
            DiagnosisReport,
            FailureDiagnosis,
            FailureCategory,
        )

        diagnosis = DiagnosisReport(
            diagnoses=[
                FailureDiagnosis(
                    category=FailureCategory.NO_RECORDS,
                    severity="critical",
                    evidence="zero records",
                ),
            ],
        )
        resolved = _count_resolved_diagnoses(
            diagnosis=diagnosis, after_records=0, after_health="critical",
        )
        self.assertEqual(resolved, 0)


if __name__ == "__main__":
    unittest.main()
