"""SCALE-HARDEN-1: Parameterized 10k/30k native long-run stress runner.

Proves CLM-native async fetch pool supports 10k (default) and optional 30k
URL runs with memory tracking, throughput, checkpoint roundtrip, and full
proxy/async/backpressure summary.

Usage:
    python run_scale_stress_2026_05_15.py                     # 10k default
    python run_scale_stress_2026_05_15.py --count 30000       # 30k
    python run_scale_stress_2026_05_15.py --count 1000 --quick  # quick sanity

All requests are mocked — no public network required.
"""
from __future__ import annotations

import argparse
import asyncio
import gc
import json
import tempfile
import time
import tracemalloc
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.runtime.native_async import (
    AsyncFetchMetrics,
    DomainConcurrencyPool,
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


def _memory_mb() -> float:
    """Current RSS memory in MB (best-effort cross-platform)."""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        pass
    try:
        import resource as _res
        usage = _res.getrusage(_res.RUSAGE_SELF)
        if hasattr(usage, "ru_maxrss"):
            return usage.ru_maxrss / 1024  # KB -> MB on Linux
    except (ImportError, AttributeError, OSError):
        pass
    # Windows fallback: use tracemalloc current size
    try:
        current, _ = tracemalloc.get_traced_memory()
        return current / (1024 * 1024)
    except RuntimeError:
        pass
    return 0.0


async def run_stress(
    count: int,
    num_domains: int,
    max_per_domain: int,
    max_global: int,
    chunk_size: int,
) -> dict:
    """Run the stress test and return comprehensive results."""

    fail_idx = 0
    async def _sometimes_fail(*args, **kwargs):
        nonlocal fail_idx
        fail_idx += 1
        if fail_idx % 20 == 0:  # 5% failure rate
            raise ConnectionError("proxy glitch")
        return _httpx_response()

    # Memory tracking
    tracemalloc.start()
    gc.collect()
    mem_before = _memory_mb()

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

        # Chunked execution for memory efficiency
        all_responses: list[RuntimeResponse] = []
        t0 = time.monotonic()

        if chunk_size > 0 and count > chunk_size:
            for chunk_start in range(0, count, chunk_size):
                chunk = requests[chunk_start:chunk_start + chunk_size]
                chunk_responses = await runtime.fetch_many(chunk)
                all_responses.extend(chunk_responses)
                # Allow GC between chunks
                if chunk_start + chunk_size < count:
                    await asyncio.sleep(0)
        else:
            all_responses = await runtime.fetch_many(requests)

        elapsed = time.monotonic() - t0

        # Memory after fetch
        gc.collect()
        mem_after = _memory_mb()
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Aggregate into summary
        summary = SpiderRunSummary(run_id=f"scale-{count}", status="completed")
        for resp in all_responses:
            envelope = CrawlRequestEnvelope(
                run_id=f"scale-{count}",
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
        metrics = AsyncFetchMetrics.from_responses(all_responses)

        # Checkpoint roundtrip test
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(Path(tmp) / "ckpt.sqlite3")
            store.start_run(f"scale-{count}")
            store.save_batch_checkpoint(
                run_id=f"scale-{count}",
                batch_id="batch-final",
                frontier_items=[],
                summary=summary,
            )
            loaded = store.load_latest(f"scale-{count}")
            ckpt_summary = loaded["latest_checkpoint"]["summary"] if loaded and loaded["latest_checkpoint"] else {}

    report = summary.as_dict()
    return {
        "count": count,
        "num_domains": num_domains,
        "max_per_domain": max_per_domain,
        "max_global": max_global,
        "chunk_size": chunk_size,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_urls_per_sec": round(count / max(elapsed, 0.001), 1),
        "memory": {
            "before_mb": round(mem_before, 1),
            "after_mb": round(mem_after, 1),
            "delta_mb": round(mem_after - mem_before, 1),
            "peak_traced_mb": round(peak_mem / (1024 * 1024), 1),
        },
        "summary": {
            "succeeded": summary.succeeded,
            "failed": summary.failed,
            "proxy_attempts_total": summary.proxy_attempts_total,
            "proxy_failures": summary.proxy_failures,
            "proxy_successes": summary.proxy_successes,
            "proxy_retries": summary.proxy_retries,
            "backpressure_events": summary.backpressure_events,
            "pool_acquired_events": summary.pool_acquired_events,
            "pool_released_events": summary.pool_released_events,
            "async_fetch_ok": summary.async_fetch_ok,
            "async_fetch_fail": summary.async_fetch_fail,
            "max_concurrency_per_domain": summary.max_concurrency_per_domain,
        },
        "metrics": metrics.to_dict(),
        "checkpoint": {
            "roundtrip_ok": ckpt_summary.get("succeeded") == summary.succeeded,
            "proxy_fields_ok": ckpt_summary.get("proxy_attempts_total") == summary.proxy_attempts_total,
            "async_fields_ok": ckpt_summary.get("async_fetch_ok") == summary.async_fetch_ok,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SCALE-HARDEN-1: Native long-run 10k/30k stress")
    parser.add_argument("--count", type=int, default=10000, help="Number of URLs (default 10000)")
    parser.add_argument("--domains", type=int, default=20, help="Number of domains (default 20)")
    parser.add_argument("--max-per-domain", type=int, default=4, help="Per-domain concurrency (default 4)")
    parser.add_argument("--max-global", type=int, default=32, help="Global concurrency (default 32)")
    parser.add_argument("--chunk-size", type=int, default=2000, help="Chunk size for memory efficiency (default 2000, 0=off)")
    parser.add_argument("--quick", action="store_true", help="Quick mode: 1000 URLs sanity check")
    args = parser.parse_args()

    count = 1000 if args.quick else args.count

    print("=" * 70)
    print("SCALE-HARDEN-1: Native Long-Run Stress")
    print("=" * 70)
    print(f"  URLs:              {count}")
    print(f"  Domains:           {args.domains}")
    print(f"  Per-domain:        {args.max_per_domain}")
    print(f"  Global:            {args.max_global}")
    print(f"  Chunk size:        {args.chunk_size}")
    print()

    result = asyncio.run(run_stress(
        count=count,
        num_domains=args.domains,
        max_per_domain=args.max_per_domain,
        max_global=args.max_global,
        chunk_size=args.chunk_size,
    ))

    s = result["summary"]
    m = result["memory"]
    ck = result["checkpoint"]

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"  URLs:              {result['count']}")
    print(f"  Elapsed:           {result['elapsed_seconds']}s")
    print(f"  Throughput:        {result['throughput_urls_per_sec']} URLs/s")
    print()
    print("  Memory:")
    print(f"    Before:          {m['before_mb']} MB")
    print(f"    After:           {m['after_mb']} MB")
    print(f"    Delta:           {m['delta_mb']} MB")
    print(f"    Peak (traced):   {m['peak_traced_mb']} MB")
    print()
    print("  Summary:")
    print(f"    Succeeded:       {s['succeeded']}")
    print(f"    Failed:          {s['failed']}")
    print(f"    Proxy attempts:  {s['proxy_attempts_total']}")
    print(f"    Proxy failures:  {s['proxy_failures']}")
    print(f"    Proxy retries:   {s['proxy_retries']}")
    print(f"    Backpressure:    {s['backpressure_events']}")
    print(f"    Pool acquired:   {s['pool_acquired_events']}")
    print(f"    Pool released:   {s['pool_released_events']}")
    print(f"    Async OK:        {s['async_fetch_ok']}")
    print(f"    Async fail:      {s['async_fetch_fail']}")
    print(f"    Max concurrency: {s['max_concurrency_per_domain']}")
    print()
    print("  Checkpoint:")
    print(f"    Roundtrip OK:    {ck['roundtrip_ok']}")
    print(f"    Proxy fields OK: {ck['proxy_fields_ok']}")
    print(f"    Async fields OK: {ck['async_fields_ok']}")
    print()

    # Credential check
    report_text = str(result)
    has_creds = any(c in report_text for c in ["u:p@", "secret@", "topsecret"])
    print(f"  Credential leak:   {'DETECTED!' if has_creds else 'none'}")
    print("=" * 70)

    # Save results
    out_path = Path(f"dev_logs/smoke/scale_stress_{count}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
