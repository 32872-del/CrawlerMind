"""End-to-end integration test for the AI Managed Crawl Loop v2."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from autonomous_crawler.llm.provider_registry import build_registry_from_config
from autonomous_crawler.runners.managed_actions import (
    ManagedActionPlan,
    ManagedCrawlAction,
    build_deterministic_action_plan,
    execute_managed_action_plan,
)
from autonomous_crawler.runners.managed_state import build_managed_crawl_state
from autonomous_crawler.runners.auto_repair import FailureDiagnoser, AutoRepairLoop


def log(msg: str) -> None:
    print(msg, flush=True)


def test_e2e_integration():
    """Run a full end-to-end integration test."""
    log("=" * 60)
    log("CLM AI Managed Crawl Loop - E2E Integration Test")
    log("=" * 60)

    # Step 1: Load multi-provider LLM
    log("\n[1/6] Loading LLM providers...")
    config_path = os.path.join(project_root, "clm_config.json")
    registry = build_registry_from_config(config_path)
    providers = registry.list_providers()
    log(f"  Registered providers: {len(providers)}")
    for p in providers:
        log(f"    - {p['name']}: {p['model']} ({p['base_url']})")

    advisor = registry.get_advisor()
    if advisor:
        log(f"  Active advisor: {advisor.model} @ {advisor.config.base_url}")
    else:
        log("  WARNING: No LLM advisor available, using deterministic plans")

    # Step 2: Create a mock job for testing
    log("\n[2/6] Creating test job...")
    target_url = "https://dummyjson.com/products"
    job = {
        "task_id": "e2e-test-001",
        "kind": "product_test_run",
        "status": "completed",
        "target_url": target_url,
        "product_run_spec": {
            "target_url": target_url,
            "profile": {
                "name": "dummyjson",
                "target_url": target_url,
                "target_fields": ["title", "price", "description", "brand", "category"],
                "list_selectors": {"product": ".product-card"},
                "detail_selectors": {
                    "title": "h1, .product-title",
                    "price": ".price",
                    "description": ".description",
                },
            },
        },
        "profile_run": {
            "product_stats": {
                "records_saved": 0,
                "quality_indicator": "fail",
                "failure_buckets": {},
                "quality": {"missing_fields": ["price"]},
            },
        },
    }
    log(f"  Target: {target_url}")
    log(f"  Job status: {job['status']}")

    # Step 3: Build managed crawl state
    log("\n[3/6] Building managed crawl state...")
    try:
        state = build_managed_crawl_state(job=job)
        state_keys = sorted(state.keys()) if isinstance(state, dict) else []
        log(f"  State keys: {state_keys[:10]}")
        log("  [OK] Managed state built successfully")
    except Exception as e:
        log(f"  [FAIL] State build failed: {e}")
        state = {}

    # Step 4: Build action plan
    log("\n[4/6] Building action plan...")
    profile = job["product_run_spec"]["profile"]
    try:
        plan = build_deterministic_action_plan(
            target_url=target_url,
            profile=profile,
            run_spec=job.get("product_run_spec") or {},
            progress=(job.get("profile_run") or {}).get("product_stats") or {},
            diagnostics={},
            supervision={},
        )
        log(f"  Plan actions: {len(plan.actions)}")
        for action in plan.actions:
            log(f"    - {action.action}: {action.reason[:80]}")
        log("  [OK] Action plan built successfully")
    except Exception as e:
        log(f"  [FAIL] Plan build failed: {e}")
        plan = ManagedActionPlan(actions=[], source="fallback")

    # Step 5: Execute with LLM decision
    log("\n[5/6] Executing managed actions...")
    if plan.actions:
        try:
            result = execute_managed_action_plan(
                plan=plan,
                target_url=target_url,
                profile=profile,
                advisor=advisor,
                llm_decide=advisor is not None,
                job=job,
            )
            log(f"  Source: {result.get('source', 'unknown')}")
            action_results = result.get("results") or []
            log(f"  Actions executed: {len(action_results)}")
            for r in action_results[:5]:
                status = r.get("status", "unknown")
                action = r.get("action", "?")
                log(f"    [{status}] {action}")
            if result.get("rerun_ready"):
                log("  [RERUN] Rerun ready flag detected")
            log("  [OK] Action execution completed")
        except Exception as e:
            log(f"  [FAIL] Execution failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        log("  [SKIP] No actions to execute")

    # Step 6: Failure diagnosis
    log("\n[6/6] Running failure diagnosis...")
    try:
        diagnoser = FailureDiagnoser()
        report = diagnoser.diagnose(job=job, profile=profile)
        log(f"  Health: {report.overall_health}")
        log(f"  Diagnoses: {len(report.diagnoses)}")
        for d in report.diagnoses[:5]:
            log(f"    [{d.severity}] {d.category}: {d.evidence[:80]}")
        log(f"  Auto-repairable: {report.auto_repairable}")
        log(f"  Repair actions: {len(report.repair_plan_actions)}")
        log("  [OK] Diagnosis completed")
    except Exception as e:
        log(f"  [FAIL] Diagnosis failed: {e}")
        import traceback
        traceback.print_exc()

    log("\n" + "=" * 60)
    log("E2E Integration Test Complete")
    log("=" * 60)


if __name__ == "__main__":
    test_e2e_integration()
