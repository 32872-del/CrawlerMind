from __future__ import annotations

import unittest

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.agents.extractor import extractor_node
from autonomous_crawler.agents.planner import planner_node
from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.agents.validator import validator_node
from autonomous_crawler.tools.fnspider_adapter import (
    fnspider_runtime_paths,
    save_fnspider_site_spec,
    validate_fnspider_site_spec,
)
from autonomous_crawler.tools.site_spec_adapter import build_site_spec
from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph


class WorkflowMVPTests(unittest.TestCase):
    def test_planner_understands_chinese_field_keywords(self) -> None:
        state = planner_node(
            {
                "user_goal": "\u91c7\u96c6\u5546\u54c1\u6807\u9898\u3001\u4ef7\u683c\u548c\u56fe\u7247",
                "target_url": "mock://catalog",
                "messages": [],
            }
        )

        self.assertEqual(
            state["recon_report"]["target_fields"],
            ["title", "price", "image"],
        )

    def test_planner_detects_ranking_list_goal(self) -> None:
        state = planner_node(
            {
                "user_goal": "\u91c7\u96c6\u767e\u5ea6\u70ed\u641c\u699c\u524d30\u6761",
                "target_url": "mock://ranking",
                "messages": [],
            }
        )

        self.assertEqual(state["recon_report"]["task_type"], "ranking_list")
        self.assertEqual(state["recon_report"]["constraints"]["max_items"], 30)
        self.assertIn("rank", state["recon_report"]["target_fields"])
        self.assertIn("title", state["recon_report"]["target_fields"])

    def test_executor_supports_deterministic_mock_fixture(self) -> None:
        state = executor_node(
            {
                "target_url": "mock://catalog",
                "crawl_strategy": {"mode": "http", "headers": {}},
                "messages": [],
                "error_log": [],
            }
        )

        self.assertEqual(state["status"], "executed")
        self.assertIn("mock://catalog", state["raw_html"])
        self.assertIn("Alpha Jacket", state["raw_html"]["mock://catalog"])

    def test_executor_mock_fixture_takes_precedence_over_fnspider_engine(self) -> None:
        state = executor_node(
            {
                "target_url": "mock://catalog",
                "crawl_strategy": {
                    "mode": "http",
                    "engine": "fnspider",
                    "site_spec_draft": {"site": "catalog"},
                },
                "messages": [],
                "error_log": [],
            }
        )

        self.assertEqual(state["status"], "executed")
        self.assertNotIn("engine_result", state)
        self.assertIn("Alpha Jacket", state["raw_html"]["mock://catalog"])

    def test_recon_infers_catalog_selectors(self) -> None:
        state = recon_node(
            {
                "target_url": "mock://catalog",
                "recon_report": {"target_fields": ["title", "price", "image"]},
                "messages": [],
                "error_log": [],
            }
        )

        dom = state["recon_report"]["dom_structure"]
        self.assertEqual(dom["product_selector"], ".catalog-card")
        self.assertEqual(dom["field_selectors"]["title"], ".product-name")
        self.assertEqual(dom["field_selectors"]["price"], ".product-price")
        self.assertEqual(dom["field_selectors"]["image"], ".product-photo@src")
        self.assertEqual(dom["field_selectors"]["link"], ".product-link@href")

    def test_recon_skips_unsafe_tailwind_classes_in_selectors(self) -> None:
        state = recon_node(
            {
                "target_url": "mock://tailwind-links",
                "recon_report": {"target_fields": ["title", "link"]},
                "messages": [],
                "error_log": [],
            }
        )

        dom = state["recon_report"]["dom_structure"]
        selectors = dom["field_selectors"]
        self.assertNotIn(":", selectors["title"])
        self.assertNotIn(":", selectors["link"])

    def test_recon_infers_ranking_selectors(self) -> None:
        state = recon_node(
            {
                "target_url": "mock://ranking",
                "recon_report": {
                    "target_fields": ["rank", "title", "hot_score"],
                    "task_type": "ranking_list",
                    "constraints": {"max_items": 30},
                },
                "messages": [],
                "error_log": [],
            }
        )

        dom = state["recon_report"]["dom_structure"]
        self.assertEqual(dom["product_selector"], ".category-wrap_iQLoo")
        self.assertEqual(dom["field_selectors"]["rank"], ".index_1Ew5p")
        self.assertEqual(dom["field_selectors"]["title"], ".title_dIF3B .c-single-text-ellipsis")
        self.assertEqual(dom["field_selectors"]["link"], ".title_dIF3B@href")
        self.assertEqual(dom["field_selectors"]["hot_score"], ".hot-index_1Bl1a")
        self.assertEqual(dom["field_selectors"]["summary"], ".hot-desc_1m_jR")

    def test_strategy_uses_recon_selectors(self) -> None:
        state = strategy_node(
            {
                "user_goal": "collect products",
                "target_url": "mock://catalog",
                "recon_report": {
                    "target_url": "mock://catalog",
                    "rendering": "static",
                    "anti_bot": {"detected": False},
                    "api_endpoints": [],
                    "dom_structure": {
                        "pagination_type": "none",
                        "product_selector": ".catalog-card",
                        "field_selectors": {
                            "title": ".product-name",
                            "price": ".product-price",
                            "image": ".product-photo@src",
                            "link": ".product-link@href",
                        },
                    },
                },
                "retries": 0,
                "messages": [],
            }
        )

        self.assertEqual(
            state["crawl_strategy"]["selectors"]["item_container"],
            ".catalog-card",
        )
        self.assertEqual(
            state["crawl_strategy"]["selectors"]["title"],
            ".product-name",
        )
        self.assertEqual(
            state["crawl_strategy"]["site_spec_draft"]["list"]["item_link"],
            ".product-link@href",
        )

    def test_strategy_uses_fnspider_when_explicitly_requested(self) -> None:
        state = strategy_node(
            {
                "user_goal": "collect products",
                "target_url": "https://shop.example/products",
                "preferred_engine": "fnspider",
                "recon_report": {
                    "target_url": "https://shop.example/products",
                    "task_type": "product_list",
                    "rendering": "static",
                    "anti_bot": {"detected": False},
                    "api_endpoints": [],
                    "dom_structure": {
                        "pagination_type": "none",
                        "product_selector": ".catalog-card",
                        "field_selectors": {
                            "title": ".product-name",
                            "price": ".product-price",
                            "image": ".product-photo@src",
                            "link": ".product-link@href",
                        },
                    },
                },
                "retries": 0,
                "messages": [],
            }
        )

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["engine"], "fnspider")
        self.assertEqual(strategy["extraction_method"], "fnspider_site_spec")
        self.assertEqual(strategy["site_spec_draft"]["site"], "shop_example")
        self.assertEqual(
            strategy["site_spec_draft"]["list"]["item_container"],
            ".catalog-card",
        )

    def test_strategy_does_not_route_mock_catalog_to_fnspider(self) -> None:
        state = strategy_node(
            {
                "user_goal": "collect products",
                "target_url": "mock://catalog",
                "preferred_engine": "fnspider",
                "recon_report": {
                    "target_url": "mock://catalog",
                    "task_type": "product_list",
                    "rendering": "static",
                    "anti_bot": {"detected": False},
                    "api_endpoints": [],
                    "dom_structure": {
                        "pagination_type": "none",
                        "product_selector": ".catalog-card",
                        "field_selectors": {
                            "title": ".product-name",
                            "price": ".product-price",
                            "image": ".product-photo@src",
                            "link": ".product-link@href",
                        },
                    },
                },
                "retries": 0,
                "messages": [],
            }
        )

        strategy = state["crawl_strategy"]
        self.assertNotEqual(strategy.get("engine"), "fnspider")
        self.assertEqual(strategy["extraction_method"], "dom_parse")

    def test_strategy_does_not_route_ranking_list_to_fnspider(self) -> None:
        state = strategy_node(
            {
                "user_goal": "\u91c7\u96c6\u767e\u5ea6\u70ed\u641c\u699c\u524d30\u6761",
                "target_url": "mock://ranking",
                "crawl_preferences": {"engine": "fnspider"},
                "recon_report": {
                    "target_url": "mock://ranking",
                    "task_type": "ranking_list",
                    "constraints": {"max_items": 30},
                    "rendering": "static",
                    "anti_bot": {"detected": False},
                    "api_endpoints": [],
                    "dom_structure": {
                        "pagination_type": "none",
                        "product_selector": ".category-wrap_iQLoo",
                        "field_selectors": {
                            "rank": ".index_1Ew5p",
                            "title": ".title_dIF3B .c-single-text-ellipsis",
                            "link": ".title_dIF3B@href",
                            "hot_score": ".hot-index_1Bl1a",
                        },
                    },
                },
                "retries": 0,
                "messages": [],
            }
        )

        strategy = state["crawl_strategy"]
        self.assertNotIn("engine", strategy)
        self.assertEqual(strategy["extraction_method"], "dom_parse")
        self.assertEqual(strategy["max_items"], 30)

    def test_site_spec_adapter_builds_spider_uvex_draft(self) -> None:
        spec = build_site_spec(
            user_goal="collect products",
            target_url="https://shop.example/products",
            recon_report={
                "rendering": "static",
                "anti_bot": {"detected": False},
                "dom_structure": {"pagination_type": "url_param"},
            },
            selectors={
                "item_container": ".catalog-card",
                "title": ".product-name",
                "price": ".product-price",
                "image": ".product-photo@src",
                "link": ".product-link@href",
            },
            mode="http",
        )

        self.assertEqual(spec["site"], "shop_example")
        self.assertEqual(spec["mode"], "curl_cffi")
        self.assertEqual(spec["list"]["item_container"], ".catalog-card")
        self.assertEqual(spec["detail"]["image_src"], ".product-photo@src")
        self.assertEqual(spec["pagination"]["page_param"], "page")

    def test_bundled_fnspider_adapter_validates_and_saves_spec(self) -> None:
        spec = build_site_spec(
            user_goal="collect products",
            target_url="https://shop.example/products",
            recon_report={
                "rendering": "static",
                "anti_bot": {"detected": False},
                "dom_structure": {"pagination_type": "none"},
            },
            selectors={
                "item_container": ".catalog-card",
                "title": ".product-name",
                "price": ".product-price",
                "image": ".product-photo@src",
                "link": ".product-link@href",
            },
            mode="http",
        )

        normalized = validate_fnspider_site_spec(spec)
        self.assertEqual(normalized["site"], "shop_example")
        spec_path = save_fnspider_site_spec(normalized, "unit_test_shop_example.json")
        self.assertTrue(spec_path.exists())
        self.assertIn("autonomous_crawler", str(spec_path))

    def test_bundled_fnspider_runtime_paths_are_project_local(self) -> None:
        paths = fnspider_runtime_paths()
        self.assertIn("autonomous_crawler", paths["site_specs"])
        self.assertIn("autonomous_crawler", paths["cache"])
        self.assertIn("autonomous_crawler", paths["goods"])

    def test_extractor_confidence_is_bounded_to_requested_fields(self) -> None:
        state = extractor_node(
            {
                "raw_html": {
                    "mock://catalog": """
                    <article class="catalog-card">
                        <a class="product-link" href="/products/alpha">
                            <h2 class="product-name">Alpha Jacket</h2>
                            <span class="product-price">$129.90</span>
                        </a>
                    </article>
                    """
                },
                "crawl_strategy": {
                    "selectors": {
                        "item_container": ".catalog-card",
                        "title": ".product-name",
                        "price": ".product-price",
                        "link": ".product-link@href",
                    }
                },
                "recon_report": {"target_fields": ["title", "price"]},
                "messages": [],
            }
        )

        self.assertEqual(state["extracted_data"]["item_count"], 1)
        self.assertEqual(state["extracted_data"]["confidence"], 1.0)

    def test_extractor_supports_generic_fields(self) -> None:
        state = extractor_node(
            {
                "raw_html": {
                    "mock://rankings": """
                    <div class="hot-item">
                        <span class="rank">1</span>
                        <a class="title" href="/s?q=alpha">Alpha Topic</a>
                        <span class="hot-score">12345</span>
                    </div>
                    """
                },
                "crawl_strategy": {
                    "selectors": {
                        "item_container": ".hot-item",
                        "rank": ".rank",
                        "title": ".title",
                        "link": ".title@href",
                        "hot_score": ".hot-score",
                    }
                },
                "recon_report": {"target_fields": ["rank", "title", "hot_score"]},
                "messages": [],
            }
        )

        item = state["extracted_data"]["items"][0]
        self.assertEqual(item["rank"], "1")
        self.assertEqual(item["title"], "Alpha Topic")
        self.assertEqual(item["link"], "/s?q=alpha")
        self.assertEqual(item["hot_score"], 12345)
        self.assertEqual(state["extracted_data"]["confidence"], 1.0)

    def test_extractor_cleans_rating_score(self) -> None:
        state = extractor_node(
            {
                "raw_html": {
                    "mock://ratings": """
                    <div class="item">
                        <span class="title">Movie A</span>
                        <span class="rating_num">9.7</span>
                    </div>
                    """
                },
                "crawl_strategy": {
                    "selectors": {
                        "item_container": ".item",
                        "title": ".title",
                        "hot_score": ".rating_num",
                    }
                },
                "recon_report": {"target_fields": ["title", "hot_score"]},
                "messages": [],
            }
        )

        self.assertEqual(state["extracted_data"]["items"][0]["hot_score"], 9.7)
        self.assertEqual(state["extracted_data"]["confidence"], 1.0)

    def test_validator_does_not_require_price_for_ranking_tasks(self) -> None:
        state = validator_node(
            {
                "extracted_data": {
                    "items": [{"rank": "1", "title": "Alpha Topic", "hot_score": "12345"}],
                    "confidence": 1.0,
                },
                "recon_report": {"target_fields": ["rank", "title", "hot_score"]},
                "retries": 0,
                "max_retries": 0,
                "messages": [],
            }
        )

        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["validation_result"]["is_valid"])

    def test_graph_runs_with_inferred_mock_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke(
            {
                "user_goal": "\u91c7\u96c6\u5546\u54c1\u6807\u9898\u548c\u4ef7\u683c",
                "target_url": "mock://catalog",
                "recon_report": {},
                "crawl_strategy": {},
                "visited_urls": [],
                "raw_html": {},
                "api_responses": [],
                "extracted_data": {},
                "validation_result": {},
                "retries": 0,
                "max_retries": 3,
                "status": "pending",
                "error_log": [],
                "messages": [],
            }
        )

        self.assertEqual(final_state["status"], "completed")
        self.assertEqual(final_state["extracted_data"]["item_count"], 2)
        self.assertEqual(final_state["extracted_data"]["confidence"], 1.0)
        self.assertEqual(
            final_state["crawl_strategy"]["selectors"]["item_container"],
            ".catalog-card",
        )
        self.assertEqual(
            final_state["crawl_strategy"]["site_spec_draft"]["list"]["item_link"],
            ".product-link@href",
        )

    def test_graph_runs_with_inferred_ranking_fixture(self) -> None:
        app = compile_crawl_graph()
        final_state = app.invoke(
            {
                "user_goal": "\u91c7\u96c6\u767e\u5ea6\u70ed\u641c\u699c\u524d30\u6761",
                "target_url": "mock://ranking",
                "recon_report": {},
                "crawl_strategy": {},
                "visited_urls": [],
                "raw_html": {},
                "api_responses": [],
                "extracted_data": {},
                "validation_result": {},
                "retries": 0,
                "max_retries": 3,
                "status": "pending",
                "error_log": [],
                "messages": [],
            }
        )

        self.assertEqual(final_state["status"], "completed")
        self.assertEqual(final_state["recon_report"]["task_type"], "ranking_list")
        self.assertEqual(final_state["crawl_strategy"]["max_items"], 30)
        self.assertEqual(final_state["extracted_data"]["item_count"], 2)
        self.assertEqual(final_state["extracted_data"]["items"][0]["rank"], "1")
        self.assertEqual(final_state["extracted_data"]["items"][0]["title"], "Alpha Topic")


if __name__ == "__main__":
    unittest.main()
