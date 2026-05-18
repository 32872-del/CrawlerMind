"""Profile-driven long-running ecommerce execution.

This module is the product-facing assembly layer for SCALE-RUNTIME-1.  It does
not add site rules.  It wires an explicit SiteProfile into the existing CLM
native execution stack:

SiteProfile -> URLFrontier -> BatchRunner -> SpiderRuntimeProcessor ->
ProductStore -> CheckpointStore -> profile-run-report/v1
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.runtime import BrowserRuntime, FetchRuntime, NativeParserRuntime, ParserRuntime
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore

from .batch_runner import BatchRunner, BatchRunnerConfig, BatchRunnerSummary, ProductRecordCheckpoint
from .multi_site_runner import MultiSiteRunner, MultiSiteRunnerConfig, MultiSiteRunSummary
from .profile_ecommerce import (
    infer_pagination_stop_reason,
    initial_requests_from_profile,
    make_ecommerce_profile_callbacks,
    profile_quality_summary,
)
from .profile_report import build_profile_run_report
from .site_profile import SiteProfile
from .spider_models import CrawlRequestEnvelope, SpiderRunSummary, make_spider_event
from .spider_runner import SpiderRuntimeProcessor


@dataclass(frozen=True)
class ProfileLongRunConfig:
    """Configuration for a profile-driven long-running crawl."""

    run_id: str
    worker_id: str = "profile-longrun"
    batch_size: int = 20
    max_batches: int = 0
    lease_seconds: int = 300
    retry_failed: bool = False
    mode: str = "static"
    timeout_ms: int = 30000
    item_workers: int = 1
    category: str = ""
    sample_limit: int = 20
    output_report_path: str = ""

    def __post_init__(self) -> None:
        if not str(self.run_id or "").strip():
            raise ValueError("run_id is required")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_batches < 0:
            raise ValueError("max_batches must be >= 0")
        if self.lease_seconds < 0:
            raise ValueError("lease_seconds must be >= 0")
        if self.sample_limit < 0:
            raise ValueError("sample_limit must be >= 0")
        if self.item_workers < 1:
            raise ValueError("item_workers must be >= 1")


@dataclass
class ProfileLongRunResult:
    """Serializable result for a profile long-run pass."""

    accepted: bool
    run_id: str
    profile_name: str
    status: str
    runner_summary: BatchRunnerSummary
    frontier_stats: dict[str, int]
    product_stats: dict[str, Any]
    quality_summary: dict[str, Any]
    report: dict[str, Any]
    checkpoint_latest: dict[str, Any] | None = None
    sample_records: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "run_id": self.run_id,
            "profile_name": self.profile_name,
            "status": self.status,
            "runner_summary": self.runner_summary.as_dict(),
            "frontier_stats": dict(self.frontier_stats),
            "product_stats": dict(self.product_stats),
            "quality_summary": dict(self.quality_summary),
            "checkpoint_latest": self.checkpoint_latest,
            "sample_records": list(self.sample_records),
            "failures": list(self.failures),
            "report": dict(self.report),
        }


class ProfileLongRunExecutor:
    """Reusable executor for profile-driven ecommerce long runs."""

    def __init__(
        self,
        *,
        profile: SiteProfile,
        fetch_runtime: FetchRuntime | None = None,
        browser_runtime: BrowserRuntime | None = None,
        parser: ParserRuntime | None = None,
        frontier: URLFrontier | None = None,
        product_store: ProductStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        runtime_dir: str | Path | None = None,
    ) -> None:
        if fetch_runtime is None and browser_runtime is None:
            raise ValueError("fetch_runtime or browser_runtime is required")
        self.profile = profile
        self.fetch_runtime = fetch_runtime
        self.browser_runtime = browser_runtime
        self.parser = parser or NativeParserRuntime()
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        root: Path | None = None
        if runtime_dir or frontier is None or product_store is None or checkpoint_store is None:
            root = Path(runtime_dir) if runtime_dir else self._make_temp_dir()
            root.mkdir(parents=True, exist_ok=True)
        self.frontier = frontier or URLFrontier(root / "frontier.sqlite3")  # type: ignore[operator]
        self.product_store = product_store or ProductStore(root / "products.sqlite3")  # type: ignore[operator]
        self.checkpoint_store = checkpoint_store or CheckpointStore(root / "checkpoints.sqlite3")  # type: ignore[operator]

    def close(self) -> None:
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def run(self, config: ProfileLongRunConfig) -> ProfileLongRunResult:
        self.checkpoint_store.start_run(config.run_id, {"profile": self.profile.to_dict()})
        self.seed_frontier(config)

        callbacks = make_ecommerce_profile_callbacks(self.profile, run_id=config.run_id)
        processor = SpiderRuntimeProcessor(
            run_id=config.run_id,
            fetch_runtime=self.fetch_runtime,
            browser_runtime=self.browser_runtime,
            parser=self.parser,
            checkpoint_store=self.checkpoint_store,
            mode=config.mode,
            timeout_ms=config.timeout_ms,
            selector_builder=callbacks.selector_builder,
            record_builder=callbacks.record_builder,
            link_builder=callbacks.link_builder,
        )
        runner_summary = BatchRunner(
            frontier=self.frontier,
            processor=processor,
            config=BatchRunnerConfig(
                run_id=config.run_id,
                worker_id=config.worker_id,
                batch_size=config.batch_size,
                max_batches=config.max_batches,
                lease_seconds=config.lease_seconds,
                retry_failed=config.retry_failed,
                item_workers=config.item_workers,
            ),
            checkpoint=ProductRecordCheckpoint(self.product_store),
        ).run()

        frontier_stats = self.frontier.stats()
        status = run_status_from_frontier(frontier_stats, runner_summary)
        self._save_batch_checkpoint(config, runner_summary, status=status)
        if status == "completed":
            self.checkpoint_store.mark_completed(config.run_id)
        elif status == "paused":
            self.checkpoint_store.mark_paused(config.run_id, "bounded profile long-run pass")

        records = self.product_store.list_records(config.run_id, limit=max(config.sample_limit, 1))
        failures = self.checkpoint_store.list_failures(config.run_id)
        quality_summary = profile_quality_summary(
            self.product_store.list_records(config.run_id, limit=10000),
            failed_urls=[str(item.get("url") or "") for item in failures if item.get("url")],
            pagination_stop_reason=infer_stop_reason(self.profile, frontier_stats, runner_summary),
            frontier_stats=frontier_stats,
            quality_policy=self.profile.quality_expectations,
        )
        sample_records = [product_record_sample(record) for record in records[: config.sample_limit or 0]]
        report = build_profile_run_report(
            profile_name=self.profile.name,
            run_id=config.run_id,
            runner_summary=runner_summary,
            quality_summary=quality_summary,
            sample_records=sample_records,
            failures=failures,
            runtime_backend=runtime_backend_name(self.fetch_runtime, self.browser_runtime, config.mode),
            parser_backend=getattr(self.parser, "name", type(self.parser).__name__),
            stop_reason=quality_summary.get("pagination_stop_reason", ""),
            target=first_seed_url(self.profile),
        )
        if config.output_report_path:
            write_report(config.output_report_path, report)
        return ProfileLongRunResult(
            accepted=is_accepted_profile_run(status, quality_summary, self.product_store.get_run_stats(config.run_id)),
            run_id=config.run_id,
            profile_name=self.profile.name,
            status=status,
            runner_summary=runner_summary,
            frontier_stats=frontier_stats,
            product_stats=self.product_store.get_run_stats(config.run_id),
            quality_summary=quality_summary,
            report=report,
            checkpoint_latest=self.checkpoint_store.load_latest(config.run_id),
            sample_records=sample_records,
            failures=failures,
        )

    def seed_frontier(self, config: ProfileLongRunConfig) -> dict[str, int]:
        requests = initial_requests_from_profile(
            self.profile,
            run_id=config.run_id,
            category=config.category,
        )
        totals = {"added": 0, "skipped": 0, "invalid": 0}
        for request in requests:
            added = self.frontier.add_urls(
                [request.url],
                priority=request.priority,
                kind=request.kind,
                depth=request.depth,
                parent_url=request.parent_url,
                payload=frontier_payload_from_request(request),
            )
            for key in totals:
                totals[key] += int(added.get(key, 0))
        return totals

    def _save_batch_checkpoint(
        self,
        config: ProfileLongRunConfig,
        summary: BatchRunnerSummary,
        *,
        status: str,
    ) -> None:
        spider_summary = SpiderRunSummary(
            run_id=config.run_id,
            status=status,
            batches=summary.batches,
            claimed=summary.claimed,
            succeeded=summary.succeeded,
            failed=summary.failed,
            retried=summary.retried,
            records_saved=summary.records_saved,
            discovered_urls=summary.discovered_urls,
            checkpoint_errors=summary.checkpoint_errors,
            frontier_stats=dict(summary.frontier_stats),
        )
        self.checkpoint_store.save_batch_checkpoint(
            run_id=config.run_id,
            batch_id=f"{config.worker_id}-pass-{summary.batches}",
            frontier_items=[],
            summary=spider_summary,
            events=[
                make_spider_event(
                    "checkpoint_saved",
                    "profile long-run checkpoint saved",
                    worker_id=config.worker_id,
                    status=status,
                    claimed=summary.claimed,
                    records_saved=summary.records_saved,
                )
            ],
        )

    def _make_temp_dir(self) -> Path:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="clm_profile_longrun_")
        return Path(self._temp_dir.name)


def run_profile_longrun(
    *,
    profile: SiteProfile,
    config: ProfileLongRunConfig,
    fetch_runtime: FetchRuntime | None = None,
    browser_runtime: BrowserRuntime | None = None,
    parser: ParserRuntime | None = None,
    frontier: URLFrontier | None = None,
    product_store: ProductStore | None = None,
    checkpoint_store: CheckpointStore | None = None,
    runtime_dir: str | Path | None = None,
) -> ProfileLongRunResult:
    executor = ProfileLongRunExecutor(
        profile=profile,
        fetch_runtime=fetch_runtime,
        browser_runtime=browser_runtime,
        parser=parser,
        frontier=frontier,
        product_store=product_store,
        checkpoint_store=checkpoint_store,
        runtime_dir=runtime_dir,
    )
    try:
        return executor.run(config)
    finally:
        if runtime_dir is None and frontier is None and product_store is None and checkpoint_store is None:
            executor.close()


def run_multi_profile_longrun(
    jobs: dict[str, dict[str, Any]],
    *,
    max_sites: int = 5,
    fetch_runtime_factory: Any = None,
    parser_factory: Any = None,
) -> MultiSiteRunSummary:
    """Run up to five profile long-runs concurrently.

    Each job payload accepts:
    - profile or profile_path
    - config or ProfileLongRunConfig kwargs
    - runtime_dir

    Runtime instances are created per site by default so HTTP sessions,
    cookies, and future browser contexts do not leak across domains.
    """
    if fetch_runtime_factory is None:
        from autonomous_crawler.runtime import NativeFetchRuntime

        def fetch_runtime_factory() -> NativeFetchRuntime:
            return NativeFetchRuntime(reuse_httpx_client=True)

    def make_job(name: str, payload: dict[str, Any]):
        def _run() -> dict[str, Any]:
            profile = _profile_from_job_payload(payload)
            config = _config_from_job_payload(name, payload)
            fetch_runtime = fetch_runtime_factory()
            parser = parser_factory() if parser_factory is not None else None
            try:
                result = run_profile_longrun(
                    profile=profile,
                    config=config,
                    fetch_runtime=fetch_runtime,
                    parser=parser,
                    runtime_dir=payload.get("runtime_dir") or None,
                )
                return result.to_dict()
            finally:
                close = getattr(fetch_runtime, "close", None)
                if callable(close):
                    close()

        return _run

    site_jobs = {str(name): make_job(str(name), dict(payload or {})) for name, payload in jobs.items()}
    return MultiSiteRunner(site_jobs, MultiSiteRunnerConfig(max_sites=max_sites)).run()


def _profile_from_job_payload(payload: dict[str, Any]) -> SiteProfile:
    profile_payload = payload.get("profile")
    if profile_payload is not None:
        if isinstance(profile_payload, SiteProfile):
            return profile_payload
        if isinstance(profile_payload, dict):
            return SiteProfile.from_dict(profile_payload)
        raise ValueError("profile must be a SiteProfile or dict")
    profile_path = str(payload.get("profile_path") or "").strip()
    if profile_path:
        return SiteProfile.load(profile_path)
    raise ValueError("profile or profile_path is required")


def _config_from_job_payload(name: str, payload: dict[str, Any]) -> ProfileLongRunConfig:
    raw = payload.get("config")
    if isinstance(raw, ProfileLongRunConfig):
        return raw
    config_payload = dict(raw or {})
    for key in (
        "run_id",
        "worker_id",
        "batch_size",
        "max_batches",
        "lease_seconds",
        "retry_failed",
        "mode",
        "timeout_ms",
        "item_workers",
        "category",
        "sample_limit",
        "output_report_path",
    ):
        if key in payload and key not in config_payload:
            config_payload[key] = payload[key]
    if not str(config_payload.get("run_id") or "").strip():
        config_payload["run_id"] = f"profile-{name}"
    if not str(config_payload.get("worker_id") or "").strip():
        config_payload["worker_id"] = f"multi-profile-{name}"
    return ProfileLongRunConfig(**config_payload)


def frontier_payload_from_request(request: CrawlRequestEnvelope) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "method": request.method,
        "priority": request.priority,
        "kind": request.kind,
        "depth": request.depth,
        "parent_url": request.parent_url,
        "session_id": request.session_id,
        "session_profile_id": request.session_profile_id,
        "headers": dict(request.headers),
        "cookies": dict(request.cookies),
        "params": dict(request.params),
        "data": request.data,
        "json": request.json,
        "meta": dict(request.meta),
        "dont_filter": request.dont_filter,
        "retry_count": request.retry_count,
        "max_retries": request.max_retries,
        "fingerprint": request.fingerprint,
    }


def run_status_from_frontier(
    frontier_stats: dict[str, int],
    summary: BatchRunnerSummary,
) -> str:
    if frontier_stats.get("queued") or frontier_stats.get("running"):
        return "paused"
    if summary.failed or frontier_stats.get("failed"):
        return "partial"
    return "completed"


def infer_stop_reason(
    profile: SiteProfile,
    frontier_stats: dict[str, int],
    summary: BatchRunnerSummary,
) -> str:
    if frontier_stats.get("queued") or frontier_stats.get("running"):
        return "bounded_pass_paused"
    if frontier_stats.get("failed"):
        return "frontier_failed_items"
    if summary.discovered_urls:
        return "frontier_exhausted"
    return infer_pagination_stop_reason(profile, last_item_count=summary.records_saved, next_request_count=0)


def product_record_sample(record: ProductRecord) -> dict[str, Any]:
    return {
        "title": record.title,
        "highest_price": record.highest_price,
        "currency": record.currency,
        "colors": list(record.colors),
        "sizes": list(record.sizes),
        "description": record.description,
        "image_urls": list(record.image_urls),
        "category": record.category,
        "canonical_url": record.canonical_url,
        "dedupe_key": record.dedupe_key,
    }


def runtime_backend_name(
    fetch_runtime: FetchRuntime | None,
    browser_runtime: BrowserRuntime | None,
    mode: str,
) -> str:
    if str(mode or "").lower() in {"dynamic", "protected"} and browser_runtime is not None:
        return getattr(browser_runtime, "name", type(browser_runtime).__name__)
    if fetch_runtime is not None:
        return getattr(fetch_runtime, "name", type(fetch_runtime).__name__)
    if browser_runtime is not None:
        return getattr(browser_runtime, "name", type(browser_runtime).__name__)
    return ""


def is_accepted_profile_run(
    status: str,
    quality_summary: dict[str, Any],
    product_stats: dict[str, Any],
) -> bool:
    if status == "failed":
        return False
    if int(product_stats.get("total") or 0) <= 0:
        return False
    gate = quality_summary.get("quality_gate") if isinstance(quality_summary.get("quality_gate"), dict) else {}
    return not bool(gate.get("should_fail"))


def first_seed_url(profile: SiteProfile) -> str:
    endpoint = str(profile.api_hints.get("endpoint") or "").strip()
    if endpoint:
        return endpoint
    seed_urls = profile.crawl_preferences.get("seed_urls") or profile.constraints.get("seed_urls") or []
    return str(seed_urls[0]) if seed_urls else ""


def write_report(path: str | Path, report: dict[str, Any]) -> None:
    import json

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
