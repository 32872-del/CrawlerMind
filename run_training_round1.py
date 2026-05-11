#!/usr/bin/env python3
"""Run Crawler-Mind real-site training round 1."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from autonomous_crawler.training.runner import run_training_scenarios


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
        "capability": "direct_json",
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
        "capability": "reddit_json_shape",
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
        "capability": "explicit_graphql",
    },
]


def run_training_round() -> dict[str, Any]:
    return run_training_scenarios(
        title="Crawler-Mind Real-Site Training Round 1",
        scenarios=TRAINING_SCENARIOS,
        output_path=Path("dev_logs") / "training" / "2026-05-08_real_site_training_round1.json",
        selection_policy="low-risk public JSON/GraphQL entry targets only",
    )


if __name__ == "__main__":
    run_training_round()
