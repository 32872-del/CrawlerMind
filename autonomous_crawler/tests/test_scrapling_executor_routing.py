"""Executor and strategy routing tests for runtime backends."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.agents.planner import make_planner_node
from autonomous_crawler.agents.strategy import make_strategy_node, strategy_node
from autonomous_crawler.runtime import RuntimeResponse, RuntimeSelectorResult


class _PlanningAdvisor:
    def plan(self, user_goal: str, target_url: str) -> dict:
        return {
            "task_type": "product_list",
            "crawl_preferences": {"engine": "scrapling"},
        }


class _StrategyAdvisor:
    def choose_strategy(self, planner_output: dict, recon_report: dict) -> dict:
        return {
            "mode": "http",
            "engine": "scrapling",
            "selectors": {
                "item_container": ".product",
                "title": ".name",
            },
        }


class _NativePlanningAdvisor:
    def plan(self, user_goal: str, target_url: str) -> dict:
        return {
            "task_type": "product_list",
            "crawl_preferences": {"engine": "native"},
        }


class _NativeStrategyAdvisor:
    def choose_strategy(self, planner_output: dict, recon_report: dict) -> dict:
        return {
            "mode": "http",
            "engine": "native",
            "selectors": {
                "item_container": ".product",
                "title": ".name",
            },
        }


class ScraplingExecutorRoutingTests(unittest.TestCase):
    @patch("autonomous_crawler.agents.executor.ScraplingParserRuntime")
    @patch("autonomous_crawler.agents.executor.ScraplingStaticRuntime")
    def test_static_scrapling_runtime_returns_raw_html_and_engine_result(
        self,
        static_cls: MagicMock,
        parser_cls: MagicMock,
    ) -> None:
        static_cls.return_value.fetch.return_value = RuntimeResponse(
            ok=True,
            final_url="https://shop.example/products",
            status_code=200,
            html="<div class='product'><h2 class='name'>Alpha</h2></div>",
            engine_result={"engine": "scrapling_static"},
        )
        parser_cls.return_value.parse.return_value = [
            RuntimeSelectorResult(
                name="title",
                values=["Alpha"],
                selector=".name",
                matched=1,
            )
        ]

        state = executor_node({
            "target_url": "https://shop.example/products",
            "crawl_strategy": {
                "mode": "http",
                "engine": "scrapling",
                "selectors": {
                    "item_container": ".product",
                    "title": ".name",
                },
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertIn("https://shop.example/products", state["raw_html"])
        self.assertEqual(state["engine_result"]["engine"], "scrapling")
        self.assertEqual(state["engine_result"]["backend"], "scrapling_static")
        self.assertEqual(
            state["engine_result"]["selector_results"][0]["values"],
            ["Alpha"],
        )
        static_cls.return_value.fetch.assert_called_once()
        parser_cls.return_value.parse.assert_called_once()

    @patch("autonomous_crawler.agents.executor.ScraplingParserRuntime")
    @patch("autonomous_crawler.agents.executor.ScraplingBrowserRuntime")
    def test_browser_scrapling_runtime_uses_browser_adapter(
        self,
        browser_cls: MagicMock,
        parser_cls: MagicMock,
    ) -> None:
        browser_cls.return_value.render.return_value = RuntimeResponse(
            ok=True,
            final_url="https://spa.example/products",
            status_code=200,
            html="<div class='product'><h2 class='name'>Rendered</h2></div>",
            engine_result={"engine": "scrapling_browser"},
        )
        parser_cls.return_value.parse.return_value = []

        state = executor_node({
            "target_url": "https://spa.example/products",
            "crawl_strategy": {
                "mode": "browser",
                "engine": "scrapling",
                "selectors": {
                    "item_container": ".product",
                    "title": ".name",
                },
                "wait_until": "networkidle",
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["engine_result"]["backend"], "scrapling_browser")
        request = browser_cls.return_value.render.call_args.args[0]
        self.assertEqual(request.mode, "dynamic")
        self.assertEqual(request.wait_until, "networkidle")

    @patch("autonomous_crawler.agents.executor.ScraplingStaticRuntime")
    def test_scrapling_runtime_failure_is_structured(self, static_cls: MagicMock) -> None:
        static_cls.return_value.fetch.return_value = RuntimeResponse.failure(
            final_url="https://blocked.example",
            status_code=403,
            error="Forbidden",
            engine="scrapling_static",
        )

        state = executor_node({
            "target_url": "https://blocked.example",
            "crawl_strategy": {
                "mode": "http",
                "engine": "scrapling",
                "selectors": {"title": "h1"},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["raw_html"], {})
        self.assertEqual(state["engine_result"]["engine"], "scrapling")
        self.assertIn("Scrapling runtime failed", state["error_log"][0])


class NativeExecutorRoutingTests(unittest.TestCase):
    @patch("autonomous_crawler.agents.executor.NativeParserRuntime")
    @patch("autonomous_crawler.agents.executor.NativeFetchRuntime")
    def test_static_native_runtime_returns_raw_html_and_engine_result(
        self,
        fetch_cls: MagicMock,
        parser_cls: MagicMock,
    ) -> None:
        fetch_cls.return_value.fetch.return_value = RuntimeResponse(
            ok=True,
            final_url="https://shop.example/products",
            status_code=200,
            html="<div class='product'><h2 class='name'>Alpha</h2></div>",
            engine_result={"engine": "native_static", "transport": "httpx"},
        )
        parser_cls.return_value.parse.return_value = [
            RuntimeSelectorResult(
                name="title",
                values=["Alpha"],
                selector=".name",
                matched=1,
            )
        ]

        state = executor_node({
            "target_url": "https://shop.example/products",
            "crawl_strategy": {
                "mode": "http",
                "engine": "native",
                "selectors": {
                    "item_container": ".product",
                    "title": ".name",
                },
                "transport": "httpx",
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertIn("https://shop.example/products", state["raw_html"])
        self.assertEqual(state["engine_result"]["engine"], "native")
        self.assertEqual(state["engine_result"]["backend"], "native_static")
        self.assertEqual(state["engine_result"]["transport"], "httpx")
        self.assertEqual(
            state["engine_result"]["selector_results"][0]["values"],
            ["Alpha"],
        )
        request = fetch_cls.return_value.fetch.call_args.args[0]
        self.assertEqual(request.meta["engine"], "native")
        self.assertEqual(request.meta["transport"], "httpx")
        fetch_cls.return_value.fetch.assert_called_once()
        parser_cls.return_value.parse.assert_called_once()

    @patch("autonomous_crawler.agents.executor.NativeFetchRuntime")
    def test_native_runtime_failure_is_structured(self, fetch_cls: MagicMock) -> None:
        fetch_cls.return_value.fetch.return_value = RuntimeResponse.failure(
            final_url="https://blocked.example",
            status_code=403,
            error="Forbidden",
            engine="native_static",
        )

        state = executor_node({
            "target_url": "https://blocked.example",
            "crawl_strategy": {
                "mode": "http",
                "engine": "native",
                "selectors": {"title": "h1"},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["raw_html"], {})
        self.assertEqual(state["engine_result"]["engine"], "native")
        self.assertEqual(state["engine_result"]["backend"], "native_static")
        self.assertIn("Native runtime failed", state["error_log"][0])

    @patch("autonomous_crawler.agents.executor.NativeParserRuntime")
    @patch("autonomous_crawler.agents.executor.NativeBrowserRuntime")
    def test_browser_native_runtime_uses_browser_backend(
        self,
        browser_cls: MagicMock,
        parser_cls: MagicMock,
    ) -> None:
        browser_cls.return_value.render.return_value = RuntimeResponse(
            ok=True,
            final_url="https://spa.example/products",
            status_code=200,
            html="<div class='product'><h2 class='name'>Rendered</h2></div>",
            captured_xhr=[{"url": "https://spa.example/api/products", "status_code": 200}],
            engine_result={"engine": "native_browser", "mode": "dynamic"},
        )
        parser_cls.return_value.parse.return_value = [
            RuntimeSelectorResult(
                name="title",
                values=["Rendered"],
                selector=".name",
                matched=1,
            )
        ]

        state = executor_node({
            "target_url": "https://spa.example/products",
            "crawl_strategy": {
                "mode": "browser",
                "engine": "native",
                "selectors": {
                    "item_container": ".product",
                    "title": ".name",
                },
                "wait_until": "networkidle",
                "capture_xhr": "api/products",
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "executed")
        self.assertEqual(state["engine_result"]["engine"], "native")
        self.assertEqual(state["engine_result"]["backend"], "native_browser")
        self.assertEqual(state["api_responses"][0]["url"], "https://spa.example/api/products")
        self.assertEqual(
            state["engine_result"]["selector_results"][0]["values"],
            ["Rendered"],
        )
        request = browser_cls.return_value.render.call_args.args[0]
        self.assertEqual(request.mode, "dynamic")
        self.assertEqual(request.wait_until, "networkidle")
        self.assertEqual(request.capture_xhr, "api/products")

    @patch("autonomous_crawler.agents.executor.NativeBrowserRuntime")
    def test_native_browser_runtime_failure_is_structured(self, browser_cls: MagicMock) -> None:
        browser_cls.return_value.render.return_value = RuntimeResponse.failure(
            final_url="https://spa.example/products",
            error="browser crashed",
            engine="native_browser",
        )

        state = executor_node({
            "target_url": "https://spa.example/products",
            "crawl_strategy": {
                "mode": "browser",
                "engine": "native",
                "selectors": {"title": "h1"},
            },
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["engine_result"]["engine"], "native")
        self.assertEqual(state["engine_result"]["backend"], "native_browser")
        self.assertEqual(state["error_code"], "BROWSER_RENDER_FAILED")


class ScraplingPlannerStrategyRoutingTests(unittest.TestCase):
    def test_planner_accepts_scrapling_engine_preference(self) -> None:
        node = make_planner_node(_PlanningAdvisor())
        state = node({
            "user_goal": "collect product titles",
            "target_url": "https://shop.example",
            "messages": [],
        })

        self.assertEqual(state["crawl_preferences"], {"engine": "scrapling"})
        self.assertIn("crawl_preferences", state["llm_decisions"][0]["accepted_fields"])

    def test_strategy_advisor_accepts_scrapling_engine(self) -> None:
        node = make_strategy_node(_StrategyAdvisor())
        state = node({
            "user_goal": "collect product titles",
            "target_url": "https://shop.example",
            "recon_report": {
                "task_type": "product_list",
                "target_fields": ["title"],
                "target_url": "https://shop.example",
                "dom_structure": {},
            },
            "messages": [],
        })

        self.assertEqual(state["crawl_strategy"]["engine"], "scrapling")
        self.assertIn("engine", state["llm_decisions"][0]["accepted_fields"])

    def test_preferred_scrapling_engine_generates_scrapling_strategy(self) -> None:
        state = strategy_node({
            "user_goal": "collect product titles",
            "target_url": "https://shop.example",
            "preferred_engine": "scrapling",
            "recon_report": {
                "task_type": "product_list",
                "target_fields": ["title"],
                "target_url": "https://shop.example",
                "rendering": "static",
                "anti_bot": {"detected": False},
                "dom_structure": {
                    "product_selector": ".product",
                    "item_count": 2,
                    "field_selectors": {"title": ".name"},
                },
            },
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["engine"], "scrapling")
        self.assertEqual(strategy["mode"], "http")
        self.assertEqual(strategy["extraction_method"], "scrapling_runtime")


class NativePlannerStrategyRoutingTests(unittest.TestCase):
    def test_planner_accepts_native_engine_preference(self) -> None:
        node = make_planner_node(_NativePlanningAdvisor())
        state = node({
            "user_goal": "collect product titles",
            "target_url": "https://shop.example",
            "messages": [],
        })

        self.assertEqual(state["crawl_preferences"], {"engine": "native"})
        self.assertIn("crawl_preferences", state["llm_decisions"][0]["accepted_fields"])

    def test_strategy_advisor_accepts_native_engine(self) -> None:
        node = make_strategy_node(_NativeStrategyAdvisor())
        state = node({
            "user_goal": "collect product titles",
            "target_url": "https://shop.example",
            "recon_report": {
                "task_type": "product_list",
                "target_fields": ["title"],
                "target_url": "https://shop.example",
                "dom_structure": {},
            },
            "messages": [],
        })

        self.assertEqual(state["crawl_strategy"]["engine"], "native")
        self.assertIn("engine", state["llm_decisions"][0]["accepted_fields"])

    def test_preferred_native_engine_generates_native_strategy(self) -> None:
        state = strategy_node({
            "user_goal": "collect product titles",
            "target_url": "https://shop.example",
            "preferred_engine": "native",
            "recon_report": {
                "task_type": "product_list",
                "target_fields": ["title"],
                "target_url": "https://shop.example",
                "rendering": "static",
                "anti_bot": {"detected": False},
                "dom_structure": {
                    "product_selector": ".product",
                    "item_count": 2,
                    "field_selectors": {"title": ".name"},
                },
            },
            "messages": [],
        })

        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["engine"], "native")
        self.assertEqual(strategy["mode"], "http")
        self.assertEqual(strategy["extraction_method"], "native_runtime")


if __name__ == "__main__":
    unittest.main()
