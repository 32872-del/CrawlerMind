#!/usr/bin/env python3
"""Run Crawler-Mind real-site training round 1.

This runner focuses on low-risk public targets from the training list:
direct JSON APIs and a simple public GraphQL endpoint. It saves a compact
summary to dev_logs so training outcomes become project memory.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph


COUNTRIES_QUERY = """
query CountriesTraining {
  countries {
    code
    name
    capital
  }
}
""".strip()


TRAINING_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "jsonplaceholder_posts",
        "name": "JSONPlaceholder posts",
        "url": "https://jsonplaceholder.typicode.com/posts",
        "goal": "collect post titles",
        "target_fields": ["title"],
        "constraints": {"max_items": 10},
        "expected_mode": "api_intercept",
        "risk": "low",
    },
    {
        "id": "reddit_python_json",
        "name": "Reddit r/python JSON",
        "url": "https://www.reddit.com/r/python.json",
        "goal": "collect reddit post titles and scores",
        "target_fields": ["title", "hot_score"],
        "constraints": {"max_items": 10},
        "expected_mode": "api_intercept",
        "risk": "low-public-json",
    },
    {
        "id": "countries_graphql",
        "name": "Countries GraphQL",
        "url": "https://countries.trevorblades.com",
        "goal": "collect country names and capitals",
        "target_fields": ["title", "capital"],
        "constraints": {
            "graphql_query": COUNTRIES_QUERY,
            "max_items": 10,
        },
        "expected_mode": "api_intercept",
        "risk": "low-public-graphql",
    },
]


def _initial_state(scenario: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_goal": scenario["goal"],
        "target_url": scenario["url"],
        "recon_report": {
            "target_fields": scenario.get("target_fields", ["title"]),
            "task_type": "product_list",
            "constraints": dict(scenario.get("constraints") or {}),
        },
        "crawl_strategy": {},
        "visited_urls": [],
        "raw_html": {},
        "api_responses": [],
        "extracted_data": {},
        "validation_result": {},
        "retries": 0,
        "max_retries": 1,
        "status": "pending",
        "error_log": [],
        "messages": [],
    }


def _summarize_state(scenario: dict[str, Any], final_state: dict[str, Any], elapsed: float) -> dict[str, Any]:
    extracted = final_state.get("extracted_data") or {}
    strategy = final_state.get("crawl_strategy") or {}
    validation = final_state.get("validation_result") or {}
    items = list(extracted.get("items") or [])
    return {
        "id": scenario["id"],
        "name": scenario["name"],
        "url": scenario["url"],
        "risk": scenario["risk"],
        "status": final_state.get("status"),
        "elapsed_seconds": round(elapsed, 2),
        "mode": strategy.get("mode"),
        "method": strategy.get("extraction_method"),
        "expected_mode": scenario.get("expected_mode"),
        "item_count": extracted.get("item_count", len(items)),
        "confidence": extracted.get("confidence", 0),
        "valid": validation.get("is_valid", False),
        "anomalies": validation.get("anomalies", []),
        "error_code": final_state.get("error_code", ""),
        "sample_items": [_compact_item(item) for item in items[:3]],
        "messages": final_state.get("messages", []),
    }


def _compact_item(item: dict[str, Any]) -> dict[str, Any]:
    keep_keys = [
        "index", "id", "title", "name", "code", "capital", "hot_score",
        "score", "ups", "link", "url",
    ]
    return {key: item.get(key) for key in keep_keys if item.get(key) not in {None, ""}}


def run_training_round() -> dict[str, Any]:
    app = compile_crawl_graph()
    results: list[dict[str, Any]] = []

    print("=" * 72)
    print("Crawler-Mind Real-Site Training Round 1")
    print("=" * 72)
    for scenario in TRAINING_SCENARIOS:
        print(f"\n[{scenario['id']}] {scenario['name']}")
        print(f"URL: {scenario['url']}")
        start = time.time()
        final_state = app.invoke(_initial_state(scenario))
        elapsed = time.time() - start
        summary = _summarize_state(scenario, final_state, elapsed)
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
        "selection_policy": "low-risk public JSON/GraphQL entry targets only",
        "results": results,
    }
    output_path = Path("dev_logs") / "2026-05-08_real_site_training_round1.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved summary: {output_path}")
    return output


if __name__ == "__main__":
    run_training_round()
