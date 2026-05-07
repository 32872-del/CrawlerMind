"""Project-local SQLite persistence for crawl workflow results."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "crawl_results.sqlite3"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CrawlResultStore:
    """Small SQLite store for completed or failed crawl workflow states."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
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
                CREATE TABLE IF NOT EXISTS crawl_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_goal TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0,
                    is_valid INTEGER NOT NULL DEFAULT 0,
                    final_state_json TEXT NOT NULL,
                    error_log_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    item_index INTEGER NOT NULL,
                    item_json TEXT NOT NULL,
                    title TEXT,
                    link TEXT,
                    rank TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES crawl_tasks(task_id)
                        ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crawl_tasks_updated_at
                ON crawl_tasks(updated_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_crawl_items_task_id
                ON crawl_items(task_id)
                """
            )

    def save_final_state(self, state: dict[str, Any]) -> str:
        task_id = str(state.get("task_id") or "")
        if not task_id:
            raise ValueError("Cannot persist crawl result without task_id")

        extracted = state.get("extracted_data") or {}
        validation = state.get("validation_result") or {}
        items = list(extracted.get("items") or [])
        now = utc_now_iso()
        final_state_json = _to_json(state)
        error_log_json = _to_json(state.get("error_log") or [])

        with self.connection() as conn:
            existing = conn.execute(
                "SELECT created_at FROM crawl_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            conn.execute(
                """
                INSERT INTO crawl_tasks (
                    task_id, user_goal, target_url, status, item_count,
                    confidence, is_valid, final_state_json, error_log_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    user_goal = excluded.user_goal,
                    target_url = excluded.target_url,
                    status = excluded.status,
                    item_count = excluded.item_count,
                    confidence = excluded.confidence,
                    is_valid = excluded.is_valid,
                    final_state_json = excluded.final_state_json,
                    error_log_json = excluded.error_log_json,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    str(state.get("user_goal") or ""),
                    str(state.get("target_url") or ""),
                    str(state.get("status") or "unknown"),
                    int(extracted.get("item_count") or len(items)),
                    float(extracted.get("confidence") or 0.0),
                    1 if validation.get("is_valid") else 0,
                    final_state_json,
                    error_log_json,
                    created_at,
                    now,
                ),
            )
            conn.execute("DELETE FROM crawl_items WHERE task_id = ?", (task_id,))
            conn.executemany(
                """
                INSERT INTO crawl_items (
                    task_id, item_index, item_json, title, link, rank, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        task_id,
                        index,
                        _to_json(item),
                        _optional_text(item.get("title")),
                        _optional_text(item.get("link")),
                        _optional_text(item.get("rank")),
                        now,
                    )
                    for index, item in enumerate(items)
                ],
            )

        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM crawl_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if not row:
                return None
            items = conn.execute(
                """
                SELECT item_json FROM crawl_items
                WHERE task_id = ?
                ORDER BY item_index ASC
                """,
                (task_id,),
            ).fetchall()

        result = _row_to_task(row)
        result["items"] = [json.loads(item["item_json"]) for item in items]
        return result

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 200))
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT task_id, user_goal, target_url, status, item_count,
                       confidence, is_valid, created_at, updated_at
                FROM crawl_tasks
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        return [_row_to_task(row, include_final_state=False) for row in rows]


def save_crawl_result(state: dict[str, Any], db_path: str | Path | None = None) -> str:
    return CrawlResultStore(db_path=db_path).save_final_state(state)


def load_crawl_result(task_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    return CrawlResultStore(db_path=db_path).get_task(task_id)


def list_crawl_results(limit: int = 20, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    return CrawlResultStore(db_path=db_path).list_tasks(limit=limit)


def _row_to_task(row: sqlite3.Row, include_final_state: bool = True) -> dict[str, Any]:
    result = {
        "task_id": row["task_id"],
        "user_goal": row["user_goal"],
        "target_url": row["target_url"],
        "status": row["status"],
        "item_count": row["item_count"],
        "confidence": row["confidence"],
        "is_valid": bool(row["is_valid"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_final_state and "final_state_json" in row.keys():
        result["final_state"] = json.loads(row["final_state_json"])
        result["error_log"] = json.loads(row["error_log_json"])
    return result


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)
