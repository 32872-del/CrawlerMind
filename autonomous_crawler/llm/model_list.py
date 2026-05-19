"""Fetch and normalize model lists from OpenAI-compatible providers.

Targets the common ``/v1/models`` endpoint shape. Provider-neutral and
redacts API keys from all errors and logs.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ModelEntry:
    """A single model suitable for frontend dropdowns."""
    id: str
    label: str
    owned_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "label": self.label}
        if self.owned_by:
            d["owned_by"] = self.owned_by
        return d


@dataclass(frozen=True)
class ModelListResult:
    """Result of a model-list fetch."""
    provider: str
    models: list[ModelEntry]
    raw_count: int
    status: str  # ok | error
    error: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "models": [m.to_dict() for m in self.models],
            "raw_count": self.raw_count,
            "status": self.status,
            "error": self.error,
            "latency_ms": round(self.latency_ms, 1),
        }


def build_models_endpoint(base_url: str) -> str:
    """Build a /v1/models endpoint from a provider base URL.

    Accepted inputs:
    - https://api.example.com -> https://api.example.com/v1/models
    - https://api.example.com/v1 -> https://api.example.com/v1/models
    - https://api.example.com/v1/models -> unchanged
    """
    cleaned = base_url.strip().rstrip("/")
    lowered = cleaned.lower()
    if lowered.endswith("/models"):
        return cleaned
    if lowered.endswith("/v1"):
        return cleaned + "/models"
    return cleaned + "/v1/models"


def fetch_model_list(
    base_url: str,
    api_key: str = "",
    provider: str = "openai-compatible",
    timeout_seconds: float = 15.0,
) -> ModelListResult:
    """Fetch model list from an OpenAI-compatible /v1/models endpoint.

    Handles common relay shapes: {data: [{id: ...}]}, {models: [...]}, etc.
    Redacts API key from all error messages.
    """
    endpoint = build_models_endpoint(base_url)
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(endpoint, headers=headers)
            latency_ms = (time.monotonic() - start) * 1000
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        latency_ms = (time.monotonic() - start) * 1000
        error = _redact_key(str(exc), api_key)
        return ModelListResult(
            provider=provider, models=[], raw_count=0,
            status="error", error=error, latency_ms=latency_ms,
        )
    except httpx.HTTPError as exc:
        latency_ms = (time.monotonic() - start) * 1000
        error = _redact_key(str(exc), api_key)
        return ModelListResult(
            provider=provider, models=[], raw_count=0,
            status="error", error=error, latency_ms=latency_ms,
        )

    try:
        raw = response.json()
    except ValueError:
        return ModelListResult(
            provider=provider, models=[], raw_count=0,
            status="error", error="response is not valid JSON",
            latency_ms=latency_ms,
        )

    models = _normalize_models(raw)
    return ModelListResult(
        provider=provider,
        models=models,
        raw_count=len(models),
        status="ok",
        latency_ms=latency_ms,
    )


def check_provider_health(
    base_url: str,
    api_key: str = "",
    provider: str = "openai-compatible",
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Check provider connectivity by fetching /v1/models (no chat completion).

    Returns: status, latency_ms, normalized_url, error.
    """
    normalized = _normalize_base_url(base_url)
    endpoint = build_models_endpoint(normalized)
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.monotonic()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(endpoint, headers=headers)
            latency_ms = (time.monotonic() - start) * 1000
            return {
                "status": "ok" if response.status_code < 400 else "error",
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 1),
                "normalized_url": normalized,
                "endpoint": endpoint,
                "error": "" if response.status_code < 400 else _redact_key(
                    f"HTTP {response.status_code}", api_key
                ),
            }
    except httpx.HTTPError as exc:
        latency_ms = (time.monotonic() - start) * 1000
        return {
            "status": "error",
            "status_code": 0,
            "latency_ms": round(latency_ms, 1),
            "normalized_url": normalized,
            "endpoint": endpoint,
            "error": _redact_key(str(exc), api_key),
        }


def _normalize_models(raw: Any) -> list[ModelEntry]:
    """Extract model entries from common relay response shapes."""
    items: list[Any] = []

    if isinstance(raw, dict):
        # Standard: {data: [{id: "gpt-4", ...}]}
        if isinstance(raw.get("data"), list):
            items = raw["data"]
        # Some relays: {models: [...]}
        elif isinstance(raw.get("models"), list):
            items = raw["models"]
        # Single object: {id: "model-name"}
        elif raw.get("id"):
            items = [raw]
    elif isinstance(raw, list):
        items = raw

    models: list[ModelEntry] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        owned_by = str(item.get("owned_by") or "").strip()
        label = _make_label(model_id, owned_by)
        models.append(ModelEntry(id=model_id, label=label, owned_by=owned_by))

    return models


def _make_label(model_id: str, owned_by: str) -> str:
    """Build a human-friendly label for a model."""
    if owned_by and owned_by not in {"system", "openai"}:
        return f"{model_id} ({owned_by})"
    return model_id


def _normalize_base_url(base_url: str) -> str:
    """Strip trailing /v1 or /v1/ from base URL for consistency."""
    cleaned = base_url.strip().rstrip("/")
    lowered = cleaned.lower()
    if lowered.endswith("/v1"):
        return cleaned[:-3] or cleaned
    return cleaned


def _redact_key(text: str, key: str) -> str:
    """Redact API key from text."""
    if not key or len(key) < 8:
        return text
    masked = key[:4] + "..." + key[-4:]
    return text.replace(key, masked)
