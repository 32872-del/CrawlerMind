"""REAL-HARDEN-2: Real public API/GraphQL 50+ records training.

Trains CLM's API pagination and GraphQL extraction against real public
endpoints.  Produces evidence regardless of success/failure.  Does NOT
modify runtime to adapt to any single site.

Targets:
- DummyJSON products API (REST, page/limit, 100+ items)
- Countries GraphQL (nested fields)
- AniList GraphQL (cursor pagination, nested fields)

Usage:
    python run_real_api_training_2026_05_15.py
    python run_real_api_training_2026_05_15.py --skip-network  # offline mode

All results saved to dev_logs/training/.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

from autonomous_crawler.tools.api_candidates import (
    PaginatedResult,
    PaginationSpec,
    extract_records_from_json,
    fetch_json_api,
    normalize_api_records,
)
from autonomous_crawler.tools.strategy_evidence import (
    build_strategy_evidence_report,
    has_high_crypto_replay_risk,
)


# ---------------------------------------------------------------------------
# Target definitions
# ---------------------------------------------------------------------------

TARGETS: list[dict[str, Any]] = [
    {
        "name": "dummyjson_products",
        "kind": "rest",
        "url": "https://dummyjson.com/products?limit=100&skip=0",
        "description": "DummyJSON products API — 100+ items, page/limit pagination",
        "expected_min_items": 50,
    },
    {
        "name": "dummyjson_products_paginated",
        "kind": "rest_paginated",
        "base_url": "https://dummyjson.com/products?limit=30&skip=0",
        "pagination": PaginationSpec(
            type="offset", offset_param="skip", limit_param="limit",
            limit=30, max_pages=5,
        ),
        "description": "DummyJSON products — offset pagination, 30 per page, 5 pages",
        "expected_min_items": 50,
    },
    {
        "name": "countries_graphql",
        "kind": "graphql",
        "url": "https://countries.trevorblades.com/graphql",
        "query": "{ countries { code name capital continent { name } languages { name } } }",
        "description": "Countries GraphQL — nested fields, all countries",
        "expected_min_items": 50,
    },
    {
        "name": "anilist_graphql",
        "kind": "graphql",
        "url": "https://graphql.anilist.co",
        "query": """
        query {
            Page(page: 1, perPage: 50) {
                media(type: ANIME, sort: POPULARITY_DESC) {
                    id
                    title { romaji english native }
                    format
                    status
                    episodes
                    averageScore
                    genres
                    coverImage { large }
                }
            }
        }
        """,
        "description": "AniList GraphQL — anime list with nested title/coverImage",
        "expected_min_items": 50,
    },
]


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _fetch_rest(target: dict[str, Any]) -> dict[str, Any]:
    """Fetch a REST JSON API."""
    url = target["url"]
    try:
        result = fetch_json_api(url)
        records = extract_records_from_json(result.get("data"))
        normalized = normalize_api_records(records)
        return {
            "target": target["name"],
            "kind": "rest",
            "ok": result.get("ok", False),
            "status_code": result.get("status_code", 0),
            "raw_records": len(records),
            "normalized_records": len(normalized),
            "meets_threshold": len(normalized) >= target.get("expected_min_items", 50),
            "sample_titles": [r.get("title") for r in normalized[:10]],
            "sample_fields": list(normalized[0].keys()) if normalized else [],
            "error": None,
        }
    except Exception as exc:
        return {
            "target": target["name"],
            "kind": "rest",
            "ok": False,
            "status_code": 0,
            "raw_records": 0,
            "normalized_records": 0,
            "meets_threshold": False,
            "sample_titles": [],
            "sample_fields": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def _fetch_rest_paginated(target: dict[str, Any]) -> dict[str, Any]:
    """Fetch a paginated REST API."""
    url = target["base_url"]
    pagination = target["pagination"]
    try:
        result = fetch_paginated_api(url, pagination=pagination)
        return {
            "target": target["name"],
            "kind": "rest_paginated",
            "ok": True,
            "total_items": len(result.all_items),
            "pages_fetched": result.pages_fetched,
            "stop_reason": result.stop_reason,
            "deduplicated_count": result.deduplicated_count,
            "meets_threshold": len(result.all_items) >= target.get("expected_min_items", 50),
            "sample_titles": [r.get("title") for r in result.all_items[:10]],
            "sample_fields": list(result.all_items[0].keys()) if result.all_items else [],
            "error": None,
        }
    except Exception as exc:
        return {
            "target": target["name"],
            "kind": "rest_paginated",
            "ok": False,
            "total_items": 0,
            "pages_fetched": 0,
            "stop_reason": "",
            "deduplicated_count": 0,
            "meets_threshold": False,
            "sample_titles": [],
            "sample_fields": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def _fetch_graphql(target: dict[str, Any]) -> dict[str, Any]:
    """Fetch a GraphQL endpoint."""
    url = target["url"]
    query = target["query"]
    try:
        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=15.0),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        ) as client:
            response = client.post(url, json={"query": query})
            status_code = response.status_code
            try:
                data = response.json()
            except Exception:
                data = {"_raw": response.text[:500]}

        # Extract records from various GraphQL response shapes
        records: list[dict[str, Any]] = []
        if isinstance(data, dict):
            inner = data.get("data", data)
            if isinstance(inner, dict):
                # Try common shapes
                for key in ("countries", "Page", "media", "characters", "results"):
                    val = inner.get(key)
                    if isinstance(val, list):
                        records = [v for v in val if isinstance(v, dict)]
                        break
                    if isinstance(val, dict):
                        # AniList Page shape: { media: [...] }
                        for sub_val in val.values():
                            if isinstance(sub_val, list):
                                records = [v for v in sub_val if isinstance(v, dict)]
                                break
                        if records:
                            break
            if not records and isinstance(inner, list):
                records = [v for v in inner if isinstance(v, dict)]

        normalized = normalize_api_records(records)

        # Build recon for evidence analysis
        report = build_strategy_evidence_report({
            "api_candidates": [{
                "url": url,
                "method": "POST",
                "kind": "graphql",
                "score": 70,
                "status_code": status_code,
            }],
        })

        return {
            "target": target["name"],
            "kind": "graphql",
            "ok": 200 <= status_code < 400,
            "status_code": status_code,
            "raw_records": len(records),
            "normalized_records": len(normalized),
            "meets_threshold": len(normalized) >= target.get("expected_min_items", 50),
            "sample_titles": [r.get("title") or r.get("name") for r in normalized[:10]],
            "sample_fields": list(normalized[0].keys()) if normalized else [],
            "has_errors": bool(data.get("errors")) if isinstance(data, dict) else False,
            "error_count": len(data.get("errors", [])) if isinstance(data, dict) else 0,
            "evidence_signals": [s.code for s in report.signals],
            "replay_risk": has_high_crypto_replay_risk(report),
            "error": None,
        }
    except Exception as exc:
        return {
            "target": target["name"],
            "kind": "graphql",
            "ok": False,
            "status_code": 0,
            "raw_records": 0,
            "normalized_records": 0,
            "meets_threshold": False,
            "sample_titles": [],
            "sample_fields": [],
            "has_errors": False,
            "error_count": 0,
            "evidence_signals": [],
            "replay_risk": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


# We need fetch_paginated_api from api_candidates
from autonomous_crawler.tools.api_candidates import fetch_paginated_api


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="REAL-HARDEN-2: Real public API/GraphQL training")
    parser.add_argument("--skip-network", action="store_true", help="Skip network requests (offline mode)")
    parser.add_argument("--output", type=str, default="dev_logs/training/", help="Output directory")
    args = parser.parse_args()

    print("=" * 70)
    print("REAL-HARDEN-2: Real Public API/GraphQL Training")
    print("=" * 70)
    print()

    results: list[dict[str, Any]] = []
    t0 = time.monotonic()

    for target in TARGETS:
        name = target["name"]
        kind = target["kind"]
        print(f"  [{name}] {target['description']}")

        if args.skip_network:
            result = {
                "target": name,
                "kind": kind,
                "ok": False,
                "status_code": 0,
                "meets_threshold": False,
                "error": "skipped (offline mode)",
            }
        elif kind == "rest":
            result = _fetch_rest(target)
        elif kind == "rest_paginated":
            result = _fetch_rest_paginated(target)
        elif kind == "graphql":
            result = _fetch_graphql(target)
        else:
            result = {"target": name, "kind": kind, "error": f"unknown kind: {kind}"}

        results.append(result)

        # Print result
        ok = result.get("ok", False)
        meets = result.get("meets_threshold", False)
        err = result.get("error")
        items = result.get("normalized_records") or result.get("total_items") or 0

        status = "OK" if ok and meets else ("PARTIAL" if ok else "FAIL")
        if err:
            status = f"ERROR: {err}"
        print(f"    Status:   {status}")
        print(f"    Items:    {items}")
        if result.get("sample_titles"):
            print(f"    Sample:   {result['sample_titles'][:5]}")
        if result.get("stop_reason"):
            print(f"    Stop:     {result['stop_reason']}")
        if result.get("evidence_signals"):
            print(f"    Signals:  {result['evidence_signals']}")
        if result.get("replay_risk"):
            print(f"    Replay:   RISK")
        print()

    elapsed = time.monotonic() - t0

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r.get("meets_threshold"))
    partial = sum(1 for r in results if r.get("ok") and not r.get("meets_threshold"))
    failed = sum(1 for r in results if not r.get("ok"))
    print(f"  Targets:  {len(results)} total, {passed} passed, {partial} partial, {failed} failed")
    print(f"  Elapsed:  {round(elapsed, 1)}s")
    print()

    for r in results:
        items = r.get("normalized_records") or r.get("total_items") or 0
        status = "PASS" if r.get("meets_threshold") else ("OK" if r.get("ok") else "FAIL")
        err = r.get("error", "")
        err_str = f" ({err})" if err and "skipped" not in str(err) else ""
        print(f"  [{status}] {r['target']}: {items} items{err_str}")
    print("=" * 70)

    # Save report
    report = {
        "task": "REAL-HARDEN-2",
        "worker": "LLM-2026-002",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "partial": partial,
            "failed": failed,
        },
    }
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"real_api_training_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"\nReport saved to: {out_path}")


if __name__ == "__main__":
    main()
