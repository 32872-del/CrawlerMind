#!/usr/bin/env python3
"""Test script to verify the LangGraph skeleton runs end-to-end.

Usage:
    python run_skeleton.py "采集 tatuum.com 所有商品的标题和价格" https://www.tatuum.com
    python run_skeleton.py "抓取商品数据" https://example.com
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, ".")

from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph
from autonomous_crawler.storage import save_crawl_result


def run_crawl(user_goal: str, target_url: str) -> dict:
    """Run the crawl workflow and return the final state."""
    print("=" * 70)
    print(f"Autonomous Crawl Agent - Skeleton Test")
    print(f"=" * 70)
    print(f"Goal: {user_goal}")
    print(f"URL:  {target_url}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"-" * 70)

    # Build initial state
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

    # Compile and run graph
    app = compile_crawl_graph()

    start_time = time.time()
    final_state = app.invoke(initial_state)
    elapsed = time.time() - start_time

    # Print results
    print(f"\n{'=' * 70}")
    print(f"RESULTS")
    print(f"{'=' * 70}")
    print(f"Final Status: {final_state.get('status', 'unknown')}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Retries: {final_state.get('retries', 0)}")

    # Print workflow messages
    print(f"\n--- Workflow Log ---")
    for msg in final_state.get("messages", []):
        print(f"  {msg}")

    # Print extracted data summary
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
            print(f"  - {item.get('title', '?')}: {item.get('price', '?')} | {item.get('image', '')}")

    # Print validation result
    validation = final_state.get("validation_result", {})
    print(f"\n--- Validation ---")
    print(f"  Valid: {validation.get('is_valid', False)}")
    print(f"  Completeness: {validation.get('completeness', 0):.0%}")
    if validation.get("anomalies"):
        print(f"  Anomalies: {validation['anomalies']}")

    # Print strategy
    strategy = final_state.get("crawl_strategy", {})
    print(f"\n--- Strategy ---")
    print(f"  Mode: {strategy.get('mode', '?')}")
    print(f"  Method: {strategy.get('extraction_method', '?')}")
    print(f"  Rationale: {strategy.get('rationale', '?')}")

    # Save full state to file
    output_path = "dev_logs/skeleton_run_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        # Convert non-serializable types
        serializable = json.loads(json.dumps(final_state, default=str))
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    print(f"\nFull state saved to: {output_path}")

    task_id = save_crawl_result(final_state)
    print(f"Result persisted to SQLite with task_id: {task_id}")

    return final_state


if __name__ == "__main__":
    goal = sys.argv[1] if len(sys.argv) > 1 else "采集商品的标题和价格"
    url = sys.argv[2] if len(sys.argv) > 2 else "https://www.tatuum.com"
    run_crawl(goal, url)
