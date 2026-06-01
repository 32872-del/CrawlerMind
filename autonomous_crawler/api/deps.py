"""Shared dependencies for the API layer.

Provides the singleton job registry, LLM advisor factory, managed-AI
configuration helpers, and general-purpose utilities used across routers.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..llm.openai_compatible import (
    LLMConfigurationError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
)
from ..storage.batch_registry import BatchRegistry

from .schemas import LLMConfig, ManagedAIConfig


# ---------------------------------------------------------------------------
# Singleton job registry
# ---------------------------------------------------------------------------

_registry = BatchRegistry()


def get_registry() -> BatchRegistry:
    return _registry


# ---------------------------------------------------------------------------
# Job management helpers
# ---------------------------------------------------------------------------


def _max_active_jobs() -> int:
    raw = os.environ.get("CLM_MAX_ACTIVE_JOBS", "4")
    try:
        val = int(raw)
        return val if val > 0 else 4
    except ValueError:
        return 4


def _job_retention_seconds() -> int:
    raw = os.environ.get("CLM_JOB_RETENTION_SECONDS", "3600")
    try:
        val = int(raw)
        return val if val > 0 else 3600
    except ValueError:
        return 3600


def cleanup_stale_jobs() -> int:
    return _registry.cleanup_stale(retention_seconds=_job_retention_seconds())


def register_job(task_id: str, user_goal: str, target_url: str, kind: str = "crawl") -> None:
    _registry.register(task_id, kind=kind, job_data={
        "user_goal": user_goal,
        "target_url": target_url,
        "item_count": 0,
        "is_valid": False,
        "error": "",
        "error_code": None,
    })


def try_register_job(task_id: str, user_goal: str, target_url: str, kind: str = "crawl") -> bool:
    return _registry.try_register(
        task_id,
        kind=kind,
        job_data={
            "user_goal": user_goal,
            "target_url": target_url,
            "item_count": 0,
            "is_valid": False,
            "error": "",
            "error_code": None,
        },
        max_active=_max_active_jobs(),
    )


def update_job(task_id: str, **kwargs: Any) -> None:
    _registry.update(task_id, **kwargs)
    status = kwargs.get("status")
    if status:
        _registry.mark_status(task_id, status)


def get_job(task_id: str) -> dict[str, Any] | None:
    return _registry.get(task_id)


def remove_job(task_id: str) -> None:
    _registry.remove(task_id)


def is_cancelled(task_id: str) -> bool:
    job = get_job(task_id)
    return bool(job and job.get("status") == "cancelled")


def count_active_jobs() -> int:
    return _registry.count_active()


def clear_jobs() -> None:
    """Remove all jobs. For test teardown only."""
    with _registry.connection() as conn:
        conn.execute("DELETE FROM batch_jobs")


# ---------------------------------------------------------------------------
# LLM advisor factory
# ---------------------------------------------------------------------------


def build_advisor_from_config(config: LLMConfig) -> OpenAICompatibleAdvisor:
    if not config.base_url.strip():
        raise LLMConfigurationError("llm.base_url is required when llm.enabled is true")
    if not config.model.strip():
        raise LLMConfigurationError("llm.model is required when llm.enabled is true")
    llm_config = OpenAICompatibleConfig(
        base_url=config.base_url.strip(),
        model=config.model.strip(),
        api_key=config.api_key.strip(),
        provider=config.provider.strip() or "openai-compatible",
        timeout_seconds=config.timeout_seconds,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        use_response_format=config.use_response_format,
        reasoning_effort=safe_choice(config.reasoning_effort, {"low", "medium", "high", "xhigh"}, "medium"),
        stream=bool(config.stream),
    )
    return OpenAICompatibleAdvisor(llm_config)


# ---------------------------------------------------------------------------
# Managed-AI configuration helpers
# ---------------------------------------------------------------------------


def managed_ai_enabled(config: ManagedAIConfig | None, llm: LLMConfig | None) -> bool:
    return bool(config and config.enabled and llm and llm.enabled)


def managed_ai_mode(config: ManagedAIConfig | None) -> str:
    mode = str(getattr(config, "mode", "") or "").strip().lower()
    if mode in {"analysis_only", "supervised", "full_managed"}:
        return mode
    return "analysis_only"


def managed_ai_wants_pre_run(config: ManagedAIConfig | None) -> bool:
    if not config or not config.enabled:
        return False
    mode = managed_ai_mode(config)
    return bool(config.pre_run_review or mode in {"supervised", "full_managed"})


def managed_ai_wants_post_run(config: ManagedAIConfig | None) -> bool:
    if not config or not config.enabled:
        return False
    mode = managed_ai_mode(config)
    return bool(config.post_run_diagnosis or mode in {"supervised", "full_managed"})


def managed_ai_wants_auto_repair(config: ManagedAIConfig | None) -> bool:
    if not config or not config.enabled:
        return False
    return bool(config.auto_repair or managed_ai_mode(config) == "full_managed")


def supervision_mode_for_managed_ai(config: ManagedAIConfig | None) -> str:
    if not config or not config.enabled:
        return "off"
    mode = managed_ai_mode(config)
    if mode == "full_managed":
        return "managed"
    if mode == "supervised":
        return "observe"
    return "off"


def managed_ai_public_config(config: ManagedAIConfig | None, llm: LLMConfig | None) -> dict[str, Any]:
    return {
        "enabled": managed_ai_enabled(config, llm),
        "mode": managed_ai_mode(config),
        "pre_run_review": managed_ai_wants_pre_run(config),
        "post_run_diagnosis": managed_ai_wants_post_run(config),
        "apply_pre_run_patch": bool(config and config.enabled and config.apply_pre_run_patch),
        "auto_repair": managed_ai_wants_auto_repair(config),
        "model": llm.model if llm and llm.enabled else "",
        "provider": llm.provider if llm and llm.enabled else "",
    }


# ---------------------------------------------------------------------------
# AI decision / trace helpers
# ---------------------------------------------------------------------------


def append_ai_decision(task_id: str, decision: dict[str, Any]) -> None:
    job = get_job(task_id) or {}
    decisions = list(job.get("ai_decisions") or [])
    decisions.append(decision)
    update_job(task_id, ai_decisions=decisions)


def append_llm_trace(task_id: str, trace: dict[str, Any]) -> None:
    job = get_job(task_id) or {}
    traces = list(job.get("llm_traces") or [])
    traces.append(trace)
    update_job(task_id, llm_traces=traces[-100:])


def normalize_ai_decision(stage: str, advisor: OpenAICompatibleAdvisor, raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "stage": stage,
        "enabled": True,
        "fallback_used": False,
        "provider": getattr(advisor, "provider", "unknown"),
        "model": getattr(advisor, "model", "unknown"),
        "approved": bool(data.get("approved", True)),
        "risk_level": safe_choice(data.get("risk_level"), {"low", "medium", "high"}, "medium"),
        "status_assessment": safe_choice(data.get("status_assessment"), {"good", "needs_attention", "failed"}, ""),
        "reasoning_summary": str(data.get("reasoning_summary") or "")[:1000],
        "warnings": string_list(data.get("warnings"), 20),
        "recommended_actions": string_list(data.get("recommended_actions"), 20),
        "likely_causes": string_list(data.get("likely_causes"), 20),
        "repair_suggestions": repair_suggestions_list(data.get("repair_suggestions")),
        "profile_patch": bounded_dict(data.get("profile_patch"), 8000),
        "next_run_overrides": bounded_dict(data.get("next_run_overrides"), 8000),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def ai_error_decision(stage: str, exc: Exception) -> dict[str, Any]:
    return {
        "stage": stage,
        "enabled": True,
        "fallback_used": True,
        "error": str(exc),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def ai_diagnostics_from_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "ai-run-diagnostics/v1",
        "status_assessment": decision.get("status_assessment") or "needs_attention",
        "reasoning_summary": decision.get("reasoning_summary", ""),
        "likely_causes": list(decision.get("likely_causes") or []),
        "repair_suggestions": list(decision.get("repair_suggestions") or []),
        "next_run_overrides": decision.get("next_run_overrides") or {},
        "created_at": decision.get("created_at", ""),
    }


def llm_trace_record(
    *,
    stage: str,
    advisor: OpenAICompatibleAdvisor | None,
    started_at: float,
    status: str,
    input_payload: Any = None,
    output_payload: Any = None,
    error: str = "",
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "provider": getattr(advisor, "provider", "unknown") if advisor else "unknown",
        "model": getattr(advisor, "model", "unknown") if advisor else "unknown",
        "duration_ms": int((time.perf_counter() - started_at) * 1000),
        "input_summary": payload_summary(input_payload),
        "output_summary": payload_summary(output_payload),
        "error": str(error)[:1000],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# General utilities
# ---------------------------------------------------------------------------


def json_dumps_safe(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def json_loads_text(text: str) -> Any:
    return json.loads(text)


def payload_summary(payload: Any, *, max_chars: int = 1600) -> dict[str, Any]:
    if isinstance(payload, dict):
        keys = sorted(str(key) for key in payload.keys())[:40]
        preview_source = payload
    else:
        keys = []
        preview_source = payload
    try:
        raw = json_dumps_safe(preview_source)
    except Exception:
        raw = str(preview_source)
    return {
        "keys": keys,
        "preview": raw[:max_chars],
        "truncated": len(raw) > max_chars,
    }


def safe_choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:500] for item in value[:limit] if str(item).strip()]


def repair_suggestions_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    output: list[dict[str, Any]] = []
    for item in value[:20]:
        if isinstance(item, dict):
            output.append({
                "action": str(item.get("action") or "")[:300],
                "priority": safe_choice(item.get("priority"), {"low", "medium", "high"}, "medium"),
                "rationale": str(item.get("rationale") or "")[:800],
            })
        elif str(item).strip():
            output.append({"action": str(item)[:300], "priority": "medium", "rationale": ""})
    return output


def bounded_dict(value: Any, max_chars: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) > max_chars:
        return {"_truncated_json": text[:max_chars]}
    return value


def deep_merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def load_json_file(path: str) -> Any:
    file_path = Path(path)
    return json_loads_text(file_path.read_text(encoding="utf-8-sig", errors="replace"))


def safe_url(value: str) -> bool:
    from urllib.parse import urlparse
    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
