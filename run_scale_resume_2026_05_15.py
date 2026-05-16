"""SCALE-HARDEN-2: Resumable 30k Checkpoint Restart.

Proves CLM can pause mid-run, persist checkpoint, and resume from where
it left off — including URL deduplication and failure tracking.

Simulates:
1. Run N URLs, then pause (checkpoint + mark_paused)
2. Load checkpoint, compute remaining URLs
3. Resume and complete remaining URLs
4. Verify total processed == total URLs, no duplicates, checkpoint roundtrip

All requests are mocked — no public network required.

Usage:
    python run_scale_resume_2026_05_15.py                     # 30k default
    python run_scale_resume_2026_05_15.py --count 10000       # 10k
    python run_scale_resume_2026_05_15.py --count 1000 --quick  # quick sanity
"""
from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.runtime.native_async import NativeAsyncFetchRuntime
from autonomous_crawler.runtime.models import RuntimeRequest
from autonomous_crawler.runners.spider_models import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
)
from autonomous_crawler.storage.checkpoint_store import CheckpointStore


def _httpx_response(status_code: int = 200, url: str = "https://example.com/") -> MagicMock:
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


async def run_resumable_stress(
    count: int,
    num_domains: int,
    max_per_domain: int,
    max_global: int,
    pause_at: int,
    chunk_size: int,
) -> dict:
    """Run a resumable stress test with checkpoint pause/resume."""

    fail_idx = 0
    async def _sometimes_fail(*args, **kwargs):
        nonlocal fail_idx
        fail_idx += 1
        if fail_idx % 20 == 0:  # 5% failure rate
            raise ConnectionError("proxy glitch")
        return _httpx_response()

    with tempfile.TemporaryDirectory() as tmp:
        store = CheckpointStore(Path(tmp) / "resume.sqlite3")
        run_id = f"resume-{count}"

        # --- Phase 1: Run to pause_at ---
        store.start_run(run_id)

        pool_provider = MagicMock()
        pool_provider.select.return_value = MagicMock(proxy_url="http://proxy:9090")
        pool_provider.report_result = MagicMock()
        health_store = MagicMock()
        health_store.record_failure = MagicMock()
        health_store.record_success = MagicMock()

        all_urls = _make_urls(count, num_domains)
        processed_urls: list[str] = []  # tracks request URLs in order

        with patch("autonomous_crawler.runtime.native_async.httpx.AsyncClient") as mock_cls:
            client = mock_cls.return_value.__aenter__.return_value
            client.request = AsyncMock(side_effect=_sometimes_fail)

            runtime = NativeAsyncFetchRuntime(
                max_per_domain=max_per_domain,
                max_global=max_global,
            )

            # Phase 1: process first pause_at URLs
            t0 = time.monotonic()
            summary_phase1 = SpiderRunSummary(run_id=run_id, status="running")

            phase1_urls = all_urls[:pause_at]
            requests_phase1 = [
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
                for u in phase1_urls
            ]

            # Chunked execution
            responses_phase1 = []
            for chunk_start in range(0, len(requests_phase1), chunk_size):
                chunk = requests_phase1[chunk_start:chunk_start + chunk_size]
                chunk_responses = await runtime.fetch_many(chunk)
                responses_phase1.extend(chunk_responses)

            for i, resp in enumerate(responses_phase1):
                req_url = phase1_urls[i] if i < len(phase1_urls) else "https://x.com/"
                envelope = CrawlRequestEnvelope(run_id=run_id, url=req_url)
                result = CrawlItemResult(
                    ok=resp.ok,
                    request_id=envelope.request_id,
                    url=req_url,
                    status_code=resp.status_code,
                    runtime_events=resp.runtime_events,
                )
                summary_phase1.record_item(result)
                processed_urls.append(req_url)

            # Save checkpoint and pause
            store.save_batch_checkpoint(
                run_id=run_id,
                batch_id="batch-phase1",
                frontier_items=[{"url": u} for u in all_urls[pause_at:]],
                summary=summary_phase1,
            )
            store.mark_paused(run_id, reason="simulated_pause")
            t_phase1 = time.monotonic() - t0

            # --- Phase 2: Resume from checkpoint ---
            loaded = store.load_latest(run_id)
            assert loaded is not None, "Checkpoint not found"
            assert loaded["run"]["status"] == "paused", f"Expected paused, got {loaded['run']['status']}"

            ckpt_summary = loaded["latest_checkpoint"]["summary"]
            processed_before = ckpt_summary.get("succeeded", 0) + ckpt_summary.get("failed", 0)
            remaining_urls = [item["url"] for item in loaded["latest_checkpoint"]["frontier_items"]]

            # Resume
            store.start_run(run_id)  # resets status to running
            summary_phase2 = SpiderRunSummary(run_id=run_id, status="running")

            t1 = time.monotonic()

            requests_phase2 = [
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
                for u in remaining_urls
            ]

            responses_phase2 = []
            for chunk_start in range(0, len(requests_phase2), chunk_size):
                chunk = requests_phase2[chunk_start:chunk_start + chunk_size]
                chunk_responses = await runtime.fetch_many(chunk)
                responses_phase2.extend(chunk_responses)

            for i, resp in enumerate(responses_phase2):
                req_url = remaining_urls[i] if i < len(remaining_urls) else "https://x.com/"
                envelope = CrawlRequestEnvelope(run_id=run_id, url=req_url)
                result = CrawlItemResult(
                    ok=resp.ok,
                    request_id=envelope.request_id,
                    url=req_url,
                    status_code=resp.status_code,
                    runtime_events=resp.runtime_events,
                )
                summary_phase2.record_item(result)
                processed_urls.append(req_url)

            t_phase2 = time.monotonic() - t1

            # Final checkpoint with combined phase1 + phase2 totals.
            summary_combined = combine_summaries(run_id, summary_phase1, summary_phase2)
            store.save_batch_checkpoint(
                run_id=run_id,
                batch_id="batch-phase2",
                frontier_items=[],
                summary=summary_combined,
            )
            store.mark_completed(run_id)

            # Verify
            final_loaded = store.load_latest(run_id)
            final_summary = final_loaded["latest_checkpoint"]["summary"] if final_loaded and final_loaded["latest_checkpoint"] else {}

            total_elapsed = t_phase1 + t_phase2
            total_succeeded = summary_phase1.succeeded + summary_phase2.succeeded
            total_failed = summary_phase1.failed + summary_phase2.failed
            total_urls_processed = total_succeeded + total_failed

            # Duplicate detection: check for duplicate request URLs
            unique_urls = len(set(processed_urls))
            duplicate_count = len(processed_urls) - unique_urls

    return {
        "total_urls": count,
        "processed_before_pause": processed_before,
        "processed_after_resume": len(responses_phase2),
        "total_processed": total_urls_processed,
        "unique_urls": unique_urls,
        "duplicate_count": duplicate_count,
        "failed_count": total_failed,
        "checkpoint_roundtrip": {
            "status_ok": final_loaded is not None,
            "phase1_succeeded": summary_phase1.succeeded,
            "phase2_succeeded": summary_phase2.succeeded,
            "total_succeeded": total_succeeded,
            "final_ckpt_succeeded": final_summary.get("succeeded"),
            "final_ckpt_failed": final_summary.get("failed"),
            "proxy_fields_ok": final_summary.get("proxy_attempts_total", 0) > 0,
            "async_fields_ok": final_summary.get("async_fetch_ok", 0) > 0,
        },
        "timing": {
            "phase1_seconds": round(t_phase1, 3),
            "phase2_seconds": round(t_phase2, 3),
            "total_seconds": round(total_elapsed, 3),
            "throughput_urls_per_sec": round(count / max(total_elapsed, 0.001), 1),
        },
        "pause_resume": {
            "pause_at": pause_at,
            "remaining_after_pause": len(remaining_urls),
            "resume_completed": len(responses_phase2),
        },
    }


