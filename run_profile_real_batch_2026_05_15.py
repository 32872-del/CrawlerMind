#!/usr/bin/env python3
"""Real public profile batch training for product-like APIs."""
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


OUTPUT_PATH = Path("dev_logs/training/2026-05-15_profile_real_batch_report.json")
PROFILE_PATHS = [
    Path("autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json"),
    Path("autonomous_crawler/tests/fixtures/ecommerce_real_platzi_profile.json"),
    Path("autonomous_crawler/tests/fixtures/ecommerce_real_fakestore_profile.json"),
]


class RealBatchFixtureRuntime:
    name = "profile_real_batch_fixture"

    def __init__(self, profile: SiteProfile) -> None:
        self.profile = profile
        self.requests: list[RuntimeRequest] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        query = parse_qs(urlparse(request.url).query)
        if "dummyjson" in self.profile.name:
            skip = int(query.get("skip", ["0"])[0])
            limit = int(query.get("limit", ["25"])[0])
            payload = {"products": [dummy_product(idx) for idx in range(skip, min(skip + limit, 75))]}
            return json_response(request.url, payload)
        if "platzi" in self.profile.name:
            offset = int(query.get("offset", ["0"])[0])
            limit = int(query.get("limit", ["50"])[0])
            return json_response(request.url, [platzi_product(idx) for idx in range(offset, min(offset + limit, 100))])
        if "fakestore" in self.profile.name:
            return json_response(request.url, [fakestore_product(idx) for idx in range(20)])
        return RuntimeResponse.failure(final_url=request.url, status_code=404, error="fixture profile not found", engine=self.name)


def run(*, output_path: str | Path = OUTPUT_PATH, fixture_only: bool = False) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for profile_path in PROFILE_PATHS:
        profile = SiteProfile.load(profile_path)
        real_result = None
        if not fixture_only:
            real_result = run_profile_case(
                profile=profile,
                profile_path=profile_path,
                run_id=f"profile-real-batch-{profile.name}",
                runtime=NativeFetchRuntime(),
                label="real",
            )
        fixture_result = None
        if fixture_only or not real_result or int(real_result.get("record_count") or 0) == 0:
            fixture_result = run_profile_case(
                profile=profile,
                profile_path=profile_path,
                run_id=f"profile-real-batch-{profile.name}-fixture",
                runtime=RealBatchFixtureRuntime(profile),
                label="fixture_regression",
            )
        results.append({
            "profile": profile.name,
            "profile_path": str(profile_path),
            "real_result": real_result,
            "fixture_regression": fixture_result,
        })
    summary = {
        "task": "PROFILE-HARDEN-3 real profile training batch",
        "profiles": results,
        "total_real_records": sum(int((item.get("real_result") or {}).get("record_count") or 0) for item in results),
        "accepted": all(not bool(((item.get("real_result") or item.get("fixture_regression") or {}).get("report") or {}).get("quality_gate", {}).get("should_fail")) for item in results),
        "notes": [
            "Training uses SiteProfile files and profile runner callbacks.",
            "Site-specific endpoint and field mappings live in profile files only.",
            "Warning quality gates are allowed to surface field/count gaps without aborting the batch.",
        ],
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary


def run_profile_case(
    *,
    profile: SiteProfile,
    profile_path: Path,
    run_id: str,
    runtime: Any,
    label: str,
) -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"{run_id[:48]}_"))
    try:
        frontier = URLFrontier(temp_dir / "frontier.sqlite3")
        checkpoint_store = CheckpointStore(temp_dir / "checkpoints.sqlite3")
        product_store = ProductStore(temp_dir / "products.sqlite3")
        checkpoint_store.start_run(run_id, {"profile": profile.name, "label": label})
        seeds = initial_requests_from_profile(profile, run_id=run_id)
        for request in seeds:
            frontier.add_urls(
                [request.url],
                kind=request.kind,
                priority=request.priority,
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
        records = product_store.list_records(run_id, limit=10000)
        failures = checkpoint_store.list_failures(run_id)
        stop = stop_reason(profile, frontier_stats, records, failures)
        if not frontier_stats.get("queued") and not frontier_stats.get("running"):
            checkpoint_store.mark_completed(run_id)
        quality = profile_quality_summary(
            records,
            failed_urls=[failure["url"] for failure in failures],
            pagination_stop_reason=stop,
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
            "accepted": not bool(report["quality_gate"].get("should_fail")),
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
    mode = profile.pagination_type()
    if mode == "offset":
        return "offset_max_pages_or_empty_page"
    if mode == "page":
        return "max_pages"
    if records:
        return "frontier_exhausted"
    return "no_records"


def dummy_product(idx: int) -> dict[str, Any]:
    return {
        "id": idx + 1,
        "title": f"Fixture Dummy Product {idx + 1:02d}",
        "description": f"Deterministic DummyJSON-like product {idx + 1}",
        "category": "fixture",
        "price": round(9.0 + idx * 0.5, 2),
        "thumbnail": f"https://cdn.dummyjson.test/products/{idx + 1}/thumbnail.jpg",
        "images": [f"https://cdn.dummyjson.test/products/{idx + 1}/1.jpg"],
        "tags": ["fixture"],
    }


def platzi_product(idx: int) -> dict[str, Any]:
    return {
        "id": idx + 1,
        "title": f"Fixture Platzi Product {idx + 1:02d}",
        "price": 20 + idx,
        "description": f"Deterministic Platzi-like product {idx + 1}",
        "category": {"id": 1, "name": "Fixture"},
        "images": [f"https://cdn.platzi.test/products/{idx + 1}.jpg"],
    }


def fakestore_product(idx: int) -> dict[str, Any]:
    return {
        "id": idx + 1,
        "title": f"Fixture FakeStore Product {idx + 1:02d}",
        "price": round(5.0 + idx, 2),
        "description": f"Deterministic FakeStore-like product {idx + 1}",
        "category": "fixture",
        "image": f"https://cdn.fakestore.test/products/{idx + 1}.jpg",
    }


def json_response(url: str, payload: Any) -> RuntimeResponse:
    return RuntimeResponse(
        ok=True,
        final_url=url,
        status_code=200,
        text=json.dumps(payload),
        engine_result={"engine": "profile_real_batch_fixture", "fixture": "json"},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real public profile batch training.")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    summary = run(output_path=args.output, fixture_only=args.fixture_only)
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))
    return 0 if summary.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
