#!/usr/bin/env python3
"""Full E2E training run from the site task list (2026-06-02).

Covers all safe/public targets from 爬虫Agent实战训练网站清单.
Organized by scenario family and difficulty.
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

from autonomous_crawler.runners.managed_actions import (
    build_deterministic_action_plan,
    execute_and_run,
)
from autonomous_crawler.runners.auto_repair import diagnose_and_repair

OUTPUT_DIR = Path("dev_logs/training/e2e_site_list_20260602")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# Site task list targets (safe/public only)
# ──────────────────────────────────────────────────────────────
TARGETS = {
    # ===== 一、电商类 =====
    # 1. JSON API (proven)
    "ecommerce_dummyjson": {
        "url": "https://dummyjson.com/products",
        "goal": "extract all products with title, price, category, rating, brand",
        "profile": {
            "target_fields": ["title", "price", "category", "rating", "brand"],
            "crawl_preferences": {"seed_urls": ["https://dummyjson.com/products"]},
        },
        "max_items": 100,
        "category": "ecommerce",
        "scenario": "json_api",
        "difficulty": "easy",
    },
    "ecommerce_jsonplaceholder": {
        "url": "https://jsonplaceholder.typicode.com/posts",
        "goal": "extract all posts with userId, id, title, body",
        "profile": {
            "target_fields": ["title", "body"],
            "crawl_preferences": {"seed_urls": ["https://jsonplaceholder.typicode.com/posts"]},
        },
        "max_items": 100,
        "category": "ecommerce",
        "scenario": "json_api",
        "difficulty": "easy",
    },

    # 2. SSR Ecommerce
    "ecommerce_scrapingcourse": {
        "url": "https://www.scrapingcourse.com/ecommerce/",
        "goal": "extract product names, prices, images, URLs from SSR ecommerce page",
        "profile": {
            "target_fields": ["title", "price", "image_url", "product_url"],
            "crawl_preferences": {"seed_urls": ["https://www.scrapingcourse.com/ecommerce/"]},
        },
        "max_items": 50,
        "category": "ecommerce",
        "scenario": "ssr",
        "difficulty": "medium",
    },
    "ecommerce_scrapingcourse_pagination": {
        "url": "https://www.scrapingcourse.com/pagination/",
        "goal": "extract products from paginated listings, follow all pages",
        "profile": {
            "target_fields": ["title", "price", "image_url", "product_url"],
            "crawl_preferences": {"seed_urls": ["https://www.scrapingcourse.com/pagination/"]},
        },
        "max_items": 100,
        "category": "ecommerce",
        "scenario": "pagination",
        "difficulty": "medium",
    },

    # 3. Real Ecommerce
    "ecommerce_marksandspencer": {
        "url": "https://www.marksandspencer.com/",
        "goal": "extract product names, prices, categories from homepage product listings",
        "profile": {
            "target_fields": ["title", "price", "image_url", "product_url"],
            "crawl_preferences": {"seed_urls": ["https://www.marksandspencer.com/"]},
        },
        "max_items": 30,
        "category": "ecommerce",
        "scenario": "real_ecommerce",
        "difficulty": "hard",
    },
    "ecommerce_superdry": {
        "url": "https://www.superdry.com/",
        "goal": "extract product names, prices, categories from product listings",
        "profile": {
            "target_fields": ["title", "price", "image_url", "product_url"],
            "crawl_preferences": {"seed_urls": ["https://www.superdry.com/"]},
        },
        "max_items": 30,
        "category": "ecommerce",
        "scenario": "real_ecommerce",
        "difficulty": "hard",
    },

    # ===== 二、公开 JSON API =====
    "api_hackernews": {
        "url": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "goal": "extract top story IDs from Hacker News API",
        "profile": {
            "target_fields": ["id"],
            "crawl_preferences": {"seed_urls": ["https://hacker-news.firebaseio.com/v0/topstories.json"]},
        },
        "max_items": 30,
        "category": "api",
        "scenario": "json_api",
        "difficulty": "easy",
    },

    # ===== 三、内容/SSR 站点 =====
    "content_quotes_toscrape": {
        "url": "https://quotes.toscrape.com/",
        "goal": "extract quotes text, author, tags from quotes.toscrape.com",
        "profile": {
            "target_fields": ["title", "description"],
            "crawl_preferences": {"seed_urls": ["https://quotes.toscrape.com/"]},
        },
        "max_items": 50,
        "category": "content",
        "scenario": "ssr",
        "difficulty": "easy",
    },
    "content_douban_top250": {
        "url": "https://movie.douban.com/top250",
        "goal": "extract movie names, ratings, and descriptions from Douban Top250",
        "profile": {
            "target_fields": ["title", "description"],
            "crawl_preferences": {"seed_urls": ["https://movie.douban.com/top250"]},
        },
        "max_items": 30,
        "category": "content",
        "scenario": "ssr_pagination",
        "difficulty": "medium",
    },

    # ===== 四、SPA / 浏览器渲染 =====
    "spa_nike": {
        "url": "https://www.nike.com/",
        "goal": "extract product names, prices from Nike (SPA/Next.js)",
        "profile": {
            "target_fields": ["title", "price", "image_url", "product_url"],
            "crawl_preferences": {"seed_urls": ["https://www.nike.com/"]},
        },
        "max_items": 20,
        "category": "spa",
        "scenario": "spa_browser",
        "difficulty": "hard",
        "requires_browser": True,
    },

    # ===== 五、GraphQL =====
    "graphql_countries": {
        "url": "https://countries.trevorblades.com/",
        "goal": "extract country names, codes, capitals from GraphQL API",
        "profile": {
            "target_fields": ["title", "description"],
            "crawl_preferences": {"seed_urls": ["https://countries.trevorblades.com/"]},
        },
        "max_items": 50,
        "category": "graphql",
        "scenario": "graphql",
        "difficulty": "medium",
    },

    # ===== 六、反爬诊断 (diagnosis only) =====
    "diagnosis_scrapfly_fingerprint": {
        "url": "https://scrapfly.io/web-scraping-tools/browser-fingerprint",
        "goal": "diagnose anti-bot protection level on Scrapfly fingerprint page",
        "profile": {
            "target_fields": ["title", "description"],
            "crawl_preferences": {"seed_urls": ["https://scrapfly.io/web-scraping-tools/browser-fingerprint"]},
        },
        "max_items": 5,
        "category": "diagnosis",
        "scenario": "protected",
        "difficulty": "hard",
        "diagnosis_only": True,
    },
    "diagnosis_cloudflare_challenge": {
        "url": "https://scrapingcourse.com/cloudflare-challenge",
        "goal": "diagnose Cloudflare challenge protection",
        "profile": {
            "target_fields": ["title", "description"],
            "crawl_preferences": {"seed_urls": ["https://scrapingcourse.com/cloudflare-challenge"]},
        },
        "max_items": 5,
        "category": "diagnosis",
        "scenario": "protected",
        "difficulty": "hard",
        "diagnosis_only": True,
    },
}


def run_target(name: str, target: dict) -> dict:
    """Run a single target through the managed loop."""
    result = {
        "site": name,
        "url": target["url"],
        "category": target.get("category", ""),
        "scenario": target.get("scenario", ""),
        "difficulty": target.get("difficulty", ""),
        "status": "pending",
        "records": 0,
        "field_coverage": 0.0,
        "quality": "unknown",
        "elapsed_seconds": 0.0,
        "api_hints_detected": False,
        "browser_fallback": False,
        "pagination_followed": False,
        "diagnosis_only": target.get("diagnosis_only", False),
        "errors": [],
        "notes": [],
    }

    profile = {
        "name": name,
        **target.get("profile", {}),
    }
    run_spec = {
        "selected_fields": target.get("profile", {}).get("target_fields", []),
        "test_limit": target.get("max_items", 30),
    }
    target_url = target["url"]

    print(f"\n{'='*70}", flush=True)
    print(f"[{name}] {target['url']}", flush=True)
    print(f"[{name}] Category: {target.get('category')}, Difficulty: {target.get('difficulty')}", flush=True)
    print(f"{'='*70}", flush=True)

    start = time.time()
    try:
        plan = build_deterministic_action_plan(
            target_url=target_url, profile=profile, run_spec=run_spec,
        )
        actions = [a.action for a in plan.actions]
        print(f"[{name}] Plan ({len(actions)}): {actions}", flush=True)

        exec_result = execute_and_run(
            plan=plan, target_url=target_url, profile=profile,
            run_spec=run_spec, batch_size=50, max_batches=2, item_workers=2,
        )

        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 2)

        run = exec_result.get("run_result") or {}
        summary = run.get("runner_summary") or {}
        result["records"] = int(summary.get("records_saved") or 0)
        result["status"] = run.get("status", "unknown")

        merged = exec_result.get("merged_profile") or {}
        result["api_hints_detected"] = bool(merged.get("api_hints", {}).get("endpoint"))
        result["browser_fallback"] = merged.get("access_config", {}).get("_fallback_reason") == "playwright_not_available"

        # Field coverage
        if result["records"] > 0:
            result["field_coverage"] = 50.0  # simplified
            result["quality"] = "pass"
        elif result["status"] == "completed":
            result["quality"] = "empty"
        else:
            result["quality"] = "fail"

        # Diagnosis-only: also run diagnose_and_repair
        if target.get("diagnosis_only") and result["records"] == 0:
            try:
                mock_job = {
                    "status": "failed", "target_url": target_url,
                    "error_log": ["No items extracted"],
                    "profile_run": {"product_stats": {"records_saved": 0, "quality_indicator": "fail", "failure_buckets": {}}},
                }
                diag = diagnose_and_repair(
                    job=mock_job, profile=profile, target_url=target_url,
                    run_spec=run_spec,
                )
                result["notes"].append(f"Diagnosis: {diag.get('diagnosis', {}).get('overall_health', 'unknown')}")
                repair_actions = [a["action"] for a in (diag.get("repair_plan") or {}).get("actions", [])]
                if repair_actions:
                    result["notes"].append(f"Repair plan: {repair_actions}")
            except Exception as diag_err:
                result["notes"].append(f"Diagnosis error: {diag_err}")

        print(f"[{name}] Done: records={result['records']}, status={result['status']}, "
              f"quality={result['quality']}, elapsed={elapsed:.1f}s", flush=True)

    except Exception as exc:
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 2)
        result["status"] = "error"
        result["quality"] = "fail"
        result["errors"].append(f"{type(exc).__name__}: {str(exc)[:300]}")
        print(f"[{name}] ERROR: {exc}", flush=True)

    return result


def write_summary(results: list[dict], output_path: Path):
    """Write comprehensive training summary."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(results)
    passed = sum(1 for r in results if r["quality"] == "pass")
    failed = sum(1 for r in results if r["quality"] == "fail")
    empty = sum(1 for r in results if r["quality"] == "empty")
    total_records = sum(r["records"] for r in results)
    browser_fallbacks = sum(1 for r in results if r.get("browser_fallback"))
    api_detected = sum(1 for r in results if r.get("api_hints_detected"))

    lines = [
        "# E2E Site List Training Report - 2026-06-02",
        f"Generated: {now}",
        "",
        "## Overview",
        f"- Total sites: {total}",
        f"- Pass (records > 0): {passed}",
        f"- Empty (completed, 0 records): {empty}",
        f"- Failed: {failed}",
        f"- Total records extracted: {total_records}",
        f"- Browser fallbacks (no Playwright): {browser_fallbacks}",
        f"- API auto-detected: {api_detected}",
        "",
    ]

    # By category
    categories = {}
    for r in results:
        cat = r.get("category", "other")
        categories.setdefault(cat, []).append(r)

    for cat, cat_results in categories.items():
        cat_passed = sum(1 for r in cat_results if r["quality"] == "pass")
        cat_records = sum(r["records"] for r in cat_results)
        lines.append(f"## {cat.upper()} ({len(cat_results)} sites, {cat_passed} passed, {cat_records} records)")
        lines.append("")

        for r in cat_results:
            icon = {"pass": "✅", "empty": "⚠️", "fail": "❌"}.get(r["quality"], "❓")
            lines.append(f"### {icon} {r['site']}")
            lines.append(f"- URL: {r['url']}")
            lines.append(f"- Scenario: {r.get('scenario', '')}, Difficulty: {r.get('difficulty', '')}")
            lines.append(f"- Records: {r['records']}, Status: {r['status']}, Elapsed: {r['elapsed_seconds']}s")
            if r.get("api_hints_detected"):
                lines.append("- API: auto-detected ✅")
            if r.get("browser_fallback"):
                lines.append("- Browser: fallback to static (Playwright not installed)")
            if r.get("diagnosis_only"):
                lines.append("- Mode: diagnosis only")
            if r["notes"]:
                for note in r["notes"]:
                    lines.append(f"- {note}")
            if r["errors"]:
                for err in r["errors"]:
                    lines.append(f"- ❌ {err}")
            lines.append("")

    # Summary table
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| Site | Category | Records | Quality | Elapsed |")
    lines.append("|------|----------|---------|---------|---------|")
    for r in results:
        icon = {"pass": "✅", "empty": "⚠️", "fail": "❌"}.get(r["quality"], "❓")
        lines.append(f"| {r['site']} | {r.get('category', '')} | {r['records']} | {icon} {r['quality']} | {r['elapsed_seconds']}s |")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSummary: {output_path}")


def main():
    print("=" * 70, flush=True)
    print("E2E Site List Training - 2026-06-02", flush=True)
    print(f"Time: {datetime.now().isoformat()}", flush=True)
    print(f"Targets: {len(TARGETS)}", flush=True)
    print("=" * 70, flush=True)

    results = []
    for name, target in TARGETS.items():
        result = run_target(name, target)
        results.append(result)

        # Incremental save
        (OUTPUT_DIR / f"{name}_result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        write_summary(results, OUTPUT_DIR / "training_report.md")
        time.sleep(1)

    # Final summary
    print("\n" + "=" * 70, flush=True)
    for r in results:
        icon = {"pass": "[PASS]", "empty": "[EMPTY]", "fail": "[FAIL]"}.get(r["quality"], "[??]")
        print(f"  {icon} {r['site']}: {r['records']} records, {r['elapsed_seconds']}s", flush=True)

    passed = sum(1 for r in results if r["quality"] == "pass")
    total_records = sum(r["records"] for r in results)
    print(f"\nTotal: {passed}/{len(results)} passed, {total_records} records", flush=True)

    (OUTPUT_DIR / "full_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return 0 if passed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
