"""High-difficulty GraphQL long-run training for CLM.

This training target comes from the real-site scenario list's GraphQL track.
It intentionally uses a public GraphQL API with cursor-like page traversal to
exercise long-running request scheduling, POST JSON execution, checkpointing,
product-store persistence, and profile-run reporting without adding site rules
to CLM core runtime code.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.runners.batch_runner import BatchRunner, BatchRunnerConfig, ItemProcessResult, ProductRecordCheckpoint
from autonomous_crawler.runners.profile_longrun import profile_quality_summary
from autonomous_crawler.runners.profile_report import build_profile_run_report
from autonomous_crawler.runners.spider_models import CrawlRequestEnvelope, SpiderRunSummary, make_spider_event
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore


GRAPHQL_ENDPOINT = "https://graphql.anilist.co"
RUN_ID = "anilist-graphql-longrun-2026-05-16"
DEFAULT_RUNTIME_DIR = Path("dev_logs/runtime/anilist_graphql_longrun_2026_05_16")
DEFAULT_REPORT_PATH = Path("dev_logs/training/2026-05-16_anilist_graphql_longrun_report.json")
DEFAULT_PRODUCTS_PATH = Path("dev_logs/training/2026-05-16_anilist_graphql_longrun_products.json")


ANILIST_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      total
      currentPage
      lastPage
      hasNextPage
      perPage
    }
    media(type: ANIME, sort: POPULARITY_DESC) {
      id
      siteUrl
      title {
        romaji
        english
        native
      }
      description(asHtml: false)
      episodes
      duration
      averageScore
      popularity
      genres
      tags {
        name
      }
      coverImage {
        large
        medium
      }
    }
  }
}
""".strip()


