"""Reusable real-site training runner utilities."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph


def build_initial_state(scenario: dict[str, Any]) -> dict[str, Any]:
    """Build a graph state from a training scenario definition."""
    return {
        "user_goal": scenario["goal"],
        "target_url": scenario["url"],
        "recon_report": {
            "target_fields": scenario.get("target_fields", ["title"]),
            "task_type": scenario.get("task_type", "product_list"),
            "constraints": dict(scenario.get("constraints") or {}),
        },
        "crawl_strategy": {},
        "visited_urls": [],
        "raw_html": {},
        "api_responses": [],
        "extracted_data": {},
        "validation_result": {},
        "retries": 0,
        "max_retries": int(scenario.get("max_retries", 1)),
        "status": "pending",
        "error_log": [],
        "messages": [],
    }


def run_training_scenarios(
    *,
    title: str,
    scenarios: list[dict[str, Any]],
    output_path: Path,
    selection_policy: str,
) -> dict[str, Any]:
    """Run scenarios through the main graph and save a compact JSON summary."""
    app = compile_crawl_graph()
    results: list[dict[str, Any]] = []

    print("=" * 72)
    print(title)
    print("=" * 72)
    for scenario in scenarios:
        print(f"\n[{scenario['id']}] {scenario['name']}")
        print(f"URL: {scenario['url']}")
        start = time.time()
        final_state = app.invoke(build_initial_state(scenario))
        elapsed = time.time() - start
        summary = summarize_state(scenario, final_state, elapsed)
        results.append(summary)
        print(
            "Result: "
            f"status={summary['status']} "
            f"items={summary['item_count']} "
            f"mode={summary['mode']} "
            f"method={summary['method']} "
            f"elapsed={summary['elapsed_seconds']}s"
        )
        if summary["anomalies"]:
            print(f"Anomalies: {summary['anomalies']}")

    output = {
        "run_at": datetime.now().isoformat(),
        "source_list": r"E:\爬虫Agent实战训练网站清单.md",
        "selection_policy": selection_policy,
        "results": results,
    }
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved summary: {output_path}")
    return output


def summarize_state(
    scenario: dict[str, Any],
    final_state: dict[str, Any],
    elapsed: float,
) -> dict[str, Any]:
    """Create a compact, review-friendly summary for one scenario."""
    extracted = final_state.get("extracted_data") or {}
    strategy = final_state.get("crawl_strategy") or {}
    validation = final_state.get("validation_result") or {}
    recon = final_state.get("recon_report") or {}
    items = list(extracted.get("items") or [])
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "url": scenario["url"],
        "risk": scenario.get("risk", ""),
        "capability": scenario.get("capability", ""),
        "status": final_state.get("status"),
        "elapsed_seconds": round(elapsed, 2),
        "mode": strategy.get("mode"),
        "method": strategy.get("extraction_method"),
        "expected_mode": scenario.get("expected_mode"),
        "fetch_mode": (recon.get("fetch") or {}).get("selected_mode"),
        "item_count": extracted.get("item_count", len(items)),
        "confidence": extracted.get("confidence", 0),
        "valid": validation.get("is_valid", False),
        "anomalies": validation.get("anomalies", []),
        "error_code": final_state.get("error_code", ""),
        "sample_items": [compact_item(item) for item in items[:3]],
        "messages": final_state.get("messages", []),
    }


def compact_item(item: dict[str, Any]) -> dict[str, Any]:
    """Keep only high-signal fields in training logs."""
    keep_keys = [
        "index", "id", "aid", "title", "name", "code", "capital",
        "hot_score", "score", "ups", "popularity", "averageScore",
        "link", "url", "siteUrl", "image",
    ]
    return {
        key: item.get(key)
        for key in keep_keys
        if item.get(key) not in {None, ""}
    }
