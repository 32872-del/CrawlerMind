#!/usr/bin/env python3
"""Simple Crawler-Mind entrypoint.

Usage:
    python run_simple.py "collect product titles and prices" https://example.com
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from autonomous_crawler.llm import OpenAICompatibleAdvisor, OpenAICompatibleConfig
from run_skeleton import run_crawl


CONFIG_PATH = Path("clm_config.json")


def load_simple_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """Load simple user config. Missing config means deterministic mode."""
    if not path.exists():
        return {"llm": {"enabled": False}}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_simple_advisor(config: dict[str, Any]) -> OpenAICompatibleAdvisor | None:
    """Build an LLM advisor from clm_config.json if enabled."""
    llm = config.get("llm") or {}
    if not llm.get("enabled", False):
        return None

    base_url = str(llm.get("base_url", "")).strip()
    model = str(llm.get("model", "")).strip()
    api_key = str(llm.get("api_key", "")).strip()

    if not base_url:
        raise SystemExit("clm_config.json missing llm.base_url")
    if not model:
        raise SystemExit("clm_config.json missing llm.model")
    if api_key == "replace-with-your-api-key":
        raise SystemExit("Please put your real API key in clm_config.json")

    llm_config = OpenAICompatibleConfig(
        base_url=base_url,
        model=model,
        api_key=api_key,
        provider=str(llm.get("provider", "openai-compatible")).strip()
        or "openai-compatible",
        timeout_seconds=float(llm.get("timeout_seconds", 30)),
        temperature=float(llm.get("temperature", 0)),
        max_tokens=int(llm.get("max_tokens", 800)),
        use_response_format=bool(llm.get("use_response_format", True)),
    )
    return OpenAICompatibleAdvisor(llm_config)


def run_simple(user_goal: str, target_url: str) -> dict[str, Any]:
    """Run with config-file-based LLM setup."""
    config = load_simple_config()
    advisor = build_simple_advisor(config)
    if advisor is None:
        return run_crawl(user_goal, target_url, use_llm=False)
    return run_crawl(user_goal, target_url, use_llm=True, advisor=advisor)


if __name__ == "__main__":
    goal = sys.argv[1] if len(sys.argv) > 1 else "collect product titles"
    url = sys.argv[2] if len(sys.argv) > 2 else "mock://catalog"
    run_simple(goal, url)
