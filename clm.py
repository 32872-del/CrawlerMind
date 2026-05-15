#!/usr/bin/env python3
"""Crawler-Mind Easy Mode command-line entry point."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from autonomous_crawler.llm import LLMConfigurationError
from run_simple import build_simple_advisor, check_llm_config, load_simple_config
from run_skeleton import run_crawl


DEFAULT_CONFIG_PATH = Path("clm_config.json")
DEFAULT_OUTPUT_DIR = Path("dev_logs") / "runtime"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clm.py",
        description="Crawler-Mind Easy Mode: initialize, check, and run crawls.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a local CLM config")
    init_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    init_parser.add_argument("--force", action="store_true", help="overwrite config")
    init_parser.add_argument("--enable-llm", action="store_true")
    init_parser.add_argument("--base-url", default=DEFAULT_LLM_BASE_URL)
    init_parser.add_argument("--model", default=DEFAULT_LLM_MODEL)
    init_parser.add_argument("--api-key", default="replace-with-your-api-key")
    init_parser.add_argument("--provider", default="openai-compatible")
    init_parser.add_argument("--timeout-seconds", type=float, default=30.0)
    init_parser.add_argument("--temperature", type=float, default=0.0)
    init_parser.add_argument("--max-tokens", type=int, default=800)
    init_parser.add_argument("--disable-response-format", action="store_true")
    init_parser.set_defaults(func=cmd_init)

    check_parser = subparsers.add_parser("check", help="check local setup")
    check_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    check_parser.add_argument(
        "--llm",
        action="store_true",
        help="also make a real provider request using the configured LLM",
    )
    check_parser.set_defaults(func=cmd_check)

    crawl_parser = subparsers.add_parser("crawl", help="run a crawl")
    crawl_parser.add_argument("goal", help="natural language crawl goal")
    crawl_parser.add_argument("url", help="target URL")
    crawl_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    crawl_parser.add_argument("--limit", type=int, help="requested item limit")
    crawl_parser.add_argument("--output", type=Path, help="write JSON or XLSX output")
    crawl_parser.add_argument("--llm", action="store_true", help="force LLM on")
    crawl_parser.add_argument("--no-llm", action="store_true", help="force LLM off")
    crawl_parser.set_defaults(func=cmd_crawl)

    smoke_parser = subparsers.add_parser("smoke", help="run a small smoke test")
    smoke_parser.add_argument(
        "--kind",
        choices=("runner", "baidu", "native-spider"),
        default="runner",
        help="runner/native-spider are local-only; baidu uses the public Baidu hot-list page",
    )
    smoke_parser.add_argument(
        "--plan",
        action="store_true",
        help="print the command that would run without executing it",
    )
    smoke_parser.set_defaults(func=cmd_smoke)

    train_parser = subparsers.add_parser("train", help="show developer training commands")
    train_parser.add_argument(
        "--round",
        choices=(
            "1", "2", "3", "4", "ecommerce", "real-2026-05-11",
            "native-vs-transition", "native-vs-transition-dynamic",
            "native-vs-transition-profile", "native-spider-smoke",
        ),
    )
    train_parser.set_defaults(func=cmd_train)
    return parser


def cmd_init(args: argparse.Namespace) -> int:
    config_path: Path = args.config
    if config_path.exists() and not args.force:
        print(f"Config already exists: {config_path}")
        print("Use --force to overwrite it.")
        return 1

    config = {
        "llm": {
            "enabled": bool(args.enable_llm),
            "base_url": args.base_url,
            "model": args.model,
            "api_key": args.api_key,
            "provider": args.provider,
            "timeout_seconds": args.timeout_seconds,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "use_response_format": not bool(args.disable_response_format),
        },
        "outputs": {
            "default_dir": str(DEFAULT_OUTPUT_DIR).replace("\\", "/"),
        },
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Created config: {config_path}")
    if args.enable_llm:
        print("LLM: enabled")
        if args.api_key == "replace-with-your-api-key":
            print("Reminder: replace llm.api_key before running LLM-enabled crawls.")
    else:
        print("LLM: disabled by default. Use --enable-llm when you are ready.")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    print("=" * 70)
    print("Crawler-Mind Setup Check")
    print("=" * 70)
    status = 0

    print(f"Python: {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        print("Python status: failed, Python 3.11+ is recommended")
        status = 1
    else:
        print("Python status: ok")

    for package in ("bs4", "httpx", "pandas", "playwright"):
        if importlib.util.find_spec(package) is None:
            print(f"Package {package}: missing")
            status = 1
        else:
            print(f"Package {package}: ok")

    _ensure_output_dirs()
    print(f"Output directory: {DEFAULT_OUTPUT_DIR}")

    try:
        config = load_simple_config(args.config)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Config: {args.config}")
        print(f"Status: failed")
        print(f"Reason: {exc}")
        return 1
    llm = config.get("llm") or {}
    print(f"Config: {args.config if args.config.exists() else 'not found'}")
    print(f"LLM configured: {'yes' if llm.get('enabled') else 'no'}")

    if args.llm:
        return check_llm_config(args.config)
    return status


def cmd_crawl(args: argparse.Namespace) -> int:
    if args.llm and args.no_llm:
        print("Choose either --llm or --no-llm, not both.")
        return 2

    goal = args.goal
    if args.limit:
        goal = f"{goal} limit {args.limit}"

    try:
        advisor = _build_advisor_for_crawl(args.config, force_llm=args.llm, disable_llm=args.no_llm)
    except (SystemExit, ValueError, LLMConfigurationError) as exc:
        print(f"LLM config error: {exc}")
        return 1

    final_state = run_crawl(goal, args.url, use_llm=advisor is not None, advisor=advisor)
    if args.output:
        _write_crawl_output(final_state, args.output)
        print(f"Output saved to: {args.output}")
    return 0 if final_state.get("status") == "completed" else 1


def cmd_smoke(args: argparse.Namespace) -> int:
    command = {
        "runner": "python run_batch_runner_smoke.py",
        "baidu": "python run_baidu_hot_test.py",
        "native-spider": "python run_spider_runtime_smoke_2026_05_14.py",
    }[args.kind]
    if args.plan:
        print(command)
        return 0
    if args.kind == "runner":
        import json as json_module
        from run_batch_runner_smoke import run as run_runner_smoke

        summary = run_runner_smoke(
            items=25,
            batch_size=5,
            first_pass_batches=2,
            keep_db=False,
        )
        print(json_module.dumps(summary, ensure_ascii=True, indent=2))
        return 0 if summary.get("accepted") else 1
    if args.kind == "native-spider":
        import json as json_module
        from run_spider_runtime_smoke_2026_05_14 import run as run_native_spider_smoke

        summary = run_native_spider_smoke(keep_db=False)
        print(json_module.dumps(summary, ensure_ascii=True, indent=2))
        return 0 if summary.get("accepted") else 1
    from run_baidu_hot_test import main as baidu_smoke_main

    return int(baidu_smoke_main() or 0)


def cmd_train(args: argparse.Namespace) -> int:
    commands = {
        "1": "python run_training_round1.py",
        "2": "python run_training_round2.py",
        "3": "python run_training_round3.py",
        "4": "python run_training_round4.py",
        "ecommerce": "python run_ecommerce_training_2026_05_09.py",
        "real-2026-05-11": "python run_real_training_2026_05_11.py",
        "native-vs-transition": "python run_native_transition_comparison_2026_05_14.py",
        "native-vs-transition-dynamic": "python run_native_transition_comparison_2026_05_14.py --suite dynamic",
        "native-vs-transition-profile": "python run_native_transition_comparison_2026_05_14.py --suite profile --profile autonomous_crawler/tests/fixtures/native_transition_profile.json",
        "native-spider-smoke": "python run_spider_runtime_smoke_2026_05_14.py",
    }
    if args.round:
        print(commands[args.round])
    else:
        print("Developer training commands:")
        for command in commands.values():
            print(f"  {command}")
    return 0


def _build_advisor_for_crawl(
    config_path: Path,
    *,
    force_llm: bool = False,
    disable_llm: bool = False,
) -> Any | None:
    if disable_llm:
        return None
    config = load_simple_config(config_path)
    if force_llm:
        config = dict(config)
        llm = dict(config.get("llm") or {})
        llm["enabled"] = True
        config["llm"] = llm
    return build_simple_advisor(config)


def _ensure_output_dirs() -> None:
    for path in (
        DEFAULT_OUTPUT_DIR,
        Path("dev_logs") / "smoke",
        Path("dev_logs") / "training",
        Path("dev_logs") / "stress",
    ):
        path.mkdir(parents=True, exist_ok=True)


def _write_crawl_output(final_state: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    serializable = json.loads(json.dumps(final_state, default=str))
    items = serializable.get("extracted_data", {}).get("items", [])

    if suffix == ".json":
        output_path.write_text(json.dumps(serializable, indent=2, ensure_ascii=False), encoding="utf-8")
        return
    if suffix in {".xlsx", ".xls"}:
        try:
            import pandas as pd
        except ImportError as exc:
            raise SystemExit("pandas is required for Excel output") from exc
        rows = items if isinstance(items, list) else []
        if not rows:
            rows = [{"status": serializable.get("status", "unknown"), "generated_at": datetime.now().isoformat()}]
        pd.DataFrame(rows).to_excel(output_path, index=False)
        return
    raise SystemExit("Output path must end with .json or .xlsx")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
