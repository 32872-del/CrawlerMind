from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from autonomous_crawler.runners import (
    LangGraphBatchProcessor,
    SiteProfile,
    CrawlRequestEnvelope,
    SpiderRuntimeProcessor,
)
from autonomous_crawler.runtime import (
    RuntimeEvent,
    RuntimeRequest,
    RuntimeResponse,
    RuntimeSelectorRequest,
    RuntimeSelectorResult,
)
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.runners import BatchRunner, BatchRunnerConfig
from autonomous_crawler.tools.link_discovery import SitemapDiscoveryHelper, SitemapDiscoveryRule
from autonomous_crawler.tools.rate_limit_policy import RateLimitPolicy
from autonomous_crawler.tools.robots_policy import RobotsPolicyHelper


class FakeFetchRuntime:
    name = "fake_fetch"

    def __init__(self, response: RuntimeResponse | None = None, exc: Exception | None = None) -> None:
        self.response = response or RuntimeResponse(
            ok=True,
            final_url="https://example.com/page",
            status_code=200,
            html="<html><h1>Alpha</h1></html>",
            text="<html><h1>Alpha</h1></html>",
            runtime_events=[RuntimeEvent(type="fetch_complete")],
            engine_result={"engine": "fake_fetch"},
        )
        self.exc = exc
        self.requests: list[RuntimeRequest] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        return self.response


class FixtureFetchRuntime:
    name = "fixture_fetch"

    def __init__(self, fixtures: dict[str, RuntimeResponse]) -> None:
        self.fixtures = fixtures
        self.requests: list[RuntimeRequest] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        return self.fixtures.get(request.url) or RuntimeResponse.failure(
            final_url=request.url,
            status_code=404,
            error="missing fixture",
            engine=self.name,
        )


class FakeBrowserRuntime:
    name = "fake_browser"

    def __init__(self) -> None:
        self.requests: list[RuntimeRequest] = []

    def render(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            html="<main>Rendered</main>",
            engine_result={"engine": "fake_browser"},
        )


class FakeParser:
    name = "fake_parser"

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[RuntimeSelectorRequest], str]] = []

    def parse(
        self,
        html: str,
        selectors: list[RuntimeSelectorRequest],
        *,
        url: str = "",
    ) -> list[RuntimeSelectorResult]:
        self.calls.append((html, selectors, url))
        return [
            RuntimeSelectorResult(
                name=selector.name,
                selector=selector.selector,
                values=["Alpha"],
                matched=1,
            )
            for selector in selectors
        ]


class FakeLangGraph:
    def __init__(self, *, status: str = "completed", needs_retry: bool = False) -> None:
        self.status = status
        self.needs_retry = needs_retry
        self.states: list[dict[str, Any]] = []

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        self.states.append(state)
        if self.status != "completed":
            return {
                **state,
                "status": self.status,
                "error": "deterministic fake graph failure",
                "validation_result": {"is_valid": False, "needs_retry": self.needs_retry},
                "messages": ["fake graph failed"],
            }
        return {
            **state,
            "status": "completed",
            "task_id": "fake-langgraph-task",
            "extracted_data": {
                "items": [{
                    "title": f"Product from {state['target_url']}",
                    "price": "1.00",
                }],
                "confidence": 1.0,
            },
            "validation_result": {"is_valid": True, "needs_retry": False},
            "messages": ["fake graph completed"],
        }


class SpiderRuntimeProcessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CheckpointStore(Path(self.tmp.name) / "checkpoints.sqlite3")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_static_success_fetches_parses_discovers_and_checkpoints(self) -> None:
        fetch = FakeFetchRuntime()
        parser = FakeParser()

        def selector_builder(_request: CrawlRequestEnvelope, _item: dict[str, Any]) -> list[RuntimeSelectorRequest]:
            return [RuntimeSelectorRequest(name="title", selector="h1")]

        def record_builder(
            request: CrawlRequestEnvelope,
            response: RuntimeResponse,
            selector_results: list[Any],
        ) -> list[dict[str, Any]]:
            return [{
                "record_type": "page",
                "url": response.final_url or request.url,
                "title": selector_results[0].values[0],
                "dedupe_key": request.fingerprint,
            }]

        def link_builder(request: CrawlRequestEnvelope, _response: RuntimeResponse) -> list[CrawlRequestEnvelope]:
            return [
                CrawlRequestEnvelope(
                    run_id=request.run_id,
                    url="https://example.com/detail/1",
                    kind="detail",
                    priority=9,
                )
            ]

        processor = SpiderRuntimeProcessor(
            run_id="run-spider",
            fetch_runtime=fetch,
            parser=parser,
            checkpoint_store=self.store,
            selector_builder=selector_builder,
            record_builder=record_builder,
            link_builder=link_builder,
        )

        result = processor({
            "url": "https://example.com/page",
            "kind": "list",
            "payload": {"meta": {"trace": "yes"}},
        })

        latest = self.store.load_latest("run-spider")
        items = self.store.list_items("run-spider")

        self.assertTrue(result.ok)
        self.assertEqual(result.records[0]["title"], "Alpha")
        self.assertEqual(result.discovered_urls, ["https://example.com/detail/1"])
        self.assertEqual(result.discovered_kind, "detail")
        self.assertEqual(result.discovered_priority, 9)
        self.assertEqual(fetch.requests[0].meta["kind"], "list")
        self.assertEqual(parser.calls[0][1][0].name, "title")
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["item_count"], 1)
        self.assertEqual(items[0]["record"]["title"], "Alpha")

    def test_runtime_failure_maps_to_retryable_failure_bucket(self) -> None:
        response = RuntimeResponse(
            ok=False,
            final_url="https://example.com/blocked",
            status_code=429,
            error="rate limited",
            engine_result={
                "engine": "fake_fetch",
                "failure_classification": {"category": "http_blocked"},
            },
        )
        processor = SpiderRuntimeProcessor(
            run_id="run-failure",
            fetch_runtime=FakeFetchRuntime(response=response),
            checkpoint_store=self.store,
        )

        result = processor({
            "url": "https://example.com/blocked",
            "attempts": 1,
            "payload": {"max_retries": 3},
        })

        failures = self.store.list_failures("run-failure", bucket="http_blocked")

        self.assertFalse(result.ok)
        self.assertTrue(result.retry)
        self.assertEqual(result.metrics["failure_bucket"], "http_blocked")
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0]["retryable"])

    def test_runtime_exception_is_captured(self) -> None:
        processor = SpiderRuntimeProcessor(
            run_id="run-exception",
            fetch_runtime=FakeFetchRuntime(exc=RuntimeError("boom")),
            checkpoint_store=self.store,
        )

        result = processor({"url": "https://example.com/boom"})

        failures = self.store.list_failures("run-exception", bucket="runtime_exception")

        self.assertFalse(result.ok)
        self.assertTrue(result.retry)
        self.assertEqual(len(failures), 1)
        self.assertIn("boom", failures[0]["error"])

    def test_browser_mode_uses_browser_runtime(self) -> None:
        browser = FakeBrowserRuntime()
        processor = SpiderRuntimeProcessor(
            run_id="run-browser",
            browser_runtime=browser,
            mode="dynamic",
        )

        result = processor({"url": "https://example.com/app"})

        self.assertTrue(result.ok)
        self.assertEqual(browser.requests[0].mode, "dynamic")

    def test_requires_runtime_and_run_id(self) -> None:
        with self.assertRaises(ValueError):
            SpiderRuntimeProcessor(run_id="", fetch_runtime=FakeFetchRuntime())
        with self.assertRaises(ValueError):
            SpiderRuntimeProcessor(run_id="run")

    def test_sitemap_seeded_frontier_pause_resume_preserves_checkpoints(self) -> None:
        frontier = URLFrontier(Path(self.tmp.name) / "frontier.sqlite3")
        run_id = "run-sitemap-resume"
        sitemap_xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/products/a</loc></url>
          <url><loc>https://example.com/products/b</loc></url>
          <url><loc>https://other.test/products/offsite</loc></url>
        </urlset>
        """
        fixtures = {
            "https://example.com/sitemap.xml": RuntimeResponse(
                ok=True,
                final_url="https://example.com/sitemap.xml",
                status_code=200,
                text=sitemap_xml,
                engine_result={"engine": "fixture_fetch"},
            ),
            "https://example.com/products/a": RuntimeResponse(
                ok=True,
                final_url="https://example.com/products/a",
                status_code=200,
                html="<html><h1>A</h1></html>",
                engine_result={"engine": "fixture_fetch"},
            ),
            "https://example.com/products/b": RuntimeResponse(
                ok=True,
                final_url="https://example.com/products/b",
                status_code=200,
                html="<html><h1>B</h1></html>",
                engine_result={"engine": "fixture_fetch"},
            ),
        }

        frontier.add_urls(["https://example.com/sitemap.xml"], priority=10, kind="sitemap")
        self.store.start_run(run_id, {"fixture": "sitemap"})
        processor = SpiderRuntimeProcessor(
            run_id=run_id,
            fetch_runtime=FixtureFetchRuntime(fixtures),
            checkpoint_store=self.store,
            sitemap_helper=SitemapDiscoveryHelper(),
            sitemap_rule=SitemapDiscoveryRule(default_kind="detail", priority=8),
        )

        first = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id=run_id, batch_size=1, max_batches=1),
        ).run()
        self.store.mark_paused(run_id, "bounded sitemap pass")
        second = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id=run_id, batch_size=10),
        ).run()
        self.store.mark_completed(run_id)

        latest = self.store.load_latest(run_id)

        self.assertEqual(first.claimed, 1)
        self.assertEqual(first.discovered_urls, 2)
        self.assertEqual(second.claimed, 2)
        self.assertEqual(second.succeeded, 2)
        self.assertEqual(frontier.stats(), {"done": 3})
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest["run"]["status"], "completed")

    def test_robots_and_rate_limit_metadata_are_visible_in_processor_events(self) -> None:
        helper = RobotsPolicyHelper(
            mode="respect",
            fetcher=lambda _url: "User-agent: *\nCrawl-delay: 4\nRequest-rate: 2/8\n",
        )
        processor = SpiderRuntimeProcessor(
            run_id="run-robots-rate",
            fetch_runtime=FakeFetchRuntime(),
            checkpoint_store=self.store,
            robots_policy=helper,
            rate_limit_policy=RateLimitPolicy.from_dict({"default": {"delay_seconds": 1}}),
        )

        result = processor({"url": "https://example.com/page"})
        events = result.metrics["runtime_events"]
        rate_event = next(event for event in events if event["type"] == "spider.rate_limit_checked")

        self.assertTrue(result.ok)
        self.assertEqual(rate_event["data"]["delay_seconds"], 4.0)
        self.assertEqual(rate_event["data"]["metadata"]["robots_request_rate"], [2, 8])
        self.assertTrue(any(event["type"] == "spider.robots_checked" for event in events))

    def test_site_profile_round_trip_and_state_application(self) -> None:
        profile_path = Path(self.tmp.name) / "profiles" / "mock_catalog.json"
        profile = SiteProfile(
            name="mock-catalog",
            selectors={
                "item_container": ".product-card",
                "title": ".product-title",
                "price": ".product-price",
            },
            target_fields=["title", "price"],
            api_hints={"endpoint": "https://example.test/api/catalog"},
            pagination_hints={"type": "none"},
            access_config={"mode": "disabled"},
            rate_limits={"default": {"delay_seconds": 0}},
            quality_expectations={"min_items": 2},
            training_notes=["deterministic mock catalog"],
            constraints={"max_items": 2},
            crawl_preferences={"engine": "native"},
        )

        profile.save(profile_path)
        loaded = SiteProfile.load(profile_path)
        state = loaded.apply_to_state({
            "user_goal": "collect product titles and prices",
            "target_url": "https://example.test/catalog",
            "recon_report": {},
        })

        self.assertEqual(loaded.name, "mock-catalog")
        self.assertEqual(state["recon_report"]["target_fields"], ["title", "price"])
        self.assertEqual(state["recon_report"]["inferred_selectors"]["title"], ".product-title")
        self.assertEqual(state["recon_report"]["constraints"]["max_items"], 2)
        self.assertEqual(state["crawl_preferences"]["engine"], "native")

    def test_langgraph_batch_processor_profile_pause_resume(self) -> None:
        frontier = URLFrontier(Path(self.tmp.name) / "langgraph_frontier.sqlite3")
        profile_path = Path(self.tmp.name) / "profiles" / "mock_catalog.json"
        SiteProfile(
            name="mock-catalog",
            selectors={
                "item_container": ".product-card",
                "title": ".product-title",
                "price": ".product-price",
            },
            target_fields=["title", "price"],
            constraints={"max_items": 2},
        ).save(profile_path)
        frontier.add_urls(
            ["https://example.test/catalog", "https://example.test/catalog?page=2"],
            kind="langgraph",
        )

        graph = FakeLangGraph()
        processor = LangGraphBatchProcessor(
            user_goal="collect product titles and prices",
            profile_path=profile_path,
            max_retries=0,
            graph=graph,
        )
        first = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id="run-langgraph-profile", batch_size=1, max_batches=1),
        ).run()
        after_first_stats = frontier.stats()
        second = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id="run-langgraph-profile", batch_size=10),
        ).run()

        self.assertEqual(first.claimed, 1)
        self.assertEqual(first.succeeded, 1)
        self.assertEqual(first.records_saved, 0)
        self.assertEqual(after_first_stats.get("queued"), 1)
        self.assertEqual(second.claimed, 1)
        self.assertEqual(second.succeeded, 1)
        self.assertEqual(frontier.stats(), {"done": 2})
        self.assertEqual(len(graph.states), 2)
        self.assertEqual(graph.states[0]["recon_report"]["target_fields"], ["title", "price"])
        self.assertEqual(graph.states[0]["recon_report"]["inferred_selectors"]["title"], ".product-title")

    def test_langgraph_processor_failure_can_requeue(self) -> None:
        processor = LangGraphBatchProcessor(
            user_goal="collect product titles and prices",
            max_retries=2,
            graph=FakeLangGraph(status="retrying", needs_retry=True),
        )

        result = processor({
            "url": "https://example.test/failure",
            "attempts": 1,
            "payload": {"max_retries": 2},
        })

        self.assertFalse(result.ok)
        self.assertTrue(result.retry)
        self.assertIn("workflow_status", result.metrics)


if __name__ == "__main__":
    unittest.main()
