#!/usr/bin/env python3
"""REAL-HARDEN-3 real ecommerce-like profile training.

Uses a SiteProfile to run a small product catalog training batch. The default
target is DummyJSON products, a public API with product-like records and offset
pagination. If the real target is unavailable, the script keeps failure evidence
and also runs a deterministic fixture regression with the same profile shape.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from autonomous_crawler.runners import (
    BatchRunner,
    BatchRunnerConfig,
    ProductRecordCheckpoint,
    SiteProfile,
    SpiderRuntimeProcessor,
    build_profile_run_report,
    initial_requests_from_profile,
    make_ecommerce_profile_callbacks,
    profile_quality_summary,
)
from autonomous_crawler.runtime import NativeFetchRuntime, RuntimeRequest, RuntimeResponse
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore


RUN_ID = "real-ecommerce-profile-dummyjson-2026-05-15"
PROFILE_PATH = Path("autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json")
OUTPUT_PATH = Path("dev_logs/training/2026-05-15_real_ecommerce_profile_dummyjson.json")


class FixtureDummyJsonRuntime:
    name = "fixture_dummyjson"

    def __init__(self, total: int = 60) -> None:
        self.total = total
        self.requests: list[RuntimeRequest] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        query = parse_qs(urlparse(request.url).query)
        skip = int(query.get("skip", ["0"])[0])
        limit = int(query.get("limit", ["25"])[0])
        products = [dummy_product(idx) for idx in range(skip, min(skip + limit, self.total))]
        payload = {"products": products, "total": self.total, "skip": skip, "limit": limit}
        return RuntimeResponse(
            ok=True,
            final_url=request.url,
            status_code=200,
            text=json.dumps(payload),
            engine_result={"engine": self.name},
        )


def run(
    *,
    profile_path: str | Path = PROFILE_PATH,
    output_path: str | Path = OUTPUT_PATH,
    fixture_only: bool = False,
) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = SiteProfile.load(profile_path)

    real_result = None
    if not fixture_only:
        real_result = run_case(
            profile=profile,
            profile_path=Path(profile_path),
            run_id=RUN_ID,
            runtime=NativeFetchRuntime(),
            label="real",
        )

    fixture_result = None
    if fixture_only or not real_result or not real_result.get("accepted"):
        fixture_result = run_case(
            profile=profile,
            profile_path=Path(profile_path),
            run_id=f"{RUN_ID}-fixture",
            runtime=FixtureDummyJsonRuntime(),
            label="fixture_regression",
        )

    summary = {
        "task": "REAL-HARDEN-3",
        "profile_path": str(profile_path),
        "target": "https://dummyjson.com/products",
        "real_result": real_result,
        "fixture_regression": fixture_result,
        "accepted": bool(real_result and real_result.get("accepted")),
        "fallback_used": bool(fixture_result is not None),
        "notes": [
            "Training uses profile data, not runtime site rules.",
            "DummyJSON is a public product-like API; it is not a protected ecommerce site.",
        ],
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary


def run_case(
    *,
    profile: SiteProfile,
    profile_path: Path,
    run_id: str,
    runtime: Any,
    label: str,
) -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"{run_id}_"))
    try:
        frontier = URLFrontier(temp_dir / "frontier.sqlite3")
        checkpoint_store = CheckpointStore(temp_dir / "checkpoints.sqlite3")
        product_store = ProductStore(temp_dir / "products.sqlite3")
        checkpoint_store.start_run(run_id, {"profile": profile.name, "label": label})
        seeds = initial_requests_from_profile(profile, run_id=run_id)
        frontier.add_urls(
            [request.url for request in seeds],
            kind=seeds[0].kind if seeds else "api",
            priority=seeds[0].priority if seeds else 10,
            payload={"meta": {"category": profile.quality_expectations.get("category", "")}},
        )
        callbacks = make_ecommerce_profile_callbacks(profile, run_id=run_id)
        processor = SpiderRuntimeProcessor(
            run_id=run_id,
            fetch_runtime=runtime,
            checkpoint_store=checkpoint_store,
            record_builder=callbacks.record_builder,
            link_builder=callbacks.link_builder,
        )
        runner_summary = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id=run_id, batch_size=5, max_batches=10),
            checkpoint=ProductRecordCheckpoint(product_store),
        ).run()
        frontier_stats = frontier.stats()
        records = product_store.list_records(run_id, limit=1000)
        failures = checkpoint_store.list_failures(run_id)
        if not frontier_stats.get("queued") and not frontier_stats.get("running"):
            checkpoint_store.mark_completed(run_id)
        quality = profile_quality_summary(
            records,
            failed_urls=[failure["url"] for failure in failures],
            pagination_stop_reason=stop_reason(profile, frontier_stats, records, failures),
            frontier_stats=frontier_stats,
            quality_policy=profile.quality_expectations,
        )
        sample_records = [
            {
                "title": record.title,
                "price": record.highest_price,
                "category": record.category,
                "description": record.description,
                "image_urls": record.image_urls[:2],
                "canonical_url": record.canonical_url,
            }
            for record in records[:5]
        ]
        stop = stop_reason(profile, frontier_stats, records, failures)
        report = build_profile_run_report(
            profile_name=profile.name,
            profile_path=str(profile_path),
            run_id=run_id,
            runner_summary=runner_summary,
            quality_summary=quality,
            sample_records=sample_records,
            failures=failures,
            runtime_backend=getattr(runtime, "name", type(runtime).__name__),
            parser_backend="json_profile",
            stop_reason=stop,
            target=str(profile.api_hints.get("endpoint") or ""),
            notes=list(profile.training_notes),
        )
        return {
            "label": label,
            "accepted": bool(quality.get("quality_gate", {}).get("passed")),
            "record_count": len(records),
            "runner": runner_summary.as_dict(),
            "frontier_stats": frontier_stats,
            "quality_summary": quality,
            "report": report,
            "failures": failures,
            "sample_records": sample_records,
            "runtime_name": getattr(runtime, "name", type(runtime).__name__),
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def stop_reason(
    profile: SiteProfile,
    frontier_stats: dict[str, int],
    records: list[Any],
    failures: list[dict[str, Any]],
) -> str:
    if failures:
        return "failed_urls_present"
    if frontier_stats.get("queued") or frontier_stats.get("running"):
        return "runner_bounded_before_exhaustion"
    if profile.pagination_type() == "offset":
        return "offset_max_pages"
    if records:
        return "frontier_exhausted"
    return "no_records"


def dummy_product(idx: int) -> dict[str, Any]:
    categories = ["beauty", "fragrances", "furniture", "groceries"]
    return {
        "id": idx + 1,
        "title": f"Fixture Dummy Product {idx + 1:02d}",
        "description": f"Deterministic fixture product {idx + 1}",
        "category": categories[idx % len(categories)],
        "price": round(5.0 + idx * 0.75, 2),
        "thumbnail": f"https://cdn.dummyjson.test/products/{idx + 1}/thumbnail.jpg",
        "images": [
            f"https://cdn.dummyjson.test/products/{idx + 1}/1.jpg",
            f"https://cdn.dummyjson.test/products/{idx + 1}/2.jpg",
        ],
        "tags": ["fixture", categories[idx % len(categories)]],
        "dimensions": {"width": 10 + idx, "height": 20 + idx, "depth": 5 + idx},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real ecommerce-like profile training.")
    parser.add_argument("--profile", default=str(PROFILE_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    summary = run(profile_path=args.profile, output_path=args.output, fixture_only=args.fixture_only)
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))
    return 0 if summary.get("accepted") or summary.get("fixture_regression") else 1


if __name__ == "__main__":
    raise SystemExit(main())
