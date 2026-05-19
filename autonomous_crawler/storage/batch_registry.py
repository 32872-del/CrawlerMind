"""Durable SQLite-backed batch job registry.

Replaces the in-memory ``_jobs`` dict in the FastAPI layer with a persistent
store that survives process restarts.  Follows the same constructor / connection
/ initialize pattern as URLFrontier, ProductStore, and CheckpointStore.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from .result_store import PROJECT_ROOT

DEFAULT_REGISTRY_DB = PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "batch_registry.sqlite3"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _json_or_default(text: str | None, default: dict[str, Any]) -> dict[str, Any]:
    if not text:
        return dict(default)
    try:
        result = json.loads(text)
        return dict(result) if isinstance(result, dict) else dict(default)
    except (json.JSONDecodeError, TypeError):
        return dict(default)


class BatchRegistry:
    """Durable SQLite-backed batch job registry.

    Thread-safe: all mutations go through a module-level lock to serialize
    writes.  Reads use their own connections (SQLite handles concurrent reads).
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_REGISTRY_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
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
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    task_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    job_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_jobs_status_created
                ON batch_jobs (status, created_at)
            """)

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def register(
        self,
        task_id: str,
        kind: str,
        job_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Unconditionally register a new job.  Returns the job record."""
        now = _utc_now_iso()
        record: dict[str, Any] = {
            "task_id": task_id,
            "kind": kind,
            "status": "running",
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            **(job_data or {}),
        }
        with self._lock, self.connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO batch_jobs (task_id, kind, status, created_at, updated_at, completed_at, job_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, kind, "running", now, now, None, _to_json(record)),
            )
        return record

    def try_register(
        self,
        task_id: str,
        kind: str,
        job_data: dict[str, Any] | None = None,
        max_active: int = 4,
    ) -> bool:
        """Register only if active job count is below *max_active*.

        Returns ``True`` if registered, ``False`` if at capacity.
        """
        with self._lock:
            active = self._count_active_locked()
            if active >= max_active:
                return False
            now = _utc_now_iso()
            record: dict[str, Any] = {
                "task_id": task_id,
                "kind": kind,
                "status": "running",
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
                **(job_data or {}),
            }
            with self.connection() as conn:
                conn.execute(
                    "INSERT INTO batch_jobs (task_id, kind, status, created_at, updated_at, completed_at, job_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (task_id, kind, "running", now, now, None, _to_json(record)),
                )
        return True

    def update(self, task_id: str, **kwargs: Any) -> None:
        """Merge *kwargs* into the job's JSON payload and bump ``updated_at``."""
        with self._lock, self.connection() as conn:
            row = conn.execute(
                "SELECT job_json FROM batch_jobs WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                return
            data = _json_or_default(row["job_json"], {})
            data.update(kwargs)
            data["updated_at"] = _utc_now_iso()
            conn.execute(
                "UPDATE batch_jobs SET job_json = ?, updated_at = ? WHERE task_id = ?",
                (_to_json(data), data["updated_at"], task_id),
            )

    def get(self, task_id: str) -> dict[str, Any] | None:
        """Return the job record dict, or ``None`` if not found."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT job_json FROM batch_jobs WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                return None
            data = _json_or_default(row["job_json"], {})
            data["task_id"] = task_id
            return data

    def remove(self, task_id: str) -> bool:
        """Delete a job.  Returns ``True`` if a row was removed."""
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM batch_jobs WHERE task_id = ?", (task_id,)
            )
            return cursor.rowcount > 0

    def mark_status(self, task_id: str, status: str) -> None:
        """Set the job status and update timestamps."""
        now = _utc_now_iso()
        completed_at = now if status in ("completed", "failed", "cancelled") else None
        with self._lock, self.connection() as conn:
            conn.execute(
                "UPDATE batch_jobs SET status = ?, updated_at = ?, completed_at = ? WHERE task_id = ?",
                (status, now, completed_at, task_id),
            )
            # Also update inside job_json
            row = conn.execute(
                "SELECT job_json FROM batch_jobs WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row:
                data = _json_or_default(row["job_json"], {})
                data["status"] = status
                data["updated_at"] = now
                if completed_at:
                    data["completed_at"] = completed_at
                conn.execute(
                    "UPDATE batch_jobs SET job_json = ? WHERE task_id = ?",
                    (_to_json(data), task_id),
                )

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def count_active(self) -> int:
        """Count jobs with status ``running``."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM batch_jobs WHERE status = 'running'"
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def _count_active_locked(self) -> int:
        """Count active jobs (caller must hold ``_lock``)."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM batch_jobs WHERE status = 'running'"
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def cleanup_stale(self, retention_seconds: int = 3600) -> int:
        """Remove completed/failed/cancelled jobs older than *retention_seconds*.

        Returns the number of rows deleted.
        """
        cutoff_dt = datetime.now(timezone.utc).timestamp() - retention_seconds
        cutoff = datetime.fromtimestamp(cutoff_dt, tz=timezone.utc).isoformat()
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM batch_jobs WHERE status IN ('completed', 'failed', 'cancelled') "
                "AND updated_at < ?",
                (cutoff,),
            )
            return cursor.rowcount

    def list_jobs(
        self,
        status: str = "",
        kind: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List jobs with optional filters."""
        limit = max(1, min(limit, 500))
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connection() as conn:
            rows = conn.execute(
                f"SELECT task_id, kind, status, created_at, updated_at, completed_at, job_json "
                f"FROM batch_jobs {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            data = _json_or_default(row["job_json"], {})
            data["task_id"] = row["task_id"]
            data["kind"] = row["kind"]
            data["status"] = row["status"]
            data["created_at"] = row["created_at"]
            data["updated_at"] = row["updated_at"]
            data["completed_at"] = row["completed_at"]
            results.append(data)
        return results

    def recover_running(self) -> list[dict[str, Any]]:
        """Return all jobs stuck in ``running`` state from a prior crash.

        The caller decides how to handle them (mark failed, re-enqueue, etc.).
        """
        return self.list_jobs(status="running", limit=500)