@dataclass
class GraphQLTrainingProcessor:
    run_id: str
    checkpoint_store: CheckpointStore
    per_page: int
    max_pages: int
    sleep_seconds: float = 0.35

    def __call__(self, item: dict[str, Any]) -> ItemProcessResult:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        page = int(payload.get("page") or 1)
        started = time.monotonic()
        try:
            response = self._post_page(page)
            records, page_info = self._records_from_response(response, page=page, source_url=str(item.get("url") or GRAPHQL_ENDPOINT))
            discovered: list[str] = []
            has_next = bool(page_info.get("hasNextPage"))
            current_page = int(page_info.get("currentPage") or page)
            next_page = current_page + 1
            if has_next and next_page <= self.max_pages:
                discovered.append(page_url(next_page, self.per_page))
            if self.sleep_seconds > 0:
                time.sleep(self.sleep_seconds)
            return ItemProcessResult.success(
                records=records,
                discovered_urls=discovered,
                page=page,
                record_count=len(records),
                has_next=has_next,
                duration_ms=round((time.monotonic() - started) * 1000, 2),
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.checkpoint_store.save_failure(
                run_id=self.run_id,
                request=CrawlRequestEnvelope(
                    run_id=self.run_id,
                    url=str(item.get("url") or GRAPHQL_ENDPOINT),
                    method="POST",
                    kind="graphql_page",
                    meta={"page": page},
                ),
                bucket="graphql_request_failed",
                error=error,
                retryable=False,
            )
            return ItemProcessResult.failure(error, retry=False, page=page)

    def _post_page(self, page: int) -> dict[str, Any]:
        import httpx

        payload = {
            "query": ANILIST_QUERY,
            "variables": {"page": page, "perPage": self.per_page},
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": "Crawler-Mind training/0.1",
        }
        with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True) as client:
            response = client.post(GRAPHQL_ENDPOINT, json=payload, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"GraphQL HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        if data.get("errors"):
            raise RuntimeError(f"GraphQL errors: {json.dumps(data.get('errors'), ensure_ascii=False)[:500]}")
        return data

    def _records_from_response(self, payload: dict[str, Any], *, page: int, source_url: str) -> tuple[list[ProductRecord], dict[str, Any]]:
        page_payload = (((payload.get("data") or {}).get("Page")) or {})
        media = page_payload.get("media") or []
        page_info = page_payload.get("pageInfo") or {}
        records: list[ProductRecord] = []
        for item in media:
            if not isinstance(item, dict):
                continue
            title_payload = item.get("title") if isinstance(item.get("title"), dict) else {}
            title = first_nonempty(
                title_payload.get("english"),
                title_payload.get("romaji"),
                title_payload.get("native"),
                f"AniList media {item.get('id')}",
            )
            cover = item.get("coverImage") if isinstance(item.get("coverImage"), dict) else {}
            tags = [
                str(tag.get("name"))
                for tag in (item.get("tags") or [])
                if isinstance(tag, dict) and tag.get("name")
            ][:10]
            popularity = item.get("popularity")
            score = item.get("averageScore")
            price_like_score = float(score or 0)
            record = ProductRecord(
                run_id=self.run_id,
                source_site="anilist-graphql",
                source_url=source_url,
                canonical_url=str(item.get("siteUrl") or f"https://anilist.co/anime/{item.get('id')}"),
                title=title,
                highest_price=price_like_score,
                currency="score",
                colors=[str(value) for value in (item.get("genres") or []) if str(value).strip()],
                sizes=tags,
                description=clean_html_text(str(item.get("description") or "")),
                image_urls=[str(url) for url in (cover.get("large"), cover.get("medium")) if url],
                category=f"graphql/anime/page-{page}",
                mode="graphql-longrun-training",
                raw_json={
                    "id": item.get("id"),
                    "averageScore": score,
                    "popularity": popularity,
                    "episodes": item.get("episodes"),
                    "duration": item.get("duration"),
                    "page": page,
                },
            )
            records.append(record)
        return records, page_info


def first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def clean_html_text(value: str) -> str:
    return (
        value.replace("<br>", " ")
        .replace("<br />", " ")
        .replace("<i>", "")
        .replace("</i>", "")
        .replace("<b>", "")
        .replace("</b>", "")
        .strip()
    )


def page_url(page: int, per_page: int) -> str:
    return f"{GRAPHQL_ENDPOINT}?clm_page={page}&perPage={per_page}"


def run_training(
    *,
    run_id: str = RUN_ID,
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
    products_path: Path = DEFAULT_PRODUCTS_PATH,
    target_records: int = 1000,
    per_page: int = 50,
    reset: bool = False,
) -> dict[str, Any]:
    max_pages = max(1, (target_records + per_page - 1) // per_page)
    if reset and runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    products_path.parent.mkdir(parents=True, exist_ok=True)

    frontier = URLFrontier(runtime_dir / "frontier.sqlite3")
    product_store = ProductStore(runtime_dir / "products.sqlite3")
    checkpoint_store = CheckpointStore(runtime_dir / "checkpoints.sqlite3")
    checkpoint_store.start_run(run_id, {
        "scenario": "anilist_graphql_longrun",
        "target_records": target_records,
        "per_page": per_page,
        "max_pages": max_pages,
    })
    frontier.add_urls(
        [page_url(1, per_page)],
        priority=100,
        kind="graphql_page",
        payload={
            "method": "POST",
            "page": 1,
            "per_page": per_page,
            "graphql_endpoint": GRAPHQL_ENDPOINT,
            "scenario": "anilist_graphql_longrun",
        },
    )
    processor = GraphQLTrainingProcessor(
        run_id=run_id,
        checkpoint_store=checkpoint_store,
        per_page=per_page,
        max_pages=max_pages,
    )
    started = time.monotonic()
    summary = BatchRunner(
        frontier=frontier,
        processor=processor,
        config=BatchRunnerConfig(
            run_id=run_id,
            worker_id="anilist-graphql-training",
            batch_size=1,
            max_batches=max_pages,
            lease_seconds=300,
            retry_failed=False,
        ),
        checkpoint=ProductRecordCheckpoint(product_store),
    ).run()

    records = product_store.list_records(run_id, limit=max(target_records + per_page, 1200))
    failures = checkpoint_store.list_failures(run_id)
    frontier_stats = frontier.stats()
    quality = profile_quality_summary(
        records,
        failed_urls=[str(item.get("url") or "") for item in failures],
        pagination_stop_reason="max_pages_reached" if len(records) >= target_records else "ended_before_target",
        frontier_stats=frontier_stats,
        quality_policy={
            "mode": "fail",
            "min_items": target_records,
            "required_fields": {
                "title": 1.0,
                "description": 0.8,
                "image_urls": 0.95,
                "highest_price": 0.95,
            },
            "max_duplicate_rate": 0.02,
            "max_failed_url_count": 0,
        },
    )
    sample_records = [record_sample(record) for record in records[:20]]
    report = build_profile_run_report(
        profile_name="anilist-graphql-longrun",
        run_id=run_id,
        runner_summary=summary,
        quality_summary=quality,
        sample_records=sample_records,
        failures=failures,
        runtime_backend="httpx_graphql_post_training",
        parser_backend="json_graphql_mapping",
        stop_reason=quality.get("pagination_stop_reason", ""),
        target=GRAPHQL_ENDPOINT,
        notes=[
            "Scenario source: real-site training list GraphQL track, AniList.",
            "Purpose: high-difficulty GraphQL POST pagination long-run training.",
            "No site-specific core runtime changes; training logic is isolated in this script.",
        ],
    )
    accepted = (
        int(quality.get("total_records") or 0) >= target_records
        and not bool((quality.get("quality_gate") or {}).get("should_fail"))
        and not failures
    )
    checkpoint_store.save_batch_checkpoint(
        run_id=run_id,
        batch_id="anilist-graphql-final",
        frontier_items=[],
        summary=SpiderRunSummary(
            run_id=run_id,
            status="completed" if accepted else "failed",
            batches=summary.batches,
            claimed=summary.claimed,
            succeeded=summary.succeeded,
            failed=summary.failed,
            records_saved=summary.records_saved,
            frontier_stats=frontier_stats,
        ),
        events=[
            make_spider_event(
                "checkpoint_saved",
                "AniList GraphQL training final checkpoint",
                {"record_count": len(records), "accepted": accepted},
            )
        ],
    )
    if accepted:
        checkpoint_store.mark_completed(run_id)
    else:
        checkpoint_store.mark_paused(run_id, "training did not meet acceptance gate")

    result = {
        "accepted": accepted,
        "run_id": run_id,
        "scenario": "anilist_graphql_longrun",
        "source_from_training_list": "GraphQL / AniList",
        "target": GRAPHQL_ENDPOINT,
        "target_records": target_records,
        "record_count": len(records),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "runner_summary": summary.as_dict(),
        "frontier_stats": frontier_stats,
        "quality_summary": quality,
        "report": report,
        "sample_records": sample_records,
        "runtime_dir": str(runtime_dir),
        "products_path": str(products_path),
    }
    products_payload = [record_sample(record, include_raw=True) for record in records]
    products_path.write_text(json.dumps(products_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return result


def record_sample(record: ProductRecord, *, include_raw: bool = False) -> dict[str, Any]:
    payload = {
        "title": record.title,
        "canonical_url": record.canonical_url,
        "highest_price": record.highest_price,
        "currency": record.currency,
        "colors": list(record.colors),
        "sizes": list(record.sizes),
        "description": record.description[:400],
        "image_urls": list(record.image_urls),
        "category": record.category,
        "mode": record.mode,
    }
    if include_raw:
        payload["raw_json"] = record.raw_json or {}
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AniList GraphQL long-run training.")
    parser.add_argument("--target-records", type=int, default=1000)
    parser.add_argument("--per-page", type=int, default=50)
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--products", type=Path, default=DEFAULT_PRODUCTS_PATH)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    result = run_training(
        run_id=args.run_id,
        runtime_dir=args.runtime_dir,
        report_path=args.report,
        products_path=args.products,
        target_records=args.target_records,
        per_page=args.per_page,
        reset=args.reset,
    )
    print(json.dumps({
        "accepted": result["accepted"],
        "scenario": result["scenario"],
        "record_count": result["record_count"],
        "elapsed_seconds": result["elapsed_seconds"],
        "report": str(args.report),
        "products": str(args.products),
        "runtime_dir": str(args.runtime_dir),
        "quality_gate": result["quality_summary"].get("quality_gate", {}),
    }, ensure_ascii=False, indent=2, default=str))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
