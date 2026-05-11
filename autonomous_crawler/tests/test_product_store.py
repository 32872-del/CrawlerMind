"""Tests for ProductRecord model and ProductStore."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.models.product import (
    ProductRecord,
    build_product_dedupe_key,
    record_to_row,
    row_to_record,
)
from autonomous_crawler.storage.product_store import ProductStore


class ProductRecordTests(unittest.TestCase):
    def test_default_dedupe_key_generated(self) -> None:
        record = ProductRecord(
            source_site="shop.example",
            category="shoes",
            canonical_url="https://shop.example/products/alpha",
            title="Alpha Shoe",
        )
        self.assertTrue(record.dedupe_key)
        self.assertEqual(len(record.dedupe_key), 32)

    def test_same_input_same_key(self) -> None:
        r1 = ProductRecord(source_site="a", category="b", canonical_url="https://x.com/1")
        r2 = ProductRecord(source_site="a", category="b", canonical_url="https://x.com/1")
        self.assertEqual(r1.dedupe_key, r2.dedupe_key)

    def test_different_category_different_key(self) -> None:
        r1 = ProductRecord(source_site="a", category="shoes", canonical_url="https://x.com/1")
        r2 = ProductRecord(source_site="a", category="hats", canonical_url="https://x.com/1")
        self.assertNotEqual(r1.dedupe_key, r2.dedupe_key)

    def test_fallback_to_title_when_no_url(self) -> None:
        r1 = ProductRecord(source_site="a", category="b", title="Product X")
        r2 = ProductRecord(source_site="a", category="b", title="Product X")
        self.assertEqual(r1.dedupe_key, r2.dedupe_key)

    def test_invalid_status_raises(self) -> None:
        with self.assertRaises(ValueError):
            ProductRecord(status="invalid")

    def test_valid_statuses_accepted(self) -> None:
        for status in ("ok", "partial", "blocked", "failed"):
            record = ProductRecord(status=status)
            self.assertEqual(record.status, status)

    def test_timestamps_auto_set(self) -> None:
        record = ProductRecord()
        self.assertTrue(record.created_at)
        self.assertTrue(record.updated_at)

    def test_explicit_key_preserved(self) -> None:
        record = ProductRecord(dedupe_key="custom-key-123")
        self.assertEqual(record.dedupe_key, "custom-key-123")

    def test_build_dedupe_key_generic(self) -> None:
        key = build_product_dedupe_key(ProductRecord(
            source_site="shop", category="cat", canonical_url="https://url",
        ))
        self.assertIsInstance(key, str)
        self.assertEqual(len(key), 32)


class RecordSerializationTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        record = ProductRecord(
            run_id="run-1",
            source_site="shop",
            source_url="https://shop.example/p/1",
            canonical_url="https://shop.example/products/alpha",
            title="Alpha",
            highest_price=99.99,
            currency="USD",
            colors=["Red", "Blue"],
            sizes=["S", "M", "L"],
            description="A great product",
            image_urls=["https://img.example/1.jpg", "https://img.example/2.jpg"],
            category="shoes",
            status="ok",
            mode="http",
            notes="test",
            raw_json={"foo": "bar"},
        )
        row = record_to_row(record)
        restored = row_to_record(row)

        self.assertEqual(restored.run_id, "run-1")
        self.assertEqual(restored.title, "Alpha")
        self.assertEqual(restored.highest_price, 99.99)
        self.assertEqual(restored.colors, ["Red", "Blue"])
        self.assertEqual(restored.sizes, ["S", "M", "L"])
        self.assertEqual(restored.image_urls, ["https://img.example/1.jpg", "https://img.example/2.jpg"])
        self.assertEqual(restored.raw_json, {"foo": "bar"})
        self.assertEqual(restored.dedupe_key, record.dedupe_key)

    def test_round_trip_empty_lists(self) -> None:
        record = ProductRecord(title="Empty")
        row = record_to_row(record)
        restored = row_to_record(row)
        self.assertEqual(restored.colors, [])
        self.assertEqual(restored.sizes, [])
        self.assertEqual(restored.image_urls, [])


class ProductStoreBasicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test_products.sqlite3"
        self.store = ProductStore(db_path=self.db_path)

    def test_initialize_creates_table(self) -> None:
        conn = self.store.connect()
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
            ).fetchall()
            self.assertEqual(len(tables), 1)
        finally:
            conn.close()

    def test_upsert_many_inserts(self) -> None:
        records = [
            ProductRecord(
                run_id="run-1",
                source_site="shop",
                source_url=f"https://shop.example/p/{i}",
                canonical_url=f"https://shop.example/products/{i}",
                title=f"Product {i}",
            )
            for i in range(5)
        ]
        result = self.store.upsert_many(records)
        self.assertEqual(result["inserted"], 5)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["total"], 5)

    def test_upsert_many_updates_on_conflict(self) -> None:
        record = ProductRecord(
            run_id="run-1",
            source_site="shop",
            canonical_url="https://shop.example/products/alpha",
            title="Alpha v1",
        )
        self.store.upsert_many([record])

        record_v2 = ProductRecord(
            run_id="run-1",
            source_site="shop",
            canonical_url="https://shop.example/products/alpha",
            title="Alpha v2",
        )
        result = self.store.upsert_many([record_v2])
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["updated"], 1)

        stored = self.store.get_record_by_dedupe_key("run-1", record.dedupe_key)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.title, "Alpha v2")

    def test_upsert_many_empty(self) -> None:
        result = self.store.upsert_many([])
        self.assertEqual(result, {"inserted": 0, "updated": 0, "total": 0})

    def test_list_records(self) -> None:
        records = [
            ProductRecord(
                run_id="run-1",
                source_site="shop",
                title=f"Product {i}",
            )
            for i in range(10)
        ]
        self.store.upsert_many(records)

        page1 = self.store.list_records("run-1", limit=3, offset=0)
        self.assertEqual(len(page1), 3)

        page2 = self.store.list_records("run-1", limit=3, offset=3)
        self.assertEqual(len(page2), 3)

        page_all = self.store.list_records("run-1", limit=100, offset=0)
        self.assertEqual(len(page_all), 10)

    def test_list_records_empty_run(self) -> None:
        result = self.store.list_records("nonexistent")
        self.assertEqual(result, [])

    def test_count_by_status(self) -> None:
        records = [
            ProductRecord(run_id="run-1", status="ok", title="A"),
            ProductRecord(run_id="run-1", status="ok", title="B"),
            ProductRecord(run_id="run-1", status="partial", title="C"),
            ProductRecord(run_id="run-1", status="blocked", title="D"),
        ]
        self.store.upsert_many(records)

        counts = self.store.count_by_status("run-1")
        self.assertEqual(counts["ok"], 2)
        self.assertEqual(counts["partial"], 1)
        self.assertEqual(counts["blocked"], 1)

    def test_count_by_status_empty(self) -> None:
        counts = self.store.count_by_status("nonexistent")
        self.assertEqual(counts, {})

    def test_get_record_by_dedupe_key(self) -> None:
        record = ProductRecord(
            run_id="run-1",
            source_site="shop",
            canonical_url="https://shop.example/products/alpha",
            title="Alpha",
        )
        self.store.upsert_many([record])

        found = self.store.get_record_by_dedupe_key("run-1", record.dedupe_key)
        self.assertIsNotNone(found)
        self.assertEqual(found.title, "Alpha")

    def test_get_record_by_dedupe_key_not_found(self) -> None:
        found = self.store.get_record_by_dedupe_key("run-1", "nonexistent")
        self.assertIsNone(found)

    def test_get_run_stats(self) -> None:
        records = [
            ProductRecord(
                run_id="run-1",
                source_site="shop-a",
                title=f"Product {i}",
                highest_price=float(i * 10),
            )
            for i in range(1, 6)
        ]
        self.store.upsert_many(records)

        stats = self.store.get_run_stats("run-1")
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["by_status"]["ok"], 5)
        self.assertEqual(stats["by_site"]["shop-a"], 5)
        self.assertEqual(stats["price_min"], 10.0)
        self.assertEqual(stats["price_max"], 50.0)
        self.assertEqual(stats["price_avg"], 30.0)

    def test_get_run_stats_empty(self) -> None:
        stats = self.store.get_run_stats("nonexistent")
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["by_status"], {})

    def test_count_total(self) -> None:
        records = [
            ProductRecord(run_id="run-1", title=f"Product {i}")
            for i in range(7)
        ]
        self.store.upsert_many(records)
        self.assertEqual(self.store.count_total("run-1"), 7)
        self.assertEqual(self.store.count_total("run-2"), 0)

    def test_multiple_runs_isolated(self) -> None:
        self.store.upsert_many([
            ProductRecord(run_id="run-1", title="A"),
            ProductRecord(run_id="run-2", title="B"),
        ])
        self.assertEqual(self.store.count_total("run-1"), 1)
        self.assertEqual(self.store.count_total("run-2"), 1)


class ProductStoreBatchTests(unittest.TestCase):
    """Batch write tests including 30,000-row stress test."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "batch_test.sqlite3"
        self.store = ProductStore(db_path=self.db_path)

    def test_batch_1000(self) -> None:
        records = [
            ProductRecord(
                run_id="batch-run",
                source_site="stress.test",
                source_url=f"https://stress.test/products/{i}",
                canonical_url=f"https://stress.test/products/{i}",
                title=f"Product {i}",
                highest_price=float(i % 100),
                category=f"cat-{i % 10}",
            )
            for i in range(1000)
        ]
        result = self.store.upsert_many(records)
        self.assertEqual(result["inserted"], 1000)
        self.assertEqual(result["updated"], 0)
        self.assertEqual(self.store.count_total("batch-run"), 1000)

    def test_batch_30000(self) -> None:
        records = [
            ProductRecord(
                run_id="stress-run",
                source_site="stress.test",
                source_url=f"https://stress.test/products/{i}",
                canonical_url=f"https://stress.test/products/{i}",
                title=f"Product {i}",
                highest_price=float(i % 200),
                currency="USD",
                colors=["Red", "Blue"] if i % 3 == 0 else [],
                sizes=["S", "M", "L"] if i % 5 == 0 else [],
                category=f"cat-{i % 50}",
            )
            for i in range(30000)
        ]
        result = self.store.upsert_many(records)
        self.assertEqual(result["inserted"], 30000)
        self.assertEqual(result["total"], 30000)
        self.assertEqual(self.store.count_total("stress-run"), 30000)

        stats = self.store.get_run_stats("stress-run")
        self.assertEqual(stats["total"], 30000)
        self.assertTrue(stats["by_site"])

    def test_batch_30000_upsert_updates(self) -> None:
        base_records = [
            ProductRecord(
                run_id="upsert-run",
                source_site="stress.test",
                canonical_url=f"https://stress.test/products/{i}",
                title=f"Product v1 {i}",
            )
            for i in range(30000)
        ]
        self.store.upsert_many(base_records)

        updated_records = [
            ProductRecord(
                run_id="upsert-run",
                source_site="stress.test",
                canonical_url=f"https://stress.test/products/{i}",
                title=f"Product v2 {i}",
            )
            for i in range(30000)
        ]
        result = self.store.upsert_many(updated_records)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["updated"], 30000)
        self.assertEqual(self.store.count_total("upsert-run"), 30000)

    def test_batch_with_mixed_deduplication(self) -> None:
        records = []
        for i in range(100):
            records.append(ProductRecord(
                run_id="dedup-run",
                source_site="shop",
                canonical_url=f"https://shop.example/products/{i % 20}",
                title=f"Product {i % 20}",
                category="cat",
            ))
        result = self.store.upsert_many(records)
        # 20 unique URLs, rest are upserts
        self.assertEqual(self.store.count_total("dedup-run"), 20)
        self.assertEqual(result["inserted"], 20)
        self.assertEqual(result["updated"], 80)


if __name__ == "__main__":
    unittest.main()
