from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.runners.backpressure import (
    BackpressureConfig,
    BackpressureMonitor,
    BackpressureSignals,
    classify_bottlenecks,
    recommendation_text,
)


class ClassifyBottlenecksTests(unittest.TestCase):
    def test_empty_signals_returns_no_bottlenecks(self) -> None:
        signals = BackpressureSignals()
        self.assertEqual(classify_bottlenecks(signals), [])

    def test_access_blocking_on_403_errors(self) -> None:
        signals = BackpressureSignals(failure_rate=0.35)
        errors = [
            {"error": "403 forbidden"},
            {"error": "access denied"},
            {"error": "cloudflare challenge"},
        ]
        bns = classify_bottlenecks(signals, item_errors=errors)
        keys = [bn["key"] for bn in bns]
        self.assertIn("access_blocking", keys)

    def test_selector_loss_on_parse_errors(self) -> None:
        signals = BackpressureSignals()
        errors = [{"error": "selector returned no results"}]
        bns = classify_bottlenecks(signals, item_errors=errors)
        keys = [bn["key"] for bn in bns]
        self.assertIn("selector_loss", keys)

    def test_transport_pressure_on_high_latency(self) -> None:
        signals = BackpressureSignals(avg_latency_ms=12000, p95_latency_ms=18000)
        bns = classify_bottlenecks(signals)
        keys = [bn["key"] for bn in bns]
        self.assertIn("transport_pressure", keys)

    def test_retry_pressure_on_high_retry_rate(self) -> None:
        signals = BackpressureSignals(retry_rate=0.30)
        bns = classify_bottlenecks(signals)
        keys = [bn["key"] for bn in bns]
        self.assertIn("retry_pressure", keys)

    def test_quality_loss_on_checkpoint_errors(self) -> None:
        signals = BackpressureSignals(quality_loss_rate=0.10)
        bns = classify_bottlenecks(signals)
        keys = [bn["key"] for bn in bns]
        self.assertIn("quality_loss", keys)

    def test_bottleneck_has_zh_summary(self) -> None:
        signals = BackpressureSignals(avg_latency_ms=16000)
        bns = classify_bottlenecks(signals)
        self.assertTrue(len(bns) > 0)
        for bn in bns:
            self.assertIn("summary_zh", bn)
            self.assertTrue(len(bn["summary_zh"]) > 0)

    def test_bottleneck_has_severity(self) -> None:
        signals = BackpressureSignals(failure_rate=0.45)
        errors = [{"error": "403 forbidden"}, {"error": "captcha detected"}]
        bns = classify_bottlenecks(signals, item_errors=errors)
        blocking = [bn for bn in bns if bn["key"] == "access_blocking"]
        self.assertEqual(len(blocking), 1)
        self.assertEqual(blocking[0]["severity"], "critical")


class RecommendationTextTests(unittest.TestCase):
    def test_proceed_returns_proceed(self) -> None:
        signals = BackpressureSignals(recommendation="proceed")
        rec = recommendation_text(signals)
        self.assertEqual(rec["code"], "proceed")
        self.assertIn("message_zh", rec)
        self.assertIn("正常", rec["message_zh"])

    def test_abort_with_access_blocking(self) -> None:
        signals = BackpressureSignals(recommendation="abort", failure_rate=0.45)
        bns = [{"key": "access_blocking", "severity": "critical"}]
        rec = recommendation_text(signals, bns)
        self.assertEqual(rec["code"], "abort")
        self.assertIn("封锁", rec["message_zh"])

    def test_pause_with_transport_pressure(self) -> None:
        signals = BackpressureSignals(recommendation="pause")
        bns = [{"key": "transport_pressure", "severity": "critical"}]
        rec = recommendation_text(signals, bns)
        self.assertEqual(rec["code"], "pause")
        self.assertIn("暂停", rec["message_zh"])

    def test_slow_down_with_reasons(self) -> None:
        signals = BackpressureSignals(recommendation="slow_down", retry_rate=0.30, avg_latency_ms=6000)
        bns = [{"key": "retry_pressure", "severity": "warn"}]
        rec = recommendation_text(signals, bns)
        self.assertEqual(rec["code"], "slow_down")
        self.assertIn("降速", rec["message_zh"])

    def test_all_codes_have_zh_message(self) -> None:
        for code in ("proceed", "slow_down", "pause", "abort"):
            signals = BackpressureSignals(recommendation=code, reason="test")
            rec = recommendation_text(signals)
            self.assertEqual(rec["code"], code)
            self.assertTrue(len(rec["message_zh"]) > 0)


class DiagnosticsSerializationTests(unittest.TestCase):
    def test_diagnostics_survives_json_roundtrip(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(6000.0, claimed=10, succeeded=8, failed=2, retried=1, checkpoint_errors=1)
        signals = monitor.current_signals()
        bns = classify_bottlenecks(signals, item_errors=[{"error": "403 forbidden"}])
        rec = recommendation_text(signals, bns)
        diagnostics = {
            "bottlenecks": bns,
            "recommendation": rec,
            "backpressure_signals": signals.as_dict(),
        }
        serialized = json.dumps(diagnostics, ensure_ascii=False)
        deserialized = json.loads(serialized)
        self.assertEqual(len(deserialized["bottlenecks"]), len(bns))
        self.assertEqual(deserialized["recommendation"]["code"], rec["code"])
        self.assertIn("backpressure_signals", deserialized)


class ReportPersistenceWithDiagnosticsTests(unittest.TestCase):
    def test_report_includes_backpressure_and_diagnostics(self) -> None:
        from autonomous_crawler.runners.profile_report import build_profile_run_report

        backpressure = {
            "avg_latency_ms": 6000.0,
            "failure_rate": 0.15,
            "recommendation": "slow_down",
        }
        diagnostics = {
            "bottlenecks": [{"key": "transport_pressure", "severity": "warn", "summary": "slow", "summary_zh": "慢", "evidence": {}}],
            "recommendation": {"code": "slow_down", "message_en": "slowing", "message_zh": "降速"},
            "backpressure_signals": backpressure,
        }
        report = build_profile_run_report(
            profile_name="test-site",
            run_id="r1",
            backpressure=backpressure,
            diagnostics=diagnostics,
        )
        self.assertIn("backpressure", report)
        self.assertIn("diagnostics", report)
        self.assertEqual(report["backpressure"]["recommendation"], "slow_down")
        self.assertEqual(report["diagnostics"]["recommendation"]["code"], "slow_down")

    def test_report_without_diagnostics_omits_keys(self) -> None:
        from autonomous_crawler.runners.profile_report import build_profile_run_report

        report = build_profile_run_report(
            profile_name="test-site",
            run_id="r1",
        )
        self.assertNotIn("backpressure", report)
        self.assertNotIn("diagnostics", report)

    def test_report_survives_json_roundtrip(self) -> None:
        from autonomous_crawler.runners.profile_report import build_profile_run_report

        diagnostics = {
            "bottlenecks": [],
            "recommendation": {"code": "proceed", "message_en": "ok", "message_zh": "正常"},
            "backpressure_signals": {},
        }
        report = build_profile_run_report(
            profile_name="test-site",
            run_id="r1",
            diagnostics=diagnostics,
        )
        serialized = json.dumps(report, ensure_ascii=False, default=str)
        deserialized = json.loads(serialized)
        self.assertIn("diagnostics", deserialized)
        self.assertEqual(deserialized["diagnostics"]["recommendation"]["code"], "proceed")


if __name__ == "__main__":
    unittest.main()
