from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from autonomous_crawler.api.app import create_app, _jobs, _jobs_lock
from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.runners.product_workflow import (
    ExportSpec,
    export_product_records,
    import_catalog_tree,
    resolve_fields,
)
from autonomous_crawler.storage.product_store import ProductStore


class ProductWorkflowCoreTests(unittest.TestCase):
    def test_import_catalog_tree_accepts_spider_nested_menu_shape(self) -> None:
        payload = {
            "Kobieta": {
                "Produkty": {
                    "Legginsy": "https://shop.test/leggings",
                    "Bluzy": "https://shop.test/hoodies",
                }
            }
        }

        tree = import_catalog_tree(payload)

        leaf = tree[0]["children"][0]["children"][0]
        self.assertEqual(leaf["label"], "Legginsy")
        self.assertEqual(leaf["url"], "https://shop.test/leggings")
        self.assertEqual(leaf["level1"], "Kobieta")
        self.assertEqual(leaf["level2"], "Produkty")
        self.assertEqual(leaf["level3"], "Legginsy")

    def test_resolve_fields_maps_chinese_natural_language_to_canonical_fields(self) -> None:
        available = [
            {"name": "title", "label": "商品标题"},
            {"name": "highest_price", "label": "最高价格"},
            {"name": "colors", "label": "颜色"},
        ]

        result = resolve_fields(available, natural_language="我要标题、原价和颜色")

        self.assertEqual(result["selected_fields"], ["colors", "highest_price", "title"])
        self.assertFalse(result["needs_refinement"])

    def test_export_product_records_writes_json_with_field_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProductStore(root / "products.sqlite3")
            store.upsert_many([
                ProductRecord(
                    run_id="run-export",
                    source_site="shop.test",
                    source_url="https://shop.test/p1",
                    canonical_url="https://shop.test/p1",
                    title="Alpha",
                    highest_price=12.5,
                    colors=["Black"],
                    sizes=["M"],
                    description="Nice",
                    image_urls=["https://shop.test/a.jpg"],
                    category="Women>Products>Leggings",
                )
            ])
            output = root / "out.json"

            result = export_product_records(
                run_id="run-export",
                runtime_dir=str(root),
                export_spec=ExportSpec(
                    format="json",
                    output_path=str(output),
                    field_mapping={"title": "Title", "highest_price": "Price"},
                ),
            )

            rows = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["record_count"], 1)
            self.assertEqual(rows[0], {"Title": "Alpha", "Price": 12.5})


class ProductWorkflowAPITests(unittest.TestCase):
    def setUp(self) -> None:
        with _jobs_lock:
            _jobs.clear()

    def test_catalog_import_endpoint(self) -> None:
        client = TestClient(create_app())
        response = client.post(
            "/catalog/import",
            json={"catalog": {"Women": {"Shoes": "https://shop.test/shoes"}}},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "catalog-tree/v1")
        self.assertEqual(payload["leaf_count"], 1)

    def test_site_analyze_returns_catalog_fields_and_profile(self) -> None:
        client = TestClient(create_app())
        response = client.post(
            "/site/analyze",
            json={
                "target_url": "mock://catalog",
                "field_goal": "标题 价格 图片",
                "imported_catalog": {"Women": {"Jackets": "https://shop.test/jackets"}},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema_version"], "site-analysis/v1")
        self.assertGreaterEqual(len(payload["field_candidates"]), 3)
        self.assertEqual(payload["catalog_tree"][0]["label"], "Women")
        self.assertIn("profile", payload)

    def test_fields_resolve_endpoint(self) -> None:
        client = TestClient(create_app())
        response = client.post(
            "/fields/resolve",
            json={
                "available_fields": [{"name": "title"}, {"name": "sizes"}],
                "natural_language": "我要商品标题和尺码",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selected_fields"], ["sizes", "title"])

    def test_runs_test_registers_profile_job(self) -> None:
        with patch("autonomous_crawler.api.app.run_profile_longrun_workflow") as mock_run:
            mock_run.return_value = {
                "accepted": True,
                "status": "completed",
                "run_id": "run-test",
                "product_stats": {"total": 3},
                "runner_summary": {"claimed": 3, "records_saved": 3},
                "frontier_stats": {"done": 3},
            }
            client = TestClient(create_app())
            response = client.post(
                "/runs/test",
                json={
                    "target_url": "https://shop.test",
                    "profile": {"name": "shop-test", "crawl_preferences": {"seed_urls": ["https://shop.test/c"]}},
                    "catalog_nodes": [{"label": "C", "url": "https://shop.test/c", "path": ["C"]}],
                    "selected_fields": ["title", "highest_price"],
                    "item_workers": 4,
                    "test_limit": 100,
                    "runtime_dir": "dev_logs/runtime/test-api",
                },
            )
            self.assertEqual(response.status_code, 200)
            task_id = response.json()["task_id"]
            time.sleep(0.4)
            status = client.get(f"/runs/{task_id}/status")
            events = client.get(f"/runs/{task_id}/events")

        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["record_count"], 3)
        self.assertEqual(events.status_code, 200)
        self.assertGreaterEqual(len(events.json()["events"]), 2)
        request = mock_run.call_args.args[0]
        self.assertEqual(request.item_workers, 4)
        self.assertGreaterEqual(request.max_batches, 1)

    def test_exports_endpoint_uses_product_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ProductStore(root / "products.sqlite3")
            store.upsert_many([
                ProductRecord(run_id="run-api-export", title="Beta", canonical_url="https://shop.test/b")
            ])
            output = root / "export.csv"
            client = TestClient(create_app())
            response = client.post(
                "/exports",
                json={
                    "run_id": "run-api-export",
                    "runtime_dir": str(root),
                    "format": "csv",
                    "output_path": str(output),
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(output.exists())
            self.assertEqual(response.json()["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
