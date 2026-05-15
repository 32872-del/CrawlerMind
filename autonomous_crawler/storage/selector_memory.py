"""Persistent selector signature memory for adaptive parser recovery.

The store is CLM-native and SQLite-backed. It lets parser runtimes save
successful element signatures and recover them later when CSS/XPath selectors
drift across runs.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .result_store import PROJECT_ROOT


DEFAULT_SELECTOR_MEMORY_DB = (
    PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "selector_memory.sqlite3"
)


class SelectorMemoryStore:
    """SQLite store for adaptive element signatures."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_SELECTOR_MEMORY_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS selector_signatures (
                    site_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    selector TEXT NOT NULL,
                    selector_type TEXT NOT NULL,
                    attribute TEXT NOT NULL DEFAULT '',
                    signature_json TEXT NOT NULL,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    recover_count INTEGER NOT NULL DEFAULT 0,
                    last_score REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (site_key, name, selector, selector_type, attribute)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_selector_signatures_site_name
                ON selector_signatures(site_key, name)
                """
            )

    def save_signature(
        self,
        *,
        site_key: str,
        name: str,
        selector: str,
        selector_type: str,
        attribute: str = "",
        signature: dict[str, Any],
    ) -> None:
        site_key = _clean(site_key, "default", 200)
        name = _clean(name, "field", 100)
        selector = _clean(selector, "", 600)
        selector_type = _clean(selector_type, "css", 30)
        attribute = _clean(attribute, "", 100)
        if not selector or not signature:
            return
        now = _utc_now()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO selector_signatures (
                    site_key, name, selector, selector_type, attribute,
                    signature_json, success_count, recover_count, last_score,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, ?, ?)
                ON CONFLICT(site_key, name, selector, selector_type, attribute)
                DO UPDATE SET
                    signature_json = excluded.signature_json,
                    success_count = selector_signatures.success_count + 1,
                    updated_at = excluded.updated_at
                """,
                (
                    site_key,
                    name,
                    selector,
                    selector_type,
                    attribute,
                    _to_json(signature),
                    now,
                    now,
                ),
            )

    def load_signature(
        self,
        *,
        site_key: str,
        name: str,
        selector: str,
        selector_type: str,
        attribute: str = "",
    ) -> dict[str, Any]:
        site_key = _clean(site_key, "default", 200)
        name = _clean(name, "field", 100)
        selector = _clean(selector, "", 600)
        selector_type = _clean(selector_type, "css", 30)
        attribute = _clean(attribute, "", 100)
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT signature_json FROM selector_signatures
                WHERE site_key = ? AND name = ? AND selector = ?
                  AND selector_type = ? AND attribute = ?
                """,
                (site_key, name, selector, selector_type, attribute),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    """
                    SELECT signature_json FROM selector_signatures
                    WHERE site_key = ? AND name = ?
                    ORDER BY updated_at DESC LIMIT 1
                    """,
                    (site_key, name),
                ).fetchone()
        if row is None:
            return {}
        try:
            payload = json.loads(str(row["signature_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def record_recovery(
        self,
        *,
        site_key: str,
        name: str,
        selector: str,
        selector_type: str,
        attribute: str = "",
        score: float = 0.0,
    ) -> None:
        site_key = _clean(site_key, "default", 200)
        name = _clean(name, "field", 100)
        selector = _clean(selector, "", 600)
        selector_type = _clean(selector_type, "css", 30)
        attribute = _clean(attribute, "", 100)
        now = _utc_now()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE selector_signatures
                SET recover_count = recover_count + 1,
                    last_score = ?,
                    updated_at = ?
                WHERE site_key = ? AND name = ? AND selector = ?
                  AND selector_type = ? AND attribute = ?
                """,
                (float(score), now, site_key, name, selector, selector_type, attribute),
            )

    def get_all(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT site_key, name, selector, selector_type, attribute,
                       success_count, recover_count, last_score, created_at, updated_at
                FROM selector_signatures
                ORDER BY site_key, name, selector
                """
            ).fetchall()
        return [dict(row) for row in rows]


def _to_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, default: str, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    return text[:max_len]
