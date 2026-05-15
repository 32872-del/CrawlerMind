#!/usr/bin/env python3
"""Local pause/resume smoke for the CLM-native spider runtime.

This smoke does not access the public network. It proves the long-running
spider path can claim a bounded frontier batch, discover detail URLs, pause,
resume, checkpoint item records, and persist a deterministic failure bucket.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from autonomous_crawler.runners import (
    BatchRunner,
    BatchRunnerConfig,
    CrawlRequestEnvelope,
    SpiderRunSummary,
    SpiderRuntimeProcessor,
    make_spider_event,
)
from autonomous_crawler.runtime import (
    NativeParserRuntime,
    RuntimeEvent,
    RuntimeRequest,
    RuntimeResponse,
    RuntimeSelectorRequest,
)
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.tools.link_discovery import LinkDiscoveryHelper, LinkDiscoveryRule


OUTPUT_DIR = Path("dev_logs") / "smoke"
SUMMARY_PATH = OUTPUT_DIR / "2026-05-14_spider_runtime_smoke.json"
RUN_ID = "native-spider-smoke-2026-05-14"
BASE_URL = "https://spider-smoke.local"


HTML_FIXTURES = {
    f"{BASE_URL}/catalog": """
        <html>
          <body>
            <main id="catalog">
              <a class="product-link" href="/products/alpha">Alpha shoe</a>
              <a class="product-link" href="/products/beta?ref=list">Beta shoe</a>
              <a class="asset-link" href="/assets/catalog.png">image asset</a>
              <a class="offsite-link" href="https://other.example/products/blocked">offsite</a>
            </main>
          </body>
        </html>
    """,
    f"{BASE_URL}/products/alpha": """
        <html>
          <body>
            <article class="product">
              <h1>Alpha Runner</h1>
              <span class="price">19.90</span>
              <span class="color">Black</span>
              <span class="size">42</span>
            </article>
          </body>
        </html>
    """,
    f"{BASE_URL}/products/beta?ref=list": """
        <html>
          <body>
            <article class="product">
              <h1>Beta Trail</h1>
              <span class="price">29.50</span>
              <span class="color">Blue</span>
              <span class="size">43</span>
            </article>
          </body>
        </html>
    """,
}


class FixtureFetchRuntime:
    """FetchRuntime backed by deterministic in-memory HTML fixtures."""

    name = "fixture_fetch"

    def __init__(self, fixtures: dict[str, str]) -> None:
        self.fixtures = dict(fixtures)
        self.requests: list[RuntimeRequest] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        html = self.fixtures.get(request.url)
        if html is None:
            return RuntimeResponse.failure(
                final_url=request.url,
                status_code=404,
                error="fixture not found",
                engine=self.name,
                events=[
                    RuntimeEvent(
                        type="fetch_complete",
                        message="fixture lookup failed",
                        data={"status_code": 404},
                    )
                ],
            )
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            html=html,
            text=html,
            runtime_events=[
                RuntimeEvent(
                    type="fetch_complete",
                    message="fixture fetch completed",
                    data={"status_code": 200, "bytes": len(html.encode("utf-8"))},
                )
            ],
            engine_result={"engine": self.name},
        )


def selector_builder(
    request: CrawlRequestEnvelope,
    _item: dict[str, Any],
) -> list[RuntimeSelectorRequest]:
    if request.kind != "detail":
        return []
    return [
        RuntimeSelectorRequest(name="title", selector="article.product h1", many=False),
        RuntimeSelectorRequest(name="highest_price", selector="article.product .price", many=False),
        RuntimeSelectorRequest(name="color", selector="article.product .color", many=False),
        RuntimeSelectorRequest(name="size", selector="article.product .size", many=False),
    ]


def record_builder(
    request: CrawlRequestEnvelope,
    response: RuntimeResponse,
    selector_results: list[Any],
) -> list[dict[str, Any]]:
    if request.kind != "detail":
        return []
    fields = {
        result.name: list(getattr(result, "values", []))
        for result in selector_results
        if not getattr(result, "error", "")
    }
    title = _first(fields.get("title"))
    if not title:
        return []
    return [
        {
            "record_type": "product",
            "url": response.final_url or request.url,
            "canonical_url": response.final_url or request.url,
            "dedupe_key": request.fingerprint,
            "title": title,
            "highest_price": _first(fields.get("highest_price")),
            "color": _first(fields.get("color")),
            "size": _first(fields.get("size")),
            "source": "native_spider_smoke",
        }
    ]


def link_builder(
    request: CrawlRequestEnvelope,
    response: RuntimeResponse,
) -> list[CrawlRequestEnvelope]:
    if request.kind != "list":
        return []
    helper = LinkDiscoveryHelper()
    result = helper.extract(
        response.html or response.text,
        base_url=response.final_url or request.url,
        run_id=request.run_id,
        parent_request=request,
        rules=LinkDiscoveryRule(
            allow=(r"/products/",),
            allow_domains=("spider-smoke.local",),
            restrict_css=("#catalog",),
            classify={"detail": r"/products/"},
            default_kind="page",
            priority=8,
        ),
    )
    return result.requests


def run(
    *,
    keep_db: bool = False,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="clm_spider_runtime_smoke_"))
    output = Path(output_path) if output_path else SUMMARY_PATH
    try:
        frontier = URLFrontier(temp_dir / "frontier.sqlite3")
        store = CheckpointStore(temp_dir / "checkpoints.sqlite3")
        store.start_run(RUN_ID, {"mode": "local_fixture", "goal": "pause_resume_spider_smoke"})

        list_add = frontier.add_urls(
            [f"{BASE_URL}/catalog"],
            priority=10,
            kind="list",
            payload={"max_retries": 1},
        )
        failure_add = frontier.add_urls(
            [f"{BASE_URL}/products/missing"],
            priority=1,
            kind="detail",
            payload={"max_retries": 1},
        )

        processor = SpiderRuntimeProcessor(
            run_id=RUN_ID,
            fetch_runtime=FixtureFetchRuntime(HTML_FIXTURES),
            parser=NativeParserRuntime(),
            checkpoint_store=store,
            selector_builder=selector_builder,
            record_builder=record_builder,
            link_builder=link_builder,
        )

        first = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(
                run_id=RUN_ID,
                worker_id="native-spider-smoke-pass-1",
                batch_size=1,
                max_batches=1,
            ),
        ).run()
        first_frontier_stats = frontier.stats()
        _save_runner_checkpoint(store, first, "pass-1", status="paused")
        store.mark_paused(RUN_ID, "first bounded pass completed")

        resumed = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(
                run_id=RUN_ID,
                worker_id="native-spider-smoke-resume",
                batch_size=2,
            ),
        ).run()
        _save_runner_checkpoint(store, resumed, "resume", status="completed")

        final_frontier_stats = frontier.stats()
        if not final_frontier_stats.get("queued") and not final_frontier_stats.get("running"):
            store.mark_completed(RUN_ID)

        latest = store.load_latest(RUN_ID) or {}
        items = store.list_items(RUN_ID, limit=100)
        failures = store.list_failures(RUN_ID)
        summary = {
            "run_id": RUN_ID,
            "config": {"keep_db": keep_db, "network": "none", "fixture_count": len(HTML_FIXTURES)},
            "frontier_add": {
                "list": list_add,
                "failure_seed": failure_add,
            },
            "first_pass": first.as_dict(),
            "first_frontier_stats": first_frontier_stats,
            "resume_pass": resumed.as_dict(),
            "final_frontier_stats": final_frontier_stats,
            "checkpoint_latest": latest,
            "items": items,
            "failures": failures,
            "accepted": _accepted(first, resumed, final_frontier_stats, latest, items, failures),
        }
        if keep_db:
            kept_dir = OUTPUT_DIR / "2026-05-14_spider_runtime_smoke_runtime"
            if kept_dir.exists():
                shutil.rmtree(kept_dir)
            shutil.copytree(temp_dir, kept_dir)
            summary["kept_db_dir"] = str(kept_dir)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _save_runner_checkpoint(
    store: CheckpointStore,
    summary: Any,
    batch_id: str,
    *,
    status: str,
) -> None:
    spider_summary = SpiderRunSummary(
        run_id=RUN_ID,
        status=status,
        batches=summary.batches,
        claimed=summary.claimed,
        succeeded=summary.succeeded,
        failed=summary.failed,
        retried=summary.retried,
        records_saved=summary.records_saved,
        discovered_urls=summary.discovered_urls,
        checkpoint_errors=summary.checkpoint_errors,
        frontier_stats=summary.frontier_stats,
    )
    store.save_batch_checkpoint(
        run_id=RUN_ID,
        batch_id=batch_id,
        frontier_items=[],
        summary=spider_summary,
        events=[
            make_spider_event(
                "checkpoint_saved",
                "spider runtime smoke checkpoint saved",
                batch_id=batch_id,
                claimed=summary.claimed,
            )
        ],
    )


def _accepted(
    first: Any,
    resumed: Any,
    final_frontier_stats: dict[str, int],
    latest: dict[str, Any],
    items: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> bool:
    titles = {item.get("record", {}).get("title") for item in items}
    return (
        first.claimed == 1
        and first.succeeded == 1
        and first.discovered_urls == 2
        and resumed.claimed == 3
        and resumed.succeeded == 2
        and resumed.failed == 1
        and final_frontier_stats.get("done") == 3
        and final_frontier_stats.get("failed") == 1
        and latest.get("run", {}).get("status") == "completed"
        and latest.get("latest_checkpoint") is not None
        and latest.get("item_count") == 2
        and latest.get("failure_count") == 1
        and titles == {"Alpha Runner", "Beta Trail"}
        and len(failures) == 1
        and failures[0].get("bucket") == "runtime_error"
    )


def _first(values: list[Any] | None) -> str:
    if not values:
        return ""
    return str(values[0]).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local native spider runtime pause/resume smoke.")
    parser.add_argument("--keep-db", action="store_true")
    parser.add_argument("--output", type=Path, default=SUMMARY_PATH)
    args = parser.parse_args()
    summary = run(keep_db=args.keep_db, output_path=args.output)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0 if summary.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
