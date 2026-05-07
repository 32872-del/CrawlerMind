"""Tests for the OpenAI-compatible LLM adapter.

All tests use httpx.MockTransport. No API key. No network.
"""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import httpx

from autonomous_crawler.llm.openai_compatible import (
    LLMConfigurationError,
    LLMResponseError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
    build_advisor_from_env,
    parse_json_object,
)
from autonomous_crawler.llm.protocols import PlanningAdvisor, StrategyAdvisor
from run_skeleton import _parse_cli_args


class OpenAICompatibleConfigTests(unittest.TestCase):
    def test_from_env_requires_base_url(self) -> None:
        with patch.dict(os.environ, {"CLM_LLM_MODEL": "test-model"}, clear=True):
            with self.assertRaises(LLMConfigurationError):
                OpenAICompatibleConfig.from_env()

    def test_from_env_requires_model(self) -> None:
        with patch.dict(os.environ, {"CLM_LLM_BASE_URL": "https://llm.example/v1"}, clear=True):
            with self.assertRaises(LLMConfigurationError):
                OpenAICompatibleConfig.from_env()

    def test_from_env_reads_optional_values(self) -> None:
        env = {
            "CLM_LLM_BASE_URL": "https://llm.example/v1",
            "CLM_LLM_MODEL": "test-model",
            "CLM_LLM_API_KEY": "test-key",
            "CLM_LLM_PROVIDER": "test-provider",
            "CLM_LLM_TIMEOUT_SECONDS": "9.5",
            "CLM_LLM_TEMPERATURE": "0.2",
            "CLM_LLM_MAX_TOKENS": "321",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenAICompatibleConfig.from_env()

        self.assertEqual(config.base_url, "https://llm.example/v1")
        self.assertEqual(config.model, "test-model")
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.provider, "test-provider")
        self.assertEqual(config.timeout_seconds, 9.5)
        self.assertEqual(config.temperature, 0.2)
        self.assertEqual(config.max_tokens, 321)

    def test_build_advisor_from_env_disabled_returns_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(build_advisor_from_env())

    def test_build_advisor_from_env_enabled_returns_advisor(self) -> None:
        env = {
            "CLM_LLM_ENABLED": "1",
            "CLM_LLM_BASE_URL": "https://llm.example/v1",
            "CLM_LLM_MODEL": "test-model",
        }
        with patch.dict(os.environ, env, clear=True):
            advisor = build_advisor_from_env()

        self.assertIsInstance(advisor, OpenAICompatibleAdvisor)


class OpenAICompatibleAdvisorTests(unittest.TestCase):
    def _advisor_with_response(
        self,
        content: str,
        status_code: int = 200,
        request_log: list[httpx.Request] | None = None,
    ) -> OpenAICompatibleAdvisor:
        def handler(request: httpx.Request) -> httpx.Response:
            if request_log is not None:
                request_log.append(request)
            return httpx.Response(
                status_code,
                json={
                    "choices": [
                        {"message": {"content": content}},
                    ],
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        config = OpenAICompatibleConfig(
            base_url="https://llm.example/v1",
            model="test-model",
            api_key="test-key",
            provider="unit-test",
        )
        return OpenAICompatibleAdvisor(config=config, client=client)

    def test_plan_posts_chat_completion_request(self) -> None:
        requests: list[httpx.Request] = []
        advisor = self._advisor_with_response(
            json.dumps({
                "task_type": "ranking_list",
                "target_fields": ["rank", "title"],
                "max_items": 10,
            }),
            request_log=requests,
        )

        result = advisor.plan("collect top 10", "https://example.com")

        self.assertEqual(result["task_type"], "ranking_list")
        self.assertEqual(result["max_items"], 10)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(str(request.url), "https://llm.example/v1/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        body = json.loads(request.content.decode("utf-8"))
        self.assertEqual(body["model"], "test-model")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIn("messages", body)

    def test_api_key_is_optional(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": '{"task_type": "product_list"}'}},
                    ],
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        advisor = OpenAICompatibleAdvisor(
            OpenAICompatibleConfig(
                base_url="http://localhost:11434/v1",
                model="local-model",
            ),
            client=client,
        )

        result = advisor.plan("collect products", "https://example.com")

        self.assertEqual(result["task_type"], "product_list")
        self.assertNotIn("Authorization", requests[0].headers)

    def test_choose_strategy_returns_json_object(self) -> None:
        advisor = self._advisor_with_response(
            json.dumps({
                "mode": "browser",
                "selectors": {"title": ".title"},
            })
        )

        result = advisor.choose_strategy(
            planner_output={"task_id": "abc"},
            recon_report={"task_type": "product_list"},
        )

        self.assertEqual(result["mode"], "browser")
        self.assertEqual(result["selectors"]["title"], ".title")

    def test_protocol_compliance(self) -> None:
        advisor = self._advisor_with_response("{}")

        self.assertIsInstance(advisor, PlanningAdvisor)
        self.assertIsInstance(advisor, StrategyAdvisor)

    def test_fenced_json_content_is_supported(self) -> None:
        advisor = self._advisor_with_response(
            "```json\n{\"task_type\": \"product_list\"}\n```"
        )

        result = advisor.plan("collect products", "https://example.com")

        self.assertEqual(result["task_type"], "product_list")

    def test_http_error_raises_response_error(self) -> None:
        advisor = self._advisor_with_response("{}", status_code=500)

        with self.assertRaises(LLMResponseError):
            advisor.plan("collect", "https://example.com")

    def test_missing_content_raises_response_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": [{"message": {}}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        advisor = OpenAICompatibleAdvisor(
            OpenAICompatibleConfig(
                base_url="https://llm.example/v1",
                model="test-model",
            ),
            client=client,
        )

        with self.assertRaises(LLMResponseError):
            advisor.plan("collect", "https://example.com")

    def test_non_json_content_raises_response_error(self) -> None:
        advisor = self._advisor_with_response("not json")

        with self.assertRaises(LLMResponseError):
            advisor.plan("collect", "https://example.com")


class ParseJsonObjectTests(unittest.TestCase):
    def test_parse_plain_json(self) -> None:
        self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

    def test_parse_fenced_json(self) -> None:
        self.assertEqual(parse_json_object('```json\n{"a": 1}\n```'), {"a": 1})


class RunSkeletonCLITests(unittest.TestCase):
    def test_parse_cli_args_supports_llm_flag(self) -> None:
        goal, url, use_llm = _parse_cli_args([
            "--llm",
            "collect products",
            "https://example.com",
        ])

        self.assertEqual(goal, "collect products")
        self.assertEqual(url, "https://example.com")
        self.assertTrue(use_llm)

    def test_parse_cli_args_no_llm_overrides_env(self) -> None:
        with patch.dict(os.environ, {"CLM_LLM_ENABLED": "1"}, clear=True):
            goal, url, use_llm = _parse_cli_args([
                "--no-llm",
                "collect products",
                "https://example.com",
            ])

        self.assertEqual(goal, "collect products")
        self.assertEqual(url, "https://example.com")
        self.assertFalse(use_llm)


if __name__ == "__main__":
    unittest.main()