def combine_summaries(run_id: str, *summaries: SpiderRunSummary) -> SpiderRunSummary:
    """Combine phase summaries for a final resumable-run checkpoint."""
    combined = SpiderRunSummary(run_id=run_id, status="completed")
    for summary in summaries:
        combined.batches += summary.batches
        combined.claimed += summary.claimed
        combined.succeeded += summary.succeeded
        combined.failed += summary.failed
        combined.retried += summary.retried
        combined.skipped += summary.skipped
        combined.records_saved += summary.records_saved
        combined.discovered_urls += summary.discovered_urls
        combined.robots_disallowed += summary.robots_disallowed
        combined.offsite_dropped += summary.offsite_dropped
        combined.blocked_requests += summary.blocked_requests
        combined.checkpoint_writes += summary.checkpoint_writes
        combined.checkpoint_errors += summary.checkpoint_errors
        _merge_counts(combined.response_status_count, summary.response_status_count)
        _merge_counts(combined.failure_buckets, summary.failure_buckets)
        combined.events.extend(summary.events)
        combined.proxy_attempts_total += summary.proxy_attempts_total
        combined.proxy_failures += summary.proxy_failures
        combined.proxy_successes += summary.proxy_successes
        combined.proxy_retries += summary.proxy_retries
        combined.backpressure_events += summary.backpressure_events
        combined.pool_acquired_events += summary.pool_acquired_events
        combined.pool_released_events += summary.pool_released_events
        combined.async_fetch_ok += summary.async_fetch_ok
        combined.async_fetch_fail += summary.async_fetch_fail
        for domain, value in summary.max_concurrency_per_domain.items():
            combined.max_concurrency_per_domain[domain] = max(
                combined.max_concurrency_per_domain.get(domain, 0),
                value,
            )
    return combined


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def main() -> None:
    parser = argparse.ArgumentParser(description="SCALE-HARDEN-2: Resumable Checkpoint Restart")
    parser.add_argument("--count", type=int, default=30000, help="Total URLs (default 30000)")
    parser.add_argument("--domains", type=int, default=20, help="Number of domains (default 20)")
    parser.add_argument("--max-per-domain", type=int, default=4, help="Per-domain concurrency (default 4)")
    parser.add_argument("--max-global", type=int, default=32, help="Global concurrency (default 32)")
    parser.add_argument("--pause-at", type=int, default=0, help="Pause after N URLs (default: 60%% of count)")
    parser.add_argument("--chunk-size", type=int, default=2000, help="Chunk size (default 2000)")
    parser.add_argument("--quick", action="store_true", help="Quick mode: 1000 URLs")
    args = parser.parse_args()

    count = 1000 if args.quick else args.count
    pause_at = args.pause_at if args.pause_at > 0 else int(count * 0.6)

    print("=" * 70)
    print("SCALE-HARDEN-2: Resumable Checkpoint Restart")
    print("=" * 70)
    print(f"  Total URLs:    {count}")
    print(f"  Pause at:      {pause_at}")
    print(f"  Domains:       {args.domains}")
    print(f"  Per-domain:    {args.max_per_domain}")
    print(f"  Global:        {args.max_global}")
    print(f"  Chunk size:    {args.chunk_size}")
    print()

    result = asyncio.run(run_resumable_stress(
        count=count,
        num_domains=args.domains,
        max_per_domain=args.max_per_domain,
        max_global=args.max_global,
        pause_at=pause_at,
        chunk_size=args.chunk_size,
    ))

    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"  Total URLs:           {result['total_urls']}")
    print(f"  Processed (phase1):   {result['processed_before_pause']}")
    print(f"  Processed (phase2):   {result['processed_after_resume']}")
    print(f"  Total processed:      {result['total_processed']}")
    print(f"  Unique URLs:          {result['unique_urls']}")
    print(f"  Duplicates:           {result['duplicate_count']}")
    print(f"  Failed:               {result['failed_count']}")
    print()
    print("  Checkpoint:")
    for k, v in result["checkpoint_roundtrip"].items():
        print(f"    {k}: {v}")
    print()
    print("  Timing:")
    for k, v in result["timing"].items():
        print(f"    {k}: {v}")
    print()
    print("  Pause/Resume:")
    for k, v in result["pause_resume"].items():
        print(f"    {k}: {v}")
    print()

    # Credential check
    result_str = json.dumps(result, default=str)
    has_creds = any(c in result_str for c in ["u:p@", "secret@", "topsecret"])
    print(f"  Credential leak: {'DETECTED!' if has_creds else 'none'}")
    print("=" * 70)

    # Save
    out_path = Path(f"dev_logs/smoke/scale_resume_{count}_{time.strftime('%Y%m%d_%H%M%S')}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
