from __future__ import annotations

import unittest

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph
from autonomous_crawler.tools.api_candidates import (
    build_api_candidates,
    extract_records_from_json,
    normalize_api_records,
)


class ApiInterceptTests(unittest.TestCase):
    def test_build_api_candidates_ranks_product_api(self) -> None:
        candidates = build_api_candidates(["/static/app.js", "/api/products?page=1"], base_url="https://shop.example")

        self.assertEqual(candidates[0]["url"], "https://shop.example/api/products?page=1")

    def test_extract_records_from_common_json_shapes(self) -> None:
        records = extract_records_from_json({"data": {"items": [{"name": "Alpha"}]}})

        self.assertEqual(records, [{"name": "Alpha"}])

    def test_normalize_api_records_maps_name_to_title(self) -> None:
        items = normalize_api_records([{"name": "Alpha", "url": "/p/a"}])

        self.assertEqual(items[0]["title"], "Alpha")
        self.assertEqual(items[0]["link"], "/p/a")

    def test_recon_adds_api_candidates(self) -> None:
        state = recon_node({
            "target_url": "mock://site-zoo/spa-shell",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        candidates = state["recon_report"]["api_candidates"]
        self.assertTrue(candidates)
        self.assertIn("/api/products", candidates[0]["url"])

    def test_strategy_uses_api_candidate_when_not_browser_required(self) -> None:
        state = strategy_node({
            "user_goal": "collect products",
            "target_url": "https://shop.example",
            "recon_report": {
                "target_url": "https://shop.example",
                "task_type": "product_list",
                "constraints": {"max_items": 2},
                "rendering": "static",
                "anti_bot": {"detected": False},
                "api_endpoints": [],
                "api_candidates": [{"url": "mock://api/products", "score": 32}],
                "access_diagnostics": {"findings": [], "signals": {}},
                "dom_structure": {"pagination_type": "none", "field_selectors": {}},
            },
            "retries": 0,
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_endpoint"], "mock://api/products")

    def test_executor_api_intercept_extracts_mock_json(self) -> None:
        state = executor_node({
            "target_url": "https://shop.example",
            "crawl_strategy": {
                "mode": "api_intercept",
                "api_endpoint": "mock://api/products",
                "headers": {},
                "max_items": 2,
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 2)
        self.assertEqual(state["extracted_data"]["items"][0]["title"], "API Alpha")

    def test_graph_completes_api_intercept_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect product titles and prices",
            "target_url": "mock://site-zoo/api-hint-static",
            "recon_report": {},
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 1,
            "status": "pending",
            "error_log": [],
            "messages": [],
        })

        self.assertEqual(final_state["status"], "completed")
        self.assertEqual(final_state["crawl_strategy"]["mode"], "api_intercept")
        self.assertEqual(final_state["extracted_data"]["item_count"], 2)


if __name__ == "__main__":
    unittest.main()
