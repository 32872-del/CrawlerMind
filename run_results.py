#!/usr/bin/env python3
"""Inspect and export persisted crawl results."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from autonomous_crawler.storage import list_crawl_results, load_crawl_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List, inspect, and export persisted crawl results.",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Optional path to crawl_results.sqlite3.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List recent crawl tasks.")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--json", action="store_true", help="Output JSON.")

    show_parser = subparsers.add_parser("show", help="Show one task summary.")
    show_parser.add_argument("task_id")
    show_parser.add_argument("--json", action="store_true", help="Output JSON.")

    items_parser = subparsers.add_parser("items", help="Show extracted items.")
    items_parser.add_argument("task_id")
    items_parser.add_argument("--limit", type=int, default=20)
    items_parser.add_argument("--json", action="store_true", help="Output JSON.")

    export_json_parser = subparsers.add_parser("export-json", help="Export task items to JSON.")
    export_json_parser.add_argument("task_id")
    export_json_parser.add_argument("output_path")

    export_csv_parser = subparsers.add_parser("export-csv", help="Export task items to CSV.")
    export_csv_parser.add_argument("task_id")
    export_csv_parser.add_argument("output_path")

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)

    if args.command == "list":
        rows = list_crawl_results(limit=args.limit, db_path=args.db_path)
        if args.json:
            print(_json(rows))
        else:
            print(_format_task_table(rows))
        return 0

    if args.command == "show":
        task = _load_or_report(args.task_id, args.db_path)
        if not task:
            return 1
        if args.json:
            print(_json(_task_summary(task)))
        else:
            print(_format_task_summary(task))
        return 0

    if args.command == "items":
        task = _load_or_report(args.task_id, args.db_path)
        if not task:
            return 1
        items = task.get("items", [])[: max(0, args.limit)]
        if args.json:
            print(_json(items))
        else:
            print(_format_items(items))
        return 0

    if args.command == "export-json":
        task = _load_or_report(args.task_id, args.db_path)
        if not task:
            return 1
        _write_json(Path(args.output_path), task.get("items", []))
        print(f"Exported {len(task.get('items', []))} items to {args.output_path}")
        return 0

    if args.command == "export-csv":
        task = _load_or_report(args.task_id, args.db_path)
        if not task:
            return 1
        _write_csv(Path(args.output_path), task.get("items", []))
        print(f"Exported {len(task.get('items', []))} items to {args.output_path}")
        return 0

    raise ValueError(f"unsupported command: {args.command}")


def _load_or_report(task_id: str, db_path: str | None) -> dict[str, Any] | None:
    task = load_crawl_result(task_id, db_path=db_path)
    if not task:
        print(f"Task not found: {task_id}", file=sys.stderr)
    return task


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _format_task_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No crawl results found."
    headers = ["task_id", "status", "items", "valid", "updated_at", "target_url"]
    data = [
        [
            row.get("task_id", ""),
            row.get("status", ""),
            str(row.get("item_count", 0)),
            str(bool(row.get("is_valid", False))).lower(),
            row.get("updated_at", ""),
            row.get("target_url", ""),
        ]
        for row in rows
    ]
    return _table(headers, data)


def _format_task_summary(task: dict[str, Any]) -> str:
    summary = _task_summary(task)
    lines = [
        f"task_id: {summary['task_id']}",
        f"status: {summary['status']}",
        f"item_count: {summary['item_count']}",
        f"is_valid: {str(summary['is_valid']).lower()}",
        f"confidence: {summary['confidence']}",
        f"target_url: {summary['target_url']}",
        f"user_goal: {summary['user_goal']}",
        f"created_at: {summary['created_at']}",
        f"updated_at: {summary['updated_at']}",
    ]
    return "\n".join(lines)


def _format_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No items found."
    headers = ["#", "rank", "title", "hot_score", "link"]
    data = [
        [
            str(index + 1),
            str(item.get("rank", "")),
            str(item.get("title", "")),
            str(item.get("hot_score", "")),
            str(item.get("link", "")),
        ]
        for index, item in enumerate(items)
    ]
    return _table(headers, data)


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": task.get("task_id", ""),
        "user_goal": task.get("user_goal", ""),
        "target_url": task.get("target_url", ""),
        "status": task.get("status", ""),
        "item_count": task.get("item_count", 0),
        "confidence": task.get("confidence", 0.0),
        "is_valid": bool(task.get("is_valid", False)),
        "created_at": task.get("created_at", ""),
        "updated_at": task.get("updated_at", ""),
    }


def _write_json(output_path: Path, items: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_json(items) + "\n", encoding="utf-8")


def _write_csv(output_path: Path, items: list[dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for item in items for key in item.keys()})
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    header_line = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    divider = "  ".join("-" * width for width in widths)
    body = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    ]
    return "\n".join([header_line, divider, *body])


if __name__ == "__main__":
    raise SystemExit(main())
