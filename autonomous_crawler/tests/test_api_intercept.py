from __future__ import annotations

import unittest

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph
from autonomous_crawler.tools.api_candidates import (
    build_direct_json_candidate,
    fetch_graphql_api,
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

    def test_extract_records_from_training_json_shapes(self) -> None:
        self.assertEqual(
            extract_records_from_json({"hits": [{"title": "HN Story"}]}),
            [{"title": "HN Story"}],
        )
        self.assertEqual(
            extract_records_from_json({"quotes": [{"text": "Quote text"}]}),
            [{"text": "Quote text"}],
        )

    def test_normalize_api_records_maps_name_to_title(self) -> None:
        items = normalize_api_records([{"name": "Alpha", "url": "/p/a"}])

        self.assertEqual(items[0]["title"], "Alpha")
        self.assertEqual(items[0]["link"], "/p/a")

    def test_normalize_api_records_maps_content_platform_metrics(self) -> None:
        items = normalize_api_records([
            {
                "title": {"english": "Attack on Titan", "romaji": "Shingeki no Kyojin"},
                "siteUrl": "https://anilist.co/anime/16498",
                "coverImage": {"medium": "https://img.example/a.jpg"},
                "popularity": 986169,
            },
            {
                "title": "Bilibili Video",
                "pic": "https://img.example/b.jpg",
                "stat": {"view": 12345, "like": 100},
            },
        ])

        self.assertEqual(items[0]["title"], "Attack on Titan")
        self.assertEqual(items[0]["link"], "https://anilist.co/anime/16498")
        self.assertEqual(items[0]["image"], "https://img.example/a.jpg")
        self.assertEqual(items[0]["hot_score"], 986169)
        self.assertEqual(items[1]["hot_score"], 12345)
        self.assertEqual(items[1]["rank"], 2)
        self.assertEqual(items[1]["image"], "https://img.example/b.jpg")

    def test_normalize_api_records_maps_training_api_fields(self) -> None:
        items = normalize_api_records([
            {
                "title": "HN Story",
                "points": 123,
                "story_text": "A useful story summary",
            },
            {
                "title": "Rated Product",
                "rating": 4.7,
                "description": "A product description",
            },
        ])

        self.assertEqual(items[0]["hot_score"], 123)
        self.assertEqual(items[0]["summary"], "A useful story summary")
        self.assertEqual(items[1]["hot_score"], 4.7)
        self.assertEqual(items[1]["summary"], "A product description")

    def test_normalize_api_records_maps_quote_and_github_fields(self) -> None:
        items = normalize_api_records([
            {
                "text": "Quote text",
                "author": {"name": "Ada"},
            },
            {
                "title": "Issue title",
                "html_url": "https://github.example/issues/1",
                "comments": 3,
            },
        ])

        self.assertEqual(items[0]["title"], "Quote text")
        self.assertEqual(items[0]["summary"], "Quote text")
        self.assertEqual(items[1]["link"], "https://github.example/issues/1")
        self.assertEqual(items[1]["hot_score"], 3)


    def test_extract_records_from_reddit_children_shape(self) -> None:
        records = extract_records_from_json({
            "data": {
                "children": [
                    {"kind": "t3", "data": {"title": "Alpha", "score": 12}},
                    {"kind": "t3", "data": {"title": "Beta", "score": 8}},
                ]
            }
        })

        self.assertEqual(records[0]["title"], "Alpha")
        self.assertEqual(records[0]["score"], 12)

    def test_direct_json_candidate_marks_target_url_as_api(self) -> None:
        candidate = build_direct_json_candidate("https://example.test/items.json")

        self.assertEqual(candidate["url"], "https://example.test/items.json")
        self.assertEqual(candidate["reason"], "target_url_is_json")

    def test_recon_marks_json_payload_as_direct_api(self) -> None:
        state = recon_node({
            "target_url": "mock://json-direct",
            "recon_report": {
                "target_fields": ["title"],
                "task_type": "product_list",
            },
            "messages": [],
            "error_log": [],
        })

        recon = state["recon_report"]
        self.assertEqual(recon["rendering"], "api")
        self.assertEqual(recon["api_candidates"][0]["reason"], "target_url_is_json")

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

    def test_strategy_prefers_good_dom_candidates_over_weak_api_hints(self) -> None:
        state = strategy_node({
            "user_goal": "collect documentation links",
            "target_url": "https://docs.example",
            "recon_report": {
                "target_url": "https://docs.example",
                "task_type": "product_list",
                "constraints": {"max_items": 10},
                "rendering": "ssr",
                "anti_bot": {"detected": False},
                "api_endpoints": [],
                "api_candidates": [{"url": "https://docs.example/api/", "score": 20}],
                "access_diagnostics": {"findings": [], "signals": {}},
                "dom_structure": {
                    "pagination_type": "none",
                    "product_selector": ".doc-link",
                    "item_count": 5,
                    "field_selectors": {
                        "title": "a",
                        "link": "a@href",
                    },
                },
            },
            "retries": 0,
            "messages": [],
        })

        self.assertEqual(state["crawl_strategy"]["mode"], "http")
        self.assertEqual(state["crawl_strategy"]["extraction_method"], "dom_parse")

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

    def test_executor_graphql_intercept_extracts_mock_json(self) -> None:
        state = executor_node({
            "target_url": "mock://api/graphql-countries",
            "crawl_strategy": {
                "mode": "api_intercept",
                "extraction_method": "graphql_json",
                "api_endpoint": "mock://api/graphql-countries",
                "graphql_query": "{ countries { code name capital } }",
                "graphql_variables": {},
                "headers": {},
                "max_items": 2,
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["extracted_data"]["item_count"], 2)
        self.assertEqual(state["extracted_data"]["items"][0]["title"], "China")

    def test_fetch_graphql_api_supports_mock_countries(self) -> None:
        result = fetch_graphql_api(
            "mock://api/graphql-countries",
            "{ countries { code name capital } }",
        )

        records = extract_records_from_json(result["data"])
        self.assertEqual(records[0]["code"], "CN")

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

    def test_graph_completes_direct_json_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect product titles",
            "target_url": "mock://json-direct",
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

    def test_graph_completes_explicit_graphql_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke({
            "user_goal": "collect country names and capitals",
            "target_url": "mock://api/graphql-countries",
            "recon_report": {
                "target_fields": ["title", "capital"],
                "task_type": "product_list",
                "constraints": {
                    "graphql_query": "{ countries { code name capital } }",
                    "max_items": 2,
                },
            },
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
        self.assertEqual(final_state["recon_report"]["fetch"]["selected_mode"], "configured_api")
        self.assertIn("capital", final_state["recon_report"]["target_fields"])
        self.assertEqual(final_state["crawl_strategy"]["extraction_method"], "graphql_json")
        self.assertEqual(final_state["extracted_data"]["items"][0]["capital"], "Beijing")


if __name__ == "__main__":
    unittest.main()
