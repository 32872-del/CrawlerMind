"""Adapter for the bundled fnspider engine.

The Agent should depend on this thin boundary instead of importing fnspider
internals directly. That keeps the mature crawler framework portable while
giving the workflow a simple tool-like interface.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from autonomous_crawler.engines.fnspider import settings
from autonomous_crawler.engines.fnspider.ConfigSpider import ConfigSpider
from autonomous_crawler.engines.fnspider.site_spec import (
    load_site_spec,
    normalize_site_spec,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SITE_SPECS_DIR = PACKAGE_ROOT / "site_specs"
SITE_SPECS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FnSpiderRunResult:
    status: str
    spec_path: str
    db_path: str = ""
    item_count: int = 0
    error: str = ""


def validate_fnspider_site_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a fnspider site_spec draft."""
    return normalize_site_spec(load_site_spec(spec))


def save_fnspider_site_spec(spec: dict[str, Any], filename: str | None = None) -> Path:
    """Persist a site_spec inside the current Agent project."""
    normalized = validate_fnspider_site_spec(spec)
    site = normalized["site"]
    spec_path = SITE_SPECS_DIR / (filename or f"{site}.json")
    spec_path.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return spec_path


def run_fnspider_site_spec(spec: dict[str, Any], *, save_spec: bool = True) -> FnSpiderRunResult:
    """Run ConfigSpider for a site_spec and return the generated DB path.

    This function is intended for real crawls, not unit tests. It may launch a
    browser depending on the spec mode.
    """
    try:
        normalized = validate_fnspider_site_spec(spec)
        spec_path = save_fnspider_site_spec(normalized) if save_spec else Path("")
        spider = ConfigSpider(spec=normalized)
        spider.start()
        item_count = count_goods_rows(spider.db_path)
        return FnSpiderRunResult(
            status="completed",
            spec_path=str(spec_path),
            db_path=spider.db_path,
            item_count=item_count,
        )
    except Exception as exc:
        return FnSpiderRunResult(
            status="failed",
            spec_path="",
            error=str(exc),
        )


def count_goods_rows(db_path: str | Path) -> int:
    path = Path(db_path)
    if not path.exists():
        return 0
    with sqlite3.connect(path) as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM goods")
        return int(cursor.fetchone()[0])


def load_goods_rows(db_path: str | Path, limit: int = 100) -> list[dict[str, Any]]:
    path = Path(db_path)
    if not path.exists():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM goods LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]


def fnspider_runtime_paths() -> dict[str, str]:
    return {
        "site_specs": str(SITE_SPECS_DIR),
        "cache": settings.CACHE_DIR,
        "goods": settings.OUT_PATH,
    }
