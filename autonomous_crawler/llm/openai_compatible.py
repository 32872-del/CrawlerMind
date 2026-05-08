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

from .audit import MAX_PREVIEW_LENGTH, redact_preview
from ..errors import LLM_PROVIDER_UNREACHABLE


class LLMConfigurationError(ValueError):
    """Raised when LLM configuration is incomplete."""


class LLMResponseError(RuntimeError):
    """Raised when a provider response cannot be used."""

    def __init__(self, *args: object, error_code: str | None = None) -> None:
        super().__init__(*args)
        self.error_code = error_code


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
    use_response_format: bool = True

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
            use_response_format=_bool_env("CLM_LLM_USE_RESPONSE_FORMAT", True),
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

    def check_connection(self) -> dict[str, Any]:
        """Run a minimal provider check using the same JSON path as advisors."""
        messages = [
            {
                "role": "system",
                "content": (
                    "Return only one JSON object with keys ok and "
                    "reasoning_summary. Do not include markdown."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"check": "crawler-mind-llm-connection"},
                    ensure_ascii=False,
                ),
            },
        ]
        return self._chat_json(messages)

    @property
    def endpoint(self) -> str:
        """Resolved chat-completions endpoint used by this advisor."""
        return build_chat_completions_endpoint(self.config.base_url)

    def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        endpoint = self.endpoint
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.use_response_format:
            body["response_format"] = {"type": "json_object"}

        try:
            response = self._post_chat_completion(endpoint, headers, body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if _should_retry_without_response_format(exc.response, body):
                body = dict(body)
                body.pop("response_format", None)
                try:
                    response = self._post_chat_completion(endpoint, headers, body)
                    response.raise_for_status()
                except httpx.HTTPStatusError as retry_exc:
                    preview = _safe_response_preview(retry_exc.response)
                    raise LLMResponseError(
                        f"LLM request failed: {retry_exc}; response_preview={preview}"
                    ) from retry_exc
                except httpx.HTTPError as retry_exc:
                    raise LLMResponseError(
                        f"LLM request failed: {retry_exc}",
                        error_code=LLM_PROVIDER_UNREACHABLE,
                    ) from retry_exc
            else:
                preview = _safe_response_preview(exc.response)
                raise LLMResponseError(
                    f"LLM request failed: {exc}; response_preview={preview}"
                ) from exc
        except httpx.HTTPError as exc:
            raise LLMResponseError(
                f"LLM request failed: {exc}",
                error_code=LLM_PROVIDER_UNREACHABLE,
            ) from exc

        try:
            raw = response.json()
        except ValueError as exc:
            preview = _safe_response_preview(response)
            raise LLMResponseError(
                f"LLM response is not valid JSON; response_preview={preview}"
            ) from exc

        try:
            content = extract_chat_content(raw)
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                "LLM response missing usable chat content; "
                f"{_response_shape_hint(raw)}"
            ) from exc

        try:
            parsed = parse_json_object(str(content))
        except json.JSONDecodeError as exc:
            raise LLMResponseError("LLM response content is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMResponseError("LLM response content is not a JSON object")
        return parsed

    def _post_chat_completion(
        self,
        endpoint: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> httpx.Response:
        if self._client is not None:
            return self._client.post(endpoint, headers=headers, json=body)
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            return client.post(endpoint, headers=headers, json=body)


def build_advisor_from_env() -> OpenAICompatibleAdvisor | None:
    """Return an advisor when CLM_LLM_ENABLED is truthy, otherwise None."""
    if os.environ.get("CLM_LLM_ENABLED", "").strip().lower() not in {
        "1", "true", "yes", "on",
    }:
        return None
    return OpenAICompatibleAdvisor.from_env()


def build_chat_completions_endpoint(base_url: str) -> str:
    """Build a chat-completions endpoint from a provider base URL.

    Accepted inputs:
    - https://api.example.com -> https://api.example.com/v1/chat/completions
    - https://api.example.com/v1 -> https://api.example.com/v1/chat/completions
    - https://api.example.com/v1/chat/completions -> unchanged
    """
    cleaned = base_url.strip().rstrip("/")
    lowered = cleaned.lower()
    if lowered.endswith("/chat/completions"):
        return cleaned
    if lowered.endswith("/v1"):
        return cleaned + "/chat/completions"
    return cleaned + "/v1/chat/completions"


def extract_chat_content(raw: Any) -> Any:
    """Extract text content from common OpenAI-compatible response shapes."""
    choice = raw["choices"][0]
    message = choice.get("message") if isinstance(choice, dict) else None
    if isinstance(message, dict) and "content" in message:
        content = message["content"]
        if isinstance(content, list):
            return _join_content_parts(content)
        return content
    if isinstance(choice, dict) and "text" in choice:
        return choice["text"]
    raise KeyError("choices[0].message.content")


def parse_json_object(text: str) -> Any:
    """Parse a JSON object, allowing fenced JSON output."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.I | re.S)
    if fence:
        cleaned = fence.group(1).strip()
    return json.loads(cleaned)


def _join_content_parts(parts: list[Any]) -> str:
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, dict):
            text = part.get("text") or part.get("content")
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


def _response_shape_hint(raw: Any) -> str:
    try:
        preview = json.dumps(raw, ensure_ascii=False, default=str)
    except Exception:
        preview = str(raw)
    preview = preview[:MAX_PREVIEW_LENGTH]
    redacted, _ = redact_preview(preview)

    if isinstance(raw, dict):
        keys = ", ".join(sorted(str(key) for key in raw.keys()))
        return f"top_level_keys=[{keys}], response_preview={redacted}"
    return f"response_type={type(raw).__name__}, response_preview={redacted}"


def _safe_response_preview(response: httpx.Response) -> str:
    text = response.text[:MAX_PREVIEW_LENGTH]
    redacted, _ = redact_preview(text)
    return redacted


def _should_retry_without_response_format(
    response: httpx.Response,
    body: dict[str, Any],
) -> bool:
    if "response_format" not in body:
        return False
    if response.status_code not in {400, 422}:
        return False
    return "response_format" in response.text.lower()


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


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
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
