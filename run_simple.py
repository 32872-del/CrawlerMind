#!/usr/bin/env python3
"""Simple Crawler-Mind entrypoint.

Usage:
    python run_simple.py "collect product titles and prices" https://example.com
    python run_simple.py --check-llm
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from autonomous_crawler.llm import (
    LLMResponseError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
)
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


def check_llm_config(path: Path = CONFIG_PATH) -> int:
    """Validate config and run a minimal LLM provider check."""
    print("=" * 70)
    print("Crawler-Mind LLM Config Check")
    print("=" * 70)
    print(f"Config: {path}")

    try:
        config = load_simple_config(path)
        advisor = build_simple_advisor(config)
    except (OSError, json.JSONDecodeError, SystemExit, ValueError) as exc:
        print("Status: failed")
        print(f"Reason: {exc}")
        return 1

    if advisor is None:
        print("Status: disabled")
        print("Reason: llm.enabled is false or clm_config.json is missing")
        return 1

    print("Status: configured")
    print(f"Provider: {advisor.config.provider}")
    print(f"Model: {advisor.config.model}")
    print(f"Endpoint: {advisor.endpoint}")
    print(f"API key set: {'yes' if bool(advisor.config.api_key) else 'no'}")
    print(f"Response format: {'on' if advisor.config.use_response_format else 'off'}")
    print("-" * 70)

    try:
        result = advisor.check_connection()
    except LLMResponseError as exc:
        print("Connection: failed")
        print(f"Reason: {exc}")
        return 2
    except Exception as exc:
        print("Connection: failed")
        print(f"Reason: {type(exc).__name__}: {exc}")
        return 2

    print("Connection: ok")
    if "reasoning_summary" in result:
        print(f"Summary: {result['reasoning_summary']}")
    else:
        print(f"Response keys: {', '.join(sorted(str(k) for k in result.keys()))}")
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Crawler-Mind simply.")
    parser.add_argument(
        "--check-llm",
        action="store_true",
        help="validate clm_config.json and test the configured LLM provider",
    )
    parser.add_argument(
        "goal",
        nargs="?",
        default="collect product titles",
        help="natural language crawl goal",
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="mock://catalog",
        help="target URL or mock fixture URL",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    if args.check_llm:
        raise SystemExit(check_llm_config())
    run_simple(args.goal, args.url)
