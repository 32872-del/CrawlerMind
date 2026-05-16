"""CLM-native spider request/result/summary models.

This module is SCRAPLING-ABSORB-3A.  It absorbs the useful spider request and
result-model ideas into CLM-owned data contracts without importing Scrapling.
The models are intentionally serializable, redaction-aware, and compatible
with the existing RuntimeRequest and BatchRunner boundaries.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from autonomous_crawler.runtime import RuntimeArtifact, RuntimeEvent, RuntimeRequest
from autonomous_crawler.tools.proxy_manager import redact_proxy_url
from autonomous_crawler.tools.proxy_trace import redact_error_message
from autonomous_crawler.tools.session_profile import redact_headers, redact_storage_state_path

from .batch_runner import ItemProcessResult


SPIDER_STATUSES = {"completed", "paused", "failed", "partial", "running"}
SPIDER_EVENT_TYPES = {
    "spider.run_started",
    "spider.batch_claimed",
    "spider.request_started",
    "spider.request_succeeded",
    "spider.request_failed",
    "spider.request_retried",
    "spider.request_skipped",
    "spider.links_discovered",
    "spider.robots_checked",
    "spider.checkpoint_saved",
    "spider.checkpoint_loaded",
    "spider.checkpoint_failed",
    "spider.run_paused",
    "spider.run_completed",
}


@dataclass(frozen=True)
class CrawlRequestEnvelope:
    """Serializable request envelope for long-running spider work."""

    run_id: str
    url: str
    request_id: str = ""
    method: str = "GET"
    priority: int = 0
    kind: str = "page"
    depth: int = 0
    parent_url: str = ""
    session_id: str = ""
    session_profile_id: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    data: Any = None
    json: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
    dont_filter: bool = False
    retry_count: int = 0
    max_retries: int = 3
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not str(self.run_id or "").strip():
            raise ValueError("run_id is required")
        if not str(self.url or "").strip():
            raise ValueError("url is required")

        method = str(self.method or "GET").upper()
        if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            method = "GET"
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "priority", int(self.priority or 0))
        object.__setattr__(self, "depth", max(0, int(self.depth or 0)))
        object.__setattr__(self, "retry_count", max(0, int(self.retry_count or 0)))
        object.__setattr__(self, "max_retries", max(0, int(self.max_retries or 0)))
        object.__setattr__(self, "headers", _string_dict(self.headers))
        object.__setattr__(self, "cookies", _string_dict(self.cookies))
        object.__setattr__(self, "params", _safe_dict(self.params))
        object.__setattr__(self, "meta", _safe_dict(self.meta))

        fingerprint = self.fingerprint or self.compute_fingerprint()
        object.__setattr__(self, "fingerprint", fingerprint)
        if not self.request_id:
            object.__setattr__(self, "request_id", fingerprint[:16])

    @classmethod
    def from_frontier_item(
        cls,
        item: dict[str, Any],
        *,
        run_id: str,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        session_profile_id: str = "",
    ) -> "CrawlRequestEnvelope":
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        return cls(
            run_id=run_id,
            url=str(item.get("url") or ""),
            request_id=str(payload.get("request_id") or ""),
            method=str(payload.get("method") or "GET"),
            priority=int(item.get("priority") or payload.get("priority") or 0),
            kind=str(item.get("kind") or payload.get("kind") or "page"),
            depth=int(item.get("depth") or payload.get("depth") or 0),
            parent_url=str(item.get("parent_url") or payload.get("parent_url") or ""),
            session_id=str(payload.get("session_id") or ""),
            session_profile_id=session_profile_id or str(payload.get("session_profile_id") or ""),
            headers=headers or _string_dict(payload.get("headers")),
            cookies=cookies or _string_dict(payload.get("cookies")),
            params=_safe_dict(payload.get("params")),
            data=payload.get("data"),
            json=payload.get("json"),
            meta=_safe_dict(payload.get("meta")),
            dont_filter=bool(payload.get("dont_filter", False)),
            retry_count=int(item.get("attempts") or payload.get("retry_count") or 0),
            max_retries=int(payload.get("max_retries") or 3),
            fingerprint=str(payload.get("fingerprint") or ""),
        )

    def canonical_url(self, *, keep_fragments: bool = False) -> str:
        return canonicalize_request_url(self.url, params=self.params, keep_fragments=keep_fragments)

    def compute_fingerprint(
        self,
        *,
        include_headers: bool = False,
        include_body: bool = True,
        keep_fragments: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "method": self.method.upper(),
            "url": self.canonical_url(keep_fragments=keep_fragments),
        }
        if include_body:
            payload["data"] = _stable_json_value(self.data)
            payload["json"] = _stable_json_value(self.json)
        if include_headers:
            payload["headers"] = {
                str(key).lower(): str(value)
                for key, value in sorted(self.headers.items(), key=lambda item: str(item[0]).lower())
            }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_runtime_request(self, *, mode: str = "static", timeout_ms: int = 30000) -> RuntimeRequest:
        proxy_config = {}
        proxy_url = str(self.meta.get("proxy") or self.meta.get("proxy_url") or "")
        if proxy_url:
            proxy_config["proxy"] = proxy_url
        session_profile = {
            "id": self.session_profile_id,
            "headers": dict(self.headers),
            "cookies": dict(self.cookies),
        }
        storage_state_path = str(self.meta.get("storage_state_path") or "")
        if storage_state_path:
            session_profile["storage_state_path"] = storage_state_path
        return RuntimeRequest.from_dict({
            "url": self.url,
            "method": self.method,
            "mode": mode,
            "headers": self.headers,
            "cookies": self.cookies,
            "params": self.params,
            "data": self.data,
            "json": self.json,
            "session_profile": session_profile,
            "proxy_config": proxy_config,
            "timeout_ms": timeout_ms,
            "meta": {
                **self.meta,
                "run_id": self.run_id,
                "request_id": self.request_id,
                "request_fingerprint": self.fingerprint,
                "kind": self.kind,
                "depth": self.depth,
            },
        })

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "url": self.url,
            "canonical_url": self.canonical_url(),
            "method": self.method,
            "priority": self.priority,
            "kind": self.kind,
            "depth": self.depth,
            "parent_url": self.parent_url,
            "session_id": self.session_id,
            "session_profile_id": self.session_profile_id,
            "headers": redact_headers(self.headers),
            "cookies": {key: "[redacted]" for key in self.cookies},
            "params": _redact_mapping(self.params),
            "data": _redact_value(self.data),
            "json": _redact_value(self.json),
            "meta": _redact_mapping(self.meta),
            "dont_filter": self.dont_filter,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "fingerprint": self.fingerprint,
        }


@dataclass
class CrawlItemResult:
    """Result for one spider request."""

    ok: bool
    request_id: str
    url: str
    status_code: int = 0
    records: list[Any] = field(default_factory=list)
    discovered_requests: list[CrawlRequestEnvelope] = field(default_factory=list)
    runtime_events: list[RuntimeEvent] = field(default_factory=list)
    artifacts: list[RuntimeArtifact] = field(default_factory=list)
    error: str = ""
    retry: bool = False
    failure_bucket: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        request: CrawlRequestEnvelope,
        *,
        status_code: int = 0,
        records: list[Any] | None = None,
        discovered_requests: list[CrawlRequestEnvelope] | None = None,
        runtime_events: list[RuntimeEvent] | None = None,
        artifacts: list[RuntimeArtifact] | None = None,
        **metrics: Any,
    ) -> "CrawlItemResult":
        return cls(
            ok=True,
            request_id=request.request_id,
            url=request.url,
            status_code=status_code,
            records=list(records or []),
            discovered_requests=list(discovered_requests or []),
            runtime_events=list(runtime_events or []),
            artifacts=list(artifacts or []),
            metrics=dict(metrics),
        )

    @classmethod
    def failure(
        cls,
        request: CrawlRequestEnvelope,
        *,
        error: str,
        status_code: int = 0,
        retry: bool = False,
        failure_bucket: str = "runtime_error",
        runtime_events: list[RuntimeEvent] | None = None,
        **metrics: Any,
    ) -> "CrawlItemResult":
        return cls(
            ok=False,
            request_id=request.request_id,
            url=request.url,
            status_code=status_code,
            error=redact_error_message(error),
            retry=retry,
            failure_bucket=failure_bucket,
            runtime_events=list(runtime_events or []),
            metrics=dict(metrics),
        )

    def to_item_process_result(self) -> ItemProcessResult:
        if not self.ok:
            return ItemProcessResult.failure(
                self.error,
                retry=self.retry,
                status_code=self.status_code,
                failure_bucket=self.failure_bucket,
                **self.metrics,
            )
        discovered_urls = [request.url for request in self.discovered_requests]
        discovered_kind = self.discovered_requests[0].kind if self.discovered_requests else "page"
        discovered_priority = self.discovered_requests[0].priority if self.discovered_requests else 0
        return ItemProcessResult(
            ok=True,
            records=list(self.records),
            discovered_urls=discovered_urls,
            discovered_kind=discovered_kind,
            discovered_priority=discovered_priority,
            metrics={
                **self.metrics,
                "status_code": self.status_code,
                "runtime_events": [event.to_dict() for event in self.runtime_events],
                "artifacts": [artifact.to_dict() for artifact in self.artifacts],
                "discovered_requests": [request.to_safe_dict() for request in self.discovered_requests],
            },
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "request_id": self.request_id,
            "url": self.url,
            "status_code": self.status_code,
            "record_count": len(self.records),
            "discovered_requests": [request.to_safe_dict() for request in self.discovered_requests],
            "runtime_events": [event.to_dict() for event in self.runtime_events],
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "error": redact_error_message(self.error),
            "retry": self.retry,
            "failure_bucket": self.failure_bucket,
            "metrics": _redact_mapping(self.metrics),
        }


@dataclass
class SpiderRunSummary:
    """Run-level spider metrics and event summary."""

    run_id: str
    status: str = "completed"
    batches: int = 0
    claimed: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    skipped: int = 0
    records_saved: int = 0
    discovered_urls: int = 0
    robots_disallowed: int = 0
    offsite_dropped: int = 0
    blocked_requests: int = 0
    checkpoint_writes: int = 0
    checkpoint_errors: int = 0
    response_status_count: dict[str, int] = field(default_factory=dict)
    failure_buckets: dict[str, int] = field(default_factory=dict)
    frontier_stats: dict[str, int] = field(default_factory=dict)
    events: list[RuntimeEvent] = field(default_factory=list)

    # Async/proxy/backpressure metrics (backward compatible — all default to 0)
    proxy_attempts_total: int = 0
    proxy_failures: int = 0
    proxy_successes: int = 0
    proxy_retries: int = 0
    backpressure_events: int = 0
    pool_acquired_events: int = 0
    pool_released_events: int = 0
    async_fetch_ok: int = 0
    async_fetch_fail: int = 0
    max_concurrency_per_domain: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.run_id or "").strip():
            raise ValueError("run_id is required")
        if self.status not in SPIDER_STATUSES:
            self.status = "completed"

    def record_item(self, result: CrawlItemResult) -> None:
        if result.ok:
            self.succeeded += 1
            self.records_saved += len(result.records)
            self.discovered_urls += len(result.discovered_requests)
        elif result.retry:
            self.retried += 1
        else:
            self.failed += 1
        if result.status_code:
            key = str(result.status_code)
            self.response_status_count[key] = self.response_status_count.get(key, 0) + 1
        if result.failure_bucket:
            self.failure_buckets[result.failure_bucket] = self.failure_buckets.get(result.failure_bucket, 0) + 1
        self.events.extend(result.runtime_events)
        # Aggregate async/proxy/backpressure metrics from runtime events
        self._aggregate_events(result.runtime_events, ok=result.ok)

    def add_event(self, event_type: str, message: str = "", **data: Any) -> None:
        self.events.append(RuntimeEvent(type=event_type, message=message, data=dict(data)))

    def _aggregate_events(self, events: list[RuntimeEvent], *, ok: bool) -> None:
        """Update async/proxy/backpressure counters from a list of events."""
        for event in events:
            if event.type == "proxy_attempt":
                self.proxy_attempts_total += 1
            elif event.type == "proxy_failure_recorded":
                self.proxy_failures += 1
            elif event.type == "proxy_success_recorded":
                self.proxy_successes += 1
            elif event.type == "proxy_retry":
                self.proxy_retries += 1
            elif event.type == "pool_backpressure":
                self.backpressure_events += 1
            elif event.type == "pool_acquired":
                self.pool_acquired_events += 1
                domain = event.data.get("domain", "")
                if domain:
                    active = event.data.get("active_per_domain", 0)
                    self.max_concurrency_per_domain[domain] = max(
                        self.max_concurrency_per_domain.get(domain, 0), active
                    )
            elif event.type == "pool_released":
                self.pool_released_events += 1
        if ok:
            self.async_fetch_ok += 1
        else:
            self.async_fetch_fail += 1

    def aggregate_async_metrics(self, responses: list[Any]) -> None:
        """Aggregate async/proxy/backpressure metrics from RuntimeResponse objects."""
        for resp in responses:
            events = getattr(resp, "runtime_events", []) or []
            for event in events:
                if event.type == "proxy_attempt":
                    self.proxy_attempts_total += 1
                elif event.type == "proxy_failure_recorded":
                    self.proxy_failures += 1
                elif event.type == "proxy_success_recorded":
                    self.proxy_successes += 1
                elif event.type == "proxy_retry":
                    self.proxy_retries += 1
                elif event.type == "pool_backpressure":
                    self.backpressure_events += 1
                elif event.type == "pool_acquired":
                    self.pool_acquired_events += 1
                    domain = event.data.get("domain", "")
                    if domain:
                        active = event.data.get("active_per_domain", 0)
                        self.max_concurrency_per_domain[domain] = max(
                            self.max_concurrency_per_domain.get(domain, 0), active
                        )
                elif event.type == "pool_released":
                    self.pool_released_events += 1

            ok = getattr(resp, "ok", False)
            if ok:
                self.async_fetch_ok += 1
            else:
                self.async_fetch_fail += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "batches": self.batches,
            "claimed": self.claimed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "retried": self.retried,
            "skipped": self.skipped,
            "records_saved": self.records_saved,
            "discovered_urls": self.discovered_urls,
            "robots_disallowed": self.robots_disallowed,
            "offsite_dropped": self.offsite_dropped,
            "blocked_requests": self.blocked_requests,
            "checkpoint_writes": self.checkpoint_writes,
            "checkpoint_errors": self.checkpoint_errors,
            "response_status_count": dict(self.response_status_count),
            "failure_buckets": dict(self.failure_buckets),
            "frontier_stats": dict(self.frontier_stats),
            "events": [event.to_dict() for event in self.events],
            "proxy_attempts_total": self.proxy_attempts_total,
            "proxy_failures": self.proxy_failures,
            "proxy_successes": self.proxy_successes,
            "proxy_retries": self.proxy_retries,
            "backpressure_events": self.backpressure_events,
            "pool_acquired_events": self.pool_acquired_events,
            "pool_released_events": self.pool_released_events,
            "async_fetch_ok": self.async_fetch_ok,
            "async_fetch_fail": self.async_fetch_fail,
            "max_concurrency_per_domain": dict(self.max_concurrency_per_domain),
        }


def make_spider_event(event_type: str, message: str = "", **data: Any) -> RuntimeEvent:
    """Create a spider RuntimeEvent with a stable type namespace."""
    safe_type = event_type if event_type in SPIDER_EVENT_TYPES else f"spider.{event_type.strip() or 'event'}"
    return RuntimeEvent(type=safe_type, message=message, data=dict(data))


def canonicalize_request_url(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    keep_fragments: bool = False,
) -> str:
    parsed = urlparse(str(url or "").strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    for key, value in sorted((params or {}).items(), key=lambda item: str(item[0])):
        if isinstance(value, (list, tuple)):
            query_pairs.extend((str(key), str(item)) for item in value)
        else:
            query_pairs.append((str(key), str(value)))
    query = urlencode(sorted(query_pairs), doseq=True)
    fragment = parsed.fragment if keep_fragments else ""
    return urlunparse((scheme, netloc, parsed.path or "/", "", query, fragment))


def _stable_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
    except TypeError:
        return str(value)


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items()}


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return _redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_error_message(value)
    return value


def _redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, val in value.items():
        lowered = str(key).lower()
        if lowered in {"authorization", "cookie", "x-api-key", "x-auth-token", "password", "token", "secret"}:
            result[str(key)] = "[redacted]"
        elif "proxy" in lowered and isinstance(val, str):
            result[str(key)] = redact_proxy_url(val)
        elif lowered == "storage_state_path" and isinstance(val, str):
            result[str(key)] = redact_storage_state_path(val)
        elif isinstance(val, dict):
            result[str(key)] = _redact_mapping(val)
        elif isinstance(val, list):
            result[str(key)] = [_redact_value(item) for item in val]
        elif isinstance(val, str):
            result[str(key)] = redact_error_message(val)
        else:
            result[str(key)] = val
    return result
