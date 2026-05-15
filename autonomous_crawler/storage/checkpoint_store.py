"""SQLite checkpoint store for CLM-native spider runs.

SCRAPLING-ABSORB-3B: persistent, inspectable checkpoint storage for long
running crawls.  This store is intentionally JSON/SQLite based rather than
pickle based so a failed or paused run can be inspected and resumed by CLM.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from autonomous_crawler.runners.spider_models import (
    CrawlItemResult,
    CrawlRequestEnvelope,
    SpiderRunSummary,
)
from autonomous_crawler.runtime import RuntimeEvent
from autonomous_crawler.tools.proxy_trace import redact_error_message

from .result_store import PROJECT_ROOT


DEFAULT_CHECKPOINT_DB = PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "spider_checkpoints.sqlite3"


class CheckpointStore:
    """SQLite-backed checkpoint store for native spider runs."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_CHECKPOINT_DB
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
                CREATE TABLE IF NOT EXISTS spider_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    pause_reason TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spider_checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    frontier_items_json TEXT NOT NULL,
                    events_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spider_request_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spider_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    error TEXT NOT NULL,
                    retryable INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS spider_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spider_checkpoints_run ON spider_checkpoints(run_id, id DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spider_failures_run_bucket ON spider_failures(run_id, bucket)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spider_items_run ON spider_items(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spider_events_run_request ON spider_request_events(run_id, request_id)")

    def start_run(self, run_id: str, config: dict[str, Any] | None = None) -> None:
        run_id = _require_text(run_id, "run_id")
        now = utc_now_iso()
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT started_at FROM spider_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            started_at = existing["started_at"] if existing else now
            conn.execute(
                """
                INSERT INTO spider_runs (
                    run_id, status, config_json, pause_reason, started_at,
                    updated_at, completed_at
                )
                VALUES (?, 'running', ?, '', ?, ?, '')
                ON CONFLICT(run_id) DO UPDATE SET
                    status = 'running',
                    config_json = excluded.config_json,
                    pause_reason = '',
                    updated_at = excluded.updated_at,
                    completed_at = ''
                """,
                (run_id, _to_json(config or {}), started_at, now),
            )

    def save_batch_checkpoint(
        self,
        *,
        run_id: str,
        batch_id: str,
        frontier_items: list[dict[str, Any]],
        summary: SpiderRunSummary,
        events: list[RuntimeEvent] | None = None,
    ) -> None:
        run_id = _require_text(run_id, "run_id")
        batch_id = _require_text(batch_id, "batch_id")
        now = utc_now_iso()
        safe_events = [event.to_dict() for event in (events or [])]
        with self.connection() as conn:
            self._ensure_run(conn, run_id)
            conn.execute(
                """
                INSERT INTO spider_checkpoints (
                    run_id, batch_id, summary_json, frontier_items_json,
                    events_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    batch_id,
                    _to_json(summary.as_dict()),
                    _to_json(frontier_items),
                    _to_json(safe_events),
                    now,
                ),
            )
            for event in events or []:
                conn.execute(
                    """
                    INSERT INTO spider_request_events (
                        run_id, request_id, url, event_type, event_json, created_at
                    )
                    VALUES (?, '', '', ?, ?, ?)
                    """,
                    (run_id, event.type, _to_json(event.to_dict()), now),
                )
            self._touch_run(conn, run_id, status=summary.status if summary.status != "completed" else "running", now=now)

    def save_item_checkpoint(
        self,
        *,
        run_id: str,
        request: CrawlRequestEnvelope,
        result: CrawlItemResult,
    ) -> None:
        run_id = _require_text(run_id, "run_id")
        now = utc_now_iso()
        with self.connection() as conn:
            self._ensure_run(conn, run_id)
            for event in result.runtime_events:
                conn.execute(
                    """
                    INSERT INTO spider_request_events (
                        run_id, request_id, url, event_type, event_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        request.request_id,
                        request.url,
                        event.type,
                        _to_json(event.to_dict()),
                        now,
                    ),
                )
            for record in result.records:
                conn.execute(
                    """
                    INSERT INTO spider_items (
                        run_id, request_id, record_type, record_json, dedupe_key, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        request.request_id,
                        _record_type(record),
                        _to_json(record),
                        _dedupe_key(record),
                        now,
                    ),
                )
            if not result.ok:
                conn.execute(
                    """
                    INSERT INTO spider_failures (
                        run_id, request_id, url, bucket, error, retryable,
                        attempts, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        request.request_id,
                        request.url,
                        result.failure_bucket or "runtime_error",
                        redact_error_message(result.error),
                        1 if result.retry else 0,
                        request.retry_count,
                        now,
                    ),
                )
            self._touch_run(conn, run_id, now=now)

    def save_failure(
        self,
        *,
        run_id: str,
        request: CrawlRequestEnvelope,
        bucket: str,
        error: str,
        retryable: bool,
    ) -> None:
        run_id = _require_text(run_id, "run_id")
        now = utc_now_iso()
        with self.connection() as conn:
            self._ensure_run(conn, run_id)
            conn.execute(
                """
                INSERT INTO spider_failures (
                    run_id, request_id, url, bucket, error, retryable,
                    attempts, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    request.request_id,
                    request.url,
                    bucket or "runtime_error",
                    redact_error_message(error),
                    1 if retryable else 0,
                    request.retry_count,
                    now,
                ),
            )
            self._touch_run(conn, run_id, now=now)

    def load_latest(self, run_id: str) -> dict[str, Any] | None:
        run_id = _require_text(run_id, "run_id")
        with self.connection() as conn:
            run = conn.execute(
                "SELECT * FROM spider_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not run:
                return None
            checkpoint = conn.execute(
                """
                SELECT * FROM spider_checkpoints
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            item_count = conn.execute(
                "SELECT COUNT(*) FROM spider_items WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
            failure_count = conn.execute(
                "SELECT COUNT(*) FROM spider_failures WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]

        result = {
            "run": _row_to_run(run),
            "latest_checkpoint": _row_to_checkpoint(checkpoint) if checkpoint else None,
            "item_count": item_count,
            "failure_count": failure_count,
        }
        return result

    def list_failures(self, run_id: str, bucket: str = "") -> list[dict[str, Any]]:
        run_id = _require_text(run_id, "run_id")
        with self.connection() as conn:
            if bucket:
                rows = conn.execute(
                    """
                    SELECT * FROM spider_failures
                    WHERE run_id = ? AND bucket = ?
                    ORDER BY id ASC
                    """,
                    (run_id, bucket),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM spider_failures
                    WHERE run_id = ?
                    ORDER BY id ASC
                    """,
                    (run_id,),
                ).fetchall()
        return [_row_to_failure(row) for row in rows]

    def list_items(self, run_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 10000))
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM spider_items
                WHERE run_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (run_id, safe_limit),
            ).fetchall()
        return [_row_to_item(row) for row in rows]

    def mark_paused(self, run_id: str, reason: str = "") -> None:
        run_id = _require_text(run_id, "run_id")
        now = utc_now_iso()
        with self.connection() as conn:
            self._ensure_run(conn, run_id)
            conn.execute(
                """
                UPDATE spider_runs
                SET status='paused', pause_reason=?, updated_at=?
                WHERE run_id=?
                """,
                (redact_error_message(reason), now, run_id),
            )

    def mark_completed(self, run_id: str) -> None:
        run_id = _require_text(run_id, "run_id")
        now = utc_now_iso()
        with self.connection() as conn:
            self._ensure_run(conn, run_id)
            conn.execute(
                """
                UPDATE spider_runs
                SET status='completed', updated_at=?, completed_at=?
                WHERE run_id=?
                """,
                (now, now, run_id),
            )

    def _ensure_run(self, conn: sqlite3.Connection, run_id: str) -> None:
        existing = conn.execute(
            "SELECT run_id FROM spider_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if existing:
            return
        now = utc_now_iso()
        conn.execute(
            """
            INSERT INTO spider_runs (
                run_id, status, config_json, started_at, updated_at
            )
            VALUES (?, 'running', '{}', ?, ?)
            """,
            (run_id, now, now),
        )

    def _touch_run(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        *,
        now: str,
        status: str | None = None,
    ) -> None:
        if status:
            conn.execute(
                "UPDATE spider_runs SET status=?, updated_at=? WHERE run_id=?",
                (status, now, run_id),
            )
        else:
            conn.execute(
                "UPDATE spider_runs SET updated_at=? WHERE run_id=?",
                (now, run_id),
            )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_json_default, sort_keys=True)


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_safe_dict"):
        return value.to_safe_dict()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return str(value)


def _json_or_default(value: str, default: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _require_text(value: str, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _record_type(record: Any) -> str:
    if isinstance(record, dict):
        value = record.get("record_type") or record.get("type") or "dict"
        return str(value)[:80]
    return type(record).__name__[:80]


def _dedupe_key(record: Any) -> str:
    if isinstance(record, dict):
        value = record.get("dedupe_key") or record.get("canonical_url") or record.get("url") or ""
        return str(value)[:500]
    value = getattr(record, "dedupe_key", "")
    return str(value)[:500]


def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "status": row["status"],
        "config": _json_or_default(row["config_json"], {}),
        "pause_reason": row["pause_reason"],
        "started_at": row["started_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
    }


def _row_to_checkpoint(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "batch_id": row["batch_id"],
        "summary": _json_or_default(row["summary_json"], {}),
        "frontier_items": _json_or_default(row["frontier_items_json"], []),
        "events": _json_or_default(row["events_json"], []),
        "created_at": row["created_at"],
    }


def _row_to_failure(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "request_id": row["request_id"],
        "url": row["url"],
        "bucket": row["bucket"],
        "error": redact_error_message(row["error"]),
        "retryable": bool(row["retryable"]),
        "attempts": row["attempts"],
        "created_at": row["created_at"],
    }


def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "request_id": row["request_id"],
        "record_type": row["record_type"],
        "record": _json_or_default(row["record_json"], {}),
        "dedupe_key": row["dedupe_key"],
        "created_at": row["created_at"],
    }
