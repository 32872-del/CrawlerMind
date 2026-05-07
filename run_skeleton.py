#!/usr/bin/env python3
"""Run the Crawler-Mind LangGraph workflow from the command line.

Examples:
    python run_skeleton.py "collect product titles and prices" https://example.com
    python run_skeleton.py --llm "collect top 30 hot searches" https://top.baidu.com/board?tab=realtime
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

# Add project root to path when running this script directly.
sys.path.insert(0, ".")

from autonomous_crawler.llm import OpenAICompatibleAdvisor, PlanningAdvisor
from autonomous_crawler.llm import LLMConfigurationError
from autonomous_crawler.storage import save_crawl_result
from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph


def run_crawl(
    user_goal: str,
    target_url: str,
    use_llm: bool = False,
    advisor: PlanningAdvisor | None = None,
) -> dict:
    """Run the crawl workflow and return the final state."""
    print("=" * 70)
    print("Autonomous Crawl Agent - Skeleton Test")
    print("=" * 70)
    print(f"Goal: {user_goal}")
    print(f"URL:  {target_url}")
    print(f"Time: {datetime.now().isoformat()}")
    print("-" * 70)

    initial_state = {
        "user_goal": user_goal,
        "target_url": target_url,
        "recon_report": {},
        "crawl_strategy": {},
        "visited_urls": [],
        "raw_html": {},
        "api_responses": [],
        "extracted_data": {},
        "validation_result": {},
        "retries": 0,
        "max_retries": 3,
        "status": "pending",
        "error_log": [],
        "messages": [],
    }

    try:
        advisor = advisor or (OpenAICompatibleAdvisor.from_env() if use_llm else None)
    except LLMConfigurationError as exc:
        raise SystemExit(f"LLM configuration error: {exc}") from exc
    app = compile_crawl_graph(
        planning_advisor=advisor,
        strategy_advisor=advisor,
    )

    start_time = time.time()
    final_state = app.invoke(initial_state)
    elapsed = time.time() - start_time

    print(f"\n{'=' * 70}")
    print("RESULTS")
    print(f"{'=' * 70}")
    print(f"Final Status: {final_state.get('status', 'unknown')}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Retries: {final_state.get('retries', 0)}")
    print(f"LLM Enabled: {final_state.get('llm_enabled', False)}")
    if final_state.get("llm_errors"):
        print(f"LLM Errors: {final_state['llm_errors']}")

    print("\n--- Workflow Log ---")
    for msg in final_state.get("messages", []):
        print(f"  {msg}")

    extracted = final_state.get("extracted_data", {})
    items = extracted.get("items", [])
    print(f"\n--- Extracted Data ({len(items)} items) ---")
    for item in items:
        if "rank" in item or "hot_score" in item:
            parts = [
                f"#{item.get('rank', item.get('index', '?'))}",
                item.get("title", "?"),
            ]
            if item.get("hot_score"):
                parts.append(f"hot={item['hot_score']}")
            if item.get("link"):
                parts.append(item["link"])
            print("  - " + " | ".join(str(part) for part in parts))
        else:
            title = item.get("title", "?")
            price = item.get("price", "?")
            image = item.get("image", "")
            print(f"  - {title}: {price} | {image}")

    validation = final_state.get("validation_result", {})
    print("\n--- Validation ---")
    print(f"  Valid: {validation.get('is_valid', False)}")
    print(f"  Completeness: {validation.get('completeness', 0):.0%}")
    if validation.get("anomalies"):
        print(f"  Anomalies: {validation['anomalies']}")

    strategy = final_state.get("crawl_strategy", {})
    print("\n--- Strategy ---")
    print(f"  Mode: {strategy.get('mode', '?')}")
    print(f"  Method: {strategy.get('extraction_method', '?')}")
    print(f"  Rationale: {strategy.get('rationale', '?')}")

    decisions = final_state.get("llm_decisions") or []
    if decisions:
        print(f"\n--- LLM Decisions ({len(decisions)}) ---")
        for decision in decisions:
            print(
                "  - "
                f"{decision.get('node')}: "
                f"accepted={decision.get('accepted_fields', [])}, "
                f"rejected={decision.get('rejected_fields', [])}, "
                f"fallback={decision.get('fallback_used', False)}"
            )

    output_path = "dev_logs/skeleton_run_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        serializable = json.loads(json.dumps(final_state, default=str))
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"\nFull state saved to: {output_path}")

    task_id = save_crawl_result(final_state)
    print(f"Result persisted to SQLite with task_id: {task_id}")

    return final_state


def _llm_enabled_from_env() -> bool:
    return os.environ.get("CLM_LLM_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _parse_cli_args(argv: list[str]) -> tuple[str, str, bool]:
    args = list(argv)
    use_llm = _llm_enabled_from_env()
    if "--llm" in args:
        use_llm = True
        args.remove("--llm")
    if "--no-llm" in args:
        use_llm = False
        args.remove("--no-llm")

    goal = args[0] if len(args) > 0 else "collect product titles and prices"
    url = args[1] if len(args) > 1 else "https://www.tatuum.com"
    return goal, url, use_llm


if __name__ == "__main__":
    goal_arg, url_arg, llm_flag = _parse_cli_args(sys.argv[1:])
    run_crawl(goal_arg, url_arg, use_llm=llm_flag)
