#!/usr/bin/env python3
"""Test the managed execute-and-run loop on real sites.

Tests the full managed loop: build_deterministic_action_plan → execute_and_run
on multiple sites with varying difficulty.
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
    ManagedActionPlan,
    build_deterministic_action_plan,
    execute_and_run,
    execute_managed_action_plan,
)
from autonomous_crawler.runners.auto_repair import (
    FailureDiagnoser,
    diagnose_and_repair,
)

OUTPUT_DIR = Path("dev_logs/training/e2e_run_20260602")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────────────────────
# Test targets
# ──────────────────────────────────────────────────────────────

MANAGED_LOOP_TARGETS = {
    "managed_dummyjson": {
        "url": "https://dummyjson.com/products",
        "profile": {
            "name": "dummyjson",
            "target_fields": ["title", "price", "category", "rating"],
            "crawl_preferences": {"seed_urls": ["https://dummyjson.com/products"]},
        },
        "run_spec": {"selected_fields": ["title", "price", "category", "rating"], "test_limit": 5},
        "difficulty": "easy",
    },
    "managed_scrapingcourse": {
        "url": "https://www.scrapingcourse.com/ecommerce/",
        "profile": {
            "name": "scrapingcourse",
            "target_fields": ["title", "price", "image_url", "product_url"],
            "crawl_preferences": {"seed_urls": ["https://www.scrapingcourse.com/ecommerce/"]},
        },
        "run_spec": {"selected_fields": ["title", "price", "image_url", "product_url"], "test_limit": 5},
        "difficulty": "medium",
    },
    "managed_marksandspencer": {
        "url": "https://www.marksandspencer.com/",
        "profile": {
            "name": "marksandspencer",
            "target_fields": ["title", "price", "image_url", "product_url"],
            "crawl_preferences": {"seed_urls": ["https://www.marksandspencer.com/"]},
        },
        "run_spec": {"selected_fields": ["title", "price", "image_url", "product_url"], "test_limit": 5},
        "difficulty": "hard",
    },
}


def run_execute_and_run_test(name: str, target: dict) -> dict:
    """Test execute_and_run() with actual crawl execution."""
    result = {
        "site": name, "url": target["url"], "difficulty": target["difficulty"],
        "test_type": "execute_and_run", "status": "pending", "elapsed_seconds": 0.0,
        "action_plan_actions": [], "applied_patch": False, "skipped_run": False,
        "records_saved": 0, "run_status": "unknown", "merged_profile_keys": [],
        "profile_patch_keys": [], "errors": [],
    }

    print(f"\n{'='*70}", flush=True)
    print(f"[{name}] Execute-and-Run Test: {target['url']}", flush=True)
    print(f"{'='*70}", flush=True)

    start = time.time()
    try:
        plan = build_deterministic_action_plan(
            target_url=target["url"], profile=target["profile"], run_spec=target["run_spec"],
        )
        result["action_plan_actions"] = [a.action for a in plan.actions]
        print(f"[{name}] Action plan ({len(plan.actions)}): {result['action_plan_actions']}", flush=True)

        exec_result = execute_and_run(
            plan=plan, target_url=target["url"], profile=target["profile"],
            run_spec=target["run_spec"],
        )
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 2)
        result["applied_patch"] = exec_result.get("applied_patch", False)
        result["skipped_run"] = exec_result.get("skipped_run", False)
        result["records_saved"] = exec_result.get("records_saved", 0)
        result["run_status"] = exec_result.get("run_status", "unknown")
        result["merged_profile_keys"] = sorted(exec_result.get("merged_profile", {}).keys())
        result["profile_patch_keys"] = sorted(exec_result.get("action_result", {}).get("profile_patch", {}).keys())
        result["status"] = "completed"

        print(f"[{name}] Done: run_status={result['run_status']}, "
              f"records={result['records_saved']}, "
              f"patch={result['applied_patch']}, "
              f"elapsed={elapsed:.1f}s", flush=True)

    except Exception as exc:
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 2)
        result["status"] = "error"
        result["errors"].append(f"{type(exc).__name__}: {str(exc)[:300]}")
        print(f"[{name}] ERROR: {exc}", flush=True)

    return result


def run_diagnose_repair_test(name: str, target: dict) -> dict:
    """Test diagnose_and_repair() on a simulated failed job."""
    result = {
        "site": name, "test_type": "diagnose_and_repair", "status": "pending",
        "diagnosis_health": "unknown", "repair_plan_generated": False,
        "repair_actions": [], "converged": False, "health_delta": 0, "errors": [],
    }

    print(f"\n{'='*70}", flush=True)
    print(f"[{name}] Diagnose-and-Repair Test: {target['url']}", flush=True)
    print(f"{'='*70}", flush=True)

    try:
        mock_job = {
            "status": "failed", "target_url": target["url"],
            "error_log": ["No items extracted"],
            "profile_run": {"product_stats": {"records_saved": 0, "quality_indicator": "fail", "failure_buckets": {}}},
        }
        diag_result = diagnose_and_repair(
            job=mock_job, profile=target["profile"], target_url=target["url"],
            run_spec=target["run_spec"],
        )
        result["diagnosis_health"] = diag_result.get("diagnosis", {}).get("overall_health", "unknown")
        result["converged"] = diag_result.get("converged", False)
        result["health_delta"] = diag_result.get("health_delta", 0)
        if diag_result.get("repair_plan"):
            result["repair_plan_generated"] = True
            result["repair_actions"] = [a["action"] for a in diag_result["repair_plan"]["actions"]]
        result["status"] = "completed"
        print(f"[{name}] health={result['diagnosis_health']}, "
              f"repair={result['repair_plan_generated']}, "
              f"actions={result['repair_actions']}, "
              f"converged={result['converged']}", flush=True)

    except Exception as exc:
        result["status"] = "error"
        result["errors"].append(f"{type(exc).__name__}: {str(exc)[:300]}")
        print(f"[{name}] ERROR: {exc}", flush=True)

    return result


def main():
    print("=" * 70, flush=True)
    print("Managed Loop Test - 2026-06-02", flush=True)
    print(f"Time: {datetime.now().isoformat()}", flush=True)
    print("=" * 70, flush=True)

    # Part A: Execute-and-Run tests
    print("\n" + "▓" * 70, flush=True)
    print("  PART A: Execute-and-Run Tests (with crawl)", flush=True)
    print("▓" * 70, flush=True)

    run_results = []
    for name, target in MANAGED_LOOP_TARGETS.items():
        result = run_execute_and_run_test(name, target)
        run_results.append(result)

    # Part B: Diagnose-and-Repair tests
    print("\n" + "▓" * 70, flush=True)
    print("  PART B: Diagnose-and-Repair Tests", flush=True)
    print("▓" * 70, flush=True)

    repair_results = []
    for name, target in MANAGED_LOOP_TARGETS.items():
        result = run_diagnose_repair_test(name, target)
        repair_results.append(result)

    # Save results
    all_results = {"run_results": run_results, "repair_results": repair_results}
    (OUTPUT_DIR / "managed_loop_results.json").write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    # Summary
    print("\n" + "=" * 70, flush=True)
    print("MANAGED LOOP TEST SUMMARY", flush=True)
    print("=" * 70, flush=True)

    print("\nExecute-and-Run Results:", flush=True)
    for r in run_results:
        icon = "✅" if r["status"] == "completed" and r["records_saved"] > 0 else "⚠️" if r["status"] == "completed" else "❌"
        print(f"  {icon} {r['site']}: records={r['records_saved']}, "
              f"run_status={r['run_status']}, patch={r['applied_patch']}, "
              f"elapsed={r['elapsed_seconds']}s", flush=True)
        if r["errors"]:
            print(f"    Errors: {r['errors']}", flush=True)

    print("\nDiagnose-and-Repair Results:", flush=True)
    for r in repair_results:
        icon = "✅" if r["repair_plan_generated"] else "⚠️"
        print(f"  {icon} {r['site']}: health={r['diagnosis_health']}, "
              f"repair_plan={r['repair_plan_generated']}, "
              f"actions={r['repair_actions']}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
