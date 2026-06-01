"""Multi-provider LLM registry with auto-detection and failover.

Supports:
- OpenAI / GPT (any OpenAI-compatible endpoint)
- Anthropic / Claude
- DeepSeek
- Tongyi Qianwen (通义千问)
- Moonshot / Kimi
- Xiaomi MiMo
- Zhipu GLM
- Custom OpenAI-compatible proxies/transit stations

Usage:
    registry = LLMProviderRegistry()
    registry.add_provider("mimo", base_url="https://...", model="mimo-v2.5-pro", api_key="...")
    registry.add_provider("deepseek", api_key="...", model="deepseek-chat")
    
    # Auto-detect and connect
    advisor = registry.get_advisor()
    
    # Or use with failover
    advisor = registry.get_advisor_with_fallback()
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from .openai_compatible import (
    LLMConfigurationError,
    LLMResponseError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
)


# ---------------------------------------------------------------------------
# Provider presets
# ---------------------------------------------------------------------------

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "headers": {},
        "api_style": "openai",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "headers": {},
        "api_style": "openai",
    },
    "tongyi": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "headers": {},
        "api_style": "openai",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "headers": {},
        "api_style": "openai",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "headers": {},
        "api_style": "openai",
    },
    "mimo": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "default_model": "mimo-v2.5-pro",
        "headers": {},
        "api_style": "openai",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
        "headers": {"anthropic-version": "2023-06-01"},
        "api_style": "anthropic",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o",
        "headers": {},
        "api_style": "openai",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "headers": {},
        "api_style": "openai",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.1-70b-versatile",
        "headers": {},
        "api_style": "openai",
    },
}


# URL patterns for auto-detection
URL_PROVIDER_PATTERNS: list[tuple[str, str]] = [
    (r"openai\.com", "openai"),
    (r"api\.deepseek\.com", "deepseek"),
    (r"dashscope\.aliyuncs\.com", "tongyi"),
    (r"api\.moonshot\.cn", "moonshot"),
    (r"bigmodel\.cn", "zhipu"),
    (r"xiaomimimo\.com", "mimo"),
    (r"anthropic\.com", "anthropic"),
    (r"openrouter\.ai", "openrouter"),
    (r"together\.xyz", "together"),
    (r"groq\.com", "groq"),
    (r"api\.pptoken\.", "proxy"),  # Common Chinese proxy
    (r"api\.openai-proxy", "proxy"),
    (r"one-api", "proxy"),
    (r"new-api", "proxy"),
    (r"fastgpt", "proxy"),
]


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------

@dataclass
class LLMProviderConfig:
    """Configuration for a single LLM provider."""
    name: str
    base_url: str
    model: str
    api_key: str = ""
    api_style: str = "openai"  # "openai" or "anthropic"
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 60.0
    temperature: float = 0.0
    max_tokens: int = 4000
    use_response_format: bool = True
    reasoning_effort: str = "medium"
    priority: int = 0  # Lower = higher priority
    enabled: bool = True

    def to_openai_config(self) -> OpenAICompatibleConfig:
        """Convert to OpenAI-compatible config."""
        return OpenAICompatibleConfig(
            base_url=self.base_url,
            model=self.model,
            api_key=self.api_key,
            provider=self.name,
            timeout_seconds=self.timeout_seconds,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            use_response_format=self.use_response_format,
            reasoning_effort=self.reasoning_effort,
        )


# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------

class LLMProviderRegistry:
    """Registry for managing multiple LLM providers with failover."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProviderConfig] = {}
        self._advisors: dict[str, OpenAICompatibleAdvisor] = {}

    def add_provider(
        self,
        name: str,
        *,
        base_url: str = "",
        model: str = "",
        api_key: str = "",
        provider_preset: str = "",
        priority: int = 0,
        **kwargs: Any,
    ) -> LLMProviderConfig:
        """Add a provider to the registry.

        Can specify by preset name or by explicit base_url/model/api_key.
        """
        # Resolve from preset
        if provider_preset and provider_preset in PROVIDER_PRESETS:
            preset = PROVIDER_PRESETS[provider_preset]
            base_url = base_url or preset["base_url"]
            model = model or preset["default_model"]
            if not kwargs.get("headers"):
                kwargs["headers"] = dict(preset.get("headers", {}))
            if not kwargs.get("api_style"):
                kwargs["api_style"] = preset.get("api_style", "openai")

        if not base_url:
            raise LLMConfigurationError(f"Provider '{name}' requires base_url")
        if not model:
            raise LLMConfigurationError(f"Provider '{name}' requires model")

        config = LLMProviderConfig(
            name=name,
            base_url=base_url.rstrip("/"),
            model=model,
            api_key=api_key,
            priority=priority,
            **kwargs,
        )
        self._providers[name] = config
        # Clear cached advisor
        self._advisors.pop(name, None)
        return config

    def add_from_url(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str = "",
        **kwargs: Any,
    ) -> LLMProviderConfig:
        """Add a provider, auto-detecting the provider type from URL."""
        detected = self._detect_provider(base_url)
        preset_name = detected if detected != "proxy" else ""
        return self.add_provider(
            name,
            base_url=base_url,
            model=model,
            api_key=api_key,
            provider_preset=preset_name,
            **kwargs,
        )

    def add_from_env(self, prefix: str = "CLM_LLM", name: str | None = None) -> LLMProviderConfig | None:
        """Add a provider from environment variables.

        Looks for:
            {prefix}_BASE_URL, {prefix}_MODEL, {prefix}_API_KEY, etc.
        """
        base_url = os.environ.get(f"{prefix}_BASE_URL", "").strip()
        model = os.environ.get(f"{prefix}_MODEL", "").strip()
        api_key = os.environ.get(f"{prefix}_API_KEY", "").strip()
        if not base_url or not model:
            return None
        provider_name = name or os.environ.get(f"{prefix}_PROVIDER", "").strip() or "env"
        return self.add_from_url(provider_name, base_url, model, api_key)

    def get_provider(self, name: str) -> LLMProviderConfig | None:
        """Get a provider config by name."""
        return self._providers.get(name)

    def get_advisor(self, name: str | None = None) -> OpenAICompatibleAdvisor | None:
        """Get an advisor for a specific provider, or the first available."""
        if name:
            config = self._providers.get(name)
            if not config or not config.enabled:
                return None
            return self._get_or_create_advisor(config)

        # Return first enabled provider by priority
        for config in sorted(self._providers.values(), key=lambda c: c.priority):
            if config.enabled:
                return self._get_or_create_advisor(config)
        return None

    def get_advisor_with_fallback(self) -> OpenAICompatibleAdvisor | None:
        """Get an advisor, trying each provider in priority order.

        Tests connection before returning. Falls back to next provider on failure.
        """
        for config in sorted(self._providers.values(), key=lambda c: c.priority):
            if not config.enabled:
                continue
            advisor = self._get_or_create_advisor(config)
            try:
                result = advisor.check_connection()
                if isinstance(result, dict) and result.get("ok"):
                    return advisor
            except (LLMResponseError, Exception):
                # This provider failed, try next
                continue
        return None

    def list_providers(self) -> list[dict[str, Any]]:
        """List all registered providers."""
        return [
            {
                "name": config.name,
                "base_url": config.base_url,
                "model": config.model,
                "api_style": config.api_style,
                "enabled": config.enabled,
                "priority": config.priority,
                "has_api_key": bool(config.api_key),
            }
            for config in sorted(self._providers.values(), key=lambda c: c.priority)
        ]

    def remove_provider(self, name: str) -> bool:
        """Remove a provider from the registry."""
        if name in self._providers:
            del self._providers[name]
            self._advisors.pop(name, None)
            return True
        return False

    def enable_provider(self, name: str) -> bool:
        """Enable a provider."""
        config = self._providers.get(name)
        if config:
            config.enabled = True
            return True
        return False

    def disable_provider(self, name: str) -> bool:
        """Disable a provider."""
        config = self._providers.get(name)
        if config:
            config.enabled = False
            return True
        return False

    def _get_or_create_advisor(self, config: LLMProviderConfig) -> OpenAICompatibleAdvisor:
        """Get or create an advisor for a provider config."""
        if config.name not in self._advisors:
            self._advisors[config.name] = OpenAICompatibleAdvisor(
                config=config.to_openai_config(),
            )
        return self._advisors[config.name]

    @staticmethod
    def _detect_provider(url: str) -> str:
        """Detect provider type from URL."""
        url_lower = url.lower()
        for pattern, provider in URL_PROVIDER_PATTERNS:
            if re.search(pattern, url_lower):
                return provider
        return "openai"  # Default to openai-compatible


