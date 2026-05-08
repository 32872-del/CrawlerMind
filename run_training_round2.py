#!/usr/bin/env python3
"""Run Crawler-Mind real-site training round 2.

Round 2 focuses on public content APIs and nested GraphQL records.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from autonomous_crawler.training.runner import run_training_scenarios


ANILIST_QUERY = """
query AniListTraining($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(type: ANIME, sort: POPULARITY_DESC) {
      id
      title {
        english
        romaji
      }
      popularity
      averageScore
      siteUrl
      coverImage {
        medium
      }
    }
  }
}
""".strip()


TRAINING_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "anilist_popular_anime_graphql",
        "name": "AniList popular anime GraphQL",
        "url": "https://graphql.anilist.co",
        "goal": "collect anime titles popularity scores and links",
        "target_fields": ["title", "hot_score", "link", "image"],
        "constraints": {
            "graphql_query": ANILIST_QUERY,
            "graphql_variables": {"page": 1, "perPage": 10},
            "max_items": 10,
        },
        "expected_mode": "api_intercept",
        "risk": "low-public-graphql",
        "capability": "nested_graphql_records",
    },
    {
        "id": "bilibili_ranking_public_api",
        "name": "Bilibili ranking public API",
        "url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
        "goal": "collect bilibili ranking titles and scores",
        "target_fields": ["title", "hot_score"],
        "task_type": "ranking_list",
        "constraints": {"max_items": 10},
        "expected_mode": "api_intercept",
        "risk": "medium-public-api-rate-sensitive",
        "capability": "content_api_business_error_detection",
        "max_retries": 1,
    },
]


def run_training_round() -> dict[str, Any]:
    return run_training_scenarios(
        title="Crawler-Mind Real-Site Training Round 2",
        scenarios=TRAINING_SCENARIOS,
        output_path=Path("dev_logs") / "2026-05-08_real_site_training_round2.json",
        selection_policy="public content API and nested GraphQL targets",
    )


if __name__ == "__main__":
    run_training_round()
