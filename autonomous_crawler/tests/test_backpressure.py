from __future__ import annotations

import unittest

from autonomous_crawler.runners.backpressure import (
    BackpressureConfig,
    BackpressureMonitor,
    BackpressureSignals,
)


class SignalAccumulationTests(unittest.TestCase):
    def test_empty_monitor_returns_proceed(self) -> None:
        monitor = BackpressureMonitor()
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "proceed")
        self.assertEqual(signals.total_batches, 0)

    def test_record_batch_accumulates(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(1000.0, claimed=10, succeeded=8, failed=2, retried=0)
        signals = monitor.current_signals()
        self.assertEqual(signals.total_batches, 1)
        self.assertAlmostEqual(signals.avg_latency_ms, 1000.0)
        self.assertAlmostEqual(signals.failure_rate, 0.2)

    def test_multiple_batches_average_latency(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(1000.0, claimed=10, succeeded=10, failed=0, retried=0)
        monitor.record_batch(3000.0, claimed=10, succeeded=10, failed=0, retried=0)
        signals = monitor.current_signals()
        self.assertAlmostEqual(signals.avg_latency_ms, 2000.0)
        self.assertEqual(signals.total_batches, 2)

    def test_rates_computed_over_total_claimed(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(1000.0, claimed=10, succeeded=9, failed=1, retried=0)
        monitor.record_batch(1000.0, claimed=10, succeeded=8, failed=2, retried=0)
        signals = monitor.current_signals()
        self.assertAlmostEqual(signals.failure_rate, 0.15)  # 3/20


class RecommendationTests(unittest.TestCase):
    def test_proceed_on_healthy_metrics(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(1000.0, claimed=10, succeeded=10, failed=0, retried=0)
        self.assertEqual(monitor.current_signals().recommendation, "proceed")

    def test_slow_down_on_high_failure_rate(self) -> None:
        cfg = BackpressureConfig(failure_rate_warn=0.15)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(1000.0, claimed=20, succeeded=17, failed=3, retried=0)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "slow_down")
        self.assertIn("failure_rate", signals.reason)

    def test_slow_down_on_high_retry_rate(self) -> None:
        cfg = BackpressureConfig(retry_rate_warn=0.25)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(1000.0, claimed=20, succeeded=15, failed=0, retried=5)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "slow_down")
        self.assertIn("retry_rate", signals.reason)

    def test_slow_down_on_high_latency(self) -> None:
        cfg = BackpressureConfig(latency_warn_ms=5000)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "slow_down")
        self.assertIn("avg_latency", signals.reason)

    def test_slow_down_on_quality_loss(self) -> None:
        cfg = BackpressureConfig(quality_loss_warn=0.10)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(1000.0, claimed=10, succeeded=9, failed=0, retried=0, checkpoint_errors=2)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "slow_down")
        self.assertIn("quality_loss", signals.reason)

    def test_pause_on_very_high_latency(self) -> None:
        cfg = BackpressureConfig(latency_pause_ms=15000)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(16000.0, claimed=10, succeeded=10, failed=0, retried=0)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "pause")
        self.assertIn("avg_latency", signals.reason)

    def test_pause_on_consecutive_slow_batches(self) -> None:
        cfg = BackpressureConfig(latency_warn_ms=5000, consecutive_slow_threshold=3)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "pause")
        self.assertIn("consecutive_slow", signals.reason)

    def test_abort_on_very_high_failure_rate(self) -> None:
        cfg = BackpressureConfig(failure_rate_pause=0.40)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(1000.0, claimed=10, succeeded=6, failed=4, retried=0)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "abort")
        self.assertIn("failure_rate", signals.reason)

    def test_abort_takes_priority_over_pause(self) -> None:
        cfg = BackpressureConfig(failure_rate_pause=0.40, latency_pause_ms=5000)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(10000.0, claimed=10, succeeded=5, failed=5, retried=0)
        signals = monitor.current_signals()
        self.assertEqual(signals.recommendation, "abort")

    def test_consecutive_slow_resets_on_good_batch(self) -> None:
        cfg = BackpressureConfig(latency_warn_ms=5000, consecutive_slow_threshold=3)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        monitor.record_batch(1000.0, claimed=10, succeeded=10, failed=0, retried=0)  # resets
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        signals = monitor.current_signals()
        # avg latency = (6000+6000+1000+6000)/4 = 4750ms < 5000ms warn threshold
        # so recommendation is "proceed", but consecutive_slow is 1
        self.assertEqual(signals.recommendation, "proceed")
        self.assertEqual(signals.consecutive_slow_batches, 1)


