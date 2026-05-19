"""FastAPI service boundary for the autonomous crawler MVP."""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..runners import ProfileLongRunConfig, SiteProfile, run_multi_profile_longrun, run_profile_longrun
from ..runners.product_workflow import (
    CrawlRunSpec,
    ExportSpec,
    ExportTemplate,
    analyze_site_for_product_workflow,
    build_full_run_payload,
    build_run_spec,
    build_test_run_payload,
    events_for_job,
    export_product_records,
    import_catalog_tree,
    resolve_fields,
    summarize_run_progress,
)
from ..runtime import NativeBrowserRuntime, NativeFetchRuntime
from ..storage.batch_registry import BatchRegistry
from ..llm.openai_compatible import (
    LLMConfigurationError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
)
from ..llm.model_list import check_provider_health, fetch_model_list
from ..storage import list_crawl_results, load_crawl_result, save_crawl_result
from ..tools.anti_bot_report import summarize_anti_bot_report
from ..workflows.crawl_graph import compile_crawl_graph


class LLMConfig(BaseModel):
    enabled: bool = False
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    provider: str = "openai-compatible"
    timeout_seconds: float = Field(default=30.0, gt=0)
    temperature: float = Field(default=0.0, ge=0)
    max_tokens: int = Field(default=800, gt=0)
    use_response_format: bool = True


class ManagedAIConfig(BaseModel):
    enabled: bool = False
    mode: str = "analysis_only"
    pre_run_review: bool = False
    post_run_diagnosis: bool = False
    apply_pre_run_patch: bool = False


class CrawlRequest(BaseModel):
    user_goal: str = Field(..., min_length=1)
    target_url: str = Field(..., min_length=1)
    max_retries: int = Field(default=3, ge=0, le=10)
    llm: LLMConfig | None = None


class CrawlResponse(BaseModel):
    task_id: str
    status: str
    item_count: int
    is_valid: bool
    error_code: str | None = None
    anti_bot_summary: dict[str, Any] | None = None


class ProfileRunRequest(BaseModel):
    profile: dict[str, Any] | None = None
    profile_path: str = ""
    run_id: str = ""
    batch_size: int = Field(default=20, ge=1, le=200)
    max_batches: int = Field(default=0, ge=0)
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    item_workers: int = Field(default=1, ge=1, le=128)
    category: str = ""
    output_report_path: str = ""
    runtime_dir: str = ""
    supervision_mode: str = "off"
    managed_ai: ManagedAIConfig | None = None
    llm: LLMConfig | None = None


class ProfileRunResponse(BaseModel):
    task_id: str
    run_id: str
    status: str
    profile_name: str
    record_count: int = 0
    accepted: bool = False


class MultiProfileRunRequest(BaseModel):
    jobs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    max_sites: int = Field(default=5, ge=1, le=5)
    default_item_workers: int = Field(default=1, ge=1, le=128)
    output_report_path: str = ""


class MultiProfileRunResponse(BaseModel):
    task_id: str
    status: str
    total_sites: int = 0
    ok_sites: int = 0
    failed_sites: int = 0


class CatalogImportRequest(BaseModel):
    catalog: Any | None = None
    catalog_path: str = ""


class SiteAnalyzeRequest(BaseModel):
    target_url: str = Field(..., min_length=1)
    imported_catalog: Any | None = None
    imported_catalog_path: str = ""
    field_goal: str = ""
    llm: LLMConfig | None = None


class FieldResolveRequest(BaseModel):
    available_fields: list[dict[str, Any]] = Field(default_factory=list)
    natural_language: str = ""
    requested_fields: list[str] = Field(default_factory=list)


class ProductRunRequest(BaseModel):
    target_url: str = Field(..., min_length=1)
    profile: dict[str, Any] = Field(default_factory=dict)
    catalog_nodes: list[dict[str, Any]] = Field(default_factory=list)
    selected_fields: list[str] = Field(default_factory=list)
    export: dict[str, Any] = Field(default_factory=dict)
    run_mode: str = "direct"
    item_workers: int = Field(default=4, ge=1, le=128)
    max_sites: int = Field(default=1, ge=1, le=5)
    test_limit: int = Field(default=100, ge=1, le=10000)
    runtime_dir: str = ""
    managed_ai: ManagedAIConfig | None = None
    llm: LLMConfig | None = None


class ExportRequest(BaseModel):
    run_id: str = Field(..., min_length=1)
    runtime_dir: str = ""
    format: str = "xlsx"
    output_path: str = ""
    template_path: str = ""
    field_mapping: dict[str, str] = Field(default_factory=dict)
    template: dict[str, Any] | None = None


class AIRerunRequest(BaseModel):
    run_kind: str = "test"
    apply_diagnostics: bool = True
    extra_overrides: dict[str, Any] = Field(default_factory=dict)
    managed_ai: ManagedAIConfig | None = None
    llm: LLMConfig | None = None


# ---------------------------------------------------------------------------
# Durable job registry (SQLite-backed, survives restarts)
# ---------------------------------------------------------------------------

_registry = BatchRegistry()


def _clear_jobs() -> None:
    """Remove all jobs from the registry. For test teardown only."""
    with _registry.connection() as conn:
        conn.execute("DELETE FROM batch_jobs")


def _register_job(task_id: str, user_goal: str, target_url: str, kind: str = "crawl") -> None:
    _registry.register(task_id, kind=kind, job_data={
        "user_goal": user_goal,
        "target_url": target_url,
        "item_count": 0,
        "is_valid": False,
        "error": "",
        "error_code": None,
    })


def _try_register_job(task_id: str, user_goal: str, target_url: str, kind: str = "crawl") -> bool:
    """Register a running job if the active-job limit has not been reached."""
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


def _update_job(task_id: str, **kwargs: Any) -> None:
    _registry.update(task_id, **kwargs)
    status = kwargs.get("status")
    if status:
        _registry.mark_status(task_id, status)


def _get_job(task_id: str) -> dict[str, Any] | None:
    return _registry.get(task_id)


def _remove_job(task_id: str) -> None:
    _registry.remove(task_id)


def _is_cancelled(task_id: str) -> bool:
    job = _get_job(task_id)
    return bool(job and job.get("status") == "cancelled")


def _max_active_jobs() -> int:
    """Return the maximum number of concurrent active jobs."""
    raw = os.environ.get("CLM_MAX_ACTIVE_JOBS", "4")
    try:
        val = int(raw)
        return val if val > 0 else 4
    except ValueError:
        return 4


def _count_active_jobs() -> int:
    """Count jobs that are still actively running."""
    return _registry.count_active()


def _job_retention_seconds() -> int:
    """Return how long completed/failed jobs stay in the registry."""
    raw = os.environ.get("CLM_JOB_RETENTION_SECONDS", "3600")
    try:
        val = int(raw)
        return val if val > 0 else 3600
    except ValueError:
        return 3600


def _cleanup_stale_jobs() -> int:
    """Remove completed/failed jobs older than the retention TTL."""
    return _registry.cleanup_stale(retention_seconds=_job_retention_seconds())


def _build_advisor_from_config(config: LLMConfig) -> OpenAICompatibleAdvisor:
    """Build an advisor from request-level LLM config.

    Raises LLMConfigurationError if required fields are missing.
    """
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
    )
    return OpenAICompatibleAdvisor(llm_config)


def _managed_ai_enabled(config: ManagedAIConfig | None, llm: LLMConfig | None) -> bool:
    return bool(config and config.enabled and llm and llm.enabled)