# ---------------------------------------------------------------------------
# Convenience: build registry from config file
# ---------------------------------------------------------------------------

def build_registry_from_config(config_path: str) -> LLMProviderRegistry:
    """Build a provider registry from a JSON config file.

    Expected format:
    {
        "llm": {
            "providers": {
                "mimo": {"base_url": "...", "model": "...", "api_key": "..."},
                "deepseek": {"base_url": "...", "model": "...", "api_key": "..."}
            },
            "default_provider": "mimo",
            "fallback_order": ["mimo", "deepseek", "gpt"]
        }
    }
    """
    import json

    registry = LLMProviderRegistry()

    if not os.path.exists(config_path):
        return registry

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    llm_config = data.get("llm") or {}
    providers = llm_config.get("providers") or {}

    # Also support single-provider config (backward compatible)
    if not providers and llm_config.get("base_url"):
        providers = {"default": llm_config}

    for name, prov_config in providers.items():
        if not isinstance(prov_config, dict):
            continue
        base_url = prov_config.get("base_url", "")
        model = prov_config.get("model", "")
        api_key = prov_config.get("api_key", "")
        if base_url and model:
            registry.add_from_url(name, base_url, model, api_key)

    return registry


def build_registry_from_env() -> LLMProviderRegistry:
    """Build a provider registry from environment variables.

    Supports:
        CLM_LLM_BASE_URL, CLM_LLM_MODEL, CLM_LLM_API_KEY (single provider)
        CLM_LLM_PROVIDERS (JSON dict of providers)
    """
    import json

    registry = LLMProviderRegistry()

    # Check for multi-provider env var
    providers_json = os.environ.get("CLM_LLM_PROVIDERS", "").strip()
    if providers_json:
        try:
            providers = json.loads(providers_json)
            for name, config in providers.items():
                if isinstance(config, dict):
                    registry.add_from_url(
                        name,
                        config.get("base_url", ""),
                        config.get("model", ""),
                        config.get("api_key", ""),
                    )
        except (json.JSONDecodeError, TypeError):
            pass

    # Single provider from env
    registry.add_from_env("CLM_LLM", "default")

    return registry
