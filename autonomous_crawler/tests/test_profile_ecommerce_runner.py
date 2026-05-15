from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.runners import (
    BatchRunner,
    BatchRunnerConfig,
    ProductRecordCheckpoint,
    SiteProfile,
    SpiderRuntimeProcessor,
    make_ecommerce_profile_callbacks,
)
from autonomous_crawler.runtime import NativeParserRuntime
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore

from run_profile_ecommerce_runner_smoke_2026_05_14 import (
    BASE_URL,
    HTML_FIXTURES,
    PROFILE_PATH,
    RUN_ID,
    FixtureFetchRuntime,
    run,
)


class ProfileDrivenEcommerceRunnerTests(unittest.TestCase):
    def test_profile_driven_smoke_collects_products_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run(output_path=Path(tmp) / "profile_smoke.json")

        self.assertTrue(summary["accepted"])
        self.assertEqual(summary["collected_record_count"], 2)
        self.assertEqual(summary["after_first_frontier_stats"], {"done": 1, "queued": 2})
        self.assertEqual(summary["final_frontier_stats"], {"done": 3})
        titles = {record["title"] for record in summary["records"]}
        self.assertEqual(titles, {"Alpha Runner", "Beta Trail"})

    def test_profile_callbacks_drive_runner_without_site_specific_callbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = SiteProfile.load(PROFILE_PATH)
            frontier = URLFrontier(root / "frontier.sqlite3")
            product_store = ProductStore(root / "products.sqlite3")
            checkpoint_store = CheckpointStore(root / "checkpoints.sqlite3")
            checkpoint_store.start_run(RUN_ID, {"profile": profile.name})
            frontier.add_urls([f"{BASE_URL}/collections/running"], kind="list", priority=10)

            callbacks = make_ecommerce_profile_callbacks(profile, run_id=RUN_ID)
            processor = SpiderRuntimeProcessor(
                run_id=RUN_ID,
                fetch_runtime=FixtureFetchRuntime(HTML_FIXTURES),
                parser=NativeParserRuntime(),
                checkpoint_store=checkpoint_store,
                selector_builder=callbacks.selector_builder,
                record_builder=callbacks.record_builder,
                link_builder=callbacks.link_builder,
            )

            first = BatchRunner(
                frontier=frontier,
                processor=processor,
                config=BatchRunnerConfig(run_id=RUN_ID, batch_size=1, max_batches=1),
                checkpoint=ProductRecordCheckpoint(product_store),
            ).run()
            after_first = frontier.stats()
            second = BatchRunner(
                frontier=frontier,
                processor=processor,
                config=BatchRunnerConfig(run_id=RUN_ID, batch_size=10),
                checkpoint=ProductRecordCheckpoint(product_store),
            ).run()

            records = product_store.list_records(RUN_ID, limit=10)

        self.assertEqual(first.discovered_urls, 2)
        self.assertEqual(after_first, {"done": 1, "queued": 2})
        self.assertEqual(second.succeeded, 2)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].currency, "USD")
        self.assertEqual(records[0].category, "training-shoes")
        self.assertTrue(records[0].image_urls[0].startswith(BASE_URL))


if __name__ == "__main__":
    unittest.main()
