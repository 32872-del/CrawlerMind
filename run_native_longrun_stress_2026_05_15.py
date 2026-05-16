"""Optional long-run stress runner for SCRAPLING-HARDEN-1.

Runs 1k (default) or 10k URL fetch simulation against the CLM-native async
fetch pool, aggregates metrics into SpiderRunSummary, and reports throughput,
concurrency, retry/proxy counts, and checkpoint resume behavior.

Usage:
    python run_native_longrun_stress_2026_05_15.py              # 1k URLs
    python run_native_longrun_stress_2026_05_15.py --count 10000 # 10k URLs
    python run_native_longrun_stress_2026_05_15.py --count 10000 --domains 50

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
from autonomous_crawler.runtime.models import RuntimeEvent, RuntimeRequest, RuntimeResponse
from autonomous_crawler.runners.spider_models import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
)
from autonomous_crawler.storage.checkpoint_store import CheckpointStore


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


def _make_urls(n: int, num_domains: int) -> list[str]:
    domains = [f"domain{i}.example.com" for i in range(num_domains)]
    return [f"https://{domains[i % num_domains]}/page/{i}" for i in range(n)]


async def run_stress(count: int, num_domains: int, max_per_domain: int, max_global: int) -> dict:
    """Run the stress test and return results dict."""

    fail_idx = 0
    async def _sometimes_fail(*args, **kwargs):
        nonlocal fail_idx
        fail_idx += 1
        if fail_idx % 20 == 0:  # 5% failure rate
            raise ConnectionError("proxy glitch")
        return _httpx_response()

    with patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient") as mock_cls:
        client = mock_cls.return_value.__aenter__.return_value
        client.request = AsyncMock(side_effect=_sometimes_fail)

        pool_provider = MagicMock()
        pool_provider.select.return_value = MagicMock(proxy_url="http://alt:cred@proxy-b:9090")
        pool_provider.report_result = MagicMock()
        health_store = MagicMock()
        health_store.record_failure = MagicMock()
        health_store.record_success = MagicMock()

        runtime = NativeAsyncFetchRuntime(
            max_per_domain=max_per_domain,
            max_global=max_global,
        )

        urls = _make_urls(count, num_domains)
        requests = [
            RuntimeRequest(
                url=u,
                proxy_config={
                    "proxy": "http://u:p@proxy-a:8080",
                    "retry_on_proxy_failure": True,
                    "max_proxy_attempts": 2,
                    "pool_provider": pool_provider,
                    "health_store": health_store,
                },
            )
            for u in urls
        ]

        # Run
        t0 = time.monotonic()
        responses = await runtime.fetch_many(requests)
        elapsed = time.monotonic() - t0

        # Aggregate into summary
        summary = SpiderRunSummary(run_id=f"stress-{count}", status="completed")
        for resp in responses:
            envelope = CrawlRequestEnvelope(
                run_id=f"stress-{count}",
                url=resp.final_url or "https://x.com/",
            )
            result = CrawlItemResult(
                ok=resp.ok,
                request_id=envelope.request_id,
                url=resp.final_url or "https://x.com/",
                status_code=resp.status_code,
                runtime_events=resp.runtime_events,
            )
            summary.record_item(result)

        # AsyncFetchMetrics
        metrics = AsyncFetchMetrics.from_responses(responses)

        # Checkpoint test
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "ckpt.sqlite3")
            store.start_run(f"stress-{count}")
            store.save_batch_checkpoint(
                run_id=f"stress-{count}",
                batch_id="batch-final",
                frontier_items=[],
                summary=summary,
            )
            loaded = store.load_latest(f"stress-{count}")
            ckpt_summary = loaded["latest_checkpoint"]["summary"] if loaded and loaded["latest_checkpoint"] else {}

    report = summary.as_dict()
    return {
        "count": count,
        "num_domains": num_domains,
        "max_per_domain": max_per_domain,
        "max_global": max_global,
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
        "checkpoint_roundtrip_ok": ckpt_summary.get("succeeded") == summary.succeeded,
        "checkpoint_proxy_fields_ok": ckpt_summary.get("proxy_attempts_total") == summary.proxy_attempts_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CLM-native async stress runner")
    parser.add_argument("--count", type=int, default=1000, help="Number of URLs (default 1000)")
    parser.add_argument("--domains", type=int, default=10, help="Number of domains (default 10)")
    parser.add_argument("--max-per-domain", type=int, default=4, help="Per-domain concurrency (default 4)")
    parser.add_argument("--max-global", type=int, default=16, help="Global concurrency (default 16)")
    args = parser.parse_args()

    print(f"Running stress: {args.count} URLs, {args.domains} domains, "
          f"per_domain={args.max_per_domain}, global={args.max_global}")
    print()

    result = asyncio.run(run_stress(
        count=args.count,
        num_domains=args.domains,
        max_per_domain=args.max_per_domain,
        max_global=args.max_global,
    ))

    print("=" * 60)
    print("STRESS RESULTS")
    print("=" * 60)
    print(f"  URLs:              {result['count']}")
    print(f"  Domains:           {result['num_domains']}")
    print(f"  Elapsed:           {result['elapsed_seconds']}s")
    print(f"  Throughput:        {result['throughput_urls_per_sec']} URLs/s")
    print()
    print("  Summary:")
    s = result["summary"]
    print(f"    Succeeded:       {s['succeeded']}")
    print(f"    Failed:          {s['failed']}")
    print(f"    Proxy attempts:  {s['proxy_attempts_total']}")
    print(f"    Proxy failures:  {s['proxy_failures']}")
    print(f"    Proxy retries:   {s['proxy_retries']}")
    print(f"    Backpressure:    {s['backpressure_events']}")
    print(f"    Async OK:        {s['async_fetch_ok']}")
    print(f"    Async Fail:      {s['async_fetch_fail']}")
    print(f"    Max concurrency: {s['max_concurrency_per_domain']}")
    print()
    print("  Checkpoint:")
    print(f"    Roundtrip OK:    {result['checkpoint_roundtrip_ok']}")
    print(f"    Proxy fields OK: {result['checkpoint_proxy_fields_ok']}")
    print()

    # Credential check
    report_text = str(result)
    has_creds = any(c in report_text for c in ["u:p@", "secret@", "topsecret"])
    print(f"  Credential leak:   {'DETECTED!' if has_creds else 'none'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
