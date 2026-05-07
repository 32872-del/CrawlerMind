"""OpenAI-compatible chat-completions advisors.

The adapter targets the common ``/chat/completions`` API shape used by many
hosted and local LLM providers. It is intentionally provider-neutral and keeps
real network usage opt-in.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


class LLMConfigurationError(ValueError):
    """Raised when LLM configuration is incomplete."""


class LLMResponseError(RuntimeError):
    """Raised when a provider response cannot be used."""


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    """Configuration for an OpenAI-compatible chat completion endpoint."""

    base_url: str
    model: str
    api_key: str = ""
    provider: str = "openai-compatible"
    timeout_seconds: float = 30.0
    temperature: float = 0.0
    max_tokens: int = 800

    @classmethod
    def from_env(cls) -> "OpenAICompatibleConfig":
        """Build config from CLM_LLM_* environment variables."""
        base_url = os.environ.get("CLM_LLM_BASE_URL", "").strip()
        model = os.environ.get("CLM_LLM_MODEL", "").strip()
        api_key = os.environ.get("CLM_LLM_API_KEY", "").strip()
        provider = os.environ.get("CLM_LLM_PROVIDER", "openai-compatible").strip()

        if not base_url:
            raise LLMConfigurationError("CLM_LLM_BASE_URL is required")
        if not model:
            raise LLMConfigurationError("CLM_LLM_MODEL is required")

        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            provider=provider or "openai-compatible",
            timeout_seconds=_float_env("CLM_LLM_TIMEOUT_SECONDS", 30.0),
            temperature=_float_env("CLM_LLM_TEMPERATURE", 0.0),
            max_tokens=_int_env("CLM_LLM_MAX_TOKENS", 800),
        )


class OpenAICompatibleAdvisor:
    """Planning and Strategy advisor backed by chat completions."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.provider = config.provider
        self.model = config.model
        self._client = client

    @classmethod
    def from_env(cls) -> "OpenAICompatibleAdvisor":
        """Create an advisor from CLM_LLM_* environment variables."""
        return cls(OpenAICompatibleConfig.from_env())

    def plan(self, user_goal: str, target_url: str) -> dict[str, Any]:
        """Return normalized crawl intent fields."""
        messages = [
            {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {"user_goal": user_goal, "target_url": target_url},
                    ensure_ascii=False,
                ),
            },
        ]
        return self._chat_json(messages)

    def choose_strategy(
        self,
        planner_output: dict[str, Any],
        recon_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a safe strategy suggestion based on planner and recon output."""
        payload = {
            "planner_output": _bounded(planner_output, 5000),
            "recon_report": _bounded(recon_report, 8000),
        }
        messages = [
            {"role": "system", "content": _STRATEGY_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        return self._chat_json(messages)

    def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        body = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }

        try:
            if self._client is not None:
                response = self._client.post(endpoint, headers=headers, json=body)
            else:
                with httpx.Client(timeout=self.config.timeout_seconds) as client:
                    response = client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMResponseError(f"LLM request failed: {exc}") from exc

        try:
            raw = response.json()
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError(
                "LLM response missing choices[0].message.content"
            ) from exc

        try:
            parsed = parse_json_object(str(content))
        except json.JSONDecodeError as exc:
            raise LLMResponseError("LLM response content is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMResponseError("LLM response content is not a JSON object")
        return parsed


def build_advisor_from_env() -> OpenAICompatibleAdvisor | None:
    """Return an advisor when CLM_LLM_ENABLED is truthy, otherwise None."""
    if os.environ.get("CLM_LLM_ENABLED", "").strip().lower() not in {
        "1", "true", "yes", "on",
    }:
        return None
    return OpenAICompatibleAdvisor.from_env()


def parse_json_object(text: str) -> Any:
    """Parse a JSON object, allowing fenced JSON output."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.I | re.S)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


def _bounded(value: Any, max_chars: int) -> Any:
    """JSON-roundtrip a value and truncate it for prompt safety."""
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return value
    return {"_truncated_json": text[:max_chars]}


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


_PLANNER_SYSTEM_PROMPT = """You are the planning advisor for Crawler-Mind.
Return only one JSON object. Do not include markdown or commentary.

Allowed keys:
- task_type: "product_list" or "ranking_list"
- target_fields: array using known fields such as title, price, image, link,
  rank, hot_score, summary, description, url, stock, size, color
- max_items: positive integer when the user asks for a count
- constraints: object with simple scalar constraints
- crawl_preferences: object, for example {"engine": "fnspider"}
- reasoning_summary: one short sentence

If uncertain, omit the field instead of guessing.
"""


_STRATEGY_SYSTEM_PROMPT = """You are the strategy advisor for Crawler-Mind.
Return only one JSON object. Do not include markdown or commentary.

Allowed keys:
- mode: "http", "browser", or "api_intercept"
- engine: "" or "fnspider"; use fnspider only for product_list tasks
- selectors: object with keys like item_container, title, price, image, link,
  rank, hot_score, summary, description, url, stock, size, color
- wait_selector: CSS selector string
- wait_until: "domcontentloaded", "load", or "networkidle"
- max_items: positive integer
- reasoning_summary: one short sentence

Prefer deterministic recon selectors when they look usable. Suggest only small,
safe changes.
"""
