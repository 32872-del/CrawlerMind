"""API / GraphQL / Reverse Evidence Trainer — SCRAPLING-HARDEN-4.

Training runner that exercises CLM's GraphQL, API pagination, and reverse
evidence capabilities through deterministic mock fixtures.  Integrates
async/backpressure/proxy metrics from SpiderRunSummary.

Usage:
    python run_api_graphql_training_2026_05_15.py
    python run_api_graphql_training_2026_05_15.py --output dev_logs/training/

All requests are mocked — no public network required.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.runtime.native_async import (
    AsyncFetchMetrics,
    NativeAsyncFetchRuntime,
)
from autonomous_crawler.runtime.models import RuntimeRequest, RuntimeResponse
from autonomous_crawler.runners.spider_models import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
)
from autonomous_crawler.tools.api_candidates import (
    PaginatedResult,
    PaginationSpec,
    build_graphql_candidate,
    build_graphql_cursor_query,
    build_graphql_nested_fields_query,
    extract_records_from_json,
    fetch_graphql_api,
    fetch_json_api,
    fetch_paginated_api,
    normalize_api_records,
)
from autonomous_crawler.tools.js_crypto_analysis import analyze_js_crypto
from autonomous_crawler.tools.strategy_evidence import (
    StrategyEvidenceReport,
    build_reverse_engineering_hints,
    build_strategy_evidence_report,
    has_high_crypto_replay_risk,
)


# ---------------------------------------------------------------------------
# Training scenarios
# ---------------------------------------------------------------------------

def train_graphql_nested_fields() -> dict:
    """GraphQL training: nested fields extraction."""
    result = fetch_graphql_api(
        "mock://api/graphql-nested",
        query=build_graphql_nested_fields_query(),
    )
    data = result["data"]
    characters = data["data"]["characters"]["results"]
    records = extract_records_from_json(data)
    normalized = normalize_api_records(records)

    return {
        "scenario": "graphql_nested_fields",
        "ok": result["ok"],
        "status_code": result["status_code"],
        "characters_count": len(characters),
        "total_episodes": sum(len(c.get("episode", [])) for c in characters),
        "extracted_records": len(records),
        "normalized_records": len(normalized),
        "sample_titles": [r.get("title") or r.get("name") for r in normalized[:5]],
        "nested_fields_present": all(
            "origin" in c and "episode" in c for c in characters
        ),
    }


def train_graphql_cursor_pagination() -> dict:
    """GraphQL training: Relay-style cursor pagination loop."""
    all_items = []
    pages = 0
    cursor = None
    for _ in range(10):
        result = fetch_graphql_api(
            "mock://api/graphql-paginated",
            query=build_graphql_cursor_query(),
            variables={"after": cursor},
        )
        data = result["data"]["data"]["characters"]
        edges = data["edges"]
        nodes = [e["node"] for e in edges if isinstance(e, dict) and "node" in e]
        all_items.extend(nodes)
        pages += 1
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]

    normalized = normalize_api_records(all_items)
    return {
        "scenario": "graphql_cursor_pagination",
        "pages_fetched": pages,
        "total_items": len(all_items),
        "normalized_records": len(normalized),
        "sample_titles": [r.get("title") or r.get("name") for r in normalized[:5]],
        "stop_reason": "hasNextPage=false" if pages > 1 else "single_page",
    }


def train_graphql_error_handling() -> dict:
    """GraphQL training: error response parsing."""
    result = fetch_graphql_api("mock://api/graphql-error", query="{ nonexistent }")
    errors = result["data"].get("errors", [])
    return {
        "scenario": "graphql_error_handling",
        "ok": result["ok"],
        "has_errors": bool(errors),
        "error_count": len(errors),
        "error_code": errors[0]["extensions"]["code"] if errors else None,
    }


def train_graphql_rate_limit() -> dict:
    """GraphQL training: rate-limit response detection."""
    result = fetch_graphql_api("mock://api/graphql-rate-limited", query="{}")
    errors = result["data"].get("errors", [])
    ext = errors[0].get("extensions", {}) if errors else {}
    return {
        "scenario": "graphql_rate_limit",
        "ok": result["ok"],
        "status_code": result["status_code"],
        "rate_limited": result["status_code"] == 429,
        "retry_after": ext.get("retryAfter"),
        "error_code": ext.get("code"),
    }


def train_api_page_pagination() -> dict:
    """API training: page-based pagination 50+ records."""
    result = fetch_paginated_api(
        "mock://api/paged-products-50?page=1",
        pagination=PaginationSpec(type="page", page_param="page", max_pages=10),
    )
    return {
        "scenario": "api_page_pagination",
        "total_items": len(result.all_items),
        "pages_fetched": result.pages_fetched,
        "pagination_type": result.pagination_type,
        "stop_reason": result.stop_reason,
        "deduplicated_count": result.deduplicated_count,
        "meets_50_threshold": len(result.all_items) >= 50,
        "sample_titles": [r.get("title") for r in result.all_items[:5]],
    }


def train_api_offset_pagination() -> dict:
    """API training: offset-based pagination 50+ records."""
    result = fetch_paginated_api(
        "mock://api/offset-products-50?offset=0&limit=10",
        pagination=PaginationSpec(
            type="offset", offset_param="offset", limit_param="limit",
            limit=10, max_pages=10,
        ),
    )
    return {
        "scenario": "api_offset_pagination",
        "total_items": len(result.all_items),
        "pages_fetched": result.pages_fetched,
        "pagination_type": result.pagination_type,
        "stop_reason": result.stop_reason,
        "deduplicated_count": result.deduplicated_count,
        "meets_50_threshold": len(result.all_items) >= 50,
        "sample_titles": [r.get("title") for r in result.all_items[:5]],
    }


def train_api_cursor_pagination() -> dict:
    """API training: cursor-based pagination 50+ records."""
    result = fetch_paginated_api(
        "mock://api/cursor-products-50?cursor=",
        pagination=PaginationSpec(type="cursor", cursor_param="cursor", max_pages=10),
    )
    return {
        "scenario": "api_cursor_pagination",
        "total_items": len(result.all_items),
        "pages_fetched": result.pages_fetched,
        "pagination_type": result.pagination_type,
        "stop_reason": result.stop_reason,
        "deduplicated_count": result.deduplicated_count,
        "meets_50_threshold": len(result.all_items) >= 50,
        "sample_titles": [r.get("title") for r in result.all_items[:5]],
    }


# ---------------------------------------------------------------------------
# Reverse evidence training
# ---------------------------------------------------------------------------

_REVERSE_SCENARIOS = [
    {
        "name": "signature_in_url",
        "recon": {
            "api_candidates": [
                {
                    "url": "https://api.example.com/data?x-sign=abc123&timestamp=1234567890&nonce=rand",
                    "method": "GET",
                    "kind": "json",
                    "score": 65,
                },
            ],
        },
    },
    {
        "name": "graphql_rate_limited_with_auth",
        "recon": {
            "api_candidates": [
                {
                    "url": "https://api.example.com/graphql",
                    "method": "POST",
                    "kind": "graphql",
                    "score": 70,
                    "status_code": 429,
                    "headers": {"Authorization": "Bearer tok123"},
                },
            ],
        },
    },
    {
        "name": "encrypted_payload",
        "recon": {
            "api_candidates": [
                {
                    "url": "https://api.example.com/rpc",
                    "method": "POST",
                    "kind": "json",
                    "score": 50,
                    "body": "payload=aes_encrypted_data&cipher=AES-GCM",
                },
            ],
        },
    },
    {
        "name": "js_signature_flow",
        "recon": {
            "js_evidence": {
                "items": [
                    {
                        "source": "inline",
                        "url": "https://example.com/bundle.js",
                        "total_score": 65,
                        "crypto_analysis": {
                            "signals": [
                                {"kind": "hash", "name": "SHA256"},
                                {"kind": "signature", "name": "HMAC"},
                            ],
                            "categories": ["hash", "signature"],
                            "likely_signature_flow": True,
                            "score": 70,
                            "recommendations": ["Hook hash function", "Monitor HMAC calls"],
                        },
                    },
                ],
            },
        },
    },
    {
        "name": "js_timestamp_nonce",
        "recon": {
            "js_evidence": {
                "items": [
                    {
                        "source": "inline",
                        "url": "https://example.com/auth.js",
                        "total_score": 50,
                        "crypto_analysis": {
                            "signals": [
                                {"kind": "timestamp", "name": "Date.now"},
                                {"kind": "nonce", "name": "crypto.randomUUID"},
                            ],
                            "categories": ["timestamp", "nonce"],
                            "likely_timestamp_nonce_flow": True,
                            "score": 55,
                            "recommendations": ["Capture timestamp at request time"],
                        },
                    },
                ],
            },
        },
    },
    {
        "name": "clean_api_no_blockers",
        "recon": {
            "api_candidates": [
                {
                    "url": "https://api.example.com/products?page=1&limit=20",
                    "method": "GET",
                    "kind": "json",
                    "score": 40,
                },
            ],
        },
    },
]


def train_reverse_evidence() -> list[dict]:
    """Run reverse evidence analysis on all training scenarios."""
    results = []
    for scenario in _REVERSE_SCENARIOS:
        report = build_strategy_evidence_report(scenario["recon"])
        risk = has_high_crypto_replay_risk(report)
        results.append({
            "scenario": scenario["name"],
            "signal_count": len(report.signals),
            "signal_codes": [s.code for s in report.signals],
            "warnings": list(report.warnings),
            "has_replay_blocker": bool(report.action_hints.get("api_replay_blocker")),
            "replay_risk": risk,
            "hints_keys": list(report.action_hints.keys()),
        })
    return results


# ---------------------------------------------------------------------------
# Async metrics integration
# ---------------------------------------------------------------------------

def _httpx_response(*, status_code: int = 200, url: str = "https://example.com/") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url
    resp.headers = {"Content-Type": "text/html"}
    resp.cookies = {}
    resp.content = b"<html>OK</html>"
    resp.text = "<html>OK</html>"
    resp.http_version = "HTTP/2"
    return resp


async def train_with_async_metrics(count: int = 100, num_domains: int = 5) -> dict:
    """Run async fetch simulation with metrics flowing into SpiderRunSummary."""
    domains = [f"training{i}.example.com" for i in range(num_domains)]
    urls = [f"https://{domains[i % num_domains]}/api/page/{i}" for i in range(count)]

    fail_idx = 0
    async def _sometimes_fail(*args, **kwargs):
        nonlocal fail_idx
        fail_idx += 1
        if fail_idx % 10 == 0:
            raise ConnectionError("proxy glitch")
        return _httpx_response()

    with patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient") as mock_cls:
        client = mock_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_sometimes_fail)

        pool_provider = MagicMock()
        pool_provider.select.return_value = MagicMock(proxy_url="http://u:p@proxy:8080")
        pool_provider.report_result = MagicMock()
        health_store = MagicMock()
        health_store.record_failure = MagicMock()
        health_store.record_success = MagicMock()

        runtime = NativeAsyncFetchRuntime(max_per_domain=4, max_global=16)
        requests = [
            RuntimeRequest(
                url=u,
                proxy_config={
                    "proxy": "http://u:p@proxy:8080",
                    "retry_on_proxy_failure": True,
                    "max_proxy_attempts": 2,
                    "pool_provider": pool_provider,
                    "health_store": health_store,
                },
            )
            for u in urls
        ]

        t0 = time.monotonic()
        responses = await runtime.fetch_many(requests)
        elapsed = time.monotonic() - t0

        summary = SpiderRunSummary(run_id="training-metrics", status="completed")
        for resp in responses:
            envelope = CrawlRequestEnvelope(run_id="training-metrics", url=resp.final_url or "https://x.com/")
            result = CrawlItemResult(
                ok=resp.ok,
                request_id=envelope.request_id,
                url=resp.final_url or "https://x.com/",
                status_code=resp.status_code,
                runtime_events=resp.runtime_events,
            )
            summary.record_item(result)

        metrics = AsyncFetchMetrics.from_responses(responses)

    return {
        "count": count,
        "num_domains": num_domains,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_urls_per_sec": round(count / max(elapsed, 0.001), 1),
        "summary": {
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "proxy_attempts_total": summary.proxy_attempts_total,
            "proxy_failures": summary.proxy_failures,
            "proxy_successes": summary.proxy_successes,
            "proxy_retries": summary.proxy_retries,
            "backpressure_events": summary.backpressure_events,
            "pool_acquired_events": summary.pool_acquired_events,
            "async_fetch_ok": summary.async_fetch_ok,
            "async_fetch_fail": summary.async_fetch_fail,
            "max_concurrency_per_domain": summary.max_concurrency_per_domain,
        },
        "metrics": metrics.to_dict(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="API / GraphQL / Reverse Evidence Trainer")
    parser.add_argument("--output", type=str, default="", help="Output directory for training report")
    parser.add_argument("--async-count", type=int, default=100, help="Async metrics URL count (default 100)")
    args = parser.parse_args()

    report: dict = {
        "task": "SCRAPLING-HARDEN-4",
        "worker": "LLM-2026-002",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "graphql_training": {},
        "api_pagination_training": {},
        "reverse_evidence_training": [],
        "async_metrics_training": {},
    }

    # GraphQL training
    print("=" * 60)
    print("GRAPHQL TRAINING")
    print("=" * 60)

    for name, fn in [
        ("nested_fields", train_graphql_nested_fields),
        ("cursor_pagination", train_graphql_cursor_pagination),
        ("error_handling", train_graphql_error_handling),
        ("rate_limit", train_graphql_rate_limit),
    ]:
        result = fn()
        report["graphql_training"][name] = result
        # rate_limit and error_handling are expected to have ok=False or has_errors
        if name == "rate_limit":
            status = "RATE_LIMITED" if result.get("rate_limited") else "FAIL"
        elif name == "error_handling":
            status = "ERRORS_DETECTED" if result.get("has_errors") else "FAIL"
        else:
            status = "OK" if result.get("ok", True) else "FAIL"
        print(f"  {name}: {status}")
        for k, v in result.items():
            if k != "scenario":
                print(f"    {k}: {v}")
        print()

    # API pagination training
    print("=" * 60)
    print("API PAGINATION TRAINING (50+ records)")
    print("=" * 60)

    for name, fn in [
        ("page", train_api_page_pagination),
        ("offset", train_api_offset_pagination),
        ("cursor", train_api_cursor_pagination),
    ]:
        result = fn()
        report["api_pagination_training"][name] = result
        meets = "50+ OK" if result.get("meets_50_threshold") else "BELOW 50"
        print(f"  {name}: {meets} ({result['total_items']} items, {result['pages_fetched']} pages)")
        print(f"    stop_reason: {result['stop_reason']}")
        print()

    # Reverse evidence training
    print("=" * 60)
    print("REVERSE EVIDENCE TRAINING")
    print("=" * 60)

    reverse_results = train_reverse_evidence()
    report["reverse_evidence_training"] = reverse_results
    for r in reverse_results:
        risk = "RISK" if r["replay_risk"] else "clean"
        blocker = "BLOCKER" if r["has_replay_blocker"] else "---"
        print(f"  {r['scenario']}: {risk}, {blocker}, signals={r['signal_codes']}")
    print()

    # Async metrics training
    print("=" * 60)
    print("ASYNC METRICS TRAINING")
    print("=" * 60)

    metrics_result = asyncio.run(train_with_async_metrics(count=args.async_count))
    report["async_metrics_training"] = metrics_result
    s = metrics_result["summary"]
    print(f"  URLs: {metrics_result['count']}")
    print(f"  Elapsed: {metrics_result['elapsed_seconds']}s")
    print(f"  Throughput: {metrics_result['throughput_urls_per_sec']} URLs/s")
    print(f"  Succeeded: {s['succeeded']}")
    print(f"  Failed: {s['failed']}")
    print(f"  Proxy attempts: {s['proxy_attempts_total']}")
    print(f"  Proxy failures: {s['proxy_failures']}")
    print(f"  Proxy retries: {s['proxy_retries']}")
    print(f"  Backpressure: {s['backpressure_events']}")
    print(f"  Async OK: {s['async_fetch_ok']}")
    print()

    # Summary
    print("=" * 60)
    print("TRAINING SUMMARY")
    print("=" * 60)
    gql = report["graphql_training"]
    api = report["api_pagination_training"]
    rev = report["reverse_evidence_training"]

    gql_pass = sum(1 for k, v in gql.items() if (
        v.get("ok", True) or v.get("rate_limited") or v.get("has_errors")
    ))
    api_pass = sum(1 for v in api.values() if v.get("meets_50_threshold"))
    rev_risk = sum(1 for r in rev if r["replay_risk"])
    rev_blocker = sum(1 for r in rev if r["has_replay_blocker"])

    print(f"  GraphQL scenarios:    {gql_pass}/{len(gql)} passed")
    print(f"  API 50+ pagination:  {api_pass}/{len(api)} meet threshold")
    print(f"  Reverse evidence:    {rev_risk} with replay risk, {rev_blocker} with blockers")
    print(f"  Async metrics:       {s['succeeded']}/{metrics_result['count']} succeeded")
    print("=" * 60)

    # Save report
    if args.output:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"training_{time.strftime('%Y%m%d_%H%M%S')}.json"
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
