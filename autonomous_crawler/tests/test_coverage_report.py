import unittest

from autonomous_crawler.tools.coverage_report import CoverageCounters, build_coverage_report


class CoverageReportTests(unittest.TestCase):
    def test_builds_loss_funnel_and_recovery_actions(self):
        report = build_coverage_report(
            CoverageCounters(
                estimated_inventory=5000,
                discovered_urls=4980,
                attempted_fetches=4980,
                fetched_success=4700,
                blocked_or_challenged=180,
                fetch_failed=100,
                render_attempted=200,
                render_success=170,
                render_failed=30,
                parsed_records=4550,
                quality_passed=4300,
                quality_failed=250,
                exported_unique=4280,
                duplicate_dropped=20,
            ),
            target_records=5000,
        )

        payload = report.to_dict()

        self.assertEqual(payload["schema_version"], "coverage-report/v1")
        self.assertFalse(payload["accepted"])
        self.assertEqual(payload["rates"]["overall_coverage_rate"], 0.856)
        self.assertEqual(payload["main_loss_reason"], "access_or_transport_loss")
        self.assertIn("harden_access: transport fallback + browser profile rotation + proxy/session/backoff diagnostics", payload["recommended_recovery"])
        self.assertIn("recover_quality: reject invalid pages, clean media, enqueue replacement URLs until valid target is met", payload["recommended_recovery"])

    def test_unattempted_urls_are_schedule_loss_not_access_loss(self):
        report = build_coverage_report(
            CoverageCounters(
                estimated_inventory=1000,
                discovered_urls=1000,
                attempted_fetches=100,
                fetched_success=100,
                parsed_records=100,
                quality_passed=100,
                exported_unique=100,
                time_budget_exhausted=True,
            ),
            target_records=1000,
        )

        payload = report.to_dict()
        self.assertEqual(payload["main_loss_reason"], "time_budget_or_frontier_pending")
        self.assertIn("increase_throughput: cache catalog discovery + parallel fetch + adaptive concurrency + resume pending frontier", payload["recommended_recovery"])
        access_loss = [loss for loss in payload["losses"] if loss["stage"] == "access"][0]
        self.assertEqual(access_loss["lost"], 0)

    def test_catalog_exhausted_can_be_accepted_when_true_inventory_is_smaller(self):
        report = build_coverage_report(
            CoverageCounters(
                estimated_inventory=919,
                discovered_urls=919,
                attempted_fetches=919,
                fetched_success=919,
                parsed_records=919,
                quality_passed=919,
                exported_unique=919,
                catalog_exhausted=True,
            ),
            target_records=2000,
        )

        self.assertTrue(report.accepted)
        self.assertIn("record_catalog_exhausted: report true discovered inventory instead of duplicating rows", report.recommended_recovery)


if __name__ == "__main__":
    unittest.main()
