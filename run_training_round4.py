#!/usr/bin/env python3
"""Run Crawler-Mind real-site training round 4.

Round 4 focuses on public APIs plus browser-network observation readiness.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from autonomous_crawler.training.runner import run_training_scenarios


TRAINING_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "dummyjson_products_public_api",
        "name": "DummyJSON products public API",
        "url": "https://dummyjson.com/products?limit=10",
        "goal": "collect product titles prices ratings and summaries",
        "target_fields": ["title", "price", "hot_score", "summary"],
        "constraints": {"max_items": 10},
        "expected_mode": "api_intercept",
        "risk": "low-public-json",
        "capability": "product_api_rating_summary_normalization",
    },
    {
        "id": "hn_algolia_front_page_api",
        "name": "Hacker News Algolia front page API",
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=front_page",
        "goal": "collect hacker news story titles scores and links",
        "target_fields": ["title", "hot_score", "link"],
        "task_type": "ranking_list",
        "constraints": {"max_items": 10},
        "expected_mode": "api_intercept",
        "risk": "low-public-json",
        "capability": "search_api_points_normalization",
    },
    {
        "id": "github_cpython_issues_api",
        "name": "GitHub CPython issues API",
        "url": "https://api.github.com/repos/python/cpython/issues?per_page=10",
        "goal": "collect github issue titles comment counts and links",
        "target_fields": ["title", "hot_score", "link"],
        "constraints": {"max_items": 10},
        "expected_mode": "api_intercept",
        "risk": "low-public-json-rate-limited",
        "capability": "list_json_comment_count_normalization",
    },
    {
        "id": "quotes_to_scrape_quotes_api",
        "name": "Quotes to Scrape quotes API",
        "url": "https://quotes.toscrape.com/api/quotes?page=1",
        "goal": "collect quote text and author names",
        "target_fields": ["title", "summary"],
        "constraints": {"max_items": 10},
        "expected_mode": "api_intercept",
        "risk": "low-public-training-api",
        "capability": "training_api_text_summary_normalization",
    },
    {
        "id": "hn_algolia_browser_network_observation",
        "name": "Hacker News Algolia browser network observation",
        "url": "https://hn.algolia.com/?dateRange=all&page=0&prefix=false&query=&sort=byPopularity&type=story",
        "goal": "observe browser network candidates while collecting story titles",
        "target_fields": ["title", "link"],
        "constraints": {
            "observe_network": True,
            "max_items": 10,
        },
        "expected_mode": "api_intercept",
        "risk": "low-public-spa-observation",
        "capability": "browser_network_observation_real_site_probe",
        "max_retries": 1,
    },
]


def run_training_round() -> dict[str, Any]:
    return run_training_scenarios(
        title="Crawler-Mind Real-Site Training Round 4",
        scenarios=TRAINING_SCENARIOS,
        output_path=Path("dev_logs") / "2026-05-09_real_site_training_round4.json",
        selection_policy="public JSON APIs and one browser-network observation probe",
    )


if __name__ == "__main__":
    run_training_round()
