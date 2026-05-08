"""Project-local SQLite URL frontier."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .result_store import PROJECT_ROOT


DEFAULT_FRONTIER_DB = PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "frontier.sqlite3"


class URLFrontier:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_FRONTIER_DB
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
                CREATE TABLE IF NOT EXISTS frontier_urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    url_hash TEXT NOT NULL UNIQUE,
                    domain TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'queued',
                    kind TEXT NOT NULL DEFAULT 'page',
                    depth INTEGER NOT NULL DEFAULT 0,
                    parent_url TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    worker_id TEXT NOT NULL DEFAULT '',
                    lease_token TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    locked_at REAL NOT NULL DEFAULT 0,
                    completed_at REAL NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_frontier_status_priority ON frontier_urls(status, priority DESC, created_at ASC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_frontier_domain_status ON frontier_urls(domain, status)")

    def add_urls(
        self,
        urls: list[str],
        priority: int = 0,
        kind: str = "page",
        depth: int = 0,
        parent_url: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, int]:
        now = time.time()
        added = skipped = invalid = 0
        payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        with self.connection() as conn:
            for raw in urls:
                try:
                    url = canonical_url(raw)
                except ValueError:
                    invalid += 1
                    continue
                digest = url_hash(url)
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO frontier_urls
                    (url, url_hash, domain, priority, status, kind, depth, parent_url, payload_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)
                    """,
                    (url, digest, domain_of(url), priority, kind, depth, parent_url, payload_json, now, now),
                )
                if cursor.rowcount:
                    added += 1
                else:
                    skipped += 1
        return {"added": added, "skipped": skipped, "invalid": invalid}

    def next_batch(self, limit: int = 10, worker_id: str = "worker", lease_seconds: int = 300) -> list[dict[str, Any]]:
        now = time.time()
        lease_token = str(uuid.uuid4())
        safe_limit = max(1, min(int(limit), 200))
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM frontier_urls
                WHERE status = 'queued'
                   OR (status = 'running' AND locked_at < ?)
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
                """,
                (now - lease_seconds, safe_limit),
            ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                conn.execute(
                    f"""
                    UPDATE frontier_urls
                    SET status='running', worker_id=?, lease_token=?, locked_at=?, updated_at=?, attempts=attempts+1
                    WHERE id IN ({placeholders})
                    """,
                    (worker_id, lease_token, now, now, *ids),
                )
            claimed = conn.execute(
                f"SELECT * FROM frontier_urls WHERE lease_token = ?" if ids else "SELECT * FROM frontier_urls WHERE 0",
                (lease_token,) if ids else (),
            ).fetchall()
        return [_row_to_frontier(row) for row in claimed]

    def mark_done(self, items: list[int | str]) -> int:
        return self._mark(items, "done")

    def mark_failed(self, items: list[int | str], error: str = "", retry: bool = False) -> int:
        return self._mark(items, "queued" if retry else "failed", error=error)

    def stats(self) -> dict[str, int]:
        with self.connection() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM frontier_urls GROUP BY status").fetchall()
        return {row["status"]: row["count"] for row in rows}

    def _mark(self, items: list[int | str], status: str, error: str = "") -> int:
        now = time.time()
        changed = 0
        with self.connection() as conn:
            for item in items:
                if isinstance(item, int):
                    cursor = conn.execute(
                        "UPDATE frontier_urls SET status=?, error=?, updated_at=?, completed_at=? WHERE id=?",
                        (status, error, now, now if status == "done" else 0, item),
                    )
                else:
                    cursor = conn.execute(
                        "UPDATE frontier_urls SET status=?, error=?, updated_at=?, completed_at=? WHERE url=?",
                        (status, error, now, now if status == "done" else 0, item),
                    )
                changed += cursor.rowcount
        return changed


def canonical_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("frontier only accepts http/https URLs")
    return parsed.geturl()


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _row_to_frontier(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json") or "{}")
    return item
