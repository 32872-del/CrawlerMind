#!/usr/bin/env python3
"""E2E training run for 2026-06-01 - Multi-site crawl training."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Fix Windows GBK encoding for non-ASCII characters (e.g. £, €, ¥)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, ".")

from autonomous_crawler.llm import OpenAICompatibleAdvisor, LLMConfigurationError
from run_skeleton import run_crawl

OUTPUT_DIR = Path("dev_logs/training/e2e_run_20260601")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Training targets organized by difficulty
TARGETS = {
    # Batch 1 - Easy (JSON API / SSR)
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
        "goal": "extract product names, prices from paginated product listings, follow pagination",
        "max_items": 30,
        "batch": 2,
        "difficulty": "medium",
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
        print("No clm_config.json found, running without LLM")
        return None
    config = json.loads(config_path.read_text(encoding="utf-8"))
    llm = config.get("llm", {})
    if not llm.get("enabled", False):
        return None
    try:
        return OpenAICompatibleAdvisor.from_config(config)
    except Exception as exc:
        print(f"LLM advisor build failed: {exc}")
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
    }

    goal_with_limit = f"{target['goal']} limit {target.get('max_items', 30)}"
    
    print(f"\n{'='*70}")
    print(f"[{name}] Starting crawl: {target['url']}")
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

        # Extract results from final state
        status = final_state.get("status", "unknown")
        result["status"] = status

        # Count extracted records
        extracted = final_state.get("extracted_data", {})
        if isinstance(extracted, dict):
            items = extracted.get("items", extracted.get("products", extracted.get("data", [])))
            if isinstance(items, list):
                result["records"] = len(items)
            elif isinstance(extracted, dict) and "title" in extracted:
                result["records"] = 1
        elif isinstance(extracted, list):
            result["records"] = len(extracted)

        # Check API responses too
        api_responses = final_state.get("api_responses", [])
        if api_responses and result["records"] == 0:
            for resp in api_responses:
                if isinstance(resp, dict):
                    data = resp.get("data", resp.get("items", resp.get("products", [])))
                    if isinstance(data, list):
                        result["records"] = max(result["records"], len(data))

        # Field coverage - check what fields were extracted
        if result["records"] > 0:
            sample = None
            if isinstance(extracted, dict):
                items = extracted.get("items", extracted.get("products", extracted.get("data", [])))
                if isinstance(items, list) and items:
                    sample = items[0]
            if sample and isinstance(sample, dict):
                filled = sum(1 for v in sample.values() if v is not None and v != "")
                total = len(sample)
                result["field_coverage"] = round((filled / total * 100) if total > 0 else 0, 1)
                result["notes"].append(f"Sample fields: {list(sample.keys())}")

        # Quality assessment
        status = result["status"]
        if status == "failed" or status == "error":
            result["quality"] = "fail"
        elif result["records"] > 0 and result["field_coverage"] >= 50:
            result["quality"] = "pass"
        elif result["records"] > 0:
            result["quality"] = "partial"
        else:
            result["quality"] = "fail"

        # Collect errors
        error_log = final_state.get("error_log", [])
        if error_log:
            result["failures"] = [str(e) for e in error_log[-5:]]  # Last 5 errors

        result["raw_state"] = {
            "status": status,
            "retries": final_state.get("retries", 0),
            "llm_enabled": final_state.get("llm_enabled", False),
            "visited_urls": len(final_state.get("visited_urls", [])),
            "has_api_responses": bool(api_responses),
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
        result["notes"].append(f"Traceback: {traceback.format_exc()[-500:]}")
        print(f"[{name}] ERROR: {exc}")

    return result


def format_result_markdown(result: dict) -> str:
    """Format a single result as markdown."""
    lines = [
        f"## Site: {result['url']}",
        f"- **Name**: {result['site']}",
        f"- **Batch**: {result['batch']} ({result['difficulty']})",
        f"- **Status**: {result['status']}",
        f"- **Records**: {result['records']}",
        f"- **Field coverage**: {result['field_coverage']}%",
        f"- **Quality**: {result['quality']}",
        f"- **Elapsed**: {result['elapsed_seconds']}s",
    ]
    if result["failures"]:
        lines.append(f"- **Failures**: {result['failures']}")
    if result["repair_actions"]:
        lines.append(f"- **Repair actions**: {result['repair_actions']}")
    if result["notes"]:
        lines.append(f"- **Notes**: {result['notes']}")
    lines.append("")
    return "\n".join(lines)


def write_summary(results: list[dict], output_path: Path):
    """Write the full training summary."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Stats
    total = len(results)
    success = sum(1 for r in results if r["status"] == "completed" and r["quality"] == "pass")
    partial = sum(1 for r in results if r["quality"] == "partial")
    failed = sum(1 for r in results if r["quality"] == "fail" or r["status"] == "error")
    total_records = sum(r["records"] for r in results)
    avg_coverage = sum(r["field_coverage"] for r in results) / total if total > 0 else 0

    lines = [
        "# E2E Training Summary - 2026-06-01",
        f"Generated: {now}",
        "",
        "## Overview",
        f"- Total sites: {total}",
        f"- Success (pass): {success}",
        f"- Partial: {partial}",
        f"- Failed: {failed}",
        f"- Total records extracted: {total_records}",
        f"- Average field coverage: {avg_coverage:.1f}%",
        "",
    ]

    # Group by batch
    for batch_num in [1, 2, 3]:
        batch_results = [r for r in results if r["batch"] == batch_num]
        if batch_results:
            batch_names = {1: "Easy (JSON API / SSR)", 2: "Medium (SSR E-commerce)", 3: "Harder (Real E-commerce)"}
            lines.append(f"## Batch {batch_num} - {batch_names[batch_num]}")
            lines.append("")
            for r in batch_results:
                lines.append(format_result_markdown(r))

    # Failure analysis
    failures = [r for r in results if r["failures"]]
    if failures:
        lines.append("## Failure Analysis")
        lines.append("")
        for r in failures:
            lines.append(f"### {r['site']}")
            for f in r["failures"]:
                lines.append(f"- {f}")
            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary written to: {output_path}")


def main():
    print("=" * 70)
    print("E2E Training Run - 2026-06-01")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 70)

    # Build advisor
    advisor = build_advisor()
    if advisor:
        print("LLM advisor: enabled")
    else:
        print("LLM advisor: disabled (running deterministic)")

    results = []
    
    # Run all targets in order
    for name, target in TARGETS.items():
        result = run_single_site(name, target, advisor=advisor)
        results.append(result)
        
        # Save incremental results
        incremental_path = OUTPUT_DIR / f"{name}_result.json"
        incremental_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        
        # Write running summary
        write_summary(results, OUTPUT_DIR / "e2e_training_summary_20260601.md")
        
        # Brief pause between sites
        time.sleep(2)

    # Final summary
    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    for r in results:
        status_icon = {"pass": "[PASS]", "partial": "[PARTIAL]", "fail": "[FAIL]"}.get(r["quality"], "[??]")
        print(f"  {status_icon} {r['site']}: {r['records']} records, {r['field_coverage']}% coverage, {r['elapsed_seconds']}s")

    total_records = sum(r["records"] for r in results)
    pass_count = sum(1 for r in results if r["quality"] == "pass")
    print(f"\nTotal: {pass_count}/{len(results)} passed, {total_records} records extracted")
    
    # Save full results as JSON
    full_results_path = OUTPUT_DIR / "full_results.json"
    full_results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"Full results: {full_results_path}")

    return 0 if pass_count >= len(results) // 2 else 1


if __name__ == "__main__":
    sys.exit(main())