class ShouldPauseTests(unittest.TestCase):
    def test_should_pause_false_when_proceed(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(1000.0, claimed=10, succeeded=10, failed=0, retried=0)
        self.assertFalse(monitor.should_pause())

    def test_should_pause_true_on_pause(self) -> None:
        cfg = BackpressureConfig(latency_pause_ms=5000)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        self.assertTrue(monitor.should_pause())

    def test_should_pause_true_on_abort(self) -> None:
        cfg = BackpressureConfig(failure_rate_pause=0.40)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(1000.0, claimed=10, succeeded=5, failed=5, retried=0)
        self.assertTrue(monitor.should_pause())


class ShouldAbortTests(unittest.TestCase):
    def test_should_abort_false_when_proceed(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(1000.0, claimed=10, succeeded=10, failed=0, retried=0)
        self.assertFalse(monitor.should_abort())

    def test_should_abort_false_on_pause(self) -> None:
        cfg = BackpressureConfig(latency_pause_ms=5000)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(6000.0, claimed=10, succeeded=10, failed=0, retried=0)
        self.assertFalse(monitor.should_abort())

    def test_should_abort_true_on_abort(self) -> None:
        cfg = BackpressureConfig(failure_rate_pause=0.40)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(1000.0, claimed=10, succeeded=5, failed=5, retried=0)
        self.assertTrue(monitor.should_abort())


class ResetTests(unittest.TestCase):
    def test_reset_clears_state(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(1000.0, claimed=10, succeeded=8, failed=2, retried=1)
        monitor.reset()
        signals = monitor.current_signals()
        self.assertEqual(signals.total_batches, 0)
        self.assertEqual(signals.recommendation, "proceed")

    def test_reset_allows_fresh_recommendations(self) -> None:
        cfg = BackpressureConfig(failure_rate_pause=0.40)
        monitor = BackpressureMonitor(cfg)
        monitor.record_batch(1000.0, claimed=10, succeeded=5, failed=5, retried=0)
        self.assertTrue(monitor.should_abort())
        monitor.reset()
        self.assertFalse(monitor.should_abort())


class AsDictTests(unittest.TestCase):
    def test_signals_as_dict(self) -> None:
        monitor = BackpressureMonitor()
        monitor.record_batch(2000.0, claimed=10, succeeded=9, failed=1, retried=0)
        d = monitor.current_signals().as_dict()
        self.assertIn("avg_latency_ms", d)
        self.assertIn("failure_rate", d)
        self.assertIn("recommendation", d)
        self.assertIsInstance(d["avg_latency_ms"], float)

    def test_config_as_dict(self) -> None:
        cfg = BackpressureConfig()
        d = cfg.as_dict()
        self.assertIn("latency_warn_ms", d)
        self.assertIn("failure_rate_pause", d)


class BatchTimerTests(unittest.TestCase):
    def test_timer_records_batch(self) -> None:
        monitor = BackpressureMonitor()
        with monitor.time_batch() as timer:
            timer.claimed = 10
            timer.succeeded = 9
            timer.failed = 1
        signals = monitor.current_signals()
        self.assertEqual(signals.total_batches, 1)
        self.assertAlmostEqual(signals.failure_rate, 0.1)

    def test_timer_measures_latency(self) -> None:
        monitor = BackpressureMonitor()
        with monitor.time_batch() as timer:
            timer.claimed = 1
            timer.succeeded = 1
        signals = monitor.current_signals()
        self.assertGreater(signals.avg_latency_ms, 0)


class P95LatencyTests(unittest.TestCase):
    def test_p95_latency(self) -> None:
        monitor = BackpressureMonitor()
        for i in range(100):
            monitor.record_batch(float(i * 100), claimed=1, succeeded=1, failed=0, retried=0)
        signals = monitor.current_signals()
        self.assertGreater(signals.p95_latency_ms, 0)
        self.assertLessEqual(signals.p95_latency_ms, 10000.0)


if __name__ == "__main__":
    unittest.main()
