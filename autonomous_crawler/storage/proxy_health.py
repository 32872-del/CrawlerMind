"""Proxy health persistence for long-running crawl stability (CAP-3.3).

Stores per-proxy success/failure counts, cooldown state, and last error.
Never stores plaintext proxy passwords — only a redacted proxy ID derived
from the URL hash.
"""
from __future__ import annotations

import hashlib
import sqlite3
import time
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .result_store import PROJECT_ROOT


DEFAULT_HEALTH_DB = PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "proxy_health.sqlite3"

# Cooldown durations (seconds)
COOLDOWN_BASE_SECONDS = 30
COOLDOWN_MAX_SECONDS = 600


def proxy_id(proxy_url: str) -> str:
    """Derive a stable, non-reversible ID from a proxy URL.

    Strips credentials before hashing so the ID is safe to persist.
    """
    if not proxy_url:
        return ""
    parsed = urlparse(proxy_url)
    # Build a canonical form without credentials
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    canonical = f"{parsed.scheme}://{host}{parsed.path or ''}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def redact_proxy_url(proxy_url: str) -> str:
    """Redact proxy credentials for logging/display."""
    if not proxy_url:
        return ""
    parsed = urlparse(proxy_url)
    if not parsed.username and not parsed.password:
        return proxy_url
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return f"{parsed.scheme}://***:***@{host}{parsed.path or ''}"


class ProxyHealthStore:
    """SQLite-backed proxy health tracker.

    Schema:
        proxy_health
            proxy_id     TEXT PRIMARY KEY — sha256-derived, no credentials
            proxy_label  TEXT NOT NULL DEFAULT '' — redacted URL for display
            domain       TEXT NOT NULL DEFAULT '' — optional domain affinity
            success_count INTEGER NOT NULL DEFAULT 0
            failure_count INTEGER NOT NULL DEFAULT 0
            last_error   TEXT NOT NULL DEFAULT ''
            last_used_at REAL NOT NULL DEFAULT 0
            cooldown_until REAL NOT NULL DEFAULT 0
            created_at   REAL NOT NULL
            updated_at   REAL NOT NULL
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_HEALTH_DB
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
                CREATE TABLE IF NOT EXISTS proxy_health (
                    proxy_id      TEXT PRIMARY KEY,
                    proxy_label   TEXT NOT NULL DEFAULT '',
                    domain        TEXT NOT NULL DEFAULT '',
                    success_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    last_error    TEXT NOT NULL DEFAULT '',
                    last_used_at  REAL NOT NULL DEFAULT 0,
                    cooldown_until REAL NOT NULL DEFAULT 0,
                    created_at    REAL NOT NULL,
                    updated_at    REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proxy_health_domain ON proxy_health(domain)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_proxy_health_cooldown ON proxy_health(cooldown_until)"
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, proxy_url: str, domain: str = "") -> dict[str, Any] | None:
        """Return health record for a proxy, or None."""
        pid = proxy_id(proxy_url)
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM proxy_health WHERE proxy_id = ?", (pid,)
            ).fetchone()
        return dict(row) if row else None

    def is_available(self, proxy_url: str, *, now: float = 0.0, domain: str = "") -> bool:
        """Check if a proxy is not in cooldown."""
        record = self.get(proxy_url, domain)
        if not record:
            return True  # unknown proxy is available
        return record["cooldown_until"] <= now

    def available_proxies(self, proxy_urls: list[str], *, now: float = 0.0) -> list[str]:
        """Filter proxy URLs to those not in cooldown."""
        return [url for url in proxy_urls if self.is_available(url, now=now)]

    def get_all(self) -> list[dict[str, Any]]:
        """Return all health records."""
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM proxy_health ORDER BY failure_count DESC").fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record_success(self, proxy_url: str, *, now: float = 0.0, domain: str = "") -> None:
        """Record a successful request through this proxy."""
        now = now or time.time()
        pid = proxy_id(proxy_url)
        label = redact_proxy_url(proxy_url)
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO proxy_health (proxy_id, proxy_label, domain, success_count, failure_count, last_error, last_used_at, cooldown_until, created_at, updated_at)
                VALUES (?, ?, ?, 1, 0, '', ?, 0, ?, ?)
                ON CONFLICT(proxy_id) DO UPDATE SET
                    success_count = success_count + 1,
                    failure_count = 0,
                    last_error = '',
                    last_used_at = excluded.last_used_at,
                    cooldown_until = 0,
                    updated_at = excluded.updated_at
                """,
                (pid, label, domain, now, now, now),
            )

    def record_failure(
        self,
        proxy_url: str,
        *,
        error: str = "",
        now: float = 0.0,
        domain: str = "",
        max_failures: int = 3,
    ) -> None:
        """Record a failed request. Applies cooldown after max_failures."""
        now = now or time.time()
        pid = proxy_id(proxy_url)
        label = redact_proxy_url(proxy_url)
        safe_error = (error or "proxy failure")[:300]

        # Read current failure count to compute cooldown
        existing = self.get(proxy_url)
        current_failures = existing["failure_count"] if existing else 0
        new_failures = current_failures + 1

        cooldown_until = 0.0
        if new_failures >= max_failures:
            # Exponential backoff: 30s, 60s, 120s, ... capped at 600s
            backoff = min(
                COOLDOWN_BASE_SECONDS * (2 ** (new_failures - max_failures)),
                COOLDOWN_MAX_SECONDS,
            )
            cooldown_until = now + backoff

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO proxy_health (proxy_id, proxy_label, domain, success_count, failure_count, last_error, last_used_at, cooldown_until, created_at, updated_at)
                VALUES (?, ?, ?, 0, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(proxy_id) DO UPDATE SET
                    failure_count = failure_count + 1,
                    last_error = excluded.last_error,
                    last_used_at = excluded.last_used_at,
                    cooldown_until = MAX(proxy_health.cooldown_until, excluded.cooldown_until),
                    updated_at = excluded.updated_at
                """,
                (pid, label, domain, safe_error, now, cooldown_until, now, now),
            )

    def reset(self, proxy_url: str) -> None:
        """Reset health state for a proxy (e.g. after manual review)."""
        pid = proxy_id(proxy_url)
        now = time.time()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE proxy_health
                SET failure_count = 0, last_error = '', cooldown_until = 0, updated_at = ?
                WHERE proxy_id = ?
                """,
                (now, pid),
            )

    def prune(self, *, older_than: float = 86400 * 7) -> int:
        """Remove records not used within older_than seconds."""
        cutoff = time.time() - older_than
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM proxy_health WHERE last_used_at < ? AND last_used_at > 0",
                (cutoff,),
            )
        return cursor.rowcount
