import unittest

from autonomous_crawler.runners.threaded_stage_runner import (
    ThreadedStageRunner,
    ThreadedStageRunnerConfig,
)


class ThreadedStageRunnerTests(unittest.TestCase):
    def test_three_stage_pipeline_saves_records(self):
        saved = []

        runner = ThreadedStageRunner(
            seeds=[{"url": "https://example.test/cat"}],
            list_callback=lambda item: [
                {"url": "https://example.test/p1"},
                {"url": "https://example.test/p2"},
            ],
            detail_callback=lambda item: [{"url": item["url"], "variant": "default"}],
            variant_callback=lambda item: [{"url": item["url"], "title": item["variant"]}],
            sink=saved.append,
            key_func=lambda item: item.get("url", ""),
            config=ThreadedStageRunnerConfig(detail_workers=2, variant_workers=2),
        )

        summary = runner.run()

        self.assertEqual(summary.records_saved, 2)
        self.assertEqual(len(saved), 2)
        self.assertEqual(summary.failures, [])

    def test_dedupes_stage_items_and_saved_records(self):
        saved = []

        runner = ThreadedStageRunner(
            seeds=[{"url": "https://example.test/cat"}],
            list_callback=lambda item: [
                {"url": "https://example.test/p1"},
                {"url": "https://example.test/p1"},
            ],
            detail_callback=lambda item: [
                {"url": item["url"], "variant": "a"},
                {"url": item["url"], "variant": "b"},
            ],
            variant_callback=lambda item: [{"url": item["url"], "title": item["variant"]}],
            sink=saved.append,
            key_func=lambda item: item.get("url", ""),
            config=ThreadedStageRunnerConfig(detail_workers=2, variant_workers=2),
        )

        summary = runner.run()

        self.assertEqual(summary.records_saved, 1)
        self.assertGreaterEqual(summary.duplicates_skipped, 1)

    def test_captures_stage_failures(self):
        def bad_detail(_item):
            raise RuntimeError("detail failed")

        runner = ThreadedStageRunner(
            seeds=[{"url": "https://example.test/cat"}],
            list_callback=lambda item: [{"url": "https://example.test/p1"}],
            detail_callback=bad_detail,
            variant_callback=lambda item: [item],
            sink=lambda item: None,
            key_func=lambda item: item.get("url", ""),
            config=ThreadedStageRunnerConfig(detail_workers=1, variant_workers=1),
        )

        summary = runner.run()

        self.assertEqual(summary.records_saved, 0)
        self.assertEqual(summary.failures[0]["stage"], "detail")
        self.assertIn("detail failed", summary.failures[0]["error"])


if __name__ == "__main__":
    unittest.main()
