import time
import unittest

from autonomous_crawler.runners.multi_site_runner import MultiSiteRunner, MultiSiteRunnerConfig
from autonomous_crawler.runners.profile_longrun import run_multi_profile_longrun


class MultiSiteRunnerTests(unittest.TestCase):
    def test_runs_sites_concurrently(self):
        def job(name):
            def _inner():
                time.sleep(0.05)
                return name
            return _inner

        started = time.perf_counter()
        summary = MultiSiteRunner(
            {"a": job("a"), "b": job("b"), "c": job("c")},
            MultiSiteRunnerConfig(max_sites=3),
        ).run()
        elapsed = time.perf_counter() - started

        self.assertEqual(summary.ok_sites, 3)
        self.assertLess(elapsed, 0.14)
        self.assertEqual([result.result for result in summary.results], ["a", "b", "c"])

    def test_caps_at_five_sites(self):
        with self.assertRaises(ValueError):
            MultiSiteRunnerConfig(max_sites=6)

        jobs = {str(i): (lambda: i) for i in range(6)}
        with self.assertRaises(ValueError):
            MultiSiteRunner(jobs, MultiSiteRunnerConfig(max_sites=5))

    def test_captures_site_failure(self):
        def boom():
            raise RuntimeError("site failed")

        summary = MultiSiteRunner({"ok": lambda: 1, "bad": boom}).run()

        self.assertEqual(summary.ok_sites, 1)
        self.assertEqual(summary.failed_sites, 1)
        bad = [result for result in summary.results if result.name == "bad"][0]
        self.assertIn("site failed", bad.error)

    def test_profile_longrun_batch_uses_per_site_payloads(self):
        calls = []

        class Fetch:
            pass

        def fake_run_profile_longrun(*, profile, config, fetch_runtime, parser=None, runtime_dir=None):
            calls.append({
                "profile": profile.name,
                "run_id": config.run_id,
                "workers": config.item_workers,
                "runtime_dir": runtime_dir,
                "fetch": type(fetch_runtime).__name__,
            })

            class Result:
                def to_dict(self):
                    return {
                        "profile_name": profile.name,
                        "run_id": config.run_id,
                        "product_stats": {"total": 2},
                    }

            return Result()

        from unittest.mock import patch

        with patch("autonomous_crawler.runners.profile_longrun.run_profile_longrun", side_effect=fake_run_profile_longrun):
            summary = run_multi_profile_longrun(
                {
                    "shop_a": {
                        "profile": {"name": "shop-a"},
                        "run_id": "run-a",
                        "item_workers": 4,
                        "runtime_dir": "runtime/a",
                    },
                    "shop_b": {
                        "profile": {"name": "shop-b"},
                        "run_id": "run-b",
                        "item_workers": 2,
                    },
                },
                max_sites=2,
                fetch_runtime_factory=Fetch,
            )

        self.assertEqual(summary.ok_sites, 2)
        self.assertEqual(sorted(call["workers"] for call in calls), [2, 4])
        self.assertEqual(sorted(call["fetch"] for call in calls), ["Fetch", "Fetch"])


if __name__ == "__main__":
    unittest.main()
