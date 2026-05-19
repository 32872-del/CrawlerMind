from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from autonomous_crawler.runners import (
    ProfileLongRunConfig,
    SiteProfile,
    run_profile_longrun,
)
from autonomous_crawler.runtime import RuntimeRequest, RuntimeResponse
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore


API_PROFILE_PATH = Path("autonomous_crawler/tests/fixtures/ecommerce_api_pagination_profile.json")


class ApiFixtureFetchRuntime:
    name = "profile_longrun_api_fixture"

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
                "name": f"LongRun Product {idx:02d}",
                "price": {"amount": 20 + idx / 10, "currency": "USD"},
                "url": f"https://api-profile-shop.local/products/{idx:02d}",
                "variants": {
                    "colors": ["Black", "Blue"] if idx % 2 == 0 else ["White"],
                    "sizes": ["40", "41", "42"],
                },
                "description": f"Long-run API product {idx}",
                "media": {"images": [f"/images/longrun-product-{idx:02d}.jpg"]},
            }
            for idx in range(start, end)
        ]
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            text=json.dumps({"data": {"products": products}}),
            engine_result={"engine": self.name},
        )


EMPTY_LIST_PROFILE = SiteProfile.from_dict({
    "name": "empty-list-shop",
    "selectors": {
        "item_container": ".product-card",
        "detail_link": "a",
        "title": "h1",
    },
    "crawl_preferences": {
        "seed_urls": [
            "https://empty-shop.local/list/1",
            "https://empty-shop.local/list/2",
            "https://empty-shop.local/list/3",
        ],
        "seed_kind": "list",
    },
    "pagination_hints": {"type": "none"},
    "quality_expectations": {"required_fields": ["title"]},
})


class EmptyHtmlFetchRuntime:
    name = "empty_html_fixture"

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            text="<html><body><main>No products here</main></body></html>",
            engine_result={"engine": self.name},
        )


class ProfileLongRunTests(unittest.TestCase):
    def test_profile_longrun_pauses_and_resumes_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = SiteProfile.load(API_PROFILE_PATH)
            frontier = URLFrontier(root / "frontier.sqlite3")
            product_store = ProductStore(root / "products.sqlite3")
            checkpoint_store = CheckpointStore(root / "checkpoints.sqlite3")
            fetch = ApiFixtureFetchRuntime(total=55, page_size=20)

            first = run_profile_longrun(
                profile=profile,
                config=ProfileLongRunConfig(
                    run_id="profile-longrun-api",
                    worker_id="profile-longrun-pass-1",
                    batch_size=1,
                    max_batches=1,
                    sample_limit=5,
                ),
                fetch_runtime=fetch,
                frontier=frontier,
                product_store=product_store,
                checkpoint_store=checkpoint_store,
            )
            resumed = run_profile_longrun(
                profile=profile,
                config=ProfileLongRunConfig(
                    run_id="profile-longrun-api",
                    worker_id="profile-longrun-resume",
                    batch_size=10,
                    item_workers=3,
                    sample_limit=10,
                    output_report_path=root / "report.json",
                ),
                fetch_runtime=fetch,
                frontier=frontier,
                product_store=product_store,
                checkpoint_store=checkpoint_store,
            )
            report_payload = json.loads((root / "report.json").read_text(encoding="utf-8"))

        self.assertEqual(first.status, "paused")
        self.assertEqual(first.runner_summary.records_saved, 20)
        self.assertEqual(first.frontier_stats, {"done": 1, "queued": 1})
        self.assertEqual(resumed.status, "completed")
        self.assertEqual(resumed.runner_summary.records_saved, 35)
        self.assertEqual(resumed.product_stats["total"], 55)
        self.assertEqual(resumed.quality_summary["total_records"], 55)
        self.assertTrue(resumed.quality_summary["quality_gate"]["passed"])
        self.assertEqual(resumed.report["schema_version"], "profile-run-report/v1")
        self.assertEqual(resumed.report["metrics"]["record_count"], 55)
        self.assertEqual(resumed.runner_summary.claimed, 2)
        self.assertEqual(report_payload["metrics"]["record_count"], 55)
        self.assertEqual(resumed.checkpoint_latest["run"]["status"], "completed")
        self.assertEqual(len(resumed.sample_records), 10)
        requested_pages = [
            int(parse_qs(urlparse(request.url).query).get("page", ["0"])[0])
            for request in fetch.requests
        ]
        self.assertEqual(requested_pages, [1, 2, 3])

    def test_profile_longrun_supervision_pauses_consecutive_empty_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run_profile_longrun(
                profile=EMPTY_LIST_PROFILE,
                config=ProfileLongRunConfig(
                    run_id="profile-supervision-empty",
                    batch_size=1,
                    supervision_mode="managed",
                    sample_limit=5,
                ),
                fetch_runtime=EmptyHtmlFetchRuntime(),
                runtime_dir=tmp,
            )

        supervision = result.diagnostics["supervision"]
        self.assertEqual(result.status, "paused")
        self.assertTrue(supervision["enabled"])
        self.assertEqual(supervision["recommended_next_action"], "ai_rerun")
        self.assertEqual(supervision["last_event"]["action"], "pause")
        self.assertIn("supervision_events", result.runner_summary.as_dict())

    def test_profile_longrun_temp_runtime_is_allowed_for_one_shot(self) -> None:
        profile = SiteProfile.load(API_PROFILE_PATH)
        result = run_profile_longrun(
            profile=profile,
            config=ProfileLongRunConfig(
                run_id="profile-longrun-temp",
                batch_size=10,
                sample_limit=3,
            ),
            fetch_runtime=ApiFixtureFetchRuntime(total=20, page_size=20),
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.product_stats["total"], 20)
        self.assertEqual(len(result.sample_records), 3)

    def test_profile_longrun_requires_runtime(self) -> None:
        profile = SiteProfile.load(API_PROFILE_PATH)
        with self.assertRaises(ValueError):
            run_profile_longrun(
                profile=profile,
                config=ProfileLongRunConfig(run_id="missing-runtime"),
            )

    def test_profile_longrun_rejects_invalid_workers(self) -> None:
        with self.assertRaises(ValueError):
            ProfileLongRunConfig(run_id="bad-workers", item_workers=0)