def _managed_ai_mode(config: ManagedAIConfig | None) -> str:
    mode = str(getattr(config, "mode", "") or "").strip().lower()
    if mode in {"analysis_only", "supervised", "full_managed"}:
        return mode
    return "analysis_only"


def _managed_ai_wants_pre_run(config: ManagedAIConfig | None) -> bool:
    if not config or not config.enabled:
        return False
    mode = _managed_ai_mode(config)
    return bool(config.pre_run_review or mode in {"supervised", "full_managed"})


def _managed_ai_wants_post_run(config: ManagedAIConfig | None) -> bool:
    if not config or not config.enabled:
        return False
    mode = _managed_ai_mode(config)
    return bool(config.post_run_diagnosis or mode in {"supervised", "full_managed"})


def _managed_ai_public_config(config: ManagedAIConfig | None, llm: LLMConfig | None) -> dict[str, Any]:
    return {
        "enabled": _managed_ai_enabled(config, llm),
        "mode": _managed_ai_mode(config),
        "pre_run_review": _managed_ai_wants_pre_run(config),
        "post_run_diagnosis": _managed_ai_wants_post_run(config),
        "apply_pre_run_patch": bool(config and config.enabled and config.apply_pre_run_patch),
        "model": llm.model if llm and llm.enabled else "",
        "provider": llm.provider if llm and llm.enabled else "",
    }


def _supervision_mode_for_managed_ai(config: ManagedAIConfig | None) -> str:
    if not config or not config.enabled:
        return "off"
    mode = _managed_ai_mode(config)
    if mode == "full_managed":
        return "managed"
    if mode == "supervised":
        return "observe"
    return "off"


def _append_ai_decision(task_id: str, decision: dict[str, Any]) -> None:
    job = _get_job(task_id) or {}
    decisions = list(job.get("ai_decisions") or [])
    decisions.append(decision)
    _update_job(task_id, ai_decisions=decisions)


