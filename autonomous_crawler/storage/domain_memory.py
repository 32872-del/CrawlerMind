"""Small SQLite domain memory for crawl mode decisions."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from .result_store import PROJECT_ROOT


DEFAULT_DOMAIN_MEMORY_DB = PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "domain_memory.sqlite3"


class DomainMemory:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DOMAIN_MEMORY_DB
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
                CREATE TABLE IF NOT EXISTS domain_modes (
                    domain TEXT PRIMARY KEY,
                    preferred_mode TEXT NOT NULL DEFAULT '',
                    last_challenge TEXT NOT NULL DEFAULT '',
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
                """
            )

    def record_success(self, domain: str, mode: str) -> None:
        now = time.time()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO domain_modes (domain, preferred_mode, success_count, failure_count, updated_at)
                VALUES (?, ?, 1, 0, ?)
                ON CONFLICT(domain) DO UPDATE SET
                  preferred_mode=excluded.preferred_mode,
                  success_count=domain_modes.success_count+1,
                  updated_at=excluded.updated_at
                """,
                (domain.lower(), mode, now),
            )

    def record_failure(self, domain: str, challenge: str = "") -> None:
        now = time.time()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO domain_modes (domain, last_challenge, success_count, failure_count, updated_at)
                VALUES (?, ?, 0, 1, ?)
                ON CONFLICT(domain) DO UPDATE SET
                  last_challenge=CASE WHEN excluded.last_challenge != '' THEN excluded.last_challenge ELSE domain_modes.last_challenge END,
                  failure_count=domain_modes.failure_count+1,
                  updated_at=excluded.updated_at
                """,
                (domain.lower(), challenge, now),
            )

    def lookup(self, domain: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM domain_modes WHERE domain=?", (domain.lower(),)).fetchone()
        return dict(row) if row else None

    def stats(self) -> dict[str, int]:
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM domain_modes").fetchone()[0]
        return {"total_domains": int(total)}
