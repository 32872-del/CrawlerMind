#!/usr/bin/env python3
"""Smoke test: collect top 30 Baidu realtime hot-search items with the Agent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from autonomous_crawler.agents.extractor import extractor_node
from autonomous_crawler.agents.validator import validator_node
from autonomous_crawler.storage import save_crawl_result
from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph


TARGET_URL = "https://top.baidu.com/board?tab=realtime"
USER_GOAL = "采集百度热搜榜前30条"
OUTPUT_PATH = Path("dev_logs") / "baidu_hot_smoke_result.json"


def build_initial_state() -> dict:
    return {
        "user_goal": USER_GOAL,
        "target_url": TARGET_URL,
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


def run_agent_smoke_test() -> dict:
    app = compile_crawl_graph()
    return app.invoke(build_initial_state())


def run_with_rendered_html(html: str) -> dict:
    """Compatibility helper for the older browser-rendered HTML harness."""
    state = {
        "task_id": "baidu-hot-smoke",
        "user_goal": USER_GOAL,
        "target_url": TARGET_URL,
        "recon_report": {
            "target_fields": ["rank", "title", "hot_score"],
            "target_url": TARGET_URL,
            "frontend_framework": "vue",
            "rendering": "browser",
            "anti_bot": {"detected": False, "type": "none", "severity": "low"},
            "api_endpoints": [],
            "dom_structure": {
                "is_product_list": False,
                "is_ranking_list": True,
                "item_count": 50,
                "product_selector": ".category-wrap_iQLoo",
                "field_selectors": {
                    "rank": ".index_1Ew5p",
                    "title": ".title_dIF3B .c-single-text-ellipsis",
                    "link": ".title_dIF3B@href",
                    "hot_score": ".hot-index_1Bl1a",
                    "summary": ".hot-desc_1m_jR",
                    "image": ".img-wrapper_29V76 img@src",
                },
            },
        },
        "crawl_strategy": {
            "mode": "browser",
            "extraction_method": "browser_render",
            "selectors": {
                "item_container": ".category-wrap_iQLoo",
                "rank": ".index_1Ew5p",
                "title": ".title_dIF3B .c-single-text-ellipsis",
                "link": ".title_dIF3B@href",
                "hot_score": ".hot-index_1Bl1a",
                "summary": ".hot-desc_1m_jR",
                "image": ".img-wrapper_29V76 img@src",
            },
            "max_items": 30,
            "headers": {},
            "rationale": "Baidu realtime board uses browser-rendered DOM selectors",
        },
        "visited_urls": [],
        "raw_html": {TARGET_URL: html},
        "api_responses": [],
        "extracted_data": {},
        "validation_result": {},
        "retries": 0,
        "max_retries": 0,
        "status": "pending",
        "error_log": [],
        "messages": [],
    }
    state = extractor_node(state)
    state = validator_node(state)
    return state


def save_result(state: dict) -> Path:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return OUTPUT_PATH


def main() -> int:
    state = run_agent_smoke_test()
    output_path = save_result(state)
    task_id = save_crawl_result(state)
    extracted = state.get("extracted_data", {})
    item_count = extracted.get("item_count", 0)
    is_valid = state.get("validation_result", {}).get("is_valid", False)

    print(f"Status: {state.get('status')}")
    print(f"Items: {item_count}")
    print(f"Valid: {is_valid}")
    print(f"Output: {output_path}")
    print(f"Persisted task_id: {task_id}")

    if state.get("status") != "completed" or item_count < 30 or not is_valid:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
