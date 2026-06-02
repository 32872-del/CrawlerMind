"""Product run endpoints and managed action lifecycle.

Covers: /runs/test, /runs/full, /runs/{id}/status, /runs/{id}/events,
/runs/{id}/managed-actions, /runs/{id}/managed-step, /runs/{id}/access-probe,
/runs/{id}/managed-control-loop, /runs/{id}/managed-repair-run, /runs/{id}/ai-rerun.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from ...llm.openai_compatible import LLMConfigurationError, OpenAICompatibleAdvisor
from ...runners.managed_actions import (
    SUPPORTED_ACTIONS,
    ManagedActionPlan,
    ManagedCrawlAction,
    build_deterministic_action_plan,
    execute_managed_action_plan,
    execute_and_run,
    _execute_inspect_access,
)
from ...runners.auto_repair import (
    AutoRepairLoop,
    FailureDiagnoser,
    diagnose_and_repair,
)
from ...runners.managed_state import build_managed_crawl_state, compact_managed_state_for_llm
from ...runners.product_workflow import (
    CrawlRunSpec,
    ExportSpec,
    ExportTemplate,
    build_full_run_payload,
    build_run_evidence_pack,
    build_run_spec,
    build_test_run_payload,
    events_for_job,
    export_product_records,
    summarize_run_progress,
)
from ...runners import SiteProfile, ProfileLongRunConfig, run_profile_longrun
from ...runtime import NativeBrowserRuntime, NativeFetchRuntime
from ..deps import (
    append_ai_decision,
    append_llm_trace,
    ai_diagnostics_from_decision,
    ai_error_decision,
    build_advisor_from_config,
    bounded_dict,
    cleanup_stale_jobs,
    deep_merge_dicts,
    get_job,
    llm_trace_record,
    managed_ai_enabled,
    managed_ai_mode,
    managed_ai_public_config,
    managed_ai_wants_auto_repair,
    managed_ai_wants_post_run,
    managed_ai_wants_pre_run,
    normalize_ai_decision,
    payload_summary,
    safe_choice,
    string_list,
    supervision_mode_for_managed_ai,
    try_register_job,
    update_job,
)
from ..schemas import (
    AIRerunRequest,
    AutoRepairDiagnoseRequest,
    AutoRepairLoopRequest,
    LLMConfig,
    ManagedAIConfig,
    ManagedActionsRequest,
    ManagedControlLoopRequest,
    ManagedRepairRunRequest,
    ManagedRepairRequest,
    ManagedRunRequest,
    ManagedStepRequest,
    AccessProbeRequest,
    ProductRunRequest,
    ProfileRunRequest,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Profile run workflow (used by both /runs/* and /profile-runs)
# ---------------------------------------------------------------------------


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
                adaptive_item_workers=request.adaptive_item_workers,
                min_item_workers=request.min_item_workers,
                max_item_workers=request.max_item_workers,
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


# ---------------------------------------------------------------------------
# Profile patching and run override logic
# ---------------------------------------------------------------------------


def _apply_managed_profile_patch(
    profile_data: dict[str, Any],
    patch: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(patch, dict) or not patch:
        return profile_data, {"applied": False, "accepted": [], "rejected": ["empty_patch"]}
    updated = dict(profile_data or {})
    accepted: list[str] = []
    rejected: list[str] = []

    # crawl_preferences
    prefs_patch = patch.get("crawl_preferences") if isinstance(patch.get("crawl_preferences"), dict) else {}
    if prefs_patch:
        prefs = dict(updated.get("crawl_preferences") or {})
        if isinstance(prefs_patch.get("seed_urls"), list):
            from ..deps import safe_url
            urls = [str(url).strip() for url in prefs_patch.get("seed_urls")[:500] if safe_url(str(url))]
            if urls:
                prefs["seed_urls"] = urls
                accepted.append("crawl_preferences.seed_urls")
            else:
                rejected.append("crawl_preferences.seed_urls")
        if str(prefs_patch.get("seed_kind") or "").strip():
            seed_kind = safe_choice(prefs_patch.get("seed_kind"), {"entry", "list", "detail", "api", "catalog"}, "")
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

    # access_config
    access_patch = patch.get("access_config") if isinstance(patch.get("access_config"), dict) else {}
    if access_patch:
        access = dict(updated.get("access_config") or {})
        mode = safe_choice(access_patch.get("mode") or access_patch.get("runtime_mode"), {"static", "dynamic", "protected"}, "")
        if mode:
            access["mode"] = mode
            accepted.append("access_config.mode")
        elif "mode" in access_patch or "runtime_mode" in access_patch:
            rejected.append("access_config.mode")
        wait_until = safe_choice(access_patch.get("wait_until"), {"domcontentloaded", "load", "networkidle"}, "")
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
            for key in ("capture_api", "auto_accept_cookies", "persistent_context", "close_persistent_context", "pool_enabled"):
                if key in browser_patch:
                    browser[key] = bool(browser_patch[key])
                    accepted.append(f"access_config.browser_config.{key}")
            for key in ("pool_id", "profile_id", "storage_state_path"):
                if key in browser_patch:
                    text = str(browser_patch.get(key) or "").strip()
                    if 0 < len(text) <= 200 and "\x00" not in text:
                        browser[key] = text
                        accepted.append(f"access_config.browser_config.{key}")
                    else:
                        rejected.append(f"access_config.browser_config.{key}")
            access["browser_config"] = browser
        updated["access_config"] = access

    # api_hints
    api_patch = patch.get("api_hints") if isinstance(patch.get("api_hints"), dict) else {}
    if api_patch:
        api_hints = dict(updated.get("api_hints") or {})
        if "endpoint" in api_patch:
            from ..deps import safe_url
            endpoint = str(api_patch.get("endpoint") or "").strip()
            if safe_url(endpoint):
                api_hints["endpoint"] = endpoint
                accepted.append("api_hints.endpoint")
            else:
                rejected.append("api_hints.endpoint")
        method = safe_choice(api_patch.get("method"), {"GET", "POST", "get", "post"}, "")
        if method:
            api_hints["method"] = method.upper()
            accepted.append("api_hints.method")
        elif "method" in api_patch:
            rejected.append("api_hints.method")
        fmt = safe_choice(api_patch.get("format"), {"json", "graphql"}, "")
        if fmt:
            api_hints["format"] = fmt
            accepted.append("api_hints.format")
        elif "format" in api_patch:
            rejected.append("api_hints.format")
        for key in ("items_path", "records_path", "data_path", "total_path", "kind", "category"):
            if key in api_patch:
                text = str(api_patch.get(key) or "").strip()
                if 0 < len(text) <= 300 and "\x00" not in text:
                    api_hints[key] = text
                    accepted.append(f"api_hints.{key}")
                else:
                    rejected.append(f"api_hints.{key}")
        for key in ("priority", "page_size"):
            if key in api_patch:
                try:
                    api_hints[key] = max(1, min(int(api_patch[key]), 10000))
                    accepted.append(f"api_hints.{key}")
                except (TypeError, ValueError):
                    rejected.append(f"api_hints.{key}")
        if isinstance(api_patch.get("field_mapping"), dict):
            mapping = _safe_api_field_mapping(api_patch.get("field_mapping"))
            if mapping:
                api_hints["field_mapping"] = mapping
                accepted.append("api_hints.field_mapping")
            else:
                rejected.append("api_hints.field_mapping")
        if isinstance(api_patch.get("params"), dict):
            params = _safe_string_mapping(api_patch.get("params"), max_items=60, max_value_len=300)
            if params:
                api_hints["params"] = params
                accepted.append("api_hints.params")
            else:
                rejected.append("api_hints.params")
        if isinstance(api_patch.get("headers"), dict):
            headers = _safe_string_mapping(api_patch.get("headers"), max_items=40, max_value_len=1000)
            if headers:
                api_hints["headers"] = headers
                accepted.append("api_hints.headers")
            else:
                rejected.append("api_hints.headers")
        if isinstance(api_patch.get("post_json"), dict):
            post_json = _safe_json_like(api_patch.get("post_json"), max_chars=12000)
            if post_json is not None:
                api_hints["post_json"] = post_json
                accepted.append("api_hints.post_json")
            else:
                rejected.append("api_hints.post_json")
        if "post_data" in api_patch:
            post_data = str(api_patch.get("post_data") or "")
            if 0 < len(post_data) <= 12000 and "\x00" not in post_data:
                api_hints["post_data"] = post_data
                accepted.append("api_hints.post_data")
            else:
                rejected.append("api_hints.post_data")
        if isinstance(api_patch.get("replay_diagnostics"), dict):
            replay_diagnostics = _safe_json_like(api_patch.get("replay_diagnostics"), max_chars=12000)
            if isinstance(replay_diagnostics, dict):
                api_hints["replay_diagnostics"] = replay_diagnostics
                accepted.append("api_hints.replay_diagnostics")
            else:
                rejected.append("api_hints.replay_diagnostics")
        if isinstance(api_patch.get("replay_runtime"), dict):
            replay_runtime = _safe_json_like(api_patch.get("replay_runtime"), max_chars=24000)
            if isinstance(replay_runtime, dict):
                api_hints["replay_runtime"] = replay_runtime
                accepted.append("api_hints.replay_runtime")
            else:
                rejected.append("api_hints.replay_runtime")
        if isinstance(api_patch.get("replay_plan"), dict):
            replay_plan = _safe_json_like(api_patch.get("replay_plan"), max_chars=24000)
            if isinstance(replay_plan, dict):
                api_hints["replay_plan"] = replay_plan
                accepted.append("api_hints.replay_plan")
            else:
                rejected.append("api_hints.replay_plan")
        updated["api_hints"] = api_hints

    # selectors
    selectors_patch = patch.get("selectors") if isinstance(patch.get("selectors"), dict) else {}
    if selectors_patch:
        selectors = dict(updated.get("selectors") or {})
        for key, value in selectors_patch.items():
            safe_value = _safe_selector_value(value)
            if safe_value:
                selectors[str(key)[:80]] = safe_value
                accepted.append(f"selectors.{str(key)[:80]}")
            else:
                rejected.append(f"selectors.{str(key)[:80]}")
        updated["selectors"] = selectors

    # pagination_hints
    pagination_patch = patch.get("pagination_hints") if isinstance(patch.get("pagination_hints"), dict) else {}
    if pagination_patch:
        pagination = dict(updated.get("pagination_hints") or {})
        page_type = safe_choice(pagination_patch.get("type"), {"none", "dom_links", "page", "offset", "cursor", "api"}, "")
        if page_type:
            pagination["type"] = page_type
            accepted.append("pagination_hints.type")
        for key in ("page_param", "offset_param", "limit_param", "cursor_param", "next_selector",
                     "next_cursor_path", "json_page_path", "json_page_size_path", "json_cursor_path"):
            if key in pagination_patch:
                text = str(pagination_patch.get(key) or "").strip()
                if 0 < len(text) <= 300 and "\x00" not in text:
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

    # quality_expectations
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
        if "min_records" in quality_patch:
            try:
                quality["min_records"] = max(1, min(int(quality_patch.get("min_records")), 1_000_000))
                accepted.append("quality_expectations.min_records")
            except (TypeError, ValueError):
                rejected.append("quality_expectations.min_records")
        if "min_field_coverage" in quality_patch:
            try:
                quality["min_field_coverage"] = max(0.0, min(float(quality_patch.get("min_field_coverage")), 1.0))
                accepted.append("quality_expectations.min_field_coverage")
            except (TypeError, ValueError):
                rejected.append("quality_expectations.min_field_coverage")
        updated["quality_expectations"] = quality

    # target_fields
    if isinstance(patch.get("target_fields"), list):
        fields = [str(item).strip() for item in patch.get("target_fields", [])[:50] if str(item).strip()]
        if fields:
            updated["target_fields"] = fields
            accepted.append("target_fields")
        else:
            rejected.append("target_fields")

    return updated, {
        "applied": bool(accepted),
        "accepted": accepted,
        "rejected": rejected,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _safe_selector_value(value: Any) -> Any:
    selector = _safe_css_selector(value)
    if selector:
        return selector
    if not isinstance(value, dict):
        return None
    allowed: dict[str, Any] = {}
    for key, item in value.items():
        safe_key = str(key).strip()[:80]
        if not safe_key or "\x00" in safe_key:
            continue
        if isinstance(item, dict):
            nested: dict[str, Any] = {}
            selector_value = _safe_css_selector(item.get("selector"))
            if selector_value:
                nested["selector"] = selector_value
                selector_type = safe_choice(item.get("selector_type"), {"css", "xpath", "text", "regex"}, "")
                if selector_type:
                    nested["selector_type"] = selector_type
                if "many" in item:
                    nested["many"] = bool(item.get("many"))
            if nested:
                allowed[safe_key] = nested
        else:
            nested_selector = _safe_css_selector(item)
            if nested_selector:
                allowed[safe_key] = nested_selector
    return allowed or None


def _safe_css_selector(value: Any) -> str:
    selector = str(value or "").strip()
    if not selector or len(selector) > 300:
        return ""
    if any(ch in selector for ch in "\x00\r\n{};"):
        return ""
    return selector


def _safe_string_mapping(value: Any, *, max_items: int, max_value_len: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, Any] = {}
    for key, item in list(value.items())[:max_items]:
        safe_key = str(key).strip()[:120]
        if not safe_key or "\x00" in safe_key:
            continue
        if isinstance(item, (str, int, float, bool)) or item is None:
            text = str(item) if item is not None else ""
            if len(text) <= max_value_len and "\x00" not in text:
                output[safe_key] = item
        elif isinstance(item, list):
            cleaned = [
                str(part) for part in item[:20]
                if len(str(part)) <= max_value_len and "\x00" not in str(part)
            ]
            if cleaned:
                output[safe_key] = cleaned
    return output


def _safe_api_field_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, Any] = {}
    for key, item in list(value.items())[:80]:
        safe_key = str(key).strip()[:80]
        if not safe_key or "\x00" in safe_key:
            continue
        if isinstance(item, list):
            paths = [
                str(path).strip()[:240]
                for path in item[:10]
                if str(path).strip() and "\x00" not in str(path)
            ]
            if paths:
                output[safe_key] = paths
        else:
            path = str(item).strip()[:240]
            if path and "\x00" not in path:
                output[safe_key] = path
    return output


def _safe_json_like(value: Any, *, max_chars: int) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return None
    if len(encoded) > max_chars or "\x00" in encoded:
        return None
    return json.loads(encoded)


def _apply_managed_run_overrides(
    spec_data: dict[str, Any],
    profile_data: dict[str, Any],
    overrides: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec_out = dict(spec_data or {})
    profile_out = dict(profile_data or {})
    accepted: list[str] = []
    rejected: list[str] = []

    if not isinstance(overrides, dict) or not overrides:
        return spec_out, profile_out, {
            "applied": False, "accepted": [], "rejected": ["empty_overrides"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    profile_patch: dict[str, Any] = {}
    for key in ("crawl_preferences", "access_config", "selectors", "api_hints", "pagination_hints", "quality_expectations"):
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
        run_mode = safe_choice(overrides.get("run_mode"), {"direct", "ai_managed", "supervised"}, "")
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
        fmt = safe_choice(export.get("format"), {"csv", "xlsx", "xls", "json", "sqlite", "db"}, "")
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
        "applied": bool(accepted), "accepted": accepted, "rejected": rejected,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Managed action execution
# ---------------------------------------------------------------------------


def _product_run_payload_from_job(job: dict[str, Any]) -> dict[str, Any]:
    spec = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    result = job.get("profile_run") if isinstance(job.get("profile_run"), dict) else {}
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    checkpoint = result.get("checkpoint_latest") if isinstance(result.get("checkpoint_latest"), dict) else {}
    checkpoint_meta = checkpoint.get("metadata") if isinstance(checkpoint.get("metadata"), dict) else {}
    profile_data = checkpoint_meta.get("profile") if isinstance(checkpoint_meta.get("profile"), dict) else {}
    if not profile_data:
        profile_data = spec.get("profile") if isinstance(spec.get("profile"), dict) else {}
    if not profile_data:
        report_profile = report.get("profile") if isinstance(report.get("profile"), dict) else {}
        profile_data = {"name": job.get("profile_name") or report_profile.get("name") or "repaired-profile"}
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


def _build_managed_action_plan_for_job(
    *, job: dict[str, Any], request: ManagedActionsRequest,
) -> tuple[ManagedActionPlan, OpenAICompatibleAdvisor | None]:
    run_spec = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    profile = _product_run_payload_from_job(job).get("profile")
    profile_data = profile if isinstance(profile, dict) else {}
    extra_context = _managed_extra_context_from_profile(profile_data, request.extra_context)
    progress = summarize_run_progress(job)
    evidence_pack = build_run_evidence_pack(job)
    managed_state = build_managed_crawl_state(job)
    managed_llm_context = compact_managed_state_for_llm(managed_state)
    if extra_context:
        managed_llm_context = _merge_extra_extraction_context(
            managed_llm_context,
            extra_context,
        )
    diagnostics = job.get("diagnostics") if isinstance(job.get("diagnostics"), dict) else {}
    supervision = job.get("supervision") if isinstance(job.get("supervision"), dict) else {}
    target_url = str(run_spec.get("target_url") or job.get("target_url") or "")
    advisor = None
    if request.use_llm and request.llm and request.llm.enabled:
        advisor = build_advisor_from_config(request.llm)
        started_at = time.perf_counter()
        input_payload = {
            "target_url": target_url, "profile": profile_data, "run_spec": run_spec,
            "progress": progress, "evidence_pack": evidence_pack,
            "managed_state": managed_state, "managed_llm_context": managed_llm_context,
            "diagnostics": diagnostics, "supervision": supervision,
            "available_actions": sorted(SUPPORTED_ACTIONS),
        }
        try:
            raw = advisor.choose_managed_actions(
                target_url=target_url,
                profile=evidence_pack.get("profile_summary") if isinstance(evidence_pack.get("profile_summary"), dict) else profile_data,
                run_spec=managed_llm_context, progress=progress,
                diagnostics={**evidence_pack, "managed_state": managed_state, "managed_llm_context": managed_llm_context},
                supervision=supervision, available_actions=sorted(SUPPORTED_ACTIONS),
            )
            task_id = str(job.get("task_id") or "")
            if task_id:
                append_llm_trace(task_id, llm_trace_record(
                    stage="managed_actions", advisor=advisor, started_at=started_at,
                    status="ok", input_payload=input_payload, output_payload=raw,
                ))
            plan = ManagedActionPlan.from_dict(raw, source="llm")
            if plan.actions:
                return plan, advisor
        except Exception as exc:
            task_id = str(job.get("task_id") or "")
            if task_id:
                append_llm_trace(task_id, llm_trace_record(
                    stage="managed_actions", advisor=advisor, started_at=started_at,
                    status="error", input_payload=input_payload, error=str(exc),
                ))
            advisor = None
    return build_deterministic_action_plan(
        target_url=target_url, profile=profile_data, run_spec=run_spec,
        progress=progress, diagnostics={**diagnostics, "evidence_pack": evidence_pack},
        supervision=supervision, extra_context=extra_context,
    ), advisor


def _execute_managed_actions_for_job(
    *, task_id: str, job: dict[str, Any], request: ManagedActionsRequest,
) -> dict[str, Any]:
    plan, advisor = _build_managed_action_plan_for_job(job=job, request=request)
    payload = _product_run_payload_from_job(job)
    profile_data = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    extra_context = _managed_extra_context_from_profile(profile_data, request.extra_context)
    progress = summarize_run_progress(job)
    diagnostics = job.get("diagnostics") if isinstance(job.get("diagnostics"), dict) else {}
    supervision = job.get("supervision") if isinstance(job.get("supervision"), dict) else {}
    result = (
        execute_managed_action_plan(
            plan=plan, target_url=str(payload.get("target_url") or ""),
            profile=profile_data,
            run_spec=job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {},
            advisor=advisor, extra_context=extra_context, job=job,
            llm_decide=bool(request.llm_decide and advisor is not None),
            llm_decision_callback=lambda decision: append_ai_decision(task_id, decision),
            llm_trace_callback=lambda trace: append_llm_trace(task_id, trace),
            progress=progress,
            diagnostics=diagnostics,
            supervision=supervision,
        )
        if request.execute
        else {
            "schema_version": "managed-action-result/v1", "plan": plan.to_dict(),
            "results": [], "profile_patch": {}, "run_overrides": {}, "rerun_ready": False,
        }
    )
    record = {"created_at": datetime.now(timezone.utc).isoformat(), "executed": bool(request.execute), "result": result}
    _append_managed_action_record(task_id, record)
    return {"task_id": task_id, **record}


def _managed_extra_context_from_profile(
    profile_data: dict[str, Any],
    extra_context: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(extra_context or {})
    constraints = profile_data.get("constraints") if isinstance(profile_data.get("constraints"), dict) else {}
    if "extraction_contract" not in merged and isinstance(constraints.get("extraction_contract"), dict):
        merged["extraction_contract"] = constraints.get("extraction_contract")
    if "contract" not in merged and isinstance(constraints.get("extraction_contract"), dict):
        merged["contract"] = constraints.get("extraction_contract")
    if "extraction_contract_discovery" not in merged and isinstance(constraints.get("extraction_contract_discovery"), dict):
        merged["extraction_contract_discovery"] = constraints.get("extraction_contract_discovery")
    if "extraction_evidence" not in merged and constraints.get("extraction_evidence") not in (None, ""):
        merged["extraction_evidence"] = constraints.get("extraction_evidence")
    if "evidence" not in merged and constraints.get("extraction_evidence") not in (None, ""):
        merged["evidence"] = constraints.get("extraction_evidence")
    if "source_url" not in merged and constraints.get("extraction_evidence_source_url"):
        merged["source_url"] = str(constraints.get("extraction_evidence_source_url") or "")
    return merged


def _merge_extra_extraction_context(
    managed_llm_context: dict[str, Any],
    extra_context: dict[str, Any],
) -> dict[str, Any]:
    context = dict(managed_llm_context or {})
    extra = extra_context if isinstance(extra_context, dict) else {}
    contract = extra.get("extraction_contract")
    if not isinstance(contract, dict):
        contract = extra.get("contract")
    evidence = extra.get("extraction_evidence")
    if evidence in (None, ""):
        evidence = extra.get("evidence")
    if not isinstance(contract, dict) and evidence in (None, ""):
        return context
    extraction_context = dict(context.get("extraction_context") or {})
    strategy = contract.get("parser_strategy") if isinstance(contract, dict) and isinstance(contract.get("parser_strategy"), dict) else {}
    extraction_context.update({
        "has_contract": isinstance(contract, dict) and bool(contract),
        "site": contract.get("site", "") if isinstance(contract, dict) else "",
        "parser_strategy": strategy.get("name", "") if isinstance(strategy, dict) else "",
        "source_url": (
            extra.get("source_url")
            or (contract.get("source_url", "") if isinstance(contract, dict) else "")
        ),
        "has_evidence": evidence not in (None, ""),
        "evidence_type": type(evidence).__name__ if evidence not in (None, "") else "",
        "evidence_size": len(evidence) if isinstance(evidence, (str, list, dict)) else 0,
        "can_execute_extract_from_contract": bool(isinstance(contract, dict) and contract and evidence not in (None, "")),
    })
    context["extraction_context"] = extraction_context
    return context


def _append_managed_action_record(task_id: str, record: dict[str, Any]) -> None:
    job = get_job(task_id) or {}
    records = list(job.get("managed_actions") or [])
    records.append(record)
    update_job(task_id, managed_actions=records[-50:])


def _append_managed_step_record(task_id: str, record: dict[str, Any]) -> None:
    job = get_job(task_id) or {}
    records = list(job.get("managed_steps") or [])
    records.append(record)
    update_job(task_id, managed_steps=records[-50:])


def _append_access_probe_record(task_id: str, record: dict[str, Any]) -> None:
    job = get_job(task_id) or {}
    records = list(job.get("access_probe_history") or [])
    records.append(record)
    update_job(task_id, access_probe_history=records[-20:], latest_access_probe=record)


def _append_managed_control_record(task_id: str, record: dict[str, Any]) -> None:
    job = get_job(task_id) or {}
    records = list(job.get("managed_control_loops") or [])
    records.append(record)
    update_job(task_id, managed_control_loops=records[-30:], latest_managed_control_loop=record)


def _managed_step_stage_for_job(job: dict[str, Any]) -> str:
    status = str(job.get("status") or "").lower()
    if status in {"queued", "running"}:
        return "runtime_supervision"
    if status in {"paused", "failed", "aborted", "partial"}:
        return "repair_after_failure"
    if status in {"completed", "finished"}:
        return "quality_review"
    return "planning"


# ---------------------------------------------------------------------------
# Supervision / repair helpers
# ---------------------------------------------------------------------------


def _supervision_from_result(result: dict[str, Any]) -> dict[str, Any] | None:
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    supervision = diagnostics.get("supervision") if isinstance(diagnostics.get("supervision"), dict) else {}
    if supervision:
        return supervision
    runner = result.get("runner_summary") if isinstance(result.get("runner_summary"), dict) else {}
    events = runner.get("supervision_events") if isinstance(runner.get("supervision_events"), list) else []
    if not events:
        return None
    return {"enabled": True, "event_count": len(events), "last_event": events[-1]}


def _repair_overrides_from_supervision(supervision: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(supervision, dict):
        return {}
    last = supervision.get("last_event") if isinstance(supervision.get("last_event"), dict) else {}
    action = str(last.get("action") or "").strip().lower()
    reason = str(last.get("reason") or "").lower()
    suggestions = last.get("suggestions") if isinstance(last.get("suggestions"), list) else []
    suggestion_actions = {
        str(item.get("action") or "").strip().lower()
        for item in suggestions if isinstance(item, dict)
    }
    overrides: dict[str, Any] = {}
    if action in {"pause", "abort", "repair_after_run"}:
        overrides.setdefault("access_config", {})
        challenge_hint = "challenge" in reason or "captcha" in reason
        overrides["access_config"].update({
            "mode": "protected" if challenge_hint else "dynamic",
            "wait_until": "domcontentloaded" if challenge_hint else "networkidle",
            "browser_config": {
                "capture_api": True, "auto_accept_cookies": True,
                "render_time_ms": 5000 if challenge_hint else 3000,
                "max_wait_ms": 45000 if challenge_hint else 30000,
                "persistent_context": challenge_hint,
                "close_persistent_context": not challenge_hint,
                "pool_enabled": challenge_hint,
                "pool_id": "managed-protected" if challenge_hint else "",
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


def _managed_run_depth(job: dict[str, Any]) -> int:
    depth = 0
    current = job
    seen: set[str] = set()
    while True:
        parent_id = str(current.get("parent_task_id") or "")
        if not parent_id or parent_id in seen:
            return depth
        seen.add(parent_id)
        parent = get_job(parent_id)
        if not parent:
            return depth + 1
        depth += 1
        current = parent


def _run_needs_managed_repair(job: dict[str, Any], result: dict[str, Any]) -> bool:
    status = str(result.get("status") or job.get("status") or "").lower()
    if status in {"paused", "aborted", "failed", "partial"}:
        return True
    if result.get("accepted") is False:
        return True
    stats = result.get("product_stats") if isinstance(result.get("product_stats"), dict) else {}
    if int(stats.get("total") or 0) <= 0:
        return True
    progress = summarize_run_progress({**job, "profile_run": result})
    quality = str(progress.get("quality_indicator") or "").lower()
    return quality in {"fail", "unknown"}


def _start_managed_child_run(
    *, task_id: str, job: dict[str, Any], request: AIRerunRequest,
) -> dict[str, Any]:
    payload = _product_run_payload_from_job(job)
    overrides: dict[str, Any] = {}
    diagnostics = job.get("ai_diagnostics") if isinstance(job.get("ai_diagnostics"), dict) else {}
    if request.apply_diagnostics and isinstance(diagnostics.get("next_run_overrides"), dict):
        overrides.update(diagnostics.get("next_run_overrides") or {})
    supervision_overrides = _repair_overrides_from_supervision(
        job.get("supervision") if isinstance(job.get("supervision"), dict) else {}
    )
    if request.apply_diagnostics and supervision_overrides:
        overrides = deep_merge_dicts(overrides, supervision_overrides)
    managed_records = job.get("managed_actions") if isinstance(job.get("managed_actions"), list) else []
    if request.apply_diagnostics and managed_records:
        latest = managed_records[-1] if isinstance(managed_records[-1], dict) else {}
        result_payload = latest.get("result") if isinstance(latest.get("result"), dict) else {}
        action_overrides = result_payload.get("run_overrides") if isinstance(result_payload.get("run_overrides"), dict) else {}
        if action_overrides:
            overrides = deep_merge_dicts(overrides, action_overrides)
    overrides.update(dict(request.extra_overrides or {}))

    patched_spec, patched_profile, patch_result = _apply_managed_run_overrides(
        payload, payload.get("profile") if isinstance(payload.get("profile"), dict) else {}, overrides,
    )
    patched_spec["profile"] = patched_profile
    spec = build_run_spec(patched_spec)
    run_kind = safe_choice(request.run_kind, {"test", "full"}, "")
    if not run_kind:
        run_kind = "full" if job.get("kind") == "product_full_run" else "test"
    result = register_product_run_job(
        kind="product_full_run" if run_kind == "full" else "product_test_run",
        run_payload=build_full_run_payload(spec) if run_kind == "full" else build_test_run_payload(spec),
        spec=spec, managed_ai=request.managed_ai, llm=request.llm,
    )
    child_id = result["task_id"]
    update_job(
        child_id, parent_task_id=task_id, repair_source="ai_rerun",
        ai_patch_applications=[{**patch_result, "source_task_id": task_id, "source": "ai_diagnostics.next_run_overrides"}],
    )
    return {**result, "parent_task_id": task_id, "repair_source": "ai_rerun", "patch_application": patch_result}


# ---------------------------------------------------------------------------
# Product run registration
# ---------------------------------------------------------------------------


def register_product_run_job(
    *, kind: str, run_payload: dict[str, Any], spec: CrawlRunSpec,
    managed_ai: ManagedAIConfig | None = None, llm: LLMConfig | None = None,
) -> dict[str, Any]:
    profile = SiteProfile.from_dict(run_payload["profile"])
    advisor = None
    if managed_ai and managed_ai.enabled:
        if not llm or not llm.enabled:
            raise HTTPException(status_code=400, detail="managed_ai requires llm.enabled=true")
        try:
            advisor = build_advisor_from_config(llm)
        except LLMConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    pre_decision: dict[str, Any] | None = None
    patch_result: dict[str, Any] | None = None
    pre_trace: dict[str, Any] | None = None
    if advisor is not None and managed_ai_wants_pre_run(managed_ai):
        pre_decision = normalize_ai_decision("pre_run_review", advisor, {})
        started_at = time.perf_counter()
        input_payload = {"run_spec": _product_spec_summary(spec), "profile": profile.to_dict()}
        try:
            raw = advisor.review_run_plan(input_payload["run_spec"], input_payload["profile"])
            pre_decision = normalize_ai_decision("pre_run_review", advisor, raw)
            pre_trace = llm_trace_record(
                stage="pre_run_review", advisor=advisor, started_at=started_at,
                status="ok", input_payload=input_payload, output_payload=raw,
            )
        except Exception as exc:
            pre_decision = ai_error_decision("pre_run_review", exc)
            pre_trace = llm_trace_record(
                stage="pre_run_review", advisor=advisor, started_at=started_at,
                status="error", input_payload=input_payload, error=str(exc),
            )
        if managed_ai and managed_ai.apply_pre_run_patch and not pre_decision.get("fallback_used"):
            patched_profile, patch_result = _apply_managed_profile_patch(
                profile.to_dict(),
                pre_decision.get("profile_patch") if isinstance(pre_decision.get("profile_patch"), dict) else {},
            )
            if patch_result and patch_result.get("applied"):
                profile = SiteProfile.from_dict(patched_profile)

    request = ProfileRunRequest(
        profile=profile.to_dict(), run_id=str(run_payload.get("run_id") or ""),
        batch_size=int(run_payload.get("batch_size") or 20),
        max_batches=int(run_payload.get("max_batches") or 0),
        item_workers=int(run_payload.get("item_workers") or spec.item_workers),
        runtime_dir=str(run_payload.get("runtime_dir") or spec.runtime_dir),
        supervision_mode=supervision_mode_for_managed_ai(managed_ai),
        adaptive_item_workers=True, min_item_workers=1,
        max_item_workers=max(int(run_payload.get("item_workers") or spec.item_workers), 1),
        managed_ai=managed_ai, llm=llm,
    )
    task_id = str(uuid.uuid4())[:8]
    if not try_register_job(task_id, f"{kind}:{profile.name}", _first_profile_target(profile), kind=kind):
        raise HTTPException(status_code=429, detail=f"too many active jobs ({_max_active_jobs_ref()} max)")
    update_job(
        task_id, run_id=request.run_id, profile_name=profile.name, kind=kind,
        product_run_spec={
            "target_url": spec.target_url, "profile": profile.to_dict(),
            "catalog_nodes": list(spec.catalog_nodes), "selected_fields": list(spec.selected_fields),
            "run_mode": spec.run_mode, "item_workers": spec.item_workers,
            "max_sites": spec.max_sites, "test_limit": spec.test_limit,
            "runtime_dir": request.runtime_dir,
            "export": {"format": spec.export.format, "output_path": spec.export.output_path,
                       "template_path": spec.export.template_path, "field_mapping": dict(spec.export.field_mapping)},
            "auto_export": bool(spec.export.output_path),
            "supervision_mode": supervision_mode_for_managed_ai(managed_ai),
        },
        managed_ai=managed_ai_public_config(managed_ai, llm),
        ai_decisions=[], ai_diagnostics=None, ai_repair_suggestions=[],
        ai_patch_applications=[], managed_actions=[], llm_traces=[],
    )
    if pre_decision is not None:
        append_ai_decision(task_id, pre_decision)
    if pre_trace is not None:
        append_llm_trace(task_id, pre_trace)
    if patch_result is not None:
        update_job(task_id, ai_patch_applications=[patch_result])
    thread = threading.Thread(target=_background_profile_run, args=(task_id, request), daemon=True)
    thread.start()
    return {
        "task_id": task_id, "run_id": request.run_id, "status": "running",
        "profile_name": profile.name, "record_count": 0, "accepted": False,
    }


def _max_active_jobs_ref() -> int:
    from ..deps import _max_active_jobs
    return _max_active_jobs()


def _first_profile_target(profile: SiteProfile) -> str:
    endpoint = str(profile.api_hints.get("endpoint") or "").strip()
    if endpoint:
        return endpoint
    seeds = profile.crawl_preferences.get("seed_urls") or profile.constraints.get("seed_urls") or []
    return str(seeds[0]) if seeds else ""


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------


def _background_profile_run(task_id: str, request: ProfileRunRequest) -> None:
    try:
        result = run_profile_longrun_workflow(request, task_id=task_id)
        if _is_cancelled_ref(task_id):
            return
        update_job(
            task_id,
            item_count=int(result.get("product_stats", {}).get("total") or 0),
            is_valid=bool(result.get("accepted")),
            profile_run=result,
            diagnostics=result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else None,
            supervision=_supervision_from_result(result),
        )
        auto_export = _auto_export_product_run(task_id, request, result)
        if managed_ai_enabled(request.managed_ai, request.llm) and managed_ai_wants_post_run(request.managed_ai):
            advisor = build_advisor_from_config(request.llm)  # type: ignore[arg-type]
            _run_managed_post_diagnosis(task_id=task_id, advisor=advisor, request=request, result=result)
        auto_repair = _auto_managed_repair_after_run(task_id=task_id, request=request, result=result)
        update_job(
            task_id,
            status=result.get("status", "completed"),
            export=auto_export or None,
            managed_auto_repair=auto_repair or (get_job(task_id) or {}).get("managed_auto_repair"),
        )
    except Exception as exc:
        if _is_cancelled_ref(task_id):
            return
        update_job(task_id, status="failed", error=str(exc), error_code="PROFILE_RUN_FAILED")


def _is_cancelled_ref(task_id: str) -> bool:
    from ..deps import is_cancelled
    return is_cancelled(task_id)


def _auto_export_product_run(task_id: str, request: ProfileRunRequest, result: dict[str, Any]) -> dict[str, Any] | None:
    job = get_job(task_id)
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
            "record_count": 0, "error": str(exc),
        }


def _run_managed_post_diagnosis(
    *, task_id: str, advisor: OpenAICompatibleAdvisor, request: ProfileRunRequest, result: dict[str, Any],
) -> None:
    job = get_job(task_id) or {}
    spec_payload = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    profile_payload = request.profile or {}
    progress = summarize_run_progress({**job, "profile_run": result})
    started_at = time.perf_counter()
    input_payload = {"run_spec": spec_payload, "profile": profile_payload, "run_result": result, "progress": progress}
    try:
        raw = advisor.diagnose_run_result(spec_payload, profile_payload, result, progress)
        decision = normalize_ai_decision("post_run_diagnosis", advisor, raw)
        append_llm_trace(task_id, llm_trace_record(
            stage="post_run_diagnosis", advisor=advisor, started_at=started_at,
            status="ok", input_payload=input_payload, output_payload=raw,
        ))
    except Exception as exc:
        decision = ai_error_decision("post_run_diagnosis", exc)
        append_llm_trace(task_id, llm_trace_record(
            stage="post_run_diagnosis", advisor=advisor, started_at=started_at,
            status="error", input_payload=input_payload, error=str(exc),
        ))
    diagnostics = ai_diagnostics_from_decision(decision)
    append_ai_decision(task_id, decision)
    update_job(task_id, ai_diagnostics=diagnostics, ai_repair_suggestions=list(diagnostics.get("repair_suggestions") or []))


def _auto_managed_repair_after_run(
    *, task_id: str, request: ProfileRunRequest, result: dict[str, Any],
) -> dict[str, Any] | None:
    job = get_job(task_id) or {}
    if not managed_ai_enabled(request.managed_ai, request.llm):
        return None
    if not managed_ai_wants_auto_repair(request.managed_ai):
        return None
    if _managed_run_depth(job) >= 1:
        update_job(task_id, managed_auto_repair={
            "attempted": False, "reason": "max_auto_repair_depth_reached",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return None
    if not _run_needs_managed_repair(job, result):
        update_job(task_id, managed_auto_repair={
            "attempted": False, "reason": "quality_accepted",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return None

    action_record = _execute_managed_actions_for_job(
        task_id=task_id, job=job,
        request=ManagedActionsRequest(
            execute=True, use_llm=True,
            extra_context={
                "field_goal": ", ".join(str(item) for item in (job.get("product_run_spec") or {}).get("selected_fields", [])),
                "selected_fields": (job.get("product_run_spec") or {}).get("selected_fields", []),
                "export": (job.get("product_run_spec") or {}).get("export", {}),
            },
            llm=request.llm,
        ),
    )
    repair = _start_managed_child_run(
        task_id=task_id, job=job,
        request=AIRerunRequest(
            run_kind="full" if job.get("kind") == "product_full_run" else "test",
            apply_diagnostics=True,
            managed_ai=ManagedAIConfig(
                enabled=True, mode="supervised", pre_run_review=True, post_run_diagnosis=True,
                apply_pre_run_patch=bool(request.managed_ai and request.managed_ai.apply_pre_run_patch),
                auto_repair=False,
            ),
            llm=request.llm,
        ),
    )
    auto_repair = {
        "attempted": True, "reason": "full_managed_quality_repair",
        "child_task_id": repair.get("task_id", ""), "child_run_id": repair.get("run_id", ""),
        "managed_action": action_record, "created_at": datetime.now(timezone.utc).isoformat(),
    }
    update_job(task_id, managed_auto_repair=auto_repair)
    return auto_repair


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.post("/runs/test")
def product_test_run(request: ProductRunRequest) -> dict[str, Any]:
    spec = build_run_spec(request.model_dump())
    return register_product_run_job(
        kind="product_test_run", run_payload=build_test_run_payload(spec),
        spec=spec, managed_ai=request.managed_ai, llm=request.llm,
    )


@router.post("/runs/full")
def product_full_run(request: ProductRunRequest) -> dict[str, Any]:
    spec = build_run_spec(request.model_dump())
    return register_product_run_job(
        kind="product_full_run", run_payload=build_full_run_payload(spec),
        spec=spec, managed_ai=request.managed_ai, llm=request.llm,
    )


@router.get("/runs/{task_id}/status")
def product_run_status(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    progress = summarize_run_progress(job)
    managed_state = build_managed_crawl_state(job)
    return {
        "task_id": task_id, "parent_task_id": job.get("parent_task_id", ""),
        "repair_source": job.get("repair_source", ""), "kind": job.get("kind", ""),
        "run_id": job.get("run_id", ""), "status": job.get("status", ""),
        "record_count": job.get("item_count", 0), "accepted": job.get("is_valid", False),
        "error": job.get("error", ""), "progress": progress,
        "product_run_spec": job.get("product_run_spec") or None,
        "current_stage": progress.get("current_stage", ""),
        "last_error": progress.get("last_error", ""),
        "progress_summary": progress.get("progress_summary", ""),
        "quality_indicator": progress.get("quality_indicator", "unknown"),
        "diagnostics": job.get("diagnostics") or None,
        "supervision": job.get("supervision") or None,
        "evidence_pack": build_run_evidence_pack(job),
        "export": job.get("export") or None,
        "managed_ai": job.get("managed_ai") or {"enabled": False},
        "ai_decisions": job.get("ai_decisions") or [],
        "ai_diagnostics": job.get("ai_diagnostics") or None,
        "ai_repair_suggestions": job.get("ai_repair_suggestions") or [],
        "ai_patch_applications": job.get("ai_patch_applications") or [],
        "managed_actions": job.get("managed_actions") or [],
        "managed_steps": job.get("managed_steps") or [],
        "access_probe_history": job.get("access_probe_history") or [],
        "latest_access_probe": job.get("latest_access_probe") or None,
        "managed_control_loops": job.get("managed_control_loops") or [],
        "latest_managed_control_loop": job.get("latest_managed_control_loop") or None,
        "managed_auto_repair": job.get("managed_auto_repair") or None,
        "llm_traces": job.get("llm_traces") or [],
        "managed_state": managed_state,
        "managed_llm_context": compact_managed_state_for_llm(managed_state),
    }


@router.get("/runs/{task_id}/managed-state")
def product_managed_state(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    state = build_managed_crawl_state(job)
    return {"task_id": task_id, "schema_version": state.get("schema_version", ""), "state": state, "llm_context": compact_managed_state_for_llm(state)}


@router.get("/runs/{task_id}/events")
def product_run_events(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    return {"task_id": task_id, "events": events_for_job(job)}


@router.post("/runs/{task_id}/managed-actions")
def product_managed_actions(task_id: str, request: ManagedActionsRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    if job.get("kind") not in {"product_test_run", "product_full_run"}:
        raise HTTPException(status_code=400, detail="managed actions are only available for product runs")
    try:
        return _execute_managed_actions_for_job(task_id=task_id, job=job, request=request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/runs/{task_id}/managed-step")
def product_managed_step(task_id: str, request: ManagedStepRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    if job.get("kind") not in {"product_test_run", "product_full_run"}:
        raise HTTPException(status_code=400, detail="managed step is only available for product runs")
    try:
        return _execute_managed_step_for_job(task_id=task_id, job=job, request=request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _execute_managed_step_for_job(
    *, task_id: str, job: dict[str, Any], request: ManagedStepRequest,
) -> dict[str, Any]:
    progress = summarize_run_progress(job)
    evidence_pack = build_run_evidence_pack(job)
    stage = _managed_step_stage_for_job(job)
    action_request = ManagedActionsRequest(
        execute=request.execute, use_llm=request.use_llm,
        extra_context={"managed_step_stage": stage, "progress": progress, "evidence_pack": evidence_pack, **dict(request.extra_context or {})},
        llm=request.llm,
    )
    action_record = _execute_managed_actions_for_job(task_id=task_id, job=job, request=action_request)
    if action_record.get("result") and isinstance(action_record["result"], dict):
        evidence = action_record["result"].get("evidence") if isinstance(action_record["result"].get("evidence"), dict) else None
        if evidence:
            access = evidence.get("access") if isinstance(evidence.get("access"), dict) else {}
            snapshot = evidence.get("access_snapshot") if isinstance(evidence.get("access_snapshot"), dict) else {}
            evidence_pack = {**evidence_pack, "access_evidence_request": access or evidence, "access_evidence": snapshot or evidence_pack.get("access_evidence") or {}}
    child_run: dict[str, Any] | None = None
    if request.start_child_run:
        child_run = _start_managed_child_run(
            task_id=task_id, job=get_job(task_id) or job,
            request=AIRerunRequest(run_kind=request.run_kind, apply_diagnostics=request.apply_diagnostics, extra_overrides=request.extra_overrides, managed_ai=request.managed_ai, llm=request.llm),
        )
    step_record = {
        "schema_version": "managed-step/v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage, "status_before": job.get("status", ""), "progress": progress,
        "evidence_pack": evidence_pack, "action_record": action_record, "child_run": child_run,
    }
    _append_managed_step_record(task_id, step_record)
    return {"task_id": task_id, **step_record}


@router.post("/runs/{task_id}/access-probe")
def product_access_probe(task_id: str, request: AccessProbeRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    if job.get("kind") not in {"product_test_run", "product_full_run", "profile_run"}:
        raise HTTPException(status_code=400, detail="access probe is only available for crawl runs")
    try:
        result = _execute_access_probe_for_job(task_id=task_id, job=job, request=request)
        _append_access_probe_record(task_id, result)
        return result
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _execute_access_probe_for_job(
    *, task_id: str, job: dict[str, Any], request: AccessProbeRequest,
) -> dict[str, Any]:
    profile = request.profile if isinstance(request.profile, dict) else {}
    if not profile:
        payload = _product_run_payload_from_job(job)
        profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    action = ManagedCrawlAction.from_dict({
        "action": "inspect_access",
        "params": {"live_probe": request.live_probe, "sample_limit": request.sample_limit},
    })
    result = _execute_inspect_access(
        action, target_url=str(request.target_url or job.get("target_url") or ""), profile=profile, job=job,
    )
    evidence = result.get("evidence") if isinstance(result.get("evidence"), dict) else {}
    snapshot = evidence.get("snapshot") if isinstance(evidence.get("snapshot"), dict) else {}
    base_snapshot = evidence.get("base_snapshot") if isinstance(evidence.get("base_snapshot"), dict) else {}
    response = {
        "task_id": task_id, "schema_version": "access-probe-response/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_url": str(request.target_url or job.get("target_url") or ""),
        "live_probe": bool(request.live_probe), "sample_limit": request.sample_limit,
        "result": result, "snapshot": snapshot, "base_snapshot": base_snapshot,
        "probe_snapshot": snapshot if snapshot.get("schema_version") == "access-probe/v1" else {},
    }
    if task_id:
        update_job(task_id, latest_access_probe=response)
    return response


@router.post("/runs/{task_id}/managed-control-loop")
def product_managed_control_loop(task_id: str, request: ManagedControlLoopRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    if job.get("kind") not in {"product_test_run", "product_full_run"}:
        raise HTTPException(status_code=400, detail="managed control loop is only available for product runs")
    try:
        return _execute_managed_control_loop_for_job(task_id=task_id, job=job, request=request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _execute_managed_control_loop_for_job(
    *, task_id: str, job: dict[str, Any], request: ManagedControlLoopRequest,
) -> dict[str, Any]:
    progress = summarize_run_progress(job)
    evidence_before = build_run_evidence_pack(job)
    stage = _managed_step_stage_for_job(job)
    payload = _product_run_payload_from_job(job)
    timeline: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc).isoformat()

    timeline.append({"stage": "observe", "status": "ok", "message": f"observed {job.get('status', 'unknown')} run",
                      "data": {"progress": progress, "recommended_focus": evidence_before.get("recommended_focus", [])}})

    access_probe: dict[str, Any] | None = None
    if request.include_access_probe:
        probe_request = AccessProbeRequest(
            target_url=str(payload.get("target_url") or job.get("target_url") or ""),
            task_id=task_id, live_probe=request.live_probe, sample_limit=3,
            profile=payload.get("profile") if isinstance(payload.get("profile"), dict) else {},
            extra_context=request.extra_context, llm=request.llm,
        )
        access_probe = _execute_access_probe_for_job(task_id=task_id, job=job, request=probe_request)
        _append_access_probe_record(task_id, access_probe)
        timeline.append({"stage": "access_probe", "status": "ok", "message": "access evidence prepared",
                          "data": {"live_probe": access_probe.get("live_probe"),
                                   "snapshot_version": (access_probe.get("snapshot") or {}).get("schema_version"),
                                   "recommended_runtime": ((access_probe.get("snapshot") or {}).get("summary") or {}).get("recommended_runtime", "")}})

    action_request = ManagedActionsRequest(
        execute=request.execute, use_llm=request.use_llm,
        extra_context={"control_loop_stage": stage, "progress": progress, "evidence_pack": evidence_before, **dict(request.extra_context or {})},
        llm=request.llm,
    )
    action_record = _execute_managed_actions_for_job(task_id=task_id, job=get_job(task_id) or job, request=action_request)
    action_result = action_record.get("result") if isinstance(action_record.get("result"), dict) else {}
    plan = action_result.get("plan") if isinstance(action_result.get("plan"), dict) else {}
    actions = plan.get("actions") if isinstance(plan.get("actions"), list) else []
    timeline.append({"stage": "plan_act", "status": "ok",
                      "message": f"{'executed' if request.execute else 'planned'} {len(actions)} managed actions",
                      "data": {"plan_source": plan.get("source", ""), "action_count": len(actions), "rerun_ready": bool(action_result.get("rerun_ready"))}})

    child_run: dict[str, Any] | None = None
    if request.start_child_run:
        child_run = _start_managed_child_run(
            task_id=task_id, job=get_job(task_id) or job,
            request=AIRerunRequest(run_kind=request.run_kind, apply_diagnostics=request.apply_diagnostics,
                                    extra_overrides=request.extra_overrides, managed_ai=request.managed_ai, llm=request.llm),
        )
        timeline.append({"stage": "repair_rerun", "status": "ok", "message": f"started child run {child_run.get('task_id', '')}", "data": child_run})

    evidence_after = build_run_evidence_pack(get_job(task_id) or job)
    record = {
        "schema_version": "managed-control-loop/v1", "created_at": created_at, "stage": stage,
        "status_before": job.get("status", ""), "progress": progress,
        "evidence_before": evidence_before, "evidence_after": evidence_after,
        "access_probe": access_probe, "action_record": action_record, "child_run": child_run, "timeline": timeline,
    }
    _append_managed_control_record(task_id, record)
    return {"task_id": task_id, **record}


@router.post("/runs/{task_id}/managed-repair-run")
def product_managed_repair_run(task_id: str, request: ManagedRepairRunRequest) -> dict[str, Any]:
    action_record = product_managed_actions(task_id, request)
    rerun = product_ai_rerun(
        task_id,
        AIRerunRequest(run_kind=request.run_kind, apply_diagnostics=request.apply_diagnostics,
                        extra_overrides=request.extra_overrides, managed_ai=request.managed_ai, llm=request.llm),
    )
    return {**rerun, "repair_source": "managed_actions", "managed_action": action_record}


@router.post("/runs/{task_id}/ai-rerun")
def product_ai_rerun(task_id: str, request: AIRerunRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    if job.get("kind") not in {"product_test_run", "product_full_run"}:
        raise HTTPException(status_code=400, detail="ai rerun is only available for product runs")
    return _start_managed_child_run(task_id=task_id, job=job, request=request)


# ---------------------------------------------------------------------------
# Auto-Repair: Failure Diagnosis and Closed-Loop Repair
# ---------------------------------------------------------------------------


@router.post("/runs/{task_id}/auto-repair-diagnose")
def auto_repair_diagnose(task_id: str, request: AutoRepairDiagnoseRequest) -> dict[str, Any]:
    """Diagnose failures in a run without executing repairs.

    Returns a DiagnosisReport with classified failures, severity, evidence,
    and suggested repair actions.
    """
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    run_spec = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    profile = _profile_from_job_local(job, run_spec)
    diagnoser = FailureDiagnoser()
    report = diagnoser.diagnose(
        job=job,
        execution_result=request.execution_result,
        profile=profile,
    )
    record = {
        "task_id": task_id,
        "diagnosis": report.to_dict(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append_auto_repair_record(task_id, record)
    return record


@router.post("/runs/{task_id}/auto-repair-loop")
def auto_repair_loop(task_id: str, request: AutoRepairLoopRequest) -> dict[str, Any]:
    """Run the full auto-repair loop: diagnose -> repair -> re-execute.

    Runs up to max_cycles iterations, applying repair actions and re-diagnosing
    after each cycle. Stops when health is good or max cycles reached.
    """
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="run not found")
    if job.get("kind") not in {"product_test_run", "product_full_run"}:
        raise HTTPException(status_code=400, detail="auto-repair is only available for product runs")

    run_spec = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    profile = _profile_from_job_local(job, run_spec)
    target_url = run_spec.get("target_url") or job.get("target_url") or ""

    advisor = None
    if request.llm and request.llm.base_url and request.llm.model:
        try:
            advisor = OpenAICompatibleAdvisor(
                base_url=request.llm.base_url,
                model=request.llm.model,
                api_key=request.llm.api_key or "",
            )
        except Exception:
            pass

    def _executor_fn(*, repair_actions: list, cycle: int, diagnosis: Any) -> dict[str, Any]:
        """Execute repair actions and return updated job state."""
        plan = ManagedActionPlan(actions=repair_actions, source=f"auto_repair_cycle_{cycle}")
        action_result = execute_managed_action_plan(
            plan=plan,
            target_url=target_url,
            profile=profile,
            run_spec=run_spec,
            advisor=advisor,
            extra_context=request.extra_context,
            job=job,
        )
        # Apply profile patches
        patch = action_result.get("profile_patch") or {}
        if patch:
            profile.update(patch)
        # Start a child run with accumulated patches
        overrides = action_result.get("run_overrides") or {}
        child_request = AIRerunRequest(
            run_kind="test",
            apply_diagnostics=True,
            extra_overrides=overrides,
            managed_ai={"enabled": True},
            llm=request.llm,
        )
        child = _start_managed_child_run(task_id=task_id, job=job, request=child_request)
        return child

    loop = AutoRepairLoop(
        max_cycles=request.max_cycles,
        advisor=advisor,
    )
    result = loop.run(
        job=job,
        profile=profile,
        target_url=target_url,
        executor_fn=_executor_fn,
        run_spec=run_spec,
        extra_context=request.extra_context,
    )
    record = {
        "task_id": task_id,
        "auto_repair_result": result.to_dict(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append_auto_repair_record(task_id, record)
    return record


def _profile_from_job_local(job: dict[str, Any], run_spec: dict[str, Any]) -> dict[str, Any]:
    """Extract profile from job or run_spec."""
    profile = run_spec.get("profile") if isinstance(run_spec.get("profile"), dict) else {}
    if profile:
        return dict(profile)
    profile_run = job.get("profile_run") if isinstance(job.get("profile_run"), dict) else {}
    report = profile_run.get("report") if isinstance(profile_run.get("report"), dict) else {}
    if isinstance(report.get("profile"), dict):
        return dict(report["profile"])
    return {}


def _append_auto_repair_record(task_id: str, record: dict[str, Any]) -> None:
    """Append auto-repair record to job history."""
    job = get_job(task_id)
    if not job:
        return
    records = list(job.get("auto_repair_history") or [])
    records.append(record)
    update_job(task_id, auto_repair_history=records[-50:])


# ---------------------------------------------------------------------------
# Standalone managed execute-and-run endpoint
# ---------------------------------------------------------------------------


@router.post("/runs/managed")
def managed_execute_and_run(request: ManagedRunRequest) -> dict[str, Any]:
    """Execute a managed action plan and run the crawl in one shot.

    This is the **closed-loop** entry point: it builds an action plan,
    executes it (applying profile patches), then immediately runs the
    crawl with the patched profile.
    """
    from uuid import uuid4

    task_id = "managed-" + uuid4().hex[:12]

    # Build advisor if LLM config provided
    advisor = None
    if request.llm and request.llm.enabled:
        try:
            from ...llm import OpenAICompatibleAdvisor
            advisor = OpenAICompatibleAdvisor(
                base_url=request.llm.base_url,
                model=request.llm.model,
                api_key=request.llm.api_key or "",
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"LLM init failed: {exc}")

    # Register job
    try_register_job(
        task_id,
        job_type="managed_run",
        target_url=request.target_url,
        status="running",
        managed_ai=managed_ai_public_config(request.managed_ai, request.llm),
    )

    try:
        result = execute_and_run(
            target_url=request.target_url,
            profile=request.profile,
            run_spec=request.run_spec,
            advisor=advisor,
            extra_context=request.extra_context,
            llm_decide=request.llm_decide,
            batch_size=request.batch_size,
            max_batches=request.max_batches,
            item_workers=request.item_workers,
            runtime_dir=request.runtime_dir,
            run_mode=request.run_mode,
        )
        update_job(
            task_id,
            status=result.get("run_status", "completed"),
            managed_run_result=result,
        )
        return {"task_id": task_id, **result}
    except Exception as exc:
        update_job(task_id, status="failed", error=str(exc)[:500])
        raise HTTPException(status_code=500, detail=str(exc)[:500])


@router.post("/runs/managed/repair")
def managed_diagnose_and_repair(request: ManagedRepairRequest) -> dict[str, Any]:
    """Diagnose failures and auto-repair in one shot.

    This endpoint takes a target URL + profile, runs the crawl,
    diagnoses failures, generates repair actions, and re-runs.
    """
    from uuid import uuid4

    task_id = "repair-" + uuid4().hex[:12]

    advisor = None
    if request.llm and request.llm.enabled:
        try:
            from ...llm import OpenAICompatibleAdvisor
            advisor = OpenAICompatibleAdvisor(
                base_url=request.llm.base_url,
                model=request.llm.model,
                api_key=request.llm.api_key or "",
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"LLM init failed: {exc}")

    try_register_job(
        task_id,
        job_type="managed_repair",
        target_url=request.target_url,
        status="running",
    )

    try:
        # First, do an initial run
        initial_result = execute_and_run(
            target_url=request.target_url,
            profile=request.profile,
            run_spec=request.run_spec,
            advisor=advisor,
            extra_context=request.extra_context,
            batch_size=request.batch_size,
            max_batches=request.max_batches,
            item_workers=request.item_workers,
            runtime_dir=request.runtime_dir,
        )

        # Then diagnose and repair
        job = get_job(task_id) or {}
        result = diagnose_and_repair(
            job=job,
            profile=request.profile,
            target_url=request.target_url,
            run_spec=request.run_spec,
            extra_context=request.extra_context,
            max_cycles=request.max_cycles,
            batch_size=request.batch_size,
            max_batches=request.max_batches,
            item_workers=request.item_workers,
            runtime_dir=request.runtime_dir,
            advisor=advisor,
        )

        update_job(
            task_id,
            status="completed",
            initial_run=initial_result,
            repair_result=result,
        )
        return {"task_id": task_id, "initial_run": initial_result, "repair": result}
    except Exception as exc:
        update_job(task_id, status="failed", error=str(exc)[:500])
        raise HTTPException(status_code=500, detail=str(exc)[:500])
