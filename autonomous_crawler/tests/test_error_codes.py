"""Tests for structured error codes."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.errors import (
    ANTI_BOT_BLOCKED,
    BROWSER_RENDER_FAILED,
    EXTRACTION_EMPTY,
    FETCH_HTTP_ERROR,
    FETCH_UNSUPPORTED_SCHEME,
    LLM_CONFIG_INVALID,
    LLM_PROVIDER_UNREACHABLE,
    LLM_RESPONSE_INVALID,
    RECON_FAILED,
    SELECTOR_INVALID,
    VALIDATION_FAILED,
    classify_llm_error,
    format_error_entry,
)
from autonomous_crawler.llm.openai_compatible import (
    LLMConfigurationError,
    LLMResponseError,
)


# ---------------------------------------------------------------------------
# classify_llm_error
# ---------------------------------------------------------------------------

class TestClassifyLLMError(unittest.TestCase):

    def test_config_error_returns_llm_config_invalid(self):
        exc = LLMConfigurationError("missing base_url")
        self.assertEqual(classify_llm_error(exc), LLM_CONFIG_INVALID)

    def test_response_error_with_provider_unreachable_code(self):
        exc = LLMResponseError("connection refused", error_code=LLM_PROVIDER_UNREACHABLE)
        self.assertEqual(classify_llm_error(exc), LLM_PROVIDER_UNREACHABLE)

    def test_response_error_without_code_returns_response_invalid(self):
        exc = LLMResponseError("bad json")
        self.assertEqual(classify_llm_error(exc), LLM_RESPONSE_INVALID)

    def test_connection_error_returns_provider_unreachable(self):
        exc = ConnectionError("refused")
        self.assertEqual(classify_llm_error(exc), LLM_PROVIDER_UNREACHABLE)

    def test_timeout_error_returns_provider_unreachable(self):
        exc = TimeoutError("timed out")
        self.assertEqual(classify_llm_error(exc), LLM_PROVIDER_UNREACHABLE)

    def test_generic_exception_returns_response_invalid(self):
        exc = RuntimeError("something weird")
        self.assertEqual(classify_llm_error(exc), LLM_RESPONSE_INVALID)


# ---------------------------------------------------------------------------
# format_error_entry
# ---------------------------------------------------------------------------

class TestFormatErrorEntry(unittest.TestCase):

    def test_code_and_message(self):
        result = format_error_entry(FETCH_HTTP_ERROR, "HTTP 500")
        self.assertEqual(result, "[FETCH_HTTP_ERROR] HTTP 500")

    def test_code_message_and_details(self):
        result = format_error_entry(
            LLM_CONFIG_INVALID, "missing model", field="model"
        )
        self.assertEqual(result, "[LLM_CONFIG_INVALID] missing model (field=model)")

    def test_multiple_details(self):
        result = format_error_entry(
            FETCH_HTTP_ERROR, "timeout", url="https://x.com", retries=3
        )
        self.assertIn("[FETCH_HTTP_ERROR]", result)
        self.assertIn("timeout", result)
        self.assertIn("url=https://x.com", result)
        self.assertIn("retries=3", result)


# ---------------------------------------------------------------------------
# LLMResponseError.error_code attribute
# ---------------------------------------------------------------------------

class TestLLMResponseErrorErrorCode(unittest.TestCase):

    def test_default_error_code_is_none(self):
        exc = LLMResponseError("test")
        self.assertIsNone(exc.error_code)

    def test_error_code_can_be_set(self):
        exc = LLMResponseError("test", error_code=LLM_PROVIDER_UNREACHABLE)
        self.assertEqual(exc.error_code, LLM_PROVIDER_UNREACHABLE)


# ---------------------------------------------------------------------------
# Executor error codes
# ---------------------------------------------------------------------------

class TestExecutorErrorCodes(unittest.TestCase):

    def _make_state(self, **overrides):
        base = {
            "user_goal": "test",
            "target_url": "https://example.com",
            "crawl_strategy": {"mode": "http"},
            "recon_report": {},
            "status": "executing",
            "error_log": [],
            "messages": [],
        }
        base.update(overrides)
        return base

    def test_unsupported_scheme_sets_error_code(self):
        from autonomous_crawler.agents.executor import executor_node

        state = self._make_state(target_url="ftp://files.example.com/data")
        result = executor_node(state)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], FETCH_UNSUPPORTED_SCHEME)
        self.assertIn("[FETCH_UNSUPPORTED_SCHEME]", result["error_log"][0])

    @patch("autonomous_crawler.agents.executor.httpx.Client")
    def test_http_error_sets_error_code(self, mock_client_cls):
        import httpx
        from autonomous_crawler.agents.executor import executor_node

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock(status_code=500)
        )
        mock_client.get.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        state = self._make_state()
        result = executor_node(state)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], FETCH_HTTP_ERROR)
        self.assertIn("[FETCH_HTTP_ERROR]", result["error_log"][0])

    def test_browser_failure_sets_error_code(self):
        from autonomous_crawler.agents.executor import executor_node

        state = self._make_state(
            target_url="https://example.com",
            crawl_strategy={"mode": "browser"},
        )
        with patch(
            "autonomous_crawler.agents.executor.fetch_rendered_html"
        ) as mock_browser:
            mock_browser.return_value = MagicMock(
                status="error", error="Browser not found"
            )
            result = executor_node(state)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], BROWSER_RENDER_FAILED)
        self.assertIn("[BROWSER_RENDER_FAILED]", result["error_log"][0])


# ---------------------------------------------------------------------------
# Validator error codes
# ---------------------------------------------------------------------------

class TestValidatorErrorCodes(unittest.TestCase):

    def _make_state(self, **overrides):
        base = {
            "user_goal": "test",
            "target_url": "https://example.com",
            "recon_report": {"target_fields": ["title", "price"]},
            "extracted_data": {"items": [], "confidence": 0},
            "retries": 3,
            "max_retries": 3,
            "status": "executed",
            "error_log": [],
            "messages": [],
        }
        base.update(overrides)
        return base

    def test_no_items_sets_extraction_empty(self):
        from autonomous_crawler.agents.validator import validator_node

        state = self._make_state()
        result = validator_node(state)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], EXTRACTION_EMPTY)

    def test_low_completeness_sets_validation_failed(self):
        from autonomous_crawler.agents.validator import validator_node

        items = [{"title": "Widget", "price": None}]
        state = self._make_state(
            extracted_data={"items": items, "confidence": 0.8, "item_count": 1},
            retries=3,
            max_retries=3,
        )
        result = validator_node(state)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], VALIDATION_FAILED)

    def test_valid_result_has_no_error_code(self):
        from autonomous_crawler.agents.validator import validator_node

        items = [{"title": "Widget", "price": "$10"}]
        state = self._make_state(
            extracted_data={"items": items, "confidence": 1.0, "item_count": 1},
        )
        result = validator_node(state)
        self.assertEqual(result["status"], "completed")
        self.assertNotIn("error_code", result)

    def test_challenge_empty_result_sets_anti_bot_blocked(self):
        from autonomous_crawler.agents.validator import validator_node

        state = self._make_state(
            recon_report={
                "target_fields": ["title"],
                "access_diagnostics": {
                    "signals": {"challenge": "cf-challenge"},
                    "findings": ["challenge_detected:cf-challenge"],
                },
            }
        )
        result = validator_node(state)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], ANTI_BOT_BLOCKED)


# ---------------------------------------------------------------------------
# Recon error codes
# ---------------------------------------------------------------------------

class TestReconErrorCodes(unittest.TestCase):

    def test_unsupported_scheme_in_recon(self):
        from autonomous_crawler.agents.recon import recon_node

        state = {
            "target_url": "ftp://example.com",
            "recon_report": {},
            "status": "pending",
            "error_log": [],
            "messages": [],
        }
        result = recon_node(state)
        self.assertEqual(result["status"], "recon_failed")
        self.assertEqual(result["error_code"], FETCH_UNSUPPORTED_SCHEME)

    @patch("autonomous_crawler.agents.recon.fetch_html")
    def test_http_error_in_recon(self, mock_fetch):
        from autonomous_crawler.agents.recon import recon_node

        mock_fetch.return_value = MagicMock(error="Connection refused")
        state = {
            "target_url": "https://down.example.com",
            "recon_report": {},
            "status": "pending",
            "error_log": [],
            "messages": [],
        }
        result = recon_node(state)
        self.assertEqual(result["status"], "recon_failed")
        self.assertEqual(result["error_code"], FETCH_HTTP_ERROR)


# ---------------------------------------------------------------------------
# LLM planner/strategy error classification
# ---------------------------------------------------------------------------

class TestLLMAgentErrorClassification(unittest.TestCase):

    def test_planner_classifies_config_error(self):
        from autonomous_crawler.agents.planner import make_planner_node

        failing_advisor = MagicMock()
        failing_advisor.plan.side_effect = LLMConfigurationError("missing model")
        node = make_planner_node(failing_advisor)

        state = {
            "user_goal": "test",
            "target_url": "https://example.com",
            "recon_report": {},
            "status": "planning",
            "error_log": [],
            "messages": [],
        }
        result = node(state)
        llm_errors = result.get("llm_errors", [])
        self.assertEqual(len(llm_errors), 1)
        self.assertIn(f"[{LLM_CONFIG_INVALID}]", llm_errors[0])

    def test_strategy_classifies_provider_unreachable(self):
        from autonomous_crawler.agents.strategy import make_strategy_node

        exc = LLMResponseError("connection refused", error_code=LLM_PROVIDER_UNREACHABLE)
        failing_advisor = MagicMock()
        failing_advisor.choose_strategy.side_effect = exc
        node = make_strategy_node(failing_advisor)

        state = {
            "user_goal": "test",
            "target_url": "https://example.com",
            "recon_report": {"task_type": "product_list", "target_fields": ["title"]},
            "crawl_strategy": {"mode": "http", "selectors": {}},
            "status": "strategy",
            "error_log": [],
            "messages": [],
            "llm_enabled": True,
            "llm_decisions": [],
            "llm_errors": [],
        }
        result = node(state)
        llm_errors = result.get("llm_errors", [])
        self.assertEqual(len(llm_errors), 1)
        self.assertIn(f"[{LLM_PROVIDER_UNREACHABLE}]", llm_errors[0])

    def test_planner_classifies_response_invalid(self):
        from autonomous_crawler.agents.planner import make_planner_node

        failing_advisor = MagicMock()
        failing_advisor.plan.side_effect = LLMResponseError("bad json")
        node = make_planner_node(failing_advisor)

        state = {
            "user_goal": "test",
            "target_url": "https://example.com",
            "recon_report": {},
            "status": "planning",
            "error_log": [],
            "messages": [],
        }
        result = node(state)
        llm_errors = result.get("llm_errors", [])
        self.assertEqual(len(llm_errors), 1)
        self.assertIn(f"[{LLM_RESPONSE_INVALID}]", llm_errors[0])


# ---------------------------------------------------------------------------
# Error code constants are all strings
# ---------------------------------------------------------------------------

class TestErrorCodeConstants(unittest.TestCase):

    def test_all_codes_are_strings(self):
        codes = [
            LLM_CONFIG_INVALID,
            LLM_PROVIDER_UNREACHABLE,
            LLM_RESPONSE_INVALID,
            FETCH_UNSUPPORTED_SCHEME,
            FETCH_HTTP_ERROR,
            BROWSER_RENDER_FAILED,
            EXTRACTION_EMPTY,
            SELECTOR_INVALID,
            VALIDATION_FAILED,
            ANTI_BOT_BLOCKED,
            RECON_FAILED,
        ]
        for code in codes:
            self.assertIsInstance(code, str)
            self.assertTrue(code.isupper())
            self.assertTrue(len(code) > 0)


if __name__ == "__main__":
    unittest.main()
