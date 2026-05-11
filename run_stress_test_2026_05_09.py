#!/usr/bin/env python3
"""Local stress test for Crawler-Mind large ecommerce runs.

This script does not hit public websites. It generates synthetic ecommerce
records and exercises the local frontier, result store, and Excel export path.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from autonomous_crawler.storage.frontier import URLFrontier
from autonomous_crawler.storage.result_store import CrawlResultStore


OUTPUT_DIR = Path("dev_logs") / "stress"
SUMMARY_PATH = OUTPUT_DIR / "2026-05-09_local_stress_test_summary.json"
REPORT_PATH = OUTPUT_DIR / "2026-05-09_local_stress_test_report.md"


@dataclass
class SyntheticProduct:
    source_site: str
    category: str
    source_url: str
    product_title: str
    highest_price: str
    colors: str
    sizes: str
    product_description: str
    image_urls: str
    mode: str = "synthetic_local_stress"
    status: str = "ok"
    notes: str = ""


def build_product(index: int) -> SyntheticProduct:
    category_id = index % 120
    variant_id = index % 8
    return SyntheticProduct(
        source_site="stress.local",
        category=f"category-{category_id:03d}",
        source_url=f"https://stress.local/category/{category_id:03d}/product/{index:07d}",
        product_title=f"Synthetic Product {index:07d}",
        highest_price=f"€{(index % 500) + 9.99:.2f}",
        colors=["Black", "White", "Blue", "Red", "Green", "Tan", "Silver", "Pink"][variant_id],
        sizes=" | ".join(["XS", "S", "M", "L", "XL"][: (index % 5) + 1]),
        product_description=(
            "Synthetic ecommerce detail record used for local CLM stress testing. "
            f"category={category_id:03d}; variant={variant_id}; index={index}."
        ),
        image_urls=(
            f"https://stress.local/images/{index:07d}_1.jpg | "
            f"https://stress.local/images/{index:07d}_2.jpg"
        ),
        notes="generated without network access",
    )


def chunked_range(total: int, chunk_size: int) -> list[range]:
    return [range(start, min(start + chunk_size, total)) for start in range(0, total, chunk_size)]


def run_frontier_stress(db_path: Path, total: int, batch_size: int) -> dict[str, Any]:
    frontier = URLFrontier(db_path)
    started = time.perf_counter()
    add_summary = {"added": 0, "skipped": 0, "invalid": 0}
    duplicate_every = max(1, total // 20)
    for part in chunked_range(total, batch_size * 10):
        urls = [build_product(index).source_url for index in part]
        urls.extend(build_product(index).source_url for index in part if index % duplicate_every == 0)
        urls.append("not-a-url")
        result = frontier.add_urls(urls, priority=10, kind="detail_page", depth=1)
        for key in add_summary:
            add_summary[key] += result[key]
    add_elapsed = time.perf_counter() - started

    processed = 0
    claim_started = time.perf_counter()
    checkpoints: list[dict[str, Any]] = []
    while True:
        batch = frontier.next_batch(limit=batch_size, worker_id="stress-test", lease_seconds=60)
        if not batch:
            break
        frontier.mark_done([item["id"] for item in batch])
        processed += len(batch)
        if processed % max(batch_size * 10, 1) == 0 or processed == total:
            checkpoints.append({"processed": processed, "stats": frontier.stats()})
    claim_elapsed = time.perf_counter() - claim_started

    return {
        "db_path": str(db_path),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "add_summary": add_summary,
        "final_stats": frontier.stats(),
        "processed": processed,
        "add_elapsed_seconds": round(add_elapsed, 3),
        "claim_mark_elapsed_seconds": round(claim_elapsed, 3),
        "checkpoints": checkpoints[-10:],
    }


def run_result_store_stress(db_path: Path, total: int) -> dict[str, Any]:
    store = CrawlResultStore(db_path)
    items = [asdict(build_product(index)) for index in range(total)]
    state = {
        "task_id": f"stress-{total}",
        "user_goal": f"local stress test with {total} ecommerce records",
        "target_url": "mock://stress/ecommerce",
        "status": "completed",
        "extracted_data": {
            "items": items,
            "item_count": len(items),
            "confidence": 1.0,
        },
        "validation_result": {
            "is_valid": True,
            "completeness": 1.0,
            "anomalies": [],
        },
        "error_log": [],
    }
    started = time.perf_counter()
    task_id = store.save_final_state(state)
    save_elapsed = time.perf_counter() - started
    load_started = time.perf_counter()
    loaded = store.get_task(task_id)
    load_elapsed = time.perf_counter() - load_started
    return {
        "db_path": str(db_path),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "task_id": task_id,
        "saved_items": len(items),
        "loaded_items": len((loaded or {}).get("items") or []),
        "save_elapsed_seconds": round(save_elapsed, 3),
        "load_elapsed_seconds": round(load_elapsed, 3),
    }


def run_excel_export(total: int, keep_excel: bool) -> dict[str, Any]:
    output_path = OUTPUT_DIR / f"2026-05-09_stress_export_{total}.xlsx"
    frame = pd.DataFrame(asdict(build_product(index)) for index in range(total))
    started = time.perf_counter()
    frame.to_excel(output_path, sheet_name="stress.local", index=False)
    elapsed = time.perf_counter() - started
    size = output_path.stat().st_size if output_path.exists() else 0
    if not keep_excel and output_path.exists():
        output_path.unlink()
    return {
        "path": str(output_path),
        "kept": keep_excel,
        "rows": total,
        "columns": len(frame.columns),
        "size_bytes": size,
        "elapsed_seconds": round(elapsed, 3),
    }


def analyze(summary: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    total = int(summary["config"]["items"])
    frontier = summary["frontier"]
    result_store = summary["result_store"]
    export = summary["excel_export"]
    if frontier["processed"] == total and frontier["final_stats"].get("done") == total:
        findings.append("PASS: frontier inserted, claimed, and completed all unique synthetic URLs.")
    else:
        findings.append("FAIL: frontier did not process all expected URLs.")
    if frontier["add_summary"]["skipped"] > 0 and frontier["add_summary"]["invalid"] > 0:
        findings.append("PASS: duplicate and invalid URL paths were exercised.")
    else:
        findings.append("WARN: duplicate/invalid URL paths were not meaningfully exercised.")
    if result_store["saved_items"] == total and result_store["loaded_items"] == total:
        findings.append("PASS: result store saved and loaded all synthetic records.")
    else:
        findings.append("FAIL: result store item count mismatch.")
    if export["rows"] == total and export["size_bytes"] > 0:
        findings.append("PASS: Excel export completed for the requested row count.")
    else:
        findings.append("FAIL: Excel export did not complete.")
    findings.append(
        "RISK: current CrawlResultStore duplicates large result payloads in final_state_json "
        "and crawl_items, so very large crawls need checkpointed product storage before real long runs."
    )
    findings.append(
        "RISK: FastAPI job registry remains in-memory; process restart loses running job state."
    )
    return findings


def write_report(summary: dict[str, Any]) -> None:
    lines = [
        "# 2026-05-09 Local Stress Test Report",
        "",
        "This is a local synthetic test. It does not send requests to public websites.",
        "",
        "## Config",
        "",
        f"- items: {summary['config']['items']}",
        f"- batch_size: {summary['config']['batch_size']}",
        f"- keep_excel: {summary['config']['keep_excel']}",
        "",
        "## Timing",
        "",
        f"- frontier add: {summary['frontier']['add_elapsed_seconds']}s",
        f"- frontier claim/mark: {summary['frontier']['claim_mark_elapsed_seconds']}s",
        f"- result store save: {summary['result_store']['save_elapsed_seconds']}s",
        f"- result store load: {summary['result_store']['load_elapsed_seconds']}s",
        f"- Excel export: {summary['excel_export']['elapsed_seconds']}s",
        "",
        "## Sizes",
        "",
        f"- frontier db: {summary['frontier']['db_size_bytes']} bytes",
        f"- result db: {summary['result_store']['db_size_bytes']} bytes",
        f"- Excel file: {summary['excel_export']['size_bytes']} bytes",
        f"- peak memory: {summary['memory']['peak_mb']} MB",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in summary["findings"])
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def run(items: int, batch_size: int, keep_excel: bool, keep_db: bool) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix="clm_stress_"))
    try:
        tracemalloc.start()
        started = time.perf_counter()
        frontier = run_frontier_stress(temp_dir / "frontier.sqlite3", items, batch_size)
        result_store = run_result_store_stress(temp_dir / "results.sqlite3", items)
        excel_export = run_excel_export(items, keep_excel)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        summary: dict[str, Any] = {
            "config": {
                "items": items,
                "batch_size": batch_size,
                "keep_excel": keep_excel,
                "keep_db": keep_db,
            },
            "frontier": frontier,
            "result_store": result_store,
            "excel_export": excel_export,
            "memory": {
                "current_mb": round(current / 1024 / 1024, 2),
                "peak_mb": round(peak / 1024 / 1024, 2),
            },
            "total_elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        if keep_db:
            kept_dir = OUTPUT_DIR / f"2026-05-09_stress_runtime_{items}"
            if kept_dir.exists():
                shutil.rmtree(kept_dir)
            shutil.copytree(temp_dir, kept_dir)
            summary["kept_db_dir"] = str(kept_dir)
        summary["findings"] = analyze(summary)
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        write_report(summary)
        return summary
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local synthetic CLM stress test.")
    parser.add_argument("--items", type=int, default=30000, help="Synthetic product count.")
    parser.add_argument("--batch-size", type=int, default=500, help="Frontier claim batch size.")
    parser.add_argument("--keep-excel", action="store_true", help="Keep generated Excel file.")
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="Keep temporary SQLite DBs under dev_logs/stress.",
    )
    args = parser.parse_args()
    summary = run(
        items=max(1, args.items),
        batch_size=max(1, args.batch_size),
        keep_excel=args.keep_excel,
        keep_db=args.keep_db,
    )
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
