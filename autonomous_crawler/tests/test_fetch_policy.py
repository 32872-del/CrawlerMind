from __future__ import annotations

import unittest

from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.agents.strategy import strategy_node
from autonomous_crawler.tools.fetch_policy import FetchAttempt, fetch_best_page, score_html_attempt
from autonomous_crawler.tools.html_recon import (
    MOCK_CHALLENGE_HTML,
    MOCK_JS_SHELL_HTML,
    MOCK_PRODUCT_HTML,
    fetch_best_html,
)


class FetchPolicyTests(unittest.TestCase):
    def test_scores_good_static_html_above_js_shell(self) -> None:
        good = FetchAttempt(
            mode="requests",
            url="https://shop.example",
            html=MOCK_PRODUCT_HTML,
            status_code=200,
        )
        shell = FetchAttempt(
            mode="requests",
            url="https://app.example",
            html=MOCK_JS_SHELL_HTML,
            status_code=200,
        )

        good_score, good_reasons = score_html_attempt(good)
        shell_score, shell_reasons = score_html_attempt(shell)

        self.assertGreater(good_score, shell_score)
        self.assertIn("dom_candidates", good_reasons)
        self.assertIn("js_shell", shell_reasons)

    def test_challenge_scores_low_and_records_reason(self) -> None:
        attempt = FetchAttempt(
            mode="requests",
            url="https://blocked.example",
            html=MOCK_CHALLENGE_HTML,
            status_code=403,
        )

        score, reasons = score_html_attempt(attempt)

        self.assertLess(score, 0)
        self.assertTrue(any(reason.startswith("challenge:") for reason in reasons))
        self.assertEqual(attempt.diagnostics["signals"]["challenge"], "cf-challenge")

    def test_fetch_best_page_escalates_from_js_shell_to_browser(self) -> None:
        def requests_fetch(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="requests",
                url=url,
                html=MOCK_JS_SHELL_HTML,
                status_code=200,
            )

        def browser_fetch(url: str, headers: dict[str, str] | None, options=None) -> FetchAttempt:
            return FetchAttempt(
                mode="browser",
                url=url,
                html=MOCK_PRODUCT_HTML,
                status_code=200,
            )

        result = fetch_best_page(
            "https://spa.example",
            modes=["requests", "browser"],
            fetchers={"requests": requests_fetch, "browser": browser_fetch},
        )

        self.assertEqual(result.mode, "browser")
        self.assertEqual([attempt.mode for attempt in result.attempts], ["requests", "browser"])
        self.assertIn("js_shell", result.attempts[0].reasons)

    def test_fetch_best_page_keeps_json_payload_on_requests(self) -> None:
        def requests_fetch(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="requests",
                url=url,
                html='{"data":{"list":[{"title":"Alpha"}]}}',
                status_code=200,
            )

        def browser_fetch(url: str, headers: dict[str, str] | None, options=None) -> FetchAttempt:
            raise AssertionError("browser should not be launched for JSON payloads")

        result = fetch_best_page(
            "https://api.example/list",
            modes=["requests", "browser"],
            fetchers={"requests": requests_fetch, "browser": browser_fetch},
        )

        self.assertEqual(result.mode, "requests")
        self.assertIn("json_payload", result.attempts[0].reasons)

    def test_fetch_best_page_skips_browser_after_transport_errors(self) -> None:
        def failed_fetch(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(
                mode="requests",
                url=url,
                error="DNS resolution failed",
            )

        def browser_fetch(url: str, headers: dict[str, str] | None, options=None) -> FetchAttempt:
            raise AssertionError("browser should not be launched after transport errors")

        result = fetch_best_page(
            "https://down.example",
            modes=["requests", "browser"],
            fetchers={"requests": failed_fetch, "browser": browser_fetch},
        )

        self.assertEqual(result.mode, "requests")
        self.assertEqual(result.error, "DNS resolution failed")
        self.assertEqual(result.attempts[-1].mode, "browser")
        self.assertIn("skipped", result.attempts[-1].error)

    def test_fetch_best_html_mock_js_shell_records_escalation_trace(self) -> None:
        result = fetch_best_html("mock://js-shell")

        self.assertEqual(result.mode, "browser")
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.attempts[0].mode, "requests")
        self.assertEqual(result.attempts[1].mode, "browser")

    def test_recon_records_fetch_trace_and_selected_mode(self) -> None:
        state = recon_node({
            "target_url": "mock://js-shell",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        recon = state["recon_report"]
        self.assertEqual(recon["fetch"]["selected_mode"], "browser")
        self.assertEqual(recon["fetch_trace"]["selected_mode"], "browser")
        self.assertEqual(recon["dom_structure"]["product_selector"], ".catalog-card")

    def test_strategy_keeps_browser_when_recon_selected_browser(self) -> None:
        state = strategy_node({
            "user_goal": "collect products",
            "target_url": "mock://js-shell",
            "recon_report": {
                "target_url": "mock://js-shell",
                "task_type": "product_list",
                "constraints": {},
                "rendering": "static",
                "fetch": {"selected_mode": "browser"},
                "anti_bot": {"detected": False},
                "api_endpoints": [],
                "access_diagnostics": {"findings": [], "signals": {}},
                "dom_structure": {
                    "pagination_type": "none",
                    "product_selector": ".catalog-card",
                    "field_selectors": {"title": ".product-name"},
                },
            },
            "retries": 0,
            "messages": [],
        })

        self.assertEqual(state["crawl_strategy"]["mode"], "browser")


if __name__ == "__main__":
    unittest.main()
