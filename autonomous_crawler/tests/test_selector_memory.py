"""Tests for persistent adaptive selector memory."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.storage.selector_memory import SelectorMemoryStore


class SelectorMemoryStoreTests(unittest.TestCase):
    def test_save_and_load_exact_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SelectorMemoryStore(Path(tmp) / "memory.sqlite3")
            signature = {"tag": "h2", "text": "Alpha", "path": ["html", "body", "h2"]}

            store.save_signature(
                site_key="shop.example",
                name="title",
                selector=".title",
                selector_type="css",
                signature=signature,
            )

            loaded = store.load_signature(
                site_key="shop.example",
                name="title",
                selector=".title",
                selector_type="css",
            )

        self.assertEqual(loaded["tag"], "h2")
        self.assertEqual(loaded["text"], "Alpha")

    def test_load_falls_back_to_latest_signature_for_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SelectorMemoryStore(Path(tmp) / "memory.sqlite3")
            store.save_signature(
                site_key="shop.example",
                name="title",
                selector=".old-title",
                selector_type="css",
                signature={"tag": "h2", "text": "Alpha"},
            )

            loaded = store.load_signature(
                site_key="shop.example",
                name="title",
                selector=".new-title",
                selector_type="css",
            )

        self.assertEqual(loaded["tag"], "h2")
        self.assertEqual(loaded["text"], "Alpha")

    def test_record_recovery_updates_counters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SelectorMemoryStore(Path(tmp) / "memory.sqlite3")
            store.save_signature(
                site_key="shop.example",
                name="title",
                selector=".title",
                selector_type="css",
                signature={"tag": "h2"},
            )
            store.record_recovery(
                site_key="shop.example",
                name="title",
                selector=".title",
                selector_type="css",
                score=72.5,
            )
            rows = store.get_all()

        self.assertEqual(rows[0]["success_count"], 1)
        self.assertEqual(rows[0]["recover_count"], 1)
        self.assertEqual(rows[0]["last_score"], 72.5)

    def test_persists_across_store_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "memory.sqlite3"
            SelectorMemoryStore(db_path).save_signature(
                site_key="shop.example",
                name="price",
                selector=".price",
                selector_type="css",
                signature={"tag": "span", "text": "$10"},
            )
            loaded = SelectorMemoryStore(db_path).load_signature(
                site_key="shop.example",
                name="price",
                selector=".price",
                selector_type="css",
            )

        self.assertEqual(loaded["tag"], "span")
        self.assertEqual(loaded["text"], "$10")


if __name__ == "__main__":
    unittest.main()
