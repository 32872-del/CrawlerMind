#!/usr/bin/env python3
"""Profile-driven ecommerce runner smoke.

This smoke stays offline. It proves a CLM `SiteProfile` can drive selectors,
link discovery, product record construction, checkpoint writes, and
pause/resume through `BatchRunner`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from autonomous_crawler.runners import (
    BatchRunner,
    BatchRunnerConfig,
    ProductRecordCheckpoint,
    SpiderRunSummary,
    SpiderRuntimeProcessor,
    make_spider_event,
    make_ecommerce_profile_callbacks,
)
from autonomous_crawler.runtime import NativeParserRuntime, RuntimeEvent, RuntimeRequest, RuntimeResponse
from autonomous_crawler.runners.site_profile import SiteProfile
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore


RUN_ID = "profile-ecommerce-runner-2026-05-14"
BASE_URL = "https://profile-shop.local"
PROFILE_PATH = Path("autonomous_crawler/tests/fixtures/ecommerce_site_profile.json")
OUTPUT_PATH = Path("dev_logs/smoke/2026-05-14_profile_ecommerce_runner_smoke.json")


HTML_FIXTURES = {
    f"{BASE_URL}/collections/running": """
        <html>
          <body>
            <main id="catalog">
              <section class="product-card">
                <a class="product-link" href="/products/alpha-runner">Alpha Runner</a>
              </section>
              <section class="product-card">
                <a class="product-link" href="/products/beta-trail?variant=blue">Beta Trail</a>
              </section>
              <a class="asset-link" href="/assets/banner.jpg">asset</a>
              <a class="offsite-link" href="https://other.example/products/offsite">offsite</a>
            </main>
          </body>
        </html>
    """,
    f"{BASE_URL}/products/alpha-runner": """
        <html>
          <body>
            <article class="product">
              <h1>Alpha Runner</h1>
              <span class="price">$19.90</span>
              <span class="color">Black</span>
              <span class="color">White</span>
              <span class="size">42</span>
              <span class="size">43</span>
              <p class="description">Lightweight road training shoe.</p>
              <img class="product-photo" src="/images/alpha.jpg" />
            </article>
          </body>
        </html>
    """,
    f"{BASE_URL}/products/beta-trail?variant=blue": """
        <html>
          <body>
            <article class="product">
              <h1>Beta Trail</h1>
              <span class="price">$29.50</span>
              <span class="color">Blue</span>
              <span class="size">41</span>
              <span class="size">44</span>
              <p class="description">Trail shoe fixture with stable selectors.</p>
              <img class="product-photo" src="/images/beta.jpg" />
            </article>
          </body>
        </html>
    """,
}


class FixtureFetchRuntime:
    name = "profile_fixture_fetch"

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
                events=[RuntimeEvent(type="fetch_complete", message="fixture missing")],
            )
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            html=html,
            text=html,
            runtime_events=[RuntimeEvent(type="fetch_complete", message="fixture fetch completed")],
            engine_result={"engine": self.name},
        )


def run(
    *,
    output_path: str | Path | None = None,
    profile_path: str | Path = PROFILE_PATH,
    keep_db: bool = False,
) -> dict[str, object]:
    output = Path(output_path) if output_path else OUTPUT_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="clm_profile_ecommerce_runner_"))
    try:
        profile = SiteProfile.load(profile_path)
        frontier = URLFrontier(temp_dir / "frontier.sqlite3")
        checkpoint_store = CheckpointStore(temp_dir / "checkpoints.sqlite3")
        product_store = ProductStore(temp_dir / "products.sqlite3")
        checkpoint_store.start_run(RUN_ID, {"profile": profile.name, "profile_path": str(profile_path)})

        frontier.add_urls(
            [f"{BASE_URL}/collections/running"],
            priority=10,
            kind="list",
            payload={"max_retries": 1, "meta": {"category": profile.quality_expectations.get("category", "")}},
        )
        callbacks = make_ecommerce_profile_callbacks(profile, run_id=RUN_ID)
        processor = SpiderRuntimeProcessor(
            run_id=RUN_ID,
            fetch_runtime=FixtureFetchRuntime(HTML_FIXTURES),
            parser=NativeParserRuntime(),
            checkpoint_store=checkpoint_store,
            selector_builder=callbacks.selector_builder,
            record_builder=callbacks.record_builder,
            link_builder=callbacks.link_builder,
        )

        first = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(
                run_id=RUN_ID,
                worker_id="profile-ecommerce-pass-1",
                batch_size=1,
                max_batches=1,
            ),
            checkpoint=ProductRecordCheckpoint(product_store),
        ).run()
        after_first_stats = frontier.stats()
        _save_runner_checkpoint(checkpoint_store, first, "pass-1", status="paused")
        checkpoint_store.mark_paused(RUN_ID, "profile smoke bounded first pass")

        resumed = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(
                run_id=RUN_ID,
                worker_id="profile-ecommerce-resume",
                batch_size=10,
            ),
            checkpoint=ProductRecordCheckpoint(product_store),
        ).run()
        final_frontier_stats = frontier.stats()
        _save_runner_checkpoint(checkpoint_store, resumed, "resume", status="completed")
        if not final_frontier_stats.get("queued") and not final_frontier_stats.get("running"):
            checkpoint_store.mark_completed(RUN_ID)

        records = product_store.list_records(RUN_ID, limit=100)
        checkpoint_latest = checkpoint_store.load_latest(RUN_ID) or {}
        summary: dict[str, object] = {
            "run_id": RUN_ID,
            "profile_path": str(profile_path),
            "profile_schema_example": profile.to_dict(),
            "first_pass": first.as_dict(),
            "after_first_frontier_stats": after_first_stats,
            "resume_pass": resumed.as_dict(),
            "final_frontier_stats": final_frontier_stats,
            "collected_record_count": len(records),
            "records": [
                {
                    "title": record.title,
                    "price": record.highest_price,
                    "currency": record.currency,
                    "colors": record.colors,
                    "sizes": record.sizes,
                    "image_urls": record.image_urls,
                    "category": record.category,
                    "dedupe_key": record.dedupe_key,
                }
                for record in records
            ],
            "product_store_stats": product_store.get_run_stats(RUN_ID),
            "checkpoint_latest": checkpoint_latest,
            "accepted": (
                first.claimed == 1
                and first.discovered_urls == 2
                and after_first_stats.get("queued") == 2
                and resumed.claimed == 2
                and resumed.succeeded == 2
                and final_frontier_stats == {"done": 3}
                and len(records) == 2
                and {record.title for record in records} == {"Alpha Runner", "Beta Trail"}
                and checkpoint_latest.get("run", {}).get("status") == "completed"
            ),
            "known_gap": (
                "Fixture proves profile-driven selectors/link discovery/checkpointing; "
                "real ecommerce still needs dynamic rendering fallback, API pagination, "
                "anti-bot access decisions, and larger catalog regression runs."
            ),
        }
        if keep_db:
            kept_dir = output.parent / "2026-05-14_profile_ecommerce_runner_runtime"
            if kept_dir.exists():
                shutil.rmtree(kept_dir)
            shutil.copytree(temp_dir, kept_dir)
            summary["kept_db_dir"] = str(kept_dir)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return summary
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _save_runner_checkpoint(
    store: CheckpointStore,
    summary: object,
    batch_id: str,
    *,
    status: str,
) -> None:
    spider_summary = SpiderRunSummary(
        run_id=RUN_ID,
        status=status,
        batches=int(getattr(summary, "batches", 0)),
        claimed=int(getattr(summary, "claimed", 0)),
        succeeded=int(getattr(summary, "succeeded", 0)),
        failed=int(getattr(summary, "failed", 0)),
        retried=int(getattr(summary, "retried", 0)),
        records_saved=int(getattr(summary, "records_saved", 0)),
        discovered_urls=int(getattr(summary, "discovered_urls", 0)),
        checkpoint_errors=int(getattr(summary, "checkpoint_errors", 0)),
        frontier_stats=dict(getattr(summary, "frontier_stats", {}) or {}),
    )
    store.save_batch_checkpoint(
        run_id=RUN_ID,
        batch_id=batch_id,
        frontier_items=[],
        summary=spider_summary,
        events=[
            make_spider_event(
                "checkpoint_saved",
                "profile ecommerce runner checkpoint saved",
                batch_id=batch_id,
                claimed=spider_summary.claimed,
                records_saved=spider_summary.records_saved,
            )
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run profile-driven ecommerce runner smoke.")
    parser.add_argument("--profile", default=str(PROFILE_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--keep-db", action="store_true")
    args = parser.parse_args()
    summary = run(output_path=args.output, profile_path=args.profile, keep_db=args.keep_db)
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))
    return 0 if summary.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
