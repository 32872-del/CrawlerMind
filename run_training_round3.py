#!/usr/bin/env python3
"""Run Crawler-Mind real-site training round 3.

Round 3 focuses on static/SSR page extraction and framework reconnaissance.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from autonomous_crawler.training.runner import run_training_scenarios


TRAINING_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "douban_top250_static",
        "name": "Douban Movie Top250 static page",
        "url": "https://movie.douban.com/top250",
        "goal": "collect movie titles and scores",
        "target_fields": ["title", "hot_score"],
        "task_type": "ranking_list",
        "constraints": {"max_items": 25},
        "expected_mode": "http",
        "risk": "medium-static-rate-sensitive",
        "capability": "static_dom_ranking_with_scores",
    },
    {
        "id": "react_docs_ssr_recon",
        "name": "React docs SSR recon",
        "url": "https://react.dev/learn",
        "goal": "collect documentation links",
        "target_fields": ["title", "link"],
        "constraints": {"max_items": 10},
        "expected_mode": "http",
        "risk": "low-public-ssr",
        "capability": "ssr_framework_recon",
    },
    {
        "id": "vue_examples_static_recon",
        "name": "Vue examples static recon",
        "url": "https://vuejs.org/examples/",
        "goal": "collect example links",
        "target_fields": ["title", "link"],
        "constraints": {"max_items": 10},
        "expected_mode": "http",
        "risk": "low-public-static",
        "capability": "framework_recon_static_site",
    },
]


def run_training_round() -> dict[str, Any]:
    return run_training_scenarios(
        title="Crawler-Mind Real-Site Training Round 3",
        scenarios=TRAINING_SCENARIOS,
        output_path=Path("dev_logs") / "training" / "2026-05-08_real_site_training_round3.json",
        selection_policy="static/SSR extraction and framework reconnaissance targets",
    )


if __name__ == "__main__":
    run_training_round()