def _ai_error_decision(stage: str, exc: Exception) -> dict[str, Any]:
    return {
        "stage": stage,
        "enabled": True,
        "fallback_used": True,
        "error": str(exc),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _run_managed_pre_review(
    *,
    task_id: str,
    advisor: OpenAICompatibleAdvisor,
    spec: CrawlRunSpec,
    profile: SiteProfile,
) -> dict[str, Any]:
    try:
        raw = advisor.review_run_plan(_product_spec_summary(spec), profile.to_dict())
        decision = _normalize_ai_decision("pre_run_review", advisor, raw)
    except Exception as exc:
        decision = _ai_error_decision("pre_run_review", exc)
    _append_ai_decision(task_id, decision)
    return decision


def _run_managed_post_diagnosis(
    *,
    task_id: str,
    advisor: OpenAICompatibleAdvisor,
    request: ProfileRunRequest,
    result: dict[str, Any],
) -> None:
    job = _get_job(task_id) or {}
    spec_payload = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    profile_payload = request.profile or {}
    progress = summarize_run_progress({**job, "profile_run": result})
    try:
        raw = advisor.diagnose_run_result(spec_payload, profile_payload, result, progress)
        decision = _normalize_ai_decision("post_run_diagnosis", advisor, raw)
    except Exception as exc:
        decision = _ai_error_decision("post_run_diagnosis", exc)
    diagnostics = _ai_diagnostics_from_decision(decision)
    _append_ai_decision(task_id, decision)
    _update_job(
        task_id,
        ai_diagnostics=diagnostics,
        ai_repair_suggestions=list(diagnostics.get("repair_suggestions") or []),
    )


def _normalize_ai_decision(stage: str, advisor: OpenAICompatibleAdvisor, raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "stage": stage,
        "enabled": True,
        "fallback_used": False,
        "provider": getattr(advisor, "provider", "unknown"),
        "model": getattr(advisor, "model", "unknown"),
        "approved": bool(data.get("approved", True)),
        "risk_level": _safe_choice(data.get("risk_level"), {"low", "medium", "high"}, "medium"),
        "status_assessment": _safe_choice(data.get("status_assessment"), {"good", "needs_attention", "failed"}, ""),
        "reasoning_summary": str(data.get("reasoning_summary") or "")[:1000],
        "warnings": _string_list(data.get("warnings"), 20),
        "recommended_actions": _string_list(data.get("recommended_actions"), 20),
        "likely_causes": _string_list(data.get("likely_causes"), 20),
        "repair_suggestions": _repair_suggestions(data.get("repair_suggestions")),
        "profile_patch": _bounded_dict(data.get("profile_patch"), 8000),
        "next_run_overrides": _bounded_dict(data.get("next_run_overrides"), 8000),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _ai_diagnostics_from_decision(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "ai-run-diagnostics/v1",
        "status_assessment": decision.get("status_assessment") or "needs_attention",
        "reasoning_summary": decision.get("reasoning_summary", ""),
        "likely_causes": list(decision.get("likely_causes") or []),
        "repair_suggestions": list(decision.get("repair_suggestions") or []),
        "next_run_overrides": decision.get("next_run_overrides") or {},
        "created_at": decision.get("created_at", ""),
    }


def _supervision_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    supervision = diagnostics.get("supervision") if isinstance(diagnostics.get("supervision"), dict) else {}
    if supervision:
        return supervision
    runner = result.get("runner_summary") if isinstance(result.get("runner_summary"), dict) else {}
    events = runner.get("supervision_events") if isinstance(runner.get("supervision_events"), list) else []
    if not events:
        return None
    return {
        "enabled": True,
        "event_count": len(events),
        "last_event": events[-1],
    }


def _repair_overrides_from_supervision(supervision: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(supervision, dict):
        return {}
    last = supervision.get("last_event") if isinstance(supervision.get("last_event"), dict) else {}
    action = str(last.get("action") or "").strip().lower()
    reason = str(last.get("reason") or "").lower()
    suggestions = last.get("suggestions") if isinstance(last.get("suggestions"), list) else []
    suggestion_actions = {
        str(item.get("action") or "").strip().lower()
        for item in suggestions
        if isinstance(item, dict)
    }
    overrides: dict[str, Any] = {}
    if action in {"pause", "abort", "repair_after_run"}:
        overrides.setdefault("access_config", {})
        overrides["access_config"].update({
            "mode": "dynamic",
            "wait_until": "networkidle",
            "browser_config": {
                "capture_api": True,
                "auto_accept_cookies": True,
                "render_time_ms": 3000,
                "max_wait_ms": 30000,
            },
        })
        overrides.setdefault("pagination_hints", {})
        overrides["pagination_hints"].setdefault("type", "dom_links")
    if action == "slow_down" or "reduce_concurrency_or_rotate_proxy" in suggestion_actions:
        overrides["item_workers"] = 1
        overrides.setdefault("access_config", {})
        overrides["access_config"].setdefault("browser_config", {})
        overrides["access_config"]["browser_config"]["max_wait_ms"] = 45000
    if "empty" in reason or "no records" in reason or "switch_runtime_or_repair_selectors" in suggestion_actions:
        overrides.setdefault("quality_expectations", {})
        overrides["quality_expectations"]["required_fields"] = ["title"]
        overrides.setdefault("selectors", {})
        overrides["selectors"].setdefault("title", "h1, [class*='title'], [class*='name']")
    return overrides


def _apply_managed_profile_patch(
    profile_data: dict[str, Any],
    patch: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a bounded allowlisted LLM profile patch.

    The managed AI can adjust the "kitchen knobs" that already exist in CLM:
    seeds, runtime mode, waits, pagination, selectors, and quality thresholds.
    It cannot introduce arbitrary code, credentials, imports, or new engines.
    """
    if not isinstance(patch, dict) or not patch:
        return profile_data, {"applied": False, "accepted": [], "rejected": ["empty_patch"]}
    updated = dict(profile_data or {})
    accepted: list[str] = []
    rejected: list[str] = []

    prefs_patch = patch.get("crawl_preferences") if isinstance(patch.get("crawl_preferences"), dict) else {}
    if prefs_patch:
        prefs = dict(updated.get("crawl_preferences") or {})
        if isinstance(prefs_patch.get("seed_urls"), list):
            urls = [
                str(url).strip()
                for url in prefs_patch.get("seed_urls")[:500]
                if _safe_url_for_profile_patch(str(url))
            ]
            if urls:
                prefs["seed_urls"] = urls
                accepted.append("crawl_preferences.seed_urls")
            else:
                rejected.append("crawl_preferences.seed_urls")
        if str(prefs_patch.get("seed_kind") or "").strip():
            seed_kind = _safe_choice(prefs_patch.get("seed_kind"), {"entry", "list", "detail", "api", "catalog"}, "")
            if seed_kind:
                prefs["seed_kind"] = seed_kind
                accepted.append("crawl_preferences.seed_kind")
            else:
                rejected.append("crawl_preferences.seed_kind")
        if prefs_patch.get("max_items") is not None:
            try:
                prefs["max_items"] = max(1, min(int(prefs_patch.get("max_items")), 1_000_000))
                accepted.append("crawl_preferences.max_items")
            except (TypeError, ValueError):
                rejected.append("crawl_preferences.max_items")
        updated["crawl_preferences"] = prefs

    access_patch = patch.get("access_config") if isinstance(patch.get("access_config"), dict) else {}
    if access_patch:
        access = dict(updated.get("access_config") or {})
        mode_key = "mode" if "mode" in access_patch else "runtime_mode" if "runtime_mode" in access_patch else ""
        mode = _safe_choice(access_patch.get("mode") or access_patch.get("runtime_mode"), {"static", "dynamic", "protected"}, "")
        if mode:
            access["mode"] = mode
            accepted.append("access_config.mode")
        elif mode_key:
            rejected.append("access_config.mode")
        wait_until = _safe_choice(access_patch.get("wait_until"), {"domcontentloaded", "load", "networkidle"}, "")
        if wait_until:
            access["wait_until"] = wait_until
            accepted.append("access_config.wait_until")
        elif "wait_until" in access_patch:
            rejected.append("access_config.wait_until")
        browser_patch = access_patch.get("browser_config") if isinstance(access_patch.get("browser_config"), dict) else {}
        if browser_patch:
            browser = dict(access.get("browser_config") or {})
            for key in ("render_time_ms", "max_wait_ms"):
                if key in browser_patch:
                    try:
                        browser[key] = max(0, min(int(browser_patch[key]), 120_000))
                        accepted.append(f"access_config.browser_config.{key}")
                    except (TypeError, ValueError):
                        rejected.append(f"access_config.browser_config.{key}")
            for key in ("capture_api", "auto_accept_cookies"):
                if key in browser_patch:
                    browser[key] = bool(browser_patch[key])
                    accepted.append(f"access_config.browser_config.{key}")
            access["browser_config"] = browser
        updated["access_config"] = access

    selectors_patch = patch.get("selectors") if isinstance(patch.get("selectors"), dict) else {}
    if selectors_patch:
        selectors = dict(updated.get("selectors") or {})
        for key, value in selectors_patch.items():
            selector = _safe_css_selector(value)
            if selector:
                selectors[str(key)[:80]] = selector
                accepted.append(f"selectors.{str(key)[:80]}")
            else:
                rejected.append(f"selectors.{str(key)[:80]}")
        updated["selectors"] = selectors

    pagination_patch = patch.get("pagination_hints") if isinstance(patch.get("pagination_hints"), dict) else {}
    if pagination_patch:
        pagination = dict(updated.get("pagination_hints") or {})
        page_type = _safe_choice(pagination_patch.get("type"), {"none", "dom_links", "page", "offset", "cursor", "api"}, "")
        if page_type:
            pagination["type"] = page_type
            accepted.append("pagination_hints.type")
        for key in ("page_param", "offset_param", "limit_param", "cursor_param", "next_selector"):
            if key in pagination_patch:
                text = str(pagination_patch.get(key) or "").strip()
                if 0 < len(text) <= 120 and "\x00" not in text:
                    pagination[key] = text
                    accepted.append(f"pagination_hints.{key}")
                else:
                    rejected.append(f"pagination_hints.{key}")
        for key in ("start_page", "page_size", "max_pages"):
            if key in pagination_patch:
                try:
                    pagination[key] = max(1, min(int(pagination_patch[key]), 10_000))
                    accepted.append(f"pagination_hints.{key}")
                except (TypeError, ValueError):
                    rejected.append(f"pagination_hints.{key}")
        updated["pagination_hints"] = pagination

    quality_patch = patch.get("quality_expectations") if isinstance(patch.get("quality_expectations"), dict) else {}
    if quality_patch:
        quality = dict(updated.get("quality_expectations") or {})
        if isinstance(quality_patch.get("required_fields"), list):
            fields = [str(item).strip() for item in quality_patch.get("required_fields")[:50] if str(item).strip()]
            if fields:
                quality["required_fields"] = fields
                accepted.append("quality_expectations.required_fields")
        if isinstance(quality_patch.get("field_thresholds"), dict):
            thresholds: dict[str, float] = {}
            for key, value in quality_patch.get("field_thresholds").items():
                try:
                    thresholds[str(key)[:80]] = max(0.0, min(float(value), 1.0))
                except (TypeError, ValueError):
                    rejected.append(f"quality_expectations.field_thresholds.{str(key)[:80]}")
            if thresholds:
                quality["field_thresholds"] = thresholds
                accepted.append("quality_expectations.field_thresholds")
        updated["quality_expectations"] = quality

    return updated, {
        "applied": bool(accepted),
        "accepted": accepted,
        "rejected": rejected,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _apply_managed_run_overrides(
    spec_data: dict[str, Any],
    profile_data: dict[str, Any],
    overrides: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Apply bounded AI run overrides to a new rerun payload.

    This turns post-run diagnosis into an executable next attempt. Profile-level
    changes reuse the same allowlist as pre-run review. Run-level changes are
    limited to operational knobs the frontend already exposes.
    """
    spec_out = dict(spec_data or {})
    profile_out = dict(profile_data or {})
    accepted: list[str] = []
    rejected: list[str] = []

    if not isinstance(overrides, dict) or not overrides:
        return spec_out, profile_out, {
            "applied": False,
            "accepted": [],
            "rejected": ["empty_overrides"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    profile_patch: dict[str, Any] = {}
    for key in ("crawl_preferences", "access_config", "selectors", "pagination_hints", "quality_expectations"):
        value = overrides.get(key)
        if isinstance(value, dict):
            profile_patch[key] = value
    if profile_patch:
        profile_out, profile_result = _apply_managed_profile_patch(profile_out, profile_patch)
        accepted.extend(f"profile.{item}" for item in profile_result.get("accepted", []))
        rejected.extend(f"profile.{item}" for item in profile_result.get("rejected", []))

    for key in ("item_workers", "test_limit"):
        if key not in overrides:
            continue
        try:
            upper = 128 if key == "item_workers" else 10000
            spec_out[key] = max(1, min(int(overrides[key]), upper))
            accepted.append(key)
        except (TypeError, ValueError):
            rejected.append(key)

    if "runtime_dir" in overrides:
        runtime_dir = str(overrides.get("runtime_dir") or "").strip()
        if runtime_dir and len(runtime_dir) <= 300 and "\x00" not in runtime_dir:
            spec_out["runtime_dir"] = runtime_dir
            accepted.append("runtime_dir")
        else:
            rejected.append("runtime_dir")

    if "run_mode" in overrides:
        run_mode = _safe_choice(overrides.get("run_mode"), {"direct", "ai_managed", "supervised"}, "")
        if run_mode:
            spec_out["run_mode"] = run_mode
            accepted.append("run_mode")
        else:
            rejected.append("run_mode")

    if isinstance(overrides.get("selected_fields"), list):
        fields = [str(item).strip() for item in overrides.get("selected_fields", [])[:50] if str(item).strip()]
        if fields:
            spec_out["selected_fields"] = fields
            accepted.append("selected_fields")
        else:
            rejected.append("selected_fields")

    export = overrides.get("export")
    if isinstance(export, dict):
        export_out = dict(spec_out.get("export") or {})
        fmt = _safe_choice(export.get("format"), {"csv", "xlsx", "xls", "json", "sqlite", "db"}, "")
        if fmt:
            export_out["format"] = fmt
            accepted.append("export.format")
        elif "format" in export:
            rejected.append("export.format")
        if "output_path" in export:
            output_path = str(export.get("output_path") or "").strip()
            if output_path and len(output_path) <= 400 and "\x00" not in output_path:
                export_out["output_path"] = output_path
                accepted.append("export.output_path")
            else:
                rejected.append("export.output_path")
        spec_out["export"] = export_out

    return spec_out, profile_out, {
        "applied": bool(accepted),
        "accepted": accepted,
        "rejected": rejected,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _product_run_payload_from_job(job: dict[str, Any]) -> dict[str, Any]:
    spec = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    result = job.get("profile_run") if isinstance(job.get("profile_run"), dict) else {}
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    checkpoint = result.get("checkpoint_latest") if isinstance(result.get("checkpoint_latest"), dict) else {}
    checkpoint_meta = checkpoint.get("metadata") if isinstance(checkpoint.get("metadata"), dict) else {}
    profile_data = (
        checkpoint_meta.get("profile")
        if isinstance(checkpoint_meta.get("profile"), dict)
        else {}
    )
    if not profile_data:
        spec_profile = spec.get("profile") if isinstance(spec.get("profile"), dict) else {}
        profile_data = spec_profile
    if not profile_data:
        report_profile = report.get("profile") if isinstance(report.get("profile"), dict) else {}
        profile_data = {
            "name": job.get("profile_name") or report_profile.get("name") or "repaired-profile",
        }
    return {
        "target_url": spec.get("target_url") or job.get("target_url") or "",
        "profile": profile_data,
        "catalog_nodes": list(profile_data.get("crawl_preferences", {}).get("catalog_tree") or []),
        "selected_fields": list(spec.get("selected_fields") or profile_data.get("target_fields") or []),
        "export": dict(spec.get("export") or {}),
        "run_mode": spec.get("run_mode") or "direct",
        "item_workers": int(spec.get("item_workers") or 4),
        "max_sites": int(spec.get("max_sites") or 1),
        "test_limit": int(spec.get("test_limit") or profile_data.get("crawl_preferences", {}).get("max_items") or 100),
        "runtime_dir": spec.get("runtime_dir") or "",
    }


def _safe_url_for_profile_patch(value: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(str(value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _safe_css_selector(value: Any) -> str:
    selector = str(value or "").strip()
    if not selector or len(selector) > 300:
        return ""
    if any(ch in selector for ch in "\x00\r\n{};"):
        return ""
    return selector


def _product_spec_summary(spec: CrawlRunSpec) -> dict[str, Any]:
    return {
        "target_url": spec.target_url,
        "selected_fields": list(spec.selected_fields),
        "catalog_node_count": len(spec.catalog_nodes),
        "seed_urls": [
            str(node.get("url") or "")
            for node in _flatten_product_catalog_nodes(spec.catalog_nodes)
            if str(node.get("url") or "").strip()
        ][:100],
        "run_mode": spec.run_mode,
        "item_workers": spec.item_workers,
        "test_limit": spec.test_limit,
        "runtime_dir": spec.runtime_dir,
        "export": {
            "format": spec.export.format,
            "output_path": spec.export.output_path,
            "field_mapping_keys": sorted(spec.export.field_mapping.keys()),
        },
    }


def _flatten_product_catalog_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    def visit(items: list[dict[str, Any]]) -> None:
        for item in items or []:
            if not isinstance(item, dict):
                continue
            output.append(item)
            children = item.get("children")
            if isinstance(children, list):
                visit(children)

    visit(nodes)
    return output


def _string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:500] for item in value[:limit] if str(item).strip()]


def _repair_suggestions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    output: list[dict[str, Any]] = []
    for item in value[:20]:
        if isinstance(item, dict):
            output.append({
                "action": str(item.get("action") or "")[:300],
                "priority": _safe_choice(item.get("priority"), {"low", "medium", "high"}, "medium"),
                "rationale": str(item.get("rationale") or "")[:800],
            })
        elif str(item).strip():
            output.append({"action": str(item)[:300], "priority": "medium", "rationale": ""})
    return output


def _safe_choice(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def _bounded_dict(value: Any, max_chars: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    import json

    text = json.dumps(value, ensure_ascii=False, default=str)
    if len(text) > max_chars:
        return {"_truncated_json": text[:max_chars]}
    return value


def _deep_merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def _background_crawl(
    task_id: str,
    user_goal: str,
    target_url: str,
    max_retries: int,
    llm_config: LLMConfig | None = None,
) -> None:
    """Run the crawl workflow in a background thread."""
    try:
        final_state = run_crawl_workflow(
            user_goal=user_goal,
            target_url=target_url,
            max_retries=max_retries,
            llm_config=llm_config,
        )
        if _is_cancelled(task_id):
            return
        save_crawl_result(final_state)

        extracted = final_state.get("extracted_data") or {}
        validation = final_state.get("validation_result") or {}
        strategy = final_state.get("crawl_strategy") or {}
        anti_bot_report = strategy.get("anti_bot_report") or {}
        _update_job(
            task_id,
            status=final_state.get("status", "completed"),
            item_count=int(extracted.get("item_count") or 0),
            is_valid=bool(validation.get("is_valid")),
            error_code=final_state.get("error_code"),
            anti_bot_summary=summarize_anti_bot_report(anti_bot_report) if anti_bot_report else None,
        )
    except Exception as exc:
        if _is_cancelled(task_id):
            return
        from ..errors import classify_llm_error
        _update_job(task_id, status="failed", error=str(exc),
                    error_code=classify_llm_error(exc))


def _load_profile_for_request(request: ProfileRunRequest) -> SiteProfile:
    if request.profile is not None:
        return SiteProfile.from_dict(request.profile)
    if request.profile_path.strip():
        return SiteProfile.load(request.profile_path)
    raise ValueError("profile or profile_path is required")


def _profile_runtime_mode(profile: SiteProfile) -> str:
    access = profile.access_config if isinstance(profile.access_config, dict) else {}
    mode = str(access.get("mode") or access.get("runtime_mode") or "static").strip().lower()
    if mode in {"browser", "playwright"}:
        return "dynamic"
    if mode in {"dynamic", "protected"}:
        return mode
    return "static"


def run_profile_longrun_workflow(request: ProfileRunRequest, *, task_id: str) -> dict[str, Any]:
    profile = _load_profile_for_request(request)
    run_id = request.run_id.strip() or f"profile-{task_id}"
    fetch_runtime = NativeFetchRuntime(reuse_httpx_client=request.item_workers > 1)
    browser_runtime = NativeBrowserRuntime() if _profile_runtime_mode(profile) in {"dynamic", "protected"} else None
    try:
        result = run_profile_longrun(
            profile=profile,
            config=ProfileLongRunConfig(
                run_id=run_id,
                worker_id="api-profile-run",
                batch_size=request.batch_size,
                max_batches=request.max_batches,
                timeout_ms=request.timeout_ms,
                item_workers=request.item_workers,
                category=request.category,
                output_report_path=request.output_report_path,
                mode=_profile_runtime_mode(profile),
                supervision_mode=request.supervision_mode,
            ),
            fetch_runtime=fetch_runtime,
            browser_runtime=browser_runtime,
            runtime_dir=request.runtime_dir or None,
        )
    finally:
        fetch_runtime.close()
        if browser_runtime is not None:
            browser_runtime.close()
    return result.to_dict()


def _background_profile_run(task_id: str, request: ProfileRunRequest) -> None:
    try:
        result = run_profile_longrun_workflow(request, task_id=task_id)
        if _is_cancelled(task_id):
            return
        auto_export = _auto_export_product_run(task_id, request, result)
        if _managed_ai_enabled(request.managed_ai, request.llm) and _managed_ai_wants_post_run(request.managed_ai):
            advisor = _build_advisor_from_config(request.llm)  # type: ignore[arg-type]
            _run_managed_post_diagnosis(
                task_id=task_id,
                advisor=advisor,
                request=request,
                result=result,
            )
        _update_job(
            task_id,
            status=result.get("status", "completed"),
            item_count=int(result.get("product_stats", {}).get("total") or 0),
            is_valid=bool(result.get("accepted")),
            profile_run=result,
            diagnostics=result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else None,
            supervision=_supervision_from_result(result),
            export=auto_export or None,
        )
    except Exception as exc:
        if _is_cancelled(task_id):
            return
        _update_job(task_id, status="failed", error=str(exc), error_code="PROFILE_RUN_FAILED")


def _auto_export_product_run(
    task_id: str,
    request: ProfileRunRequest,
    result: dict[str, Any],
) -> dict[str, Any] | None:
    job = _get_job(task_id)
    if not job or job.get("kind") not in {"product_test_run", "product_full_run"}:
        return None
    spec = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    if not spec.get("auto_export"):
        return None
    export_payload = spec.get("export") if isinstance(spec.get("export"), dict) else {}
    if not export_payload:
        return None
    try:
        return export_product_records(
            run_id=str(result.get("run_id") or request.run_id),
            runtime_dir=str(spec.get("runtime_dir") or request.runtime_dir),
            export_spec=ExportSpec(
                format=str(export_payload.get("format") or "csv"),
                output_path=str(export_payload.get("output_path") or ""),
                template_path=str(export_payload.get("template_path") or ""),
                field_mapping={str(k): str(v) for k, v in dict(export_payload.get("field_mapping") or {}).items()},
            ),
        )
    except Exception as exc:
        return {
            "schema_version": "export-result/v1",
            "run_id": str(result.get("run_id") or request.run_id),
            "format": str(export_payload.get("format") or ""),
            "output_path": str(export_payload.get("output_path") or ""),
            "record_count": 0,
            "error": str(exc),
        }


def run_multi_profile_longrun_workflow(request: MultiProfileRunRequest, *, task_id: str) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = {}
    for name, payload in request.jobs.items():
        job = dict(payload or {})
        job.setdefault("item_workers", request.default_item_workers)
        jobs[str(name)] = job
    summary = run_multi_profile_longrun(jobs, max_sites=request.max_sites)
    result = summary.to_dict()
    if request.output_report_path.strip():
        import json
        from pathlib import Path

        output = Path(request.output_report_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return result


def _background_multi_profile_run(task_id: str, request: MultiProfileRunRequest) -> None:
    try:
        result = run_multi_profile_longrun_workflow(request, task_id=task_id)
        if _is_cancelled(task_id):
            return
        _update_job(
            task_id,
            status="completed" if int(result.get("failed_sites") or 0) == 0 else "partial",
            item_count=sum(_site_record_count(item) for item in result.get("results") or []),
            is_valid=int(result.get("failed_sites") or 0) == 0,
            multi_profile_run=result,
        )
    except Exception as exc:
        if _is_cancelled(task_id):
            return
        _update_job(task_id, status="failed", error=str(exc), error_code="MULTI_PROFILE_RUN_FAILED")


def _catalog_payload_from_request(request: CatalogImportRequest | SiteAnalyzeRequest) -> Any:
    payload = getattr(request, "catalog", None)
    if payload is not None:
        return payload
    imported = getattr(request, "imported_catalog", None)
    if imported is not None:
        return imported
    path = str(getattr(request, "catalog_path", "") or getattr(request, "imported_catalog_path", "") or "").strip()
    if path:
        return _load_json_file(path)
    return None


def _load_json_file(path: str) -> Any:
    file_path = Path(path)
    return json_loads_text(file_path.read_text(encoding="utf-8-sig", errors="replace"))


def json_loads_text(text: str) -> Any:
    import json

    return json.loads(text)


def _register_product_run_job(
    *,
    kind: str,
    run_payload: dict[str, Any],
    spec: CrawlRunSpec,
    managed_ai: ManagedAIConfig | None = None,
    llm: LLMConfig | None = None,
) -> dict[str, Any]:
    profile = SiteProfile.from_dict(run_payload["profile"])
    advisor = None
    if managed_ai and managed_ai.enabled:
        if not llm or not llm.enabled:
            raise HTTPException(status_code=400, detail="managed_ai requires llm.enabled=true")
        try:
            advisor = _build_advisor_from_config(llm)
        except LLMConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    pre_decision: dict[str, Any] | None = None
    patch_result: dict[str, Any] | None = None
    if advisor is not None and _managed_ai_wants_pre_run(managed_ai):
        pre_decision = _normalize_ai_decision("pre_run_review", advisor, {})
        try:
            raw = advisor.review_run_plan(_product_spec_summary(spec), profile.to_dict())
            pre_decision = _normalize_ai_decision("pre_run_review", advisor, raw)
        except Exception as exc:
            pre_decision = _ai_error_decision("pre_run_review", exc)
        if managed_ai and managed_ai.apply_pre_run_patch and not pre_decision.get("fallback_used"):
            patched_profile, patch_result = _apply_managed_profile_patch(
                profile.to_dict(),
                pre_decision.get("profile_patch") if isinstance(pre_decision.get("profile_patch"), dict) else {},
            )
            if patch_result and patch_result.get("applied"):
                profile = SiteProfile.from_dict(patched_profile)
    request = ProfileRunRequest(
        profile=profile.to_dict(),
        run_id=str(run_payload.get("run_id") or ""),
        batch_size=int(run_payload.get("batch_size") or 20),
        max_batches=int(run_payload.get("max_batches") or 0),
        item_workers=int(run_payload.get("item_workers") or spec.item_workers),
        runtime_dir=str(run_payload.get("runtime_dir") or spec.runtime_dir),
        supervision_mode=_supervision_mode_for_managed_ai(managed_ai),
        managed_ai=managed_ai,
        llm=llm,
    )
    task_id = str(uuid.uuid4())[:8]
    if not _try_register_job(task_id, f"{kind}:{profile.name}", first_profile_target(profile), kind=kind):
        raise HTTPException(status_code=429, detail=f"too many active jobs ({_max_active_jobs()} max)")
    _update_job(
        task_id,
        run_id=request.run_id,
        profile_name=profile.name,
        kind=kind,
        product_run_spec={
            "target_url": spec.target_url,
            "profile": profile.to_dict(),
            "catalog_nodes": list(spec.catalog_nodes),
            "selected_fields": list(spec.selected_fields),
            "run_mode": spec.run_mode,
            "item_workers": spec.item_workers,
            "max_sites": spec.max_sites,
            "test_limit": spec.test_limit,
            "runtime_dir": request.runtime_dir,
            "export": {
                "format": spec.export.format,
                "output_path": spec.export.output_path,
                "template_path": spec.export.template_path,
                "field_mapping": dict(spec.export.field_mapping),
            },
            "auto_export": bool(spec.export.output_path),
            "supervision_mode": _supervision_mode_for_managed_ai(managed_ai),
        },
        managed_ai=_managed_ai_public_config(managed_ai, llm),
        ai_decisions=[],
        ai_diagnostics=None,
        ai_repair_suggestions=[],
        ai_patch_applications=[],
    )
    if pre_decision is not None:
        _append_ai_decision(task_id, pre_decision)
    if patch_result is not None:
        _update_job(task_id, ai_patch_applications=[patch_result])
    thread = threading.Thread(
        target=_background_profile_run,
        args=(task_id, request),
        daemon=True,
    )
    thread.start()
    return {
        "task_id": task_id,
        "run_id": request.run_id,
        "status": "running",
        "profile_name": profile.name,
        "record_count": 0,
        "accepted": False,
    }


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

class LLMModelsRequest(BaseModel):
    base_url: str = Field(..., min_length=1)
    api_key: str = ""
    provider: str = "openai-compatible"


class ExportPathRequest(BaseModel):
    directory: str = Field(..., min_length=1)
    create: bool = False


class ExportResolvePathRequest(BaseModel):
    directory: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    format: str = "xlsx"
    filename: str = ""


def create_app() -> FastAPI:
    from starlette.middleware.cors import CORSMiddleware

    app = FastAPI(title="Autonomous Crawl Agent", version="0.3.0")

    # CORS: permissive for local dev; tighten in production via env
    _cors_origins = os.environ.get("CLM_CORS_ORIGINS", "*")
    origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins != "*" else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _recover_jobs() -> None:
        stale = _registry.recover_running()
        for job in stale:
            _registry.mark_status(job["task_id"], "failed")
            _registry.update(job["task_id"], error="recovered from prior crash", error_code="CRASH_RECOVERY")
        if stale:
            import logging
            logging.getLogger("autonomous_crawler.api").warning(
                "Recovered %d stale running jobs from prior session", len(stale)
            )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/jobs")
    def list_jobs(
        status: str = "",
        kind: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        _cleanup_stale_jobs()
        return {"jobs": _registry.list_jobs(status=status, kind=kind, limit=limit)}

    @app.get("/jobs/{task_id}")
    def get_job_detail(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return job

    @app.post("/jobs/{task_id}/cancel")
    def cancel_job(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        if job.get("status") not in ("running", "paused"):
            raise HTTPException(
                status_code=409,
                detail=f"cannot cancel: current status is '{job.get('status')}'",
            )
        _update_job(task_id, status="cancelled", error="cancelled by user")
        _registry.mark_status(task_id, "cancelled")
        return {"task_id": task_id, "status": "cancelled"}

    @app.delete("/jobs/{task_id}")
    def delete_job(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        _remove_job(task_id)
        return {"task_id": task_id, "deleted": True}

    @app.post("/crawl", response_model=CrawlResponse)
    def crawl(request: CrawlRequest) -> dict[str, Any]:
        _cleanup_stale_jobs()

        # Validate LLM config eagerly so bad requests get a clear 400
        llm_config: LLMConfig | None = None
        if request.llm is not None and request.llm.enabled:
            try:
                _build_advisor_from_config(request.llm)
            except LLMConfigurationError as exc:
                from ..errors import LLM_CONFIG_INVALID
                raise HTTPException(
                    status_code=400,
                    detail={"error_code": LLM_CONFIG_INVALID, "message": str(exc)},
                )
            llm_config = request.llm

        task_id = str(uuid.uuid4())[:8]

        if not _try_register_job(task_id, request.user_goal, request.target_url):
            raise HTTPException(
                status_code=429,
                detail=f"too many active jobs ({_max_active_jobs()} max)",
            )

        thread = threading.Thread(
            target=_background_crawl,
            args=(task_id, request.user_goal, request.target_url, request.max_retries, llm_config),
            daemon=True,
        )
        thread.start()

        return {
            "task_id": task_id,
            "status": "running",
            "item_count": 0,
            "is_valid": False,
            "error_code": None,
            "anti_bot_summary": None,
        }

    @app.get("/crawl/{task_id}")
    def get_crawl(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()

        # Check in-memory registry first (running/queued jobs)
        job = _get_job(task_id)
        if job:
            return {
                "task_id": job["task_id"],
                "user_goal": job["user_goal"],
                "target_url": job["target_url"],
                "status": job["status"],
                "item_count": job["item_count"],
                "is_valid": job["is_valid"],
                "error": job.get("error", ""),
                "error_code": job.get("error_code"),
                "anti_bot_summary": job.get("anti_bot_summary"),
            }

        # Fall back to persisted result
        result = load_crawl_result(task_id)
        if result:
            return result

        raise HTTPException(status_code=404, detail="crawl task not found")

    @app.get("/history")
    def history(limit: int = 20) -> dict[str, Any]:
        return {"items": list_crawl_results(limit=limit)}

    @app.post("/catalog/import")
    def catalog_import(request: CatalogImportRequest) -> dict[str, Any]:
        try:
            payload = _catalog_payload_from_request(request)
            if payload is None:
                raise ValueError("catalog or catalog_path is required")
            nodes = import_catalog_tree(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "schema_version": "catalog-tree/v1",
            "catalog_tree": nodes,
            "node_count": _count_catalog_nodes(nodes),
            "leaf_count": _count_catalog_leaves(nodes),
        }

    @app.post("/site/analyze")
    def site_analyze(request: SiteAnalyzeRequest) -> dict[str, Any]:
        try:
            imported_catalog = _catalog_payload_from_request(request)
            advisor = None
            if request.llm is not None and request.llm.enabled:
                advisor = _build_advisor_from_config(request.llm)
            return analyze_site_for_product_workflow(
                request.target_url,
                imported_catalog=imported_catalog,
                field_goal=request.field_goal,
                advisor=advisor,
            )
        except LLMConfigurationError as exc:
            from ..errors import LLM_CONFIG_INVALID
            raise HTTPException(
                status_code=400,
                detail={"error_code": LLM_CONFIG_INVALID, "message": str(exc)},
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/fields/resolve")
    def fields_resolve(request: FieldResolveRequest) -> dict[str, Any]:
        return resolve_fields(
            request.available_fields,
            natural_language=request.natural_language,
            requested_fields=request.requested_fields,
        )

    @app.post("/runs/test")
    def product_test_run(request: ProductRunRequest) -> dict[str, Any]:
        spec = build_run_spec(request.model_dump())
        return _register_product_run_job(
            kind="product_test_run",
            run_payload=build_test_run_payload(spec),
            spec=spec,
            managed_ai=request.managed_ai,
            llm=request.llm,
        )

    @app.post("/runs/full")
    def product_full_run(request: ProductRunRequest) -> dict[str, Any]:
        spec = build_run_spec(request.model_dump())
        return _register_product_run_job(
            kind="product_full_run",
            run_payload=build_full_run_payload(spec),
            spec=spec,
            managed_ai=request.managed_ai,
            llm=request.llm,
        )

    @app.get("/runs/{task_id}/status")
    def product_run_status(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="run not found")
        progress = summarize_run_progress(job)
        return {
            "task_id": task_id,
            "parent_task_id": job.get("parent_task_id", ""),
            "repair_source": job.get("repair_source", ""),
            "kind": job.get("kind", ""),
            "run_id": job.get("run_id", ""),
            "status": job.get("status", ""),
            "record_count": job.get("item_count", 0),
            "accepted": job.get("is_valid", False),
            "error": job.get("error", ""),
            "progress": progress,
            "current_stage": progress.get("current_stage", ""),
            "last_error": progress.get("last_error", ""),
            "progress_summary": progress.get("progress_summary", ""),
            "quality_indicator": progress.get("quality_indicator", "unknown"),
            "diagnostics": job.get("diagnostics") or None,
            "supervision": job.get("supervision") or None,
            "export": job.get("export") or None,
            "managed_ai": job.get("managed_ai") or {"enabled": False},
            "ai_decisions": job.get("ai_decisions") or [],
            "ai_diagnostics": job.get("ai_diagnostics") or None,
            "ai_repair_suggestions": job.get("ai_repair_suggestions") or [],
            "ai_patch_applications": job.get("ai_patch_applications") or [],
        }

    @app.get("/runs/{task_id}/events")
    def product_run_events(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="run not found")
        return {"task_id": task_id, "events": events_for_job(job)}

    @app.post("/runs/{task_id}/ai-rerun")
    def product_ai_rerun(task_id: str, request: AIRerunRequest) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="run not found")
        if job.get("kind") not in {"product_test_run", "product_full_run"}:
            raise HTTPException(status_code=400, detail="ai rerun is only available for product runs")

        payload = _product_run_payload_from_job(job)
        overrides: dict[str, Any] = {}
        diagnostics = job.get("ai_diagnostics") if isinstance(job.get("ai_diagnostics"), dict) else {}
        if request.apply_diagnostics and isinstance(diagnostics.get("next_run_overrides"), dict):
            overrides.update(diagnostics.get("next_run_overrides") or {})
        supervision_overrides = _repair_overrides_from_supervision(
            job.get("supervision") if isinstance(job.get("supervision"), dict) else {}
        )
        if request.apply_diagnostics and supervision_overrides:
            overrides = _deep_merge_dicts(overrides, supervision_overrides)
        overrides.update(dict(request.extra_overrides or {}))

        patched_spec, patched_profile, patch_result = _apply_managed_run_overrides(
            payload,
            payload.get("profile") if isinstance(payload.get("profile"), dict) else {},
            overrides,
        )
        patched_spec["profile"] = patched_profile
        spec = build_run_spec(patched_spec)
        run_kind = _safe_choice(request.run_kind, {"test", "full"}, "")
        if not run_kind:
            run_kind = "full" if job.get("kind") == "product_full_run" else "test"
        result = _register_product_run_job(
            kind="product_full_run" if run_kind == "full" else "product_test_run",
            run_payload=build_full_run_payload(spec) if run_kind == "full" else build_test_run_payload(spec),
            spec=spec,
            managed_ai=request.managed_ai,
            llm=request.llm,
        )
        child_id = result["task_id"]
        _update_job(
            child_id,
            parent_task_id=task_id,
            repair_source="ai_rerun",
            ai_patch_applications=[{
                **patch_result,
                "source_task_id": task_id,
                "source": "ai_diagnostics.next_run_overrides",
            }],
        )
        return {
            **result,
            "parent_task_id": task_id,
            "repair_source": "ai_rerun",
            "patch_application": patch_result,
        }

    @app.post("/exports")
    def product_export(request: ExportRequest) -> dict[str, Any]:
        try:
            return export_product_records(
                run_id=request.run_id,
                runtime_dir=request.runtime_dir,
                export_spec=ExportSpec(
                    format=request.format,
                    output_path=request.output_path,
                    template_path=request.template_path,
                    field_mapping=dict(request.field_mapping),
                    template=ExportTemplate.from_dict(request.template) if request.template else ExportTemplate(),
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/profile-runs", response_model=ProfileRunResponse)
    def start_profile_run(request: ProfileRunRequest) -> dict[str, Any]:
        _cleanup_stale_jobs()
        try:
            profile = _load_profile_for_request(request)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        task_id = str(uuid.uuid4())[:8]
        run_id = request.run_id.strip() or f"profile-{task_id}"
        if not _try_register_job(task_id, f"profile-run:{profile.name}", first_profile_target(profile), kind="profile_run"):
            raise HTTPException(
                status_code=429,
                detail=f"too many active jobs ({_max_active_jobs()} max)",
            )
        _update_job(task_id, run_id=run_id, profile_name=profile.name, kind="profile_run")
        thread = threading.Thread(
            target=_background_profile_run,
            args=(task_id, request),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": task_id,
            "run_id": run_id,
            "status": "running",
            "profile_name": profile.name,
            "record_count": 0,
            "accepted": False,
        }

    @app.post("/profile-runs/batch", response_model=MultiProfileRunResponse)
    def start_multi_profile_run(request: MultiProfileRunRequest) -> dict[str, Any]:
        _cleanup_stale_jobs()
        if not request.jobs:
            raise HTTPException(status_code=400, detail="jobs is required")
        if len(request.jobs) > request.max_sites:
            raise HTTPException(status_code=400, detail=f"too many site jobs: {len(request.jobs)} > {request.max_sites}")

        task_id = str(uuid.uuid4())[:8]
        if not _try_register_job(task_id, "multi-profile-run", f"{len(request.jobs)} sites", kind="multi_profile_run"):
            raise HTTPException(
                status_code=429,
                detail=f"too many active jobs ({_max_active_jobs()} max)",
            )
        _update_job(task_id, kind="multi_profile_run", total_sites=len(request.jobs))
        thread = threading.Thread(
            target=_background_multi_profile_run,
            args=(task_id, request),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": task_id,
            "status": "running",
            "total_sites": len(request.jobs),
            "ok_sites": 0,
            "failed_sites": 0,
        }

    @app.get("/profile-runs/{task_id}")
    def get_profile_run(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job or job.get("kind") != "profile_run":
            raise HTTPException(status_code=404, detail="profile run not found")
        result: dict[str, Any] = {
            "task_id": task_id,
            "run_id": job.get("run_id", ""),
            "status": job.get("status", ""),
            "profile_name": job.get("profile_name", ""),
            "record_count": job.get("item_count", 0),
            "accepted": job.get("is_valid", False),
            "error": job.get("error", ""),
            "profile_run": job.get("profile_run"),
        }
        if job.get("diagnostics"):
            result["diagnostics"] = job["diagnostics"]
        if job.get("backpressure"):
            result["backpressure"] = job["backpressure"]
        return result

    @app.post("/profile-runs/{task_id}/cancel")
    def cancel_profile_run(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job or job.get("kind") != "profile_run":
            raise HTTPException(status_code=404, detail="profile run not found")
        if job.get("status") != "running":
            raise HTTPException(
                status_code=409,
                detail=f"cannot cancel: current status is '{job.get('status')}'",
            )
        _update_job(task_id, status="cancelled", error="cancelled by user")
        _registry.mark_status(task_id, "cancelled")
        return {"task_id": task_id, "status": "cancelled"}

    @app.post("/profile-runs/{task_id}/pause")
    def pause_profile_run(task_id: str) -> dict[str, Any]:
        """Request pause — sets a flag for the runner to stop after the current batch.

        Actual pause is best-effort: the runner checks this flag between batches.
        """
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job or job.get("kind") != "profile_run":
            raise HTTPException(status_code=404, detail="profile run not found")
        if job.get("status") != "running":
            raise HTTPException(
                status_code=409,
                detail=f"cannot pause: current status is '{job.get('status')}'",
            )
        _update_job(task_id, pause_requested=True)
        return {"task_id": task_id, "status": "pause_requested"}

    @app.post("/profile-runs/{task_id}/resume")
    def resume_profile_run(task_id: str) -> dict[str, Any]:
        """Resume a paused profile run — re-enqueues it for the background runner.

        Only works if the job is in 'paused' status.
        """
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job or job.get("kind") != "profile_run":
            raise HTTPException(status_code=404, detail="profile run not found")
        if job.get("status") != "paused":
            raise HTTPException(
                status_code=409,
                detail=f"cannot resume: current status is '{job.get('status')}'",
            )
        _update_job(task_id, status="running", pause_requested=False, error="")
        return {"task_id": task_id, "status": "running"}

    @app.get("/profile-runs/batch/{task_id}")
    def get_multi_profile_run(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job or job.get("kind") != "multi_profile_run":
            raise HTTPException(status_code=404, detail="multi profile run not found")
        result = job.get("multi_profile_run") or {}
        return {
            "task_id": task_id,
            "status": job.get("status", ""),
            "total_sites": job.get("total_sites", 0),
            "ok_sites": result.get("ok_sites", 0),
            "failed_sites": result.get("failed_sites", 0),
            "record_count": job.get("item_count", 0),
            "accepted": job.get("is_valid", False),
            "error": job.get("error", ""),
            "multi_profile_run": result,
        }

    # -----------------------------------------------------------------------
    # LLM model list and health
    # -----------------------------------------------------------------------

    @app.post("/llm/models")
    def llm_models(request: LLMModelsRequest) -> dict[str, Any]:
        if not request.base_url.strip():
            raise HTTPException(status_code=400, detail="base_url is required")
        result = fetch_model_list(
            base_url=request.base_url,
            api_key=request.api_key,
            provider=request.provider,
        )
        return result.to_dict()

    @app.post("/llm/health")
    def llm_health(request: LLMModelsRequest) -> dict[str, Any]:
        if not request.base_url.strip():
            raise HTTPException(status_code=400, detail="base_url is required")
        return check_provider_health(
            base_url=request.base_url,
            api_key=request.api_key,
            provider=request.provider,
        )

    # -----------------------------------------------------------------------
    # Export path helpers
    # -----------------------------------------------------------------------

    @app.post("/exports/validate-path")
    def export_validate_path(request: ExportPathRequest) -> dict[str, Any]:
        if not request.directory.strip():
            raise HTTPException(status_code=400, detail="directory is required")
        dir_path = Path(request.directory.strip())
        created = False
        try:
            if request.create and not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                created = True
            exists = dir_path.exists()
            writable = exists and os.access(dir_path, os.W_OK)
            return {
                "exists": exists,
                "created": created,
                "writable": writable,
                "normalized_path": str(dir_path.resolve()),
                "error": "" if writable else ("directory does not exist" if not exists else "directory is not writable"),
            }
        except Exception as exc:
            return {
                "exists": False,
                "created": False,
                "writable": False,
                "normalized_path": str(dir_path),
                "error": str(exc)[:200],
            }

    @app.post("/exports/resolve-path")
    def export_resolve_path(request: ExportResolvePathRequest) -> dict[str, Any]:
        if not request.directory.strip():
            raise HTTPException(status_code=400, detail="directory is required")
        if not request.run_id.strip():
            raise HTTPException(status_code=400, detail="run_id is required")
        fmt = request.format.strip().lower() or "xlsx"
        suffix = _export_suffix(fmt)
        filename = request.filename.strip() or f"{request.run_id}.{suffix}"
        # Ensure extension
        if not filename.endswith(f".{suffix}"):
            filename = f"{filename}.{suffix}"
        dir_path = Path(request.directory.strip())
        final = dir_path / filename
        return {
            "directory": str(dir_path.resolve()),
            "filename": filename,
            "output_path": str(final.resolve()),
            "format": fmt,
        }

    # -----------------------------------------------------------------------
    # Workbench config summary
    # -----------------------------------------------------------------------

    @app.get("/workbench/config")
    def workbench_config() -> dict[str, Any]:
        return {
            "version": "0.3.0",
            "supported_export_formats": ["json", "csv", "xlsx", "sqlite", "db"],
            "max_active_jobs": _max_active_jobs(),
            "default_retention_seconds": _job_retention_seconds(),
            "endpoints": {
                "catalog_import": "/catalog/import",
                "site_analyze": "/site/analyze",
                "fields_resolve": "/fields/resolve",
                "runs_test": "/runs/test",
                "runs_full": "/runs/full",
                "runs_status": "/runs/{task_id}/status",
                "runs_events": "/runs/{task_id}/events",
                "exports": "/exports",
                "exports_validate_path": "/exports/validate-path",
                "exports_resolve_path": "/exports/resolve-path",
                "llm_models": "/llm/models",
                "llm_health": "/llm/health",
                "profile_runs": "/profile-runs",
                "jobs": "/jobs",
                "health": "/health",
            },
        }

    return app


def run_crawl_workflow(
    user_goal: str,
    target_url: str,
    max_retries: int = 3,
    llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    advisor = None
    if llm_config is not None and llm_config.enabled:
        advisor = _build_advisor_from_config(llm_config)

    initial_state = {
        "user_goal": user_goal,
        "target_url": target_url,
        "recon_report": {},
        "crawl_strategy": {},
        "visited_urls": [],
        "raw_html": {},
        "api_responses": [],
        "extracted_data": {},
        "validation_result": {},
        "retries": 0,
        "max_retries": max_retries,
        "status": "pending",
        "error_log": [],
        "messages": [],
    }
    app = compile_crawl_graph(
        planning_advisor=advisor,
        strategy_advisor=advisor,
    )
    return app.invoke(initial_state)


app = create_app()


def first_profile_target(profile: SiteProfile) -> str:
    endpoint = str(profile.api_hints.get("endpoint") or "").strip()
    if endpoint:
        return endpoint
    seeds = profile.crawl_preferences.get("seed_urls") or profile.constraints.get("seed_urls") or []
    return str(seeds[0]) if seeds else ""


def _site_record_count(result: dict[str, Any]) -> int:
    if not isinstance(result, dict) or not result.get("ok"):
        return 0
    payload = result.get("result")
    if not isinstance(payload, dict):
        return 0
    stats = payload.get("product_stats")
    if isinstance(stats, dict):
        return int(stats.get("total") or 0)
    return 0


def _count_catalog_nodes(nodes: list[dict[str, Any]]) -> int:
    return sum(1 + _count_catalog_nodes(list(node.get("children") or [])) for node in nodes if isinstance(node, dict))


def _count_catalog_leaves(nodes: list[dict[str, Any]]) -> int:
    total = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        children = list(node.get("children") or [])
        if node.get("url"):
            total += 1
        total += _count_catalog_leaves(children)
    return total


def _export_suffix(fmt: str) -> str:
    value = str(fmt or "xlsx").lower()
    return "sqlite3" if value in {"sqlite", "db"} else value