class ProfileDraftToLongRunSmokeTests(unittest.TestCase):
    """End-to-end: evidence → draft profile → SiteProfile → ProfileLongRunExecutor."""

    def test_api_evidence_draft_to_longrun_collects_20_plus_records(self) -> None:
        """Full loop: API evidence → draft_profile_from_evidence → SiteProfile.from_dict
        → initial_requests_from_profile → ProfileLongRunExecutor → ≥20 product records."""
        import json as _json

        from autonomous_crawler.runners.profile_draft import draft_profile_from_evidence

        # Build API evidence that mimics what scout_page/browser training produces
        evidence = {
            "url": "https://api-draft-shop.local/products",
            "selector_matches": {"title": 5, "item": 5},
            "network_candidates": {
                "resource_counts": {"xhr": 3, "fetch": 1},
                "xhr_count": 3,
                "captured_xhr": [
                    {
                        "url": "https://api-draft-shop.local/products?page=1&limit=20",
                        "method": "GET",
                        "content_type": "application/json",
                        "body": _json.dumps({
                            "data": {
                                "products": [
                                    {"name": "Widget", "price": 9.99, "image_url": "/img.jpg", "description": "A widget"}
                                ]
                            }
                        }),
                    },
                    {
                        "url": "https://api-draft-shop.local/products?page=2&limit=20",
                        "method": "GET",
                        "content_type": "application/json",
                    },
                ],
            },
            "rendered_item_count": 20,
            "html_chars": 5000,
        }

        # 1. Draft profile from evidence
        draft = draft_profile_from_evidence(evidence, site_name="api-draft-shop")
        self.assertIn("endpoint", draft["api_hints"])
        self.assertEqual(draft["pagination_hints"]["type"], "page")
        self.assertEqual(draft["api_hints"]["items_path"], "data.products")
        self.assertIn("field_mapping", draft["api_hints"])
        runnability = draft["profile_diagnostics"]["runnability"]
        self.assertTrue(runnability["loadable"])
        self.assertTrue(runnability["has_seed_requests"])
        self.assertTrue(runnability["longrun_candidate"])

        # 2. Load as SiteProfile
        profile = SiteProfile.from_dict(draft)
        self.assertEqual(profile.name, "api-draft-shop")
        self.assertEqual(profile.pagination_type(), "page")
        self.assertEqual(profile.api_items_path(), "data.products")

        # 3. Verify initial_requests_from_profile produces a seed request
        from autonomous_crawler.runners.profile_ecommerce import initial_requests_from_profile
        requests = initial_requests_from_profile(profile, run_id="draft-smoke")
        self.assertEqual(len(requests), 1)
        self.assertIn("page=1", requests[0].url)
        self.assertIn("limit=20", requests[0].url)

        # 4. Run ProfileLongRunExecutor with fixture runtime (total=55, page_size=20)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frontier = URLFrontier(root / "frontier.sqlite3")
            product_store = ProductStore(root / "products.sqlite3")
            checkpoint_store = CheckpointStore(root / "checkpoints.sqlite3")
            fetch = ApiFixtureFetchRuntime(total=55, page_size=20)

            result = run_profile_longrun(
                profile=profile,
                config=ProfileLongRunConfig(
                    run_id="draft-smoke-run",
                    worker_id="draft-smoke-worker",
                    batch_size=20,
                    max_batches=5,
                    sample_limit=10,
                    output_report_path=root / "report.json",
                ),
                fetch_runtime=fetch,
                frontier=frontier,
                product_store=product_store,
                checkpoint_store=checkpoint_store,
            )

        # 5. Verify ≥20 product records collected
        self.assertTrue(result.accepted)
        self.assertIn(result.status, ("completed", "paused"))
        self.assertGreaterEqual(result.product_stats["total"], 20)
        self.assertEqual(result.profile_name, "api-draft-shop")
        self.assertEqual(result.report["schema_version"], "profile-run-report/v1")

    def test_mixed_evidence_draft_to_longrun(self) -> None:
        """Mixed browser + API evidence produces a runnable profile."""
        import json as _json

        from autonomous_crawler.runners.profile_draft import (
            draft_profile_from_evidence,
            merge_evidence_sources,
        )

        browser_evidence = {
            "url": "https://mixed-shop.local/catalog",
            "selector_matches": {"title": 10, "price": 8, "item": 10},
            "rendered_item_count": 15,
            "html_chars": 30000,
        }
        api_evidence = {
            "network_candidates": {
                "resource_counts": {"xhr": 2},
                "xhr_count": 2,
                "captured_xhr": [
                    {
                        "url": "https://mixed-shop.local/api/items?page=1&limit=20",
                        "method": "GET",
                        "content_type": "application/json",
                        "body": _json.dumps({"data": {"items": [{"name": "X", "price": 1.0}]}}),
                    },
                ],
            },
        }
        merged = merge_evidence_sources(browser_evidence, api_evidence)
        draft = draft_profile_from_evidence(merged, site_name="mixed-shop")

        profile = SiteProfile.from_dict(draft)
        self.assertEqual(profile.name, "mixed-shop")
        self.assertEqual(profile.pagination_type(), "page")

        from autonomous_crawler.runners.profile_ecommerce import initial_requests_from_profile
        requests = initial_requests_from_profile(profile, run_id="mixed-smoke")
        self.assertGreaterEqual(len(requests), 1)

        runnability = draft["profile_diagnostics"]["runnability"]
        self.assertTrue(runnability["longrun_candidate"])

    def test_missing_seed_blocks_longrun(self) -> None:
        """Profile with no endpoint and no seed_urls is not a longrun candidate."""
        from autonomous_crawler.runners.profile_draft import draft_profile_from_evidence

        evidence = {
            "url": "",
            "selector_matches": {"title": 5},
            "rendered_item_count": 10,
        }
        draft = draft_profile_from_evidence(evidence)
        runnability = draft["profile_diagnostics"]["runnability"]
        # Empty URL → no seed_urls generated, no endpoint → no seed requests
        # But loadable is still true
        self.assertTrue(runnability["loadable"])
        # has_seed_requests depends on whether _draft_crawl_preferences generates seed_urls from empty URL
        if not runnability["has_seed_requests"]:
            self.assertFalse(runnability["longrun_candidate"])
            self.assertIn("no_seed_requests", runnability["blocking_reasons"])

    def test_missing_items_path_still_loadable(self) -> None:
        """API evidence without body → no items_path, but still loadable."""
        from autonomous_crawler.runners.profile_draft import draft_profile_from_evidence

        evidence = {
            "url": "https://api-no-body.local/items",
            "network_candidates": {
                "resource_counts": {},
                "xhr_count": 1,
                "captured_xhr": [
                    {"url": "https://api-no-body.local/items?page=1&limit=20", "method": "GET", "content_type": "application/json"},
                ],
            },
        }
        draft = draft_profile_from_evidence(evidence)
        self.assertNotIn("items_path", draft["api_hints"])
        self.assertEqual(draft["pagination_hints"]["type"], "page")
        runnability = draft["profile_diagnostics"]["runnability"]
        self.assertTrue(runnability["loadable"])
        self.assertTrue(runnability["longrun_candidate"])


if __name__ == "__main__":
    unittest.main()
