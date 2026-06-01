"""Optional LLM advisor interfaces for Planner and Strategy nodes."""
from .protocols import PlanningAdvisor, StrategyAdvisor
from .audit import (
    build_decision_record,
    redact_preview,
    MAX_PREVIEW_LENGTH,
)
from .openai_compatible import (
    LLMConfigurationError,
    LLMResponseError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
    build_advisor_from_env,
    parse_json_object,
)
from .provider_registry import (
    LLMProviderConfig,
    LLMProviderRegistry,
    PROVIDER_PRESETS,
    build_registry_from_config,
    build_registry_from_env,
)

__all__ = [
    "PlanningAdvisor",
    "StrategyAdvisor",
    "build_decision_record",
    "redact_preview",
    "MAX_PREVIEW_LENGTH",
    "LLMConfigurationError",
    "LLMResponseError",
    "OpenAICompatibleAdvisor",
    "OpenAICompatibleConfig",
    "build_advisor_from_env",
    "parse_json_object",
    "LLMProviderConfig",
    "LLMProviderRegistry",
    "PROVIDER_PRESETS",
    "build_registry_from_config",
    "build_registry_from_env",
]
