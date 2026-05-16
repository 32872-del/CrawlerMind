from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.runners import (
    BatchRunner,
    BatchRunnerConfig,
    ProductRecordCheckpoint,
    SiteProfile,
    SpiderRuntimeProcessor,
    build_profile_run_report,
    initial_requests_from_profile,
    make_ecommerce_profile_callbacks,
    profile_quality_summary,
)
from autonomous_crawler.runtime import NativeParserRuntime, RuntimeRequest, RuntimeResponse
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
from run_profile_training_2026_05_15 import run as run_profile_training
from run_real_ecommerce_profile_training_2026_05_15 import run as run_real_ecommerce_training


API_PROFILE_PATH = Path("autonomous_crawler/tests/fixtures/ecommerce_api_pagination_profile.json")


class ApiFixtureFetchRuntime:
    name = "api_fixture_fetch"

    def __init__(self, *, total: int = 55, page_size: int = 20) -> None:
        self.total = total
        self.page_size = page_size
        self.requests: list[RuntimeRequest] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        query = parse_qs(urlparse(request.url).query)
        page = int(query.get("page", ["1"])[0])
        limit = int(query.get("limit", [str(self.page_size)])[0])
        start = (page - 1) * limit
        end = min(start + limit, self.total)
        products = [
            {
                "name": f"API Product {idx:02d}",
                "price": {"amount": 10 + idx / 10, "currency": "USD"},
                "url": f"https://api-profile-shop.local/products/{idx:02d}",
                "variants": {
                    "colors": ["Black", "Blue"] if idx % 2 == 0 else ["White"],
                    "sizes": ["40", "41", "42"],
                },
                "description": f"Fixture API product {idx}",
                "media": {"images": [f"/images/api-product-{idx:02d}.jpg"]},
            }
            for idx in range(start, end)
        ]
        payload = {
            "data": {
                "products": products,
                "page": page,
                "limit": limit,
                "total": self.total,
            }
        }
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            text=json.dumps(payload),
            engine_result={"engine": self.name},
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

    def test_api_pagination_profile_collects_50_plus_products(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = SiteProfile.load(API_PROFILE_PATH)
            frontier = URLFrontier(root / "frontier.sqlite3")
            product_store = ProductStore(root / "products.sqlite3")
            checkpoint_store = CheckpointStore(root / "checkpoints.sqlite3")
            run_id = "run-api-profile-pagination"
            checkpoint_store.start_run(run_id, {"profile": profile.name})

            seeds = initial_requests_from_profile(profile, run_id=run_id)
            frontier.add_urls(
                [request.url for request in seeds],
                kind=seeds[0].kind,
                priority=seeds[0].priority,
                payload={"meta": {"category": profile.quality_expectations["category"]}},
            )

            fetch = ApiFixtureFetchRuntime(total=55, page_size=20)
            callbacks = make_ecommerce_profile_callbacks(profile, run_id=run_id)
            processor = SpiderRuntimeProcessor(
                run_id=run_id,
                fetch_runtime=fetch,
                checkpoint_store=checkpoint_store,
                selector_builder=callbacks.selector_builder,
                record_builder=callbacks.record_builder,
                link_builder=callbacks.link_builder,
            )

            first = BatchRunner(
                frontier=frontier,
                processor=processor,
                config=BatchRunnerConfig(run_id=run_id, batch_size=1, max_batches=1),
                checkpoint=ProductRecordCheckpoint(product_store),
            ).run()
            after_first = frontier.stats()
            second = BatchRunner(
                frontier=frontier,
                processor=processor,
                config=BatchRunnerConfig(run_id=run_id, batch_size=10),
                checkpoint=ProductRecordCheckpoint(product_store),
            ).run()
            records = product_store.list_records(run_id, limit=100)

        self.assertEqual(first.claimed, 1)
        self.assertEqual(first.records_saved, 20)
        self.assertEqual(first.discovered_urls, 1)
        self.assertEqual(after_first, {"done": 1, "queued": 1})
        self.assertEqual(second.claimed, 2)
        self.assertEqual(second.records_saved, 35)
        self.assertEqual(len(records), 55)
        self.assertEqual(records[0].title, "API Product 00")
        self.assertEqual(records[-1].title, "API Product 54")
        self.assertEqual(records[-1].currency, "USD")
        self.assertTrue(records[-1].image_urls[0].startswith("https://api-profile-shop.local"))

    def test_profile_training_round_outputs_quality_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_profile_training(output_path=Path(tmp) / "profile_training.json")

        self.assertTrue(summary["accepted"])
        self.assertGreaterEqual(summary["total_records"], 50)
        profiles = {item["profile"]: item for item in summary["profiles"]}
        self.assertEqual(set(profiles), {
            "fixture-ecommerce-profile",
            "fixture-ecommerce-api-pagination",
            "fixture-ecommerce-mixed-hydration",
        })
        self.assertGreaterEqual(profiles["fixture-ecommerce-api-pagination"]["record_count"], 50)
        self.assertGreaterEqual(profiles["fixture-ecommerce-mixed-hydration"]["record_count"], 50)
        self.assertIn("profile-api-pagination", profiles["fixture-ecommerce-mixed-hydration"]["record_modes"])
        self.assertIn("profile-driven", profiles["fixture-ecommerce-mixed-hydration"]["record_modes"])
        for item in profiles.values():
            quality = item["quality_summary"]
            self.assertEqual(quality["duplicate_rate"], 0.0)
            self.assertEqual(quality["failed_url_count"], 0)
            self.assertGreaterEqual(quality["field_completeness"]["title"], 1.0)
            self.assertGreaterEqual(quality["field_completeness"]["price"], 1.0)
            self.assertIn(quality["pagination_stop_reason"], {
                "dom_link_frontier_exhausted",
                "max_pages",
                "no_next_cursor",
            })

    def test_real_ecommerce_training_fixture_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = run_real_ecommerce_training(
                output_path=Path(tmp) / "real_profile_training.json",
                fixture_only=True,
            )

        fixture = summary["fixture_regression"]
        self.assertIsNone(summary["real_result"])
        self.assertTrue(fixture["accepted"])
        self.assertGreaterEqual(fixture["record_count"], 50)
        self.assertEqual(fixture["quality_summary"]["failed_url_count"], 0)
        self.assertEqual(fixture["quality_summary"]["duplicate_rate"], 0.0)
        self.assertEqual(fixture["quality_summary"]["field_completeness"]["title"], 1.0)
        self.assertEqual(fixture["quality_summary"]["field_completeness"]["image_urls"], 1.0)

    def test_profile_quality_gate_passes_when_thresholds_are_met(self) -> None:
        records = [
            ProductRecord(
                source_site="gate-test",
                canonical_url=f"https://example.test/products/{idx}",
                title=f"Gate Product {idx}",
                highest_price=10.0 + idx,
                category="training-shoes",
                image_urls=[f"https://example.test/images/{idx}.jpg"],
            )
            for idx in range(3)
        ]

        summary = profile_quality_summary(
            records,
            min_items=3,
            required_fields=["title", "highest_price", "category", "image_urls"],
            max_duplicate_rate=0.0,
            max_failed_url_count=0,
        )

        gate = summary["quality_gate"]
        self.assertTrue(gate["passed"])
        self.assertFalse(gate["should_fail"])
        self.assertEqual(gate["severity"], "pass")
        self.assertTrue(all(check["severity"] == "pass" for check in gate["checks"]))

    def test_profile_quality_gate_warns_by_default_without_breaking_flow(self) -> None:
        records = [
            ProductRecord(
                source_site="gate-test",
                canonical_url="https://example.test/products/1",
                title="Gate Product 1",
                highest_price=None,
                category="training-shoes",
            )
        ]

        summary = profile_quality_summary(
            records,
            failed_urls=["https://example.test/broken"],
            min_items=2,
            required_fields=["title", "highest_price", "image_urls"],
            max_duplicate_rate=0.0,
            max_failed_url_count=0,
        )

        gate = summary["quality_gate"]
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["should_fail"])
        self.assertEqual(gate["mode"], "warn")
        self.assertEqual(gate["severity"], "warn")
        failed_checks = {check["name"] for check in gate["checks"] if not check["passed"]}
        self.assertEqual(failed_checks, {"min_items", "field:image_urls", "field:price", "failed_url_count"})

    def test_profile_quality_gate_can_opt_in_to_failure(self) -> None:
        records = [
            ProductRecord(
                source_site="gate-test",
                canonical_url="https://example.test/products/duplicate",
                title="Gate Product 1",
                highest_price=11.0,
                category="training-shoes",
            ),
            ProductRecord(
                source_site="gate-test",
                canonical_url="https://example.test/products/duplicate",
                title="Gate Product 1",
                highest_price=11.0,
                category="training-shoes",
            ),
        ]

        summary = profile_quality_summary(
            records,
            min_items=3,
            required_fields=["title", "price"],
            max_duplicate_rate=0.0,
            fail_on_gate=True,
        )

        gate = summary["quality_gate"]
        self.assertFalse(gate["passed"])
        self.assertTrue(gate["should_fail"])
        self.assertEqual(gate["mode"], "fail")
        self.assertEqual(gate["severity"], "fail")
        failed_checks = {check["name"] for check in gate["checks"] if not check["passed"]}
        self.assertEqual(failed_checks, {"min_items", "duplicate_rate"})

    def test_profile_quality_gate_supports_field_threshold_policy(self) -> None:
        records = [
            ProductRecord(
                source_site="policy-test",
                canonical_url=f"https://example.test/products/{idx}",
                title=f"Policy Product {idx}",
                highest_price=11.0,
                description="usable description" if idx < 3 else "",
                image_urls=[f"https://example.test/images/{idx}.jpg"] if idx < 4 else [],
                category="training-shoes",
            )
            for idx in range(5)
        ]

        summary = profile_quality_summary(
            records,
            quality_policy={
                "min_items": 5,
                "mode": "warn",
                "field_thresholds": {
                    "title": 1.0,
                    "description": 0.6,
                    "image": 0.8,
                    "colors": 0.5,
                },
                "max_duplicate_rate": 0.0,
                "max_failed_url_count": 0,
            },
        )

        gate = summary["quality_gate"]
        self.assertFalse(gate["passed"])
        self.assertFalse(gate["should_fail"])
        checks = {check["name"]: check for check in gate["checks"]}
        self.assertTrue(checks["field:title"]["passed"])
        self.assertTrue(checks["field:description"]["passed"])
        self.assertTrue(checks["field:image_urls"]["passed"])
        self.assertFalse(checks["field:colors"]["passed"])
        self.assertEqual(checks["field:colors"]["severity"], "warn")

    def test_profile_quality_gate_fail_mode_uses_policy(self) -> None:
        summary = profile_quality_summary(
            [],
            failed_urls=["https://example.test/fail"],
            quality_policy={
                "mode": "fail",
                "min_items": 1,
                "required_fields": {"title": 0.9},
                "max_failed_url_count": 0,
            },
        )

        gate = summary["quality_gate"]
        self.assertFalse(gate["passed"])
        self.assertTrue(gate["should_fail"])
        self.assertEqual(gate["severity"], "fail")
        failed_checks = {check["name"] for check in gate["checks"] if not check["passed"]}
        self.assertEqual(failed_checks, {"min_items", "field:title", "failed_url_count"})

    def test_profile_run_report_export_contains_stable_fields(self) -> None:
        quality = profile_quality_summary(
            [
                ProductRecord(
                    source_site="report-test",
                    canonical_url="https://example.test/products/1",
                    title="Report Product",
                    highest_price=12.0,
                    category="training-shoes",
                    image_urls=["https://example.test/images/1.jpg"],
                )
            ],
            quality_policy={"min_items": 1, "required_fields": {"title": 1.0}},
        )

        report = build_profile_run_report(
            profile_name="report-profile",
            profile_path="fixtures/report-profile.json",
            run_id="run-report",
            runner_summary={"records_saved": 1},
            quality_summary=quality,
            sample_records=[{"title": "Report Product"}],
            failures=[],
            runtime_backend="fixture",
            parser_backend="json_profile",
            stop_reason="max_pages",
            target="https://example.test/products",
        )

        self.assertEqual(report["schema_version"], "profile-run-report/v1")
        self.assertEqual(report["profile"]["name"], "report-profile")
        self.assertEqual(report["metrics"]["record_count"], 1)
        self.assertEqual(report["quality_gate"]["severity"], "pass")
        self.assertIn("next_actions", report)


if __name__ == "__main__":
    unittest.main()
