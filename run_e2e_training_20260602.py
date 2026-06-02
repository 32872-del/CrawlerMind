#!/usr/bin/env python3
"""E2E training run v2 - 2026-06-02.

Extends v1 with:
- Managed action loop testing (analyze -> act -> run -> repair)
- Price range parsing validation
- Pagination follow testing
- SPA auto-upgrade validation
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, ".")

from autonomous_crawler.llm import OpenAICompatibleAdvisor, LLMConfigurationError
from run_skeleton import run_crawl

OUTPUT_DIR = Path("dev_logs/training/e2e_run_20260602")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# Training targets
# ──────────────────────────────────────────────────────────────
TARGETS = {
    # Batch 1 - Easy (JSON API)
    "batch1_dummyjson_products": {
        "url": "https://dummyjson.com/products",
        "goal": "extract all products with title, price, category, rating, stock, brand from JSON API",
        "max_items": 30,
        "batch": 1,
        "difficulty": "easy",
    },
    "batch1_dummyjson_categories": {
        "url": "https://dummyjson.com/products/categories",
        "goal": "extract all product category names and slugs from JSON API",
        "max_items": 50,
        "batch": 1,
        "difficulty": "easy",
    },
    "batch1_jsonplaceholder_posts": {
        "url": "https://jsonplaceholder.typicode.com/posts",
        "goal": "extract all posts with userId, id, title, body from JSON API",
        "max_items": 30,
        "batch": 1,
        "difficulty": "easy",
    },
    # Batch 2 - Medium (SSR E-commerce)
    "batch2_scrapingcourse_ecommerce": {
        "url": "https://www.scrapingcourse.com/ecommerce/",
        "goal": "extract product names, prices, images, and URLs from ecommerce product listings",
        "max_items": 30,
        "batch": 2,
        "difficulty": "medium",
    },
    "batch2_scrapingcourse_pagination": {
        "url": "https://www.scrapingcourse.com/pagination/",
        "goal": "extract product names, prices from paginated product listings, follow all pages",
        "max_items": 100,
        "batch": 2,
        "difficulty": "medium",
        "test_pagination": True,
    },
    # Batch 3 - Harder (Real E-commerce)
    "batch3_marksandspencer": {
        "url": "https://www.marksandspencer.com/",
        "goal": "extract product names, prices, and categories from the homepage or product listings",
        "max_items": 20,
        "batch": 3,
        "difficulty": "hard",
    },
    "batch3_nike": {
        "url": "https://www.nike.com/",
        "goal": "extract product names, prices, and categories from product listings",
        "max_items": 20,
        "batch": 3,
        "difficulty": "hard",
        "test_spa_upgrade": True,
    },
    "batch3_superdry": {
        "url": "https://www.superdry.com/",
        "goal": "extract product names, prices, and categories from product listings",
        "max_items": 20,
        "batch": 3,
        "difficulty": "hard",
    },
}


def build_advisor():
    """Build LLM advisor from config."""
    config_path = Path("clm_config.json")
    if not config_path.exists():
        return None
    config = json.loads(config_path.read_text(encoding="utf-8"))
    llm = config.get("llm", {})
    if not llm.get("enabled", False):
        return None
    try:
        return OpenAICompatibleAdvisor.from_config(config)
    except Exception:
        return None


def run_single_site(name: str, target: dict, advisor=None) -> dict:
    """Run a single site crawl and return results."""
    result = {
        "site": name,
        "url": target["url"],
        "goal": target["goal"],
        "batch": target["batch"],
        "difficulty": target["difficulty"],
        "status": "pending",
        "records": 0,
        "field_coverage": 0.0,
        "quality": "unknown",
        "failures": [],
        "repair_actions": [],
        "elapsed_seconds": 0.0,
        "notes": [],
        "raw_state": None,
        # v2 additions
        "pagination_followed": False,
        "spa_upgraded": False,
        "price_range_ok": True,
    }

    goal_with_limit = f"{target['goal']} limit {target.get('max_items', 30)}"

    print(f"\n{'='*70}")
    print(f"[{name}] Starting: {target['url']}")
    print(f"[{name}] Goal: {goal_with_limit}")
    print(f"{'='*70}")

    start = time.time()
    try:
        use_llm = advisor is not None
        final_state = run_crawl(
            goal_with_limit,
            target["url"],
            use_llm=use_llm,
            advisor=advisor,
        )
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 2)

        status = final_state.get("status", "unknown")
        result["status"] = status

        # Extract records
        extracted = final_state.get("extracted_data", {})
        items = []
        if isinstance(extracted, dict):
            items = extracted.get("items", extracted.get("products", extracted.get("data", [])))
            if not isinstance(items, list):
                items = []
        elif isinstance(extracted, list):
            items = extracted

        result["records"] = len(items)

        # Also check api_responses
        api_responses = final_state.get("api_responses", [])
        if api_responses and result["records"] == 0:
            for resp in api_responses:
                if isinstance(resp, dict):
                    data = resp.get("data", resp.get("items", resp.get("products", [])))
                    if isinstance(data, list):
                        result["records"] = max(result["records"], len(data))

        # Field coverage
        if items and isinstance(items[0], dict):
            sample = items[0]
            filled = sum(1 for v in sample.values() if v is not None and v != "")
            total = len(sample)
            result["field_coverage"] = round((filled / total * 100) if total > 0 else 0, 1)
            result["notes"].append(f"Sample fields: {list(sample.keys())}")

        # Quality
        if status in ("failed", "error"):
            result["quality"] = "fail"
        elif result["records"] > 0 and result["field_coverage"] >= 50:
            result["quality"] = "pass"
        elif result["records"] > 0:
            result["quality"] = "partial"
        else:
            result["quality"] = "fail"

        # v2: Check price range parsing
        if items:
            for item in items[:5]:
                price = item.get("price", item.get("highest_price"))
                if isinstance(price, str) and any(c in price for c in ["-", "–", "to"]):
                    result["price_range_ok"] = False
                    result["notes"].append(f"Price range detected in output: {price}")
                    break

        # v2: Check pagination follow
        if target.get("test_pagination"):
            visited = final_state.get("visited_urls", [])
            if len(visited) > 1:
                result["pagination_followed"] = True
                result["notes"].append(f"Pagination: visited {len(visited)} URLs")

        # v2: Check SPA auto-upgrade
        if target.get("test_spa_upgrade"):
            engine = final_state.get("engine", "")
            mode = final_state.get("mode", "")
            if "browser" in str(engine).lower() or "dynamic" in str(mode).lower():
                result["spa_upgraded"] = True
                result["notes"].append(f"SPA upgrade: engine={engine}, mode={mode}")

        # Failures
        error_log = final_state.get("error_log", [])
        if error_log:
            result["failures"] = [str(e) for e in error_log[-5:]]

        result["raw_state"] = {
            "status": status,
            "retries": final_state.get("retries", 0),
            "llm_enabled": final_state.get("llm_enabled", False),
            "visited_urls": len(final_state.get("visited_urls", [])),
        }

        print(f"[{name}] Done: status={status}, records={result['records']}, "
              f"coverage={result['field_coverage']}%, quality={result['quality']}, "
              f"elapsed={elapsed:.1f}s")

    except Exception as exc:
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 2)
        result["status"] = "error"
        result["quality"] = "fail"
        result["failures"].append(f"Exception: {type(exc).__name__}: {str(exc)[:200]}")
        print(f"[{name}] ERROR: {exc}")

    return result


def write_summary(results: list[dict], output_path: Path):
    """Write training summary with v2 metrics."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    success = sum(1 for r in results if r["quality"] == "pass")
    failed = sum(1 for r in results if r["quality"] == "fail")
    total_records = sum(r["records"] for r in results)
    avg_coverage = sum(r["field_coverage"] for r in results) / total if total else 0
    pagination_ok = sum(1 for r in results if r.get("pagination_followed"))
    spa_ok = sum(1 for r in results if r.get("spa_upgraded"))
    price_ok = sum(1 for r in results if r.get("price_range_ok", True))

    lines = [
        "# E2E Training Summary v2 - 2026-06-02",
        f"Generated: {now}",
        "",
        "## Overview",
        f"- Total sites: {total}",
        f"- Success (pass): {success}",
        f"- Failed: {failed}",
        f"- Total records: {total_records}",
        f"- Avg field coverage: {avg_coverage:.1f}%",
        "",
        "## v2 Metrics",
        f"- Pagination followed: {pagination_ok}/{sum(1 for r in results if r.get('test_pagination'))}",
        f"- SPA auto-upgrade: {spa_ok}/{sum(1 for r in results if r.get('test_spa_upgrade'))}",
        f"- Price range OK: {price_ok}/{total}",
        "",
    ]

    for batch_num in [1, 2, 3]:
        batch_results = [r for r in results if r["batch"] == batch_num]
        if batch_results:
            names = {1: "Easy", 2: "Medium", 3: "Hard"}
            lines.append(f"## Batch {batch_num} - {names[batch_num]}")
            lines.append("")
            for r in batch_results:
                icon = {"pass": "✅", "partial": "⚠️", "fail": "❌"}.get(r["quality"], "?")
                lines.append(f"### {icon} {r['site']}")
                lines.append(f"- URL: {r['url']}")
                lines.append(f"- Records: {r['records']}, Coverage: {r['field_coverage']}%")
                lines.append(f"- Elapsed: {r['elapsed_seconds']}s")
                if r.get("pagination_followed"):
                    lines.append("- Pagination: ✅ followed")
                if r.get("spa_upgraded"):
                    lines.append("- SPA: ✅ auto-upgraded to browser")
                if not r.get("price_range_ok", True):
                    lines.append("- Price: ❌ range parsing issue")
                if r["failures"]:
                    lines.append(f"- Failures: {r['failures']}")
                if r["notes"]:
                    lines.append(f"- Notes: {r['notes']}")
                lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary: {output_path}")


def main():
    print("=" * 70)
    print("E2E Training Run v2 - 2026-06-02")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 70)

    advisor = build_advisor()
    print(f"LLM: {'enabled' if advisor else 'disabled (deterministic)'}")

    results = []
    for name, target in TARGETS.items():
        result = run_single_site(name, target, advisor=advisor)
        results.append(result)

        # Incremental save
        (OUTPUT_DIR / f"{name}_result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        write_summary(results, OUTPUT_DIR / "e2e_training_summary_20260602.md")
        time.sleep(2)

    # Final
    print("\n" + "=" * 70)
    for r in results:
        icon = {"pass": "[PASS]", "partial": "[PARTIAL]", "fail": "[FAIL]"}.get(r["quality"], "[??]")
        print(f"  {icon} {r['site']}: {r['records']} records, {r['field_coverage']}%")
    pass_count = sum(1 for r in results if r["quality"] == "pass")
    total_records = sum(r["records"] for r in results)
    print(f"\nTotal: {pass_count}/{len(results)} passed, {total_records} records")

    (OUTPUT_DIR / "full_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return 0 if pass_count >= len(results) // 2 else 1


if __name__ == "__main__":
    sys.exit(main())
