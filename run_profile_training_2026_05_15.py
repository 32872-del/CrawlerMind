#!/usr/bin/env python3
"""Offline profile-driven ecommerce training round.

Runs reusable SiteProfile examples against deterministic fixtures. This is not
real-site extraction; it is a stable training harness for DOM, API pagination,
and mixed SSR + hydration profile shapes.
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
from autonomous_crawler.runtime import NativeParserRuntime, RuntimeRequest, RuntimeResponse
from autonomous_crawler.storage.checkpoint_store import CheckpointStore
from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.product_store import ProductStore


OUTPUT_PATH = Path("dev_logs/training/2026-05-15_profile_ecommerce_training.json")
DOM_PROFILE = Path("autonomous_crawler/tests/fixtures/ecommerce_site_profile.json")
API_PROFILE = Path("autonomous_crawler/tests/fixtures/ecommerce_api_pagination_profile.json")
MIXED_PROFILE = Path("autonomous_crawler/tests/fixtures/ecommerce_mixed_hydration_profile.json")


class TrainingFetchRuntime:
    name = "profile_training_fixture_fetch"

    def __init__(self) -> None:
        self.requests: list[RuntimeRequest] = []

    def fetch(self, request: RuntimeRequest) -> RuntimeResponse:
        self.requests.append(request)
        url = request.url
        if "api-profile-shop.local" in url:
            return self._api_page(url, total=55, page_size=20)
        if "mixed-profile-shop.local/api/products" in url:
            return self._mixed_cursor_page(url)
        html = html_fixture(url)
        if html:
            return RuntimeResponse(
                ok=True,
                final_url=url,
                status_code=200,
                html=html,
                text=html,
                engine_result={"engine": self.name, "fixture": "html"},
            )
        return RuntimeResponse.failure(
            final_url=url,
            status_code=404,
            error="fixture not found",
            engine=self.name,
        )

    def _api_page(self, url: str, *, total: int, page_size: int) -> RuntimeResponse:
        query = parse_qs(urlparse(url).query)
        page = int(query.get("page", ["1"])[0])
        limit = int(query.get("limit", [str(page_size)])[0])
        start = (page - 1) * limit
        end = min(start + limit, total)
        products = [api_product(idx, host="api-profile-shop.local", currency="USD") for idx in range(start, end)]
        return json_response(url, {"data": {"products": products, "page": page, "limit": limit, "total": total}})

    def _mixed_cursor_page(self, url: str) -> RuntimeResponse:
        query = parse_qs(urlparse(url).query)
        cursor = query.get("cursor", ["start"])[0]
        ranges = {
            "start": (0, 25, "cursor-2"),
            "cursor-2": (25, 50, "cursor-3"),
            "cursor-3": (50, 60, ""),
        }
        start, end, next_cursor = ranges.get(cursor, (0, 0, ""))
        items = [
            mixed_api_product(idx)
            for idx in range(start, end)
        ]
        return json_response(url, {"payload": {"items": items, "next_cursor": next_cursor}})


def run(*, output_path: str | Path = OUTPUT_PATH) -> dict[str, Any]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    runs = [
        run_profile_case(
            profile_path=DOM_PROFILE,
            run_id="profile-training-dom-2026-05-15",
            seed_urls=["https://profile-shop.local/collections/running"],
            max_batches=10,
        ),
        run_profile_case(
            profile_path=API_PROFILE,
            run_id="profile-training-api-2026-05-15",
            seed_urls=[],
            max_batches=10,
        ),
        run_profile_case(
            profile_path=MIXED_PROFILE,
            run_id="profile-training-mixed-2026-05-15",
            seed_urls=[],
            max_batches=10,
        ),
    ]
    summary = {
        "training_round": "SCRAPLING-HARDEN-6B",
        "profiles": runs,
        "total_records": sum(int(item["record_count"]) for item in runs),
        "accepted": (
            len(runs) == 3
            and all(item["record_count"] >= item["min_items"] for item in runs)
            and sum(int(item["record_count"]) for item in runs) >= 50
        ),
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return summary


def run_profile_case(
    *,
    profile_path: Path,
    run_id: str,
    seed_urls: list[str],
    max_batches: int,
) -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"{run_id}_"))
    try:
        profile = SiteProfile.load(profile_path)
        frontier = URLFrontier(temp_dir / "frontier.sqlite3")
        product_store = ProductStore(temp_dir / "products.sqlite3")
        checkpoint_store = CheckpointStore(temp_dir / "checkpoints.sqlite3")
        checkpoint_store.start_run(run_id, {"profile": profile.name, "profile_path": str(profile_path)})
        initial = initial_requests_from_profile(profile, run_id=run_id)
        category = str(profile.quality_expectations.get("category", ""))
        for request in initial:
            frontier.add_urls(
                [request.url],
                kind=request.kind,
                priority=request.priority,
                payload={"meta": {"category": category}},
            )
        for url in seed_urls:
            frontier.add_urls(
                [url],
                kind=str(profile.crawl_preferences.get("seed_kind") or "list"),
                priority=10,
                payload={"meta": {"category": category}},
            )
        callbacks = make_ecommerce_profile_callbacks(profile, run_id=run_id)
        processor = SpiderRuntimeProcessor(
            run_id=run_id,
            fetch_runtime=TrainingFetchRuntime(),
            parser=NativeParserRuntime(),
            checkpoint_store=checkpoint_store,
            selector_builder=callbacks.selector_builder,
            record_builder=callbacks.record_builder,
            link_builder=callbacks.link_builder,
        )
        runner_summary = BatchRunner(
            frontier=frontier,
            processor=processor,
            config=BatchRunnerConfig(run_id=run_id, batch_size=5, max_batches=max_batches),
            checkpoint=ProductRecordCheckpoint(product_store),
        ).run()
        final_stats = frontier.stats()
        records = product_store.list_records(run_id, limit=10000)
        failures = checkpoint_store.list_failures(run_id)
        checkpoint_store.mark_completed(run_id)
        stop_reason = stop_reason_for_profile(profile=profile, frontier_stats=final_stats, records=records)
        quality = profile_quality_summary(
            records,
            failed_urls=[failure["url"] for failure in failures],
            pagination_stop_reason=stop_reason,
            frontier_stats=final_stats,
            quality_policy=profile.quality_expectations,
        )
        sample_records = [
            {
                "title": record.title,
                "price": record.highest_price,
                "category": record.category,
                "description": record.description,
                "image_urls": record.image_urls[:2],
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
            runtime_backend="profile_training_fixture_fetch",
            parser_backend=str(profile.crawl_preferences.get("parser") or "native_parser"),
            stop_reason=stop_reason,
            target=profile.api_hints.get("endpoint") or ",".join(seed_urls),
            notes=list(profile.training_notes),
        )
        return {
            "profile": profile.name,
            "profile_path": str(profile_path),
            "record_count": len(records),
            "min_items": int(profile.quality_expectations.get("min_items") or 0),
            "runner": runner_summary.as_dict(),
            "frontier_stats": final_stats,
            "quality_summary": quality,
            "report": report,
            "sample_records": sample_records,
            "record_modes": sorted({record.mode for record in records}),
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def stop_reason_for_profile(
    *,
    profile: SiteProfile,
    frontier_stats: dict[str, int],
    records: list[Any],
) -> str:
    if frontier_stats.get("failed"):
        return "failed_urls_present"
    if frontier_stats.get("queued") or frontier_stats.get("running"):
        return "runner_bounded_before_exhaustion"
    mode = profile.pagination_type()
    if mode == "cursor":
        return "no_next_cursor"
    if mode == "page":
        return "max_pages"
    if mode == "offset":
        return "offset_limit"
    if records:
        return "dom_link_frontier_exhausted"
    return "no_records"


def html_fixture(url: str) -> str:
    if url == "https://profile-shop.local/collections/running":
        links = "\n".join(
            f'<section class="product-card"><a class="product-link" href="/products/dom-{idx:02d}">DOM {idx:02d}</a></section>'
            for idx in range(60)
        )
        return f"<html><body><main id='catalog'>{links}</main></body></html>"
    if "profile-shop.local/products/dom-" in url:
        idx = int(url.rsplit("-", 1)[-1])
        return product_detail_html(
            title=f"DOM Product {idx:02d}",
            price=20 + idx / 10,
            category="training-shoes",
            image=f"/images/dom-{idx:02d}.jpg",
            description=f"DOM fixture product {idx:02d}",
        )
    if url == "https://mixed-profile-shop.local/collections/hydrated-training":
        links = "\n".join(
            f'<article class="product-card"><a class="product-link" href="/products/mixed-{idx:02d}">Mixed {idx:02d}</a></article>'
            for idx in range(10)
        )
        return f"<html><body><main id='hydrated-catalog'>{links}</main></body></html>"
    if "mixed-profile-shop.local/products/mixed-" in url:
        idx = int(url.rsplit("-", 1)[-1])
        return product_detail_html(
            title=f"Mixed DOM Product {idx:02d}",
            price=30 + idx / 10,
            category="hydrated-training",
            image=f"/images/mixed-dom-{idx:02d}.jpg",
            description=f"Mixed SSR fallback product {idx:02d}",
            price_attr=True,
        )
    return ""


def product_detail_html(
    *,
    title: str,
    price: float,
    category: str,
    image: str,
    description: str,
    price_attr: bool = False,
) -> str:
    price_markup = (
        f'<span data-price="{price:.2f}">{price:.2f}</span>'
        if price_attr
        else f'<span class="price">${price:.2f}</span>'
    )
    return f"""
    <html><body>
      <article class="product" data-category="{category}">
        <h1>{title}</h1>
        {price_markup}
        <span class="color" data-color="Black">Black</span>
        <span class="swatch" data-color="Blue">Blue</span>
        <span class="size">42</span>
        <span class="size">43</span>
        <p class="description">{description}</p>
        <img class="product-photo" src="{image}" />
      </article>
    </body></html>
    """


def api_product(idx: int, *, host: str, currency: str) -> dict[str, Any]:
    return {
        "name": f"API Product {idx:02d}",
        "price": {"amount": 10 + idx / 10, "currency": currency},
        "url": f"https://{host}/products/{idx:02d}",
        "variants": {"colors": ["Black", "Blue"], "sizes": ["40", "41", "42"]},
        "description": f"API fixture product {idx:02d}",
        "media": {"images": [f"/images/api-product-{idx:02d}.jpg"]},
    }


def mixed_api_product(idx: int) -> dict[str, Any]:
    return {
        "title": f"Mixed API Product {idx:02d}",
        "pricing": {"current": 30 + idx / 10, "currency": "EUR"},
        "href": f"https://mixed-profile-shop.local/products/api-{idx:02d}",
        "facets": {"colors": ["Navy", "Grey"], "sizes": ["S", "M", "L"]},
        "summary": f"Hydration API fixture product {idx:02d}",
        "images": [f"/images/mixed-api-{idx:02d}.jpg"],
    }


def json_response(url: str, payload: dict[str, Any]) -> RuntimeResponse:
    return RuntimeResponse(
        ok=True,
        final_url=url,
        status_code=200,
        text=json.dumps(payload),
        engine_result={"engine": "profile_training_fixture_fetch", "fixture": "json"},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline profile ecommerce training fixtures.")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    args = parser.parse_args()
    summary = run(output_path=args.output)
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))
    return 0 if summary.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
