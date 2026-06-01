"""Tests for multi-provider LLM registry."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from autonomous_crawler.llm.provider_registry import (
    LLMProviderRegistry,
    PROVIDER_PRESETS,
    build_registry_from_config,
    build_registry_from_env,
)


class TestLLMProviderRegistry(unittest.TestCase):
    """Test provider registry core functionality."""

    def test_add_provider_from_preset(self) -> None:
        registry = LLMProviderRegistry()
        config = registry.add_provider("mimo", provider_preset="mimo", api_key="test-key")
        self.assertEqual(config.base_url, "https://token-plan-cn.xiaomimimo.com/v1")
        self.assertEqual(config.model, "mimo-v2.5-pro")
        self.assertEqual(config.api_style, "openai")

    def test_add_provider_explicit(self) -> None:
        registry = LLMProviderRegistry()
        config = registry.add_provider(
            "custom",
            base_url="https://my-proxy.com/v1",
            model="gpt-4o",
            api_key="sk-xxx",
        )
        self.assertEqual(config.base_url, "https://my-proxy.com/v1")
        self.assertEqual(config.model, "gpt-4o")

    def test_add_provider_from_url_auto_detect(self) -> None:
        registry = LLMProviderRegistry()
        config = registry.add_from_url(
            "deepseek",
            "https://api.deepseek.com/v1",
            "deepseek-chat",
            "sk-xxx",
        )
        self.assertEqual(config.api_style, "openai")

    def test_add_provider_from_url_anthropic(self) -> None:
        registry = LLMProviderRegistry()
        config = registry.add_from_url(
            "claude",
            "https://api.anthropic.com/v1",
            "claude-sonnet-4-20250514",
            "sk-ant-xxx",
        )
        self.assertEqual(config.api_style, "anthropic")

    def test_add_provider_from_url_proxy(self) -> None:
        registry = LLMProviderRegistry()
        config = registry.add_from_url(
            "proxy",
            "https://api.pptoken.cc/v1",
            "gpt-4o",
            "sk-xxx",
        )
        self.assertEqual(config.api_style, "openai")

    def test_list_providers(self) -> None:
        registry = LLMProviderRegistry()
        registry.add_provider("a", base_url="https://a.com/v1", model="m1", priority=2)
        registry.add_provider("b", base_url="https://b.com/v1", model="m2", priority=1)
        providers = registry.list_providers()
        self.assertEqual(len(providers), 2)
        # Should be sorted by priority
        self.assertEqual(providers[0]["name"], "b")
        self.assertEqual(providers[1]["name"], "a")

    def test_remove_provider(self) -> None:
        registry = LLMProviderRegistry()
        registry.add_provider("test", base_url="https://test.com/v1", model="m1")
        self.assertTrue(registry.remove_provider("test"))
        self.assertIsNone(registry.get_provider("test"))
        self.assertFalse(registry.remove_provider("nonexistent"))

    def test_enable_disable_provider(self) -> None:
        registry = LLMProviderRegistry()
        registry.add_provider("test", base_url="https://test.com/v1", model="m1")
        registry.disable_provider("test")
        config = registry.get_provider("test")
        self.assertFalse(config.enabled)
        registry.enable_provider("test")
        self.assertTrue(config.enabled)

    def test_get_advisor_returns_first_enabled(self) -> None:
        registry = LLMProviderRegistry()
        registry.add_provider("a", base_url="https://a.com/v1", model="m1", priority=2)
        registry.add_provider("b", base_url="https://b.com/v1", model="m2", priority=1)
        advisor = registry.get_advisor()
        self.assertIsNotNone(advisor)
        self.assertEqual(advisor.model, "m2")  # Lower priority number = higher priority

    def test_get_advisor_by_name(self) -> None:
        registry = LLMProviderRegistry()
        registry.add_provider("a", base_url="https://a.com/v1", model="m1")
        registry.add_provider("b", base_url="https://b.com/v1", model="m2")
        advisor = registry.get_advisor("b")
        self.assertIsNotNone(advisor)
        self.assertEqual(advisor.model, "m2")

    def test_get_advisor_disabled_returns_none(self) -> None:
        registry = LLMProviderRegistry()
        registry.add_provider("test", base_url="https://test.com/v1", model="m1")
        registry.disable_provider("test")
        self.assertIsNone(registry.get_advisor("test"))

    def test_get_advisor_no_providers_returns_none(self) -> None:
        registry = LLMProviderRegistry()
        self.assertIsNone(registry.get_advisor())

    def test_add_provider_missing_base_url_raises(self) -> None:
        registry = LLMProviderRegistry()
        with self.assertRaises(Exception):
            registry.add_provider("test", model="m1")

    def test_add_provider_missing_model_raises(self) -> None:
        registry = LLMProviderRegistry()
        with self.assertRaises(Exception):
            registry.add_provider("test", base_url="https://test.com/v1")

    def test_all_presets_have_required_fields(self) -> None:
        for name, preset in PROVIDER_PRESETS.items():
            self.assertIn("base_url", preset, f"Preset '{name}' missing base_url")
            self.assertIn("default_model", preset, f"Preset '{name}' missing default_model")
            self.assertIn("api_style", preset, f"Preset '{name}' missing api_style")


class TestBuildRegistryFromConfig(unittest.TestCase):
    """Test building registry from config file."""

    def test_multi_provider_config(self) -> None:
        config = {
            "llm": {
                "providers": {
                    "mimo": {
                        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
                        "model": "mimo-v2.5-pro",
                        "api_key": "key1",
                    },
                    "deepseek": {
                        "base_url": "https://api.deepseek.com/v1",
                        "model": "deepseek-chat",
                        "api_key": "key2",
                    },
                },
            }
        }
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            registry = build_registry_from_config(f.name)
        os.unlink(f.name)

        self.assertEqual(len(registry.list_providers()), 2)
        self.assertIsNotNone(registry.get_provider("mimo"))
        self.assertIsNotNone(registry.get_provider("deepseek"))

    def test_single_provider_config_backward_compat(self) -> None:
        config = {
            "llm": {
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "api_key": "key",
            }
        }
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            registry = build_registry_from_config(f.name)
        os.unlink(f.name)

        self.assertEqual(len(registry.list_providers()), 1)
        self.assertIsNotNone(registry.get_provider("default"))

    def test_missing_file_returns_empty(self) -> None:
        registry = build_registry_from_config("/nonexistent/path.json")
        self.assertEqual(len(registry.list_providers()), 0)


class TestBuildRegistryFromEnv(unittest.TestCase):
    """Test building registry from environment variables."""

    @patch.dict(os.environ, {
        "CLM_LLM_BASE_URL": "https://api.deepseek.com/v1",
        "CLM_LLM_MODEL": "deepseek-chat",
        "CLM_LLM_API_KEY": "test-key",
    })
    def test_single_provider_from_env(self) -> None:
        registry = build_registry_from_env()
        self.assertEqual(len(registry.list_providers()), 1)
        provider = registry.get_provider("default")
        self.assertIsNotNone(provider)
        self.assertEqual(provider.base_url, "https://api.deepseek.com/v1")

    @patch.dict(os.environ, {
        "CLM_LLM_PROVIDERS": json.dumps({
            "mimo": {"base_url": "https://token-plan-cn.xiaomimimo.com/v1", "model": "mimo-v2.5-pro"},
            "deepseek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
        }),
    })
    def test_multi_provider_from_env(self) -> None:
        registry = build_registry_from_env()
        self.assertEqual(len(registry.list_providers()), 2)


if __name__ == "__main__":
    unittest.main()
