"""SQLite product store for ecommerce crawling.

Provides batch upsert, run-level stats, and dedupe-key lookup for
ProductRecord objects. Designed for 30,000-row batch writes in a
single transaction.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ..models.product import (
    ProductRecord,
    build_product_dedupe_key,
    record_to_row,
    row_to_record,
    utc_now_iso,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "autonomous_crawler" / "storage" / "runtime" / "products.sqlite3"


class ProductStore:
    """SQLite-backed product store with batch upsert support."""

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
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    source_site TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    canonical_url TEXT NOT NULL DEFAULT '',
                    title TEXT NOT NULL DEFAULT '',
                    highest_price REAL,
                    currency TEXT NOT NULL DEFAULT '',
                    colors TEXT NOT NULL DEFAULT '[]',
                    sizes TEXT NOT NULL DEFAULT '[]',
                    description TEXT NOT NULL DEFAULT '',
                    image_urls TEXT NOT NULL DEFAULT '[]',
                    category TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'ok',
                    mode TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    dedupe_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_products_run_dedupe "
                "ON products(run_id, dedupe_key)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_products_run_status "
                "ON products(run_id, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_products_run_site "
                "ON products(run_id, source_site)"
            )

    def upsert_many(self, records: list[ProductRecord]) -> dict[str, int]:
        """Upsert a batch of product records in a single transaction.

        Returns:
            Dict with keys: inserted, updated, total.
        """
        if not records:
            return {"inserted": 0, "updated": 0, "total": 0}

        now = utc_now_iso()
        inserted = 0
        updated = 0

        with self.connection() as conn:
            for record in records:
                if not record.dedupe_key:
                    record.dedupe_key = build_product_dedupe_key(record)
                row = record_to_row(record)
                row["updated_at"] = now

                existing = conn.execute(
                    "SELECT id FROM products WHERE run_id = ? AND dedupe_key = ?",
                    (row["run_id"], row["dedupe_key"]),
                ).fetchone()

                if existing:
                    conn.execute(
                        """
                        UPDATE products SET
                            source_site = :source_site,
                            source_url = :source_url,
                            canonical_url = :canonical_url,
                            title = :title,
                            highest_price = :highest_price,
                            currency = :currency,
                            colors = :colors,
                            sizes = :sizes,
                            description = :description,
                            image_urls = :image_urls,
                            category = :category,
                            status = :status,
                            mode = :mode,
                            notes = :notes,
                            raw_json = :raw_json,
                            updated_at = :updated_at
                        WHERE run_id = :run_id AND dedupe_key = :dedupe_key
                        """,
                        row,
                    )
                    updated += 1
                else:
                    conn.execute(
                        """
                        INSERT INTO products (
                            run_id, source_site, source_url, canonical_url,
                            title, highest_price, currency, colors, sizes,
                            description, image_urls, category, status, mode,
                            notes, raw_json, dedupe_key, created_at, updated_at
                        ) VALUES (
                            :run_id, :source_site, :source_url, :canonical_url,
                            :title, :highest_price, :currency, :colors, :sizes,
                            :description, :image_urls, :category, :status, :mode,
                            :notes, :raw_json, :dedupe_key, :created_at, :updated_at
                        )
                        """,
                        row,
                    )
                    inserted += 1

        return {"inserted": inserted, "updated": updated, "total": inserted + updated}

    def get_run_stats(self, run_id: str) -> dict[str, Any]:
        """Get aggregate stats for a run."""
        with self.connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM products WHERE run_id = ?", (run_id,)
            ).fetchone()[0]

            status_rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM products WHERE run_id = ? GROUP BY status",
                (run_id,),
            ).fetchall()
            status_counts = {row["status"]: row["cnt"] for row in status_rows}

            site_rows = conn.execute(
                "SELECT source_site, COUNT(*) as cnt FROM products WHERE run_id = ? GROUP BY source_site",
                (run_id,),
            ).fetchall()
            site_counts = {row["source_site"]: row["cnt"] for row in site_rows}

            price_row = conn.execute(
                "SELECT MIN(highest_price) as min_price, MAX(highest_price) as max_price, "
                "AVG(highest_price) as avg_price FROM products "
                "WHERE run_id = ? AND highest_price IS NOT NULL",
                (run_id,),
            ).fetchone()

        return {
            "run_id": run_id,
            "total": total,
            "by_status": status_counts,
            "by_site": site_counts,
            "price_min": price_row["min_price"] if price_row else None,
            "price_max": price_row["max_price"] if price_row else None,
            "price_avg": round(price_row["avg_price"], 2) if price_row and price_row["avg_price"] else None,
        }

    def list_records(
        self,
        run_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProductRecord]:
        """List product records for a run, ordered by created_at."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM products WHERE run_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            ).fetchall()
        return [row_to_record(dict(r)) for r in rows]

    def count_by_status(self, run_id: str) -> dict[str, int]:
        """Count products grouped by status for a run."""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM products WHERE run_id = ? GROUP BY status",
                (run_id,),
            ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    def get_record_by_dedupe_key(
        self, run_id: str, dedupe_key: str
    ) -> ProductRecord | None:
        """Retrieve a single record by run_id and dedupe_key."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE run_id = ? AND dedupe_key = ?",
                (run_id, dedupe_key),
            ).fetchone()
        if row is None:
            return None
        return row_to_record(dict(row))

    def count_total(self, run_id: str) -> int:
        """Count total products for a run."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM products WHERE run_id = ?", (run_id,)
            ).fetchone()
        return row[0] if row else 0
