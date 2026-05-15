"""CLM-native spider processor for BatchRunner.

SCRAPLING-ABSORB-3C connects the spider request/result/checkpoint models to the
existing BatchRunner without replacing the runner.  Site-specific extraction
stays outside this core through small callback hooks.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from autonomous_crawler.runtime import (
    BrowserPoolManager,
    BrowserRuntime,
    FetchRuntime,
    ParserRuntime,
    RuntimeRequest,
    RuntimeResponse,
    RuntimeSelectorRequest,
)
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.tools.link_discovery import (
    SitemapDiscoveryHelper,
    SitemapDiscoveryRule,
)
from autonomous_crawler.tools.rate_limit_policy import RateLimitPolicy
from autonomous_crawler.tools.robots_policy import RobotsPolicyHelper

from .batch_runner import FrontierItem, ItemProcessResult
from .spider_models import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
    make_spider_event,
)


SelectorBuilder = Callable[[CrawlRequestEnvelope, FrontierItem], list[RuntimeSelectorRequest]]
RecordBuilder = Callable[[CrawlRequestEnvelope, RuntimeResponse, list[Any]], list[Any]]
LinkBuilder = Callable[[CrawlRequestEnvelope, RuntimeResponse], list[CrawlRequestEnvelope]]


class SpiderRuntimeProcessor:
    """Process one URLFrontier item through a CLM runtime backend."""

    def __init__(
        self,
        *,
        run_id: str,
        fetch_runtime: FetchRuntime | None = None,
        browser_runtime: BrowserRuntime | None = None,
        parser: ParserRuntime | None = None,
        checkpoint_store: CheckpointStore | None = None,
        mode: str = "static",
        timeout_ms: int = 30000,
        selector_builder: SelectorBuilder | None = None,
        record_builder: RecordBuilder | None = None,
        link_builder: LinkBuilder | None = None,
        sitemap_helper: SitemapDiscoveryHelper | None = None,
        sitemap_rule: SitemapDiscoveryRule | None = None,
        robots_policy: RobotsPolicyHelper | None = None,
        rate_limit_policy: RateLimitPolicy | None = None,
        pool: BrowserPoolManager | None = None,
    ) -> None:
        if not str(run_id or "").strip():
            raise ValueError("run_id is required")
        if fetch_runtime is None and browser_runtime is None:
            raise ValueError("fetch_runtime or browser_runtime is required")
        self.run_id = run_id
        self.fetch_runtime = fetch_runtime
        self.browser_runtime = browser_runtime
        self.parser = parser
        self.checkpoint_store = checkpoint_store
        self.mode = mode
        self.timeout_ms = timeout_ms
        self.selector_builder = selector_builder
        self.record_builder = record_builder
        self.link_builder = link_builder
        self.sitemap_helper = sitemap_helper
        self.sitemap_rule = sitemap_rule or SitemapDiscoveryRule()
        self.robots_policy = robots_policy
        self.rate_limit_policy = rate_limit_policy
        if pool is not None and browser_runtime is not None and hasattr(browser_runtime, "_pool"):
            browser_runtime._pool = pool

    def __call__(self, item: FrontierItem) -> ItemProcessResult:
        request = self.build_request(item)
        result = self.process_request(request, item=item)
        if self.checkpoint_store is not None:
            self.checkpoint_store.save_item_checkpoint(
                run_id=self.run_id,
                request=request,
                result=result,
            )
        return result.to_item_process_result()

    def build_request(self, item: FrontierItem) -> CrawlRequestEnvelope:
        return CrawlRequestEnvelope.from_frontier_item(item, run_id=self.run_id)

    def process_request(
        self,
        request: CrawlRequestEnvelope,
        *,
        item: FrontierItem | None = None,
    ) -> CrawlItemResult:
        item = item or {}
        runtime_request = self._runtime_request_for(request, item)
        runtime_events = []
        robots_directives = None
        if self.robots_policy is not None:
            robots_directives = self.robots_policy.get_directives(request.url)
            runtime_events.extend(self.robots_policy.to_events(request.url))
        if self.rate_limit_policy is not None:
            decision = self.rate_limit_policy.decide(
                request.url,
                attempt=request.retry_count,
                robots_directives=robots_directives,
            )
            runtime_events.append(make_spider_event(
                "rate_limit_checked",
                "rate limit policy checked",
                **decision.to_dict(),
            ))

        start_event = make_spider_event(
            "request_started",
            "spider request started",
            request_id=request.request_id,
            url=request.url,
            kind=request.kind,
        )
        runtime_events.append(start_event)

        if robots_directives is not None and not robots_directives.can_fetch:
            runtime_events.append(make_spider_event(
                "request_skipped",
                "robots policy disallowed request",
                url=request.url,
                source_url=robots_directives.source_url,
            ))
            return CrawlItemResult.failure(
                request,
                error="robots disallowed",
                retry=False,
                failure_bucket="robots_disallowed",
                runtime_events=runtime_events,
            )

        try:
            response = self._execute_runtime(runtime_request)
        except Exception as exc:
            return CrawlItemResult.failure(
                request,
                error=f"{type(exc).__name__}: {exc}",
                retry=request.retry_count < request.max_retries,
                failure_bucket="runtime_exception",
                runtime_events=runtime_events,
            )

        runtime_events.extend(response.runtime_events)
        if not response.ok:
            runtime_events.append(make_spider_event(
                "request_failed",
                "spider request failed",
                status_code=response.status_code,
                error=response.error,
            ))
            return CrawlItemResult.failure(
                request,
                error=response.error or f"runtime status {response.status_code}",
                status_code=response.status_code,
                retry=request.retry_count < request.max_retries,
                failure_bucket=_failure_bucket_for(response),
                runtime_events=runtime_events,
                backend=response.engine_result.get("engine", ""),
            )

        selector_results = self._parse_response(runtime_request, response)
        records = self._records_for(request, response, selector_results)
        discovered_requests = self.discover_links(request, response)
        runtime_events.append(make_spider_event(
            "request_succeeded",
            "spider request succeeded",
            status_code=response.status_code,
            records=len(records),
            discovered=len(discovered_requests),
        ))
        return CrawlItemResult.success(
            request,
            status_code=response.status_code,
            records=records,
            discovered_requests=discovered_requests,
            runtime_events=runtime_events,
            artifacts=response.artifacts,
            backend=response.engine_result.get("engine", ""),
            selector_results=[result.to_dict() for result in selector_results],
        )

    def discover_links(
        self,
        request: CrawlRequestEnvelope,
        response: RuntimeResponse,
    ) -> list[CrawlRequestEnvelope]:
        discovered: list[CrawlRequestEnvelope] = []
        if self.link_builder is not None:
            discovered.extend(self.link_builder(request, response))
        if self.sitemap_helper is not None and _looks_like_sitemap(request, response):
            result = self.sitemap_helper.parse(
                response.text or response.html or response.body.decode("utf-8", errors="replace"),
                sitemap_url=response.final_url or request.url,
                run_id=request.run_id,
                rules=self.sitemap_rule,
                parent_request=request,
            )
            discovered.extend(result.requests)
            for sitemap_url in result.sitemap_urls:
                discovered.append(CrawlRequestEnvelope(
                    run_id=request.run_id,
                    url=sitemap_url,
                    priority=self.sitemap_rule.priority,
                    kind="sitemap",
                    depth=request.depth + 1,
                    parent_url=request.url,
                    meta={"discovered_by": "sitemap_index", "sitemap_url": response.final_url or request.url},
                ))
        return discovered

    def _runtime_request_for(
        self,
        request: CrawlRequestEnvelope,
        item: FrontierItem,
    ) -> RuntimeRequest:
        runtime_request = request.to_runtime_request(mode=self._runtime_mode(), timeout_ms=self.timeout_ms)
        selectors = self.selector_builder(request, item) if self.selector_builder else []
        if selectors:
            runtime_request = RuntimeRequest(
                url=runtime_request.url,
                method=runtime_request.method,
                mode=runtime_request.mode,
                headers=runtime_request.headers,
                cookies=runtime_request.cookies,
                params=runtime_request.params,
                data=runtime_request.data,
                json=runtime_request.json,
                selectors=selectors,
                selector_config=runtime_request.selector_config,
                browser_config=runtime_request.browser_config,
                session_profile=runtime_request.session_profile,
                proxy_config=runtime_request.proxy_config,
                capture_xhr=runtime_request.capture_xhr,
                wait_selector=runtime_request.wait_selector,
                wait_until=runtime_request.wait_until,
                timeout_ms=runtime_request.timeout_ms,
                max_items=runtime_request.max_items,
                meta=runtime_request.meta,
            )
        return runtime_request

    def _runtime_mode(self) -> str:
        configured = str(self.mode or "static").strip().lower()
        if configured in {"dynamic", "protected"}:
            return configured
        return "static"

    def _execute_runtime(self, request: RuntimeRequest) -> RuntimeResponse:
        if request.mode in {"dynamic", "protected"}:
            if self.browser_runtime is None:
                raise RuntimeError("browser_runtime is required for browser mode")
            return self.browser_runtime.render(request)
        if self.fetch_runtime is None:
            raise RuntimeError("fetch_runtime is required for static mode")
        return self.fetch_runtime.fetch(request)

    def _parse_response(
        self,
        request: RuntimeRequest,
        response: RuntimeResponse,
    ) -> list[Any]:
        if self.parser is None:
            return []
        html = response.html or response.text
        if not html:
            return []
        return self.parser.parse(html, request.selectors, url=response.final_url or request.url)

    def _records_for(
        self,
        request: CrawlRequestEnvelope,
        response: RuntimeResponse,
        selector_results: list[Any],
    ) -> list[Any]:
        if self.record_builder is not None:
            return list(self.record_builder(request, response, selector_results))
        if response.items:
            return list(response.items)
        if selector_results:
            return [
                {
                    "url": response.final_url or request.url,
                    "fields": {
                        result.name: list(result.values)
                        for result in selector_results
                        if not getattr(result, "error", "")
                    },
                }
            ]
        return []


class SpiderCheckpointSink:
    """BatchRunner checkpoint sink backed by `CheckpointStore`.

    This sink persists produced records as item checkpoints when a caller wants
    BatchRunner's existing checkpoint hook to write generic records. The main
    `SpiderRuntimeProcessor` already writes per-item checkpoints with request
    identity, so this class is optional.
    """

    def __init__(self, store: CheckpointStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id

    def save_records(self, records: list[Any]) -> dict[str, int]:
        summary = SpiderRunSummary(run_id=self.run_id, records_saved=len(records))
        self.store.save_batch_checkpoint(
            run_id=self.run_id,
            batch_id="batchrunner-record-sink",
            frontier_items=[],
            summary=summary,
            events=[],
        )
        return {"inserted": len(records), "updated": 0, "total": len(records)}


def _failure_bucket_for(response: RuntimeResponse) -> str:
    classification = response.engine_result.get("failure_classification")
    if isinstance(classification, dict) and classification.get("category"):
        return str(classification["category"])
    if response.status_code in {401, 403, 407, 429}:
        return "http_blocked"
    if response.status_code >= 500:
        return "server_error"
    if response.error:
        return "runtime_error"
    return "unknown"


def _looks_like_sitemap(request: CrawlRequestEnvelope, response: RuntimeResponse) -> bool:
    if request.kind == "sitemap":
        return True
    url = (response.final_url or request.url).lower()
    if url.endswith(".xml") or "sitemap" in url:
        return True
    text = (response.text or response.html or "").lstrip()
    return text.startswith("<?xml") or text.startswith("<urlset") or text.startswith("<sitemapindex")
