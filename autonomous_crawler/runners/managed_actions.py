"""Managed crawl action planning and execution.

This module gives CLM's managed mode a concrete tool space. Actions are
serializable, bounded, and map to existing crawler capabilities such as site
analysis, access tuning, selector repair, and executable rerun preparation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

from autonomous_crawler.runtime import NativeBrowserRuntime, RuntimeRequest
from autonomous_crawler.tools.ecommerce_extractors import (
    UnsupportedExtractorContract,
    extract_items_from_contract,
)
from autonomous_crawler.tools.extraction_contracts import discover_extraction_contracts
from autonomous_crawler.tools.html_recon import build_recon_report

from .api_replay_promotion import promote_api_replay_from_access_evidence
from .product_workflow import (
    DEFAULT_PRODUCT_FIELDS,
    analyze_site_for_product_workflow,
    build_access_evidence_snapshot,
)


ACTION_PROTOCOL_VERSION = "managed-action-plan/v2"


SUPPORTED_ACTIONS = {
    "analyze_site",
    "select_catalog",
    "resolve_fields",
    "switch_runtime",
    "patch_profile",
    "patch_selector",
    "promote_xhr_to_api",
    "apply_replay_runtime",
    "run_test",
    "rerun_failed",
    "export_results",
    "reanalyze_site",
    "discover_catalog",
    "probe_fields",
    "inspect_access",
    "repair_selectors",
    "adjust_runtime",
    "evaluate_quality",
    "prepare_export",
    "prepare_rerun",
    "extract_from_contract",
    "follow_pagination",
    "render_with_browser",
}

EXECUTABLE_ACTIONS = {
    "reanalyze_site",
    "discover_catalog",
    "probe_fields",
    "inspect_access",
    "repair_selectors",
    "adjust_runtime",
    "evaluate_quality",
    "prepare_export",
    "prepare_rerun",
    "patch_profile",
    "extract_from_contract",
    "follow_pagination",
    "render_with_browser",
}

ACTION_ALIASES = {
    "analyze_site": "reanalyze_site",
    "select_catalog": "discover_catalog",
    "resolve_fields": "probe_fields",
    "switch_runtime": "adjust_runtime",
    "patch_selector": "repair_selectors",
    "promote_xhr_to_api": "inspect_access",
    "apply_replay_runtime": "inspect_access",
    "run_test": "prepare_rerun",
    "rerun_failed": "prepare_rerun",
    "export_results": "prepare_export",
}

ACTION_ALLOWED_PARAMS = {
    "reanalyze_site": {"target_url", "field_goal", "imported_catalog"},
    "discover_catalog": {"target_url", "field_goal", "imported_catalog", "max_depth", "max_nodes"},
    "probe_fields": {"fields", "field_goal", "reanalyze", "min_field_coverage"},
    "inspect_access": {
        "target_url",
        "target_selector",
        "capture_api",
        "capture_xhr",
        "capture_js",
        "capture_dom",
        "live_probe",
        "sample_limit",
        "render_time_ms",
        "max_wait_ms",
        "timeout_ms",
        "selected_fields",
    },
    "repair_selectors": {"fields", "selectors", "selector_patch"},
    "adjust_runtime": {
        "mode",
        "wait_until",
        "capture_api",
        "protected",
        "persistent_context",
        "rotate_proxy",
        "item_workers",
        "render_time_ms",
        "max_wait_ms",
    },
    "evaluate_quality": {"required_fields", "min_records", "min_field_coverage"},
    "prepare_export": {"format", "output_path", "field_mapping", "template_path"},
    "prepare_rerun": {"run_kind", "apply_profile_patch", "reason"},
    "patch_profile": {"profile_patch", "patch", "overrides"},
    "extract_from_contract": {"contract", "evidence", "source_url", "max_items"},
    "follow_pagination": {"html", "max_pages", "current_url"},
    "render_with_browser": {"target_url", "wait_until", "timeout_ms", "max_items", "screenshot"},
}

SAFE_PROFILE_PATCH_KEYS = {
    "selectors",
    "crawl_preferences",
    "access_config",
    "api_hints",
    "pagination_hints",
    "quality_expectations",
    "target_fields",
}

SAFE_SELECTOR_FIELDS = {
    "title",
    "highest_price",
    "price",
    "original_price",
    "colors",
    "color",
    "sizes",
    "size",
    "description",
    "desc",
    "image_urls",
    "images",
    "image",
    "product_url",
    "sku",
    "brand",
    "category",
}

SAFE_RUNTIME_MODES = {"static", "dynamic", "protected"}
SAFE_WAIT_UNTIL = {"load", "domcontentloaded", "networkidle", "commit"}
SAFE_EXPORT_FORMATS = {"csv", "xlsx", "json", "sqlite", "db"}


@dataclass(frozen=True)
class ManagedCrawlAction:
    action: str
    reason: str = ""
    priority: str = "medium"
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Any) -> "ManagedCrawlAction":
        parsed = _validate_action_payload(payload)
        if parsed.get("accepted"):
            action = parsed["action"]
            return cls(
                action=action,
                reason=str(parsed.get("reason") or "")[:800],
                priority=str(parsed.get("priority") or "medium"),
                params=dict(parsed.get("params") or {}),
            )
        return cls(
            action="prepare_rerun",
            reason="Rejected invalid action; falling back to bounded rerun preparation.",
            priority="medium",
            params={},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "priority": self.priority,
            "params": dict(self.params),
        }


@dataclass(frozen=True)
class ManagedActionPlan:
    actions: list[ManagedCrawlAction] = field(default_factory=list)
    source: str = "deterministic"
    reasoning_summary: str = ""
    protocol_validation: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Any, *, source: str | None = None) -> "ManagedActionPlan":
        data = _coerce_plan_payload(payload)
        raw_actions = data.get("actions") if isinstance(data.get("actions"), list) else []
        actions: list[ManagedCrawlAction] = []
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for index, item in enumerate(raw_actions[:20]):
            parsed = _validate_action_payload(item, index=index)
            if parsed.get("accepted"):
                actions.append(ManagedCrawlAction(
                    action=str(parsed["action"]),
                    reason=str(parsed.get("reason") or "")[:800],
                    priority=str(parsed.get("priority") or "medium"),
                    params=dict(parsed.get("params") or {}),
                ))
                accepted.append(_protocol_acceptance_record(parsed))
            else:
                rejected.append(_protocol_rejection_record(parsed))
        if not actions and raw_actions:
            actions.append(ManagedCrawlAction(
                action="prepare_rerun",
                reason="No valid LLM actions survived validation; bounded fallback prepared.",
                priority="medium",
                params={},
            ))
        validation = {
            "schema_version": ACTION_PROTOCOL_VERSION,
            "raw_action_count": len(raw_actions),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "accepted": accepted,
            "rejected": rejected,
            "fallback_used": bool(raw_actions and not accepted),
        }
        return cls(
            actions=actions,
            source=str(source or data.get("source") or "llm")[:80],
            reasoning_summary=str(data.get("reasoning_summary") or "")[:1000],
            protocol_validation=validation,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "reasoning_summary": self.reasoning_summary,
            "actions": [action.to_dict() for action in self.actions],
            "protocol_validation": dict(self.protocol_validation),
        }


def build_deterministic_action_plan(
    *,
    target_url: str,
    profile: dict[str, Any],
    run_spec: dict[str, Any] | None = None,
    progress: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
    supervision: dict[str, Any] | None = None,
    extra_context: dict[str, Any] | None = None,
) -> ManagedActionPlan:
    """Build a practical action plan from current run evidence."""
    actions: list[ManagedCrawlAction] = []
    run_spec = run_spec if isinstance(run_spec, dict) else {}
    progress = progress if isinstance(progress, dict) else {}
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    supervision = supervision if isinstance(supervision, dict) else {}
    extra_context = extra_context if isinstance(extra_context, dict) else {}
    selected_fields = list(run_spec.get("selected_fields") or profile.get("target_fields") or [])
    requested_fields = _canonical_field_list(extra_context.get("selected_fields") or [])
    selected_field_set = set(_canonical_field_list(selected_fields))
    extraction_contract = extra_context.get("extraction_contract")
    extraction_evidence = extra_context.get("extraction_evidence")
    if not isinstance(extraction_contract, dict):
        extraction_contract = extra_context.get("contract") if isinstance(extra_context.get("contract"), dict) else {}
    if extraction_evidence is None:
        extraction_evidence = extra_context.get("evidence")
    if (not isinstance(extraction_contract, dict) or not extraction_contract) and extraction_evidence not in (None, ""):
        discovery = discover_extraction_contracts(
            extraction_evidence,
            source_url=str(extra_context.get("source_url") or target_url),
            site=str(extra_context.get("site") or ""),
            sample_items=5,
        )
        best_contract = discovery.get("best_contract")
        if isinstance(best_contract, dict):
            extraction_contract = best_contract
    if isinstance(extraction_contract, dict) and extraction_contract and extraction_evidence not in (None, ""):
        actions.append(ManagedCrawlAction(
            action="extract_from_contract",
            priority="high",
            reason="A structured extraction contract and matching evidence are available; run the contract extractor before selector repair.",
            params={
                "contract": extraction_contract,
                "evidence": extraction_evidence,
                "source_url": str(
                    extra_context.get("source_url")
                    or extraction_contract.get("source_url")
                    or target_url
                ),
                "max_items": int(extra_context.get("max_items") or run_spec.get("limit") or 100),
            },
        ))

    add_reanalyze = not profile.get("selectors") or not profile.get("crawl_preferences")
    if add_reanalyze:
        actions.append(ManagedCrawlAction(
            action="reanalyze_site",
            priority="high",
            reason="Profile is missing selectors or crawl preferences.",
            params={"target_url": target_url},
        ))
    catalog_nodes = run_spec.get("catalog_nodes") if isinstance(run_spec.get("catalog_nodes"), list) else []
    prefs = profile.get("crawl_preferences") if isinstance(profile.get("crawl_preferences"), dict) else {}
    seed_urls = prefs.get("seed_urls") if isinstance(prefs.get("seed_urls"), list) else []
    if not catalog_nodes and not seed_urls:
        actions.append(ManagedCrawlAction(
            action="discover_catalog",
            priority="high",
            reason="No catalog nodes or seed URLs are available for the run.",
            params={"target_url": target_url, "imported_catalog": extra_context.get("imported_catalog")},
        ))
    if (
        not selected_fields
        or any(str(item).strip().lower() in {"", "auto", "*"} for item in selected_fields)
        or any(field not in selected_field_set for field in requested_fields)
    ):
        actions.append(ManagedCrawlAction(
            action="probe_fields",
            priority="high",
            reason="Selected fields are missing or too vague; probe product fields before rerun.",
            params={
                "field_goal": str(extra_context.get("field_goal") or ""),
                "fields": requested_fields or selected_fields,
            },
        ))

    last_supervision = supervision.get("last_event") if isinstance(supervision.get("last_event"), dict) else {}
    quality = str(progress.get("quality_indicator") or "").lower()
    records_saved = int(progress.get("records_saved") or progress.get("record_count") or 0)
    failed = int(progress.get("failed") or 0)
    failure_buckets = _failure_buckets(progress, diagnostics, supervision)
    challenge_failures = sum(
        count
        for bucket, count in failure_buckets.items()
        if bucket in {"challenge_like", "captcha", "managed_challenge", "http_blocked"}
    )
    reason_text = str(last_supervision.get("reason") or diagnostics.get("recommendation") or "").lower()
    if challenge_failures:
        actions.append(ManagedCrawlAction(
            action="adjust_runtime",
            priority="high",
            reason="Challenge-like or captcha responses were detected; use protected browser mode, persistent context, lower concurrency, and proxy-ready settings.",
            params={
                "mode": "protected",
                "capture_api": True,
                "wait_until": "domcontentloaded",
                "protected": True,
                "persistent_context": True,
                "rotate_proxy": True,
                "item_workers": 1,
            },
        ))
        actions.append(ManagedCrawlAction(
            action="inspect_access",
            priority="high",
            reason="Access diagnostics found challenge-like failures; collect browser/XHR evidence before selector repair.",
            params={"target_url": target_url, "target_selector": _title_selector(profile), "challenge_failures": challenge_failures},
        ))
    if quality in {"fail", "unknown"} or records_saved == 0 or failed:
        actions.append(ManagedCrawlAction(
            action="inspect_access",
            priority="high" if records_saved == 0 else "medium",
            reason="Run quality or record yield indicates access/runtime evidence should be checked.",
            params={"target_url": target_url, "target_selector": _title_selector(profile)},
        ))
    if "empty" in reason_text or "no records" in reason_text or records_saved == 0:
        actions.append(ManagedCrawlAction(
            action="repair_selectors",
            priority="high",
            reason="Recent run produced no records; selectors need fallback repair.",
            params={"fields": list(run_spec.get("selected_fields") or profile.get("target_fields") or ["title"])},
        ))
        actions.append(ManagedCrawlAction(
            action="adjust_runtime",
            priority="high",
            reason="Empty output often means JS rendering, waits, or API capture are required.",
            params={"mode": "protected" if challenge_failures else "dynamic", "capture_api": True, "wait_until": "networkidle"},
        ))
    if quality in {"fail", "warn", "unknown"} or records_saved == 0:
        actions.append(ManagedCrawlAction(
            action="evaluate_quality",
            priority="medium",
            reason="Quality gate needs explicit required fields and success thresholds.",
            params={"required_fields": requested_fields or selected_fields or DEFAULT_PRODUCT_FIELDS},
        ))
    export = run_spec.get("export") if isinstance(run_spec.get("export"), dict) else {}
    if extra_context.get("export") or not export.get("format"):
        actions.append(ManagedCrawlAction(
            action="prepare_export",
            priority="low",
            reason="Prepare export settings so a repaired run can produce the expected artifact.",
            params=dict(extra_context.get("export") if isinstance(extra_context.get("export"), dict) else {}),
        ))

    actions.append(ManagedCrawlAction(
        action="prepare_rerun",
        priority="medium",
        reason="Prepare executable rerun payload from accumulated action results.",
        params={},
    ))
    return ManagedActionPlan(actions=_dedupe_actions(actions), source="deterministic")


def execute_managed_action_plan(
    *,
    plan: ManagedActionPlan,
    target_url: str,
    profile: dict[str, Any],
    run_spec: dict[str, Any] | None = None,
    advisor: Any = None,
    extra_context: dict[str, Any] | None = None,
    job: dict[str, Any] | None = None,
    llm_decide: bool = False,
    llm_decision_callback: Any = None,
    llm_trace_callback: Any = None,
    progress: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
    supervision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute bounded managed actions and return profile/run overrides.

    When *llm_decide* is ``True`` and an *advisor* is provided the advisor's
    ``choose_managed_actions()`` method is called to let the AI choose which
    actions to take.  The chosen plan replaces the caller-supplied *plan*.
    If the LLM call fails the original deterministic plan is used as a
    fallback.

    Parameters
    ----------
    llm_decide:
        When ``True``, ask the advisor to choose the action plan.
    llm_decision_callback:
        Optional callable ``(decision: dict) -> None`` invoked with each
        recorded LLM decision.  Used to persist decisions in a job's
        ``ai_decisions`` array.
    llm_trace_callback:
        Optional callable ``(trace: dict) -> None`` invoked with each
        LLM trace record.  Used to persist traces in a job's
        ``llm_traces`` array.
    progress:
        Current run progress dict (used by advisor when *llm_decide*).
    diagnostics:
        Current diagnostics dict (used by advisor when *llm_decide*).
    supervision:
        Current supervision dict (used by advisor when *llm_decide*).
    """
    run_spec = run_spec if isinstance(run_spec, dict) else {}
    extra_context = extra_context if isinstance(extra_context, dict) else {}
    progress = progress if isinstance(progress, dict) else {}
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    supervision = supervision if isinstance(supervision, dict) else {}
    results: list[dict[str, Any]] = []
    profile_patch: dict[str, Any] = {}
    run_overrides: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # LLM decision phase: let the advisor choose the action plan
    # ------------------------------------------------------------------
    effective_plan = plan
    llm_plan_source = "deterministic"
    if llm_decide and advisor is not None:
        effective_plan, llm_plan_source = _try_llm_plan_selection(
            advisor=advisor,
            fallback_plan=plan,
            target_url=target_url,
            profile=profile,
            run_spec=run_spec,
            progress=progress,
            diagnostics=diagnostics,
            supervision=supervision,
            job=job,
            llm_decision_callback=llm_decision_callback,
            llm_trace_callback=llm_trace_callback,
        )

    for action in effective_plan.actions:
        if action.action == "reanalyze_site":
            result = _execute_reanalyze_site(action, target_url=target_url, advisor=advisor, extra_context=extra_context)
        elif action.action == "discover_catalog":
            result = _execute_discover_catalog(action, target_url=target_url, advisor=advisor, extra_context=extra_context)
        elif action.action == "probe_fields":
            result = _execute_probe_fields(action, target_url=target_url, profile=profile, run_spec=run_spec, advisor=advisor, extra_context=extra_context)
        elif action.action == "inspect_access":
            result = _execute_inspect_access(action, target_url=target_url, profile=profile, job=job)
        elif action.action == "repair_selectors":
            result = _execute_repair_selectors(action, profile=profile)
        elif action.action == "adjust_runtime":
            result = _execute_adjust_runtime(action)
        elif action.action == "evaluate_quality":
            result = _execute_evaluate_quality(action, profile=profile, run_spec=run_spec)
        elif action.action == "prepare_export":
            result = _execute_prepare_export(action, run_spec=run_spec, extra_context=extra_context)
        elif action.action == "patch_profile":
            result = _execute_patch_profile(action)
        elif action.action == "extract_from_contract":
            result = _execute_extract_from_contract(
                _hydrate_extract_from_contract_action(action, extra_context)
            )
        elif action.action == "follow_pagination":
            result = _execute_follow_pagination(
                action, target_url=target_url, profile=profile, extra_context=extra_context
            )
        elif action.action == "render_with_browser":
            result = _execute_render_with_browser(
                action, target_url=target_url, profile=profile
            )
        else:
            result = {"action": action.action, "ok": True, "patch": {}, "overrides": {}}
        profile_patch = _deep_merge(profile_patch, result.get("patch") if isinstance(result.get("patch"), dict) else {})
        run_overrides = _deep_merge(run_overrides, result.get("overrides") if isinstance(result.get("overrides"), dict) else {})
        results.append(result)

    if not run_overrides and profile_patch:
        run_overrides = dict(profile_patch)
    api_replay_promotions = [
        result.get("api_replay_promotion")
        for result in results
        if isinstance(result.get("api_replay_promotion"), dict)
    ]
    return {
        "schema_version": "managed-action-result/v1",
        "plan": effective_plan.to_dict(),
        "plan_source": llm_plan_source,
        "llm_decide": llm_decide,
        "results": results,
        "evidence": _merge_action_evidence(results),
        "api_replay_promotions": api_replay_promotions,
        "api_replay_promotion": api_replay_promotions[-1] if api_replay_promotions else {},
        "profile_patch": profile_patch,
        "run_overrides": run_overrides,
        "rerun_ready": bool(profile_patch or run_overrides),
    }



def _try_llm_plan_selection(
    *,
    advisor: Any,
    fallback_plan: ManagedActionPlan,
    target_url: str,
    profile: dict[str, Any],
    run_spec: dict[str, Any],
    progress: dict[str, Any],
    diagnostics: dict[str, Any],
    supervision: dict[str, Any],
    job: dict[str, Any] | None,
    llm_decision_callback: Any,
    llm_trace_callback: Any,
) -> tuple[ManagedActionPlan, str]:
    """Ask the advisor to choose the action plan.

    Returns ``(plan, source)`` where *source* is ``"llm"`` on success or
    ``"deterministic_fallback"`` when the LLM call fails.
    """
    import time as _time

    started_at = _time.perf_counter()
    input_payload = {
        "target_url": target_url,
        "profile": profile,
        "run_spec": run_spec,
        "progress": progress,
        "diagnostics": diagnostics,
        "supervision": supervision,
        "available_actions": sorted(SUPPORTED_ACTIONS),
    }
    try:
        raw = advisor.choose_managed_actions(
            target_url=target_url,
            profile=profile,
            run_spec=run_spec,
            progress=progress,
            diagnostics=diagnostics,
            supervision=supervision,
            available_actions=sorted(SUPPORTED_ACTIONS),
        )
        plan = ManagedActionPlan.from_dict(raw, source="llm")

        # Record the LLM decision
        decision = {
            "stage": "managed_action_plan",
            "enabled": True,
            "fallback_used": False,
            "provider": getattr(advisor, "provider", "unknown"),
            "model": getattr(advisor, "model", "unknown"),
            "reasoning_summary": str(raw.get("reasoning_summary") or "")[:1000],
            "action_count": len(plan.actions),
            "actions": [a.action for a in plan.actions],
            "plan_source": "llm",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if llm_decision_callback is not None:
            try:
                llm_decision_callback(decision)
            except Exception:
                pass

        trace = {
            "stage": "managed_action_plan",
            "status": "ok",
            "provider": getattr(advisor, "provider", "unknown"),
            "model": getattr(advisor, "model", "unknown"),
            "duration_ms": int((_time.perf_counter() - started_at) * 1000),
            "input_summary": {
                "target_url": target_url,
                "action_count": len(plan.actions),
            },
            "output_summary": {
                "actions": [a.action for a in plan.actions],
                "reasoning_summary": str(raw.get("reasoning_summary") or "")[:500],
            },
            "error": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if llm_trace_callback is not None:
            try:
                llm_trace_callback(trace)
            except Exception:
                pass

        return plan, "llm"
    except Exception as exc:
        # Record the failed LLM attempt
        trace = {
            "stage": "managed_action_plan",
            "status": "error",
            "provider": getattr(advisor, "provider", "unknown"),
            "model": getattr(advisor, "model", "unknown"),
            "duration_ms": int((_time.perf_counter() - started_at) * 1000),
            "input_summary": {"target_url": target_url},
            "output_summary": {},
            "error": str(exc)[:1000],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if llm_trace_callback is not None:
            try:
                llm_trace_callback(trace)
            except Exception:
                pass

        decision = {
            "stage": "managed_action_plan",
            "enabled": True,
            "fallback_used": True,
            "error": str(exc)[:500],
            "plan_source": "deterministic_fallback",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if llm_decision_callback is not None:
            try:
                llm_decision_callback(decision)
            except Exception:
                pass

        return fallback_plan, "deterministic_fallback"


def _execute_reanalyze_site(
    action: ManagedCrawlAction,
    *,
    target_url: str,
    advisor: Any = None,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        extra_context = extra_context if isinstance(extra_context, dict) else {}
        analysis = analyze_site_for_product_workflow(
            str(action.params.get("target_url") or target_url),
            field_goal=str(action.params.get("field_goal") or extra_context.get("field_goal") or ""),
            imported_catalog=action.params.get("imported_catalog") or extra_context.get("imported_catalog"),
            advisor=advisor,
        )
        profile = analysis.get("profile") if isinstance(analysis.get("profile"), dict) else {}
        patch: dict[str, Any] = {}
        for key in ("selectors", "crawl_preferences", "access_config", "api_hints", "pagination_hints", "quality_expectations"):
            if isinstance(profile.get(key), dict):
                patch[key] = profile[key]
        return {
            "action": action.action,
            "ok": True,
            "summary": "site analysis completed",
            "analysis_summary": analysis.get("recon_summary", {}),
            "patch": patch,
            "overrides": patch,
        }
    except Exception as exc:
        return {"action": action.action, "ok": False, "error": str(exc), "patch": {}, "overrides": {}}


def _merge_action_evidence(results: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_items = [
        result.get("evidence")
        for result in results
        if isinstance(result.get("evidence"), dict)
    ]
    if not evidence_items:
        return {}
    access_items = [
        item for item in evidence_items
        if item.get("access_mode") or item.get("snapshot") or item.get("request")
    ]
    latest = access_items[-1] if access_items else evidence_items[-1]
    snapshots = [
        item.get("snapshot")
        for item in evidence_items
        if isinstance(item.get("snapshot"), dict)
    ]
    return {
        "schema_version": "managed-action-evidence/v1",
        "access": latest,
        "access_snapshot": snapshots[-1] if snapshots else {},
        "items": evidence_items[-10:],
    }


def _execute_discover_catalog(
    action: ManagedCrawlAction,
    *,
    target_url: str,
    advisor: Any = None,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra_context = extra_context if isinstance(extra_context, dict) else {}
    imported_catalog = action.params.get("imported_catalog") or extra_context.get("imported_catalog")
    result = _execute_reanalyze_site(
        ManagedCrawlAction(
            action="reanalyze_site",
            reason=action.reason,
            priority=action.priority,
            params={
                "target_url": action.params.get("target_url") or target_url,
                "field_goal": action.params.get("field_goal") or extra_context.get("field_goal") or "",
                "imported_catalog": imported_catalog,
            },
        ),
        target_url=target_url,
        advisor=advisor,
        extra_context=extra_context,
    )
    if not result.get("ok"):
        result["action"] = action.action
        return result
    patch = result.get("patch") if isinstance(result.get("patch"), dict) else {}
    prefs = patch.get("crawl_preferences") if isinstance(patch.get("crawl_preferences"), dict) else {}
    catalog_tree = prefs.get("catalog_tree") if isinstance(prefs.get("catalog_tree"), list) else []
    seed_urls = prefs.get("seed_urls") if isinstance(prefs.get("seed_urls"), list) else []
    return {
        "action": action.action,
        "ok": bool(catalog_tree or seed_urls),
        "summary": f"catalog discovery prepared {len(catalog_tree)} nodes and {len(seed_urls)} seeds",
        "catalog_node_count": len(catalog_tree),
        "seed_count": len(seed_urls),
        "patch": {"crawl_preferences": prefs} if prefs else {},
        "overrides": {"crawl_preferences": prefs} if prefs else {},
    }


def _execute_probe_fields(
    action: ManagedCrawlAction,
    *,
    target_url: str,
    profile: dict[str, Any],
    run_spec: dict[str, Any],
    advisor: Any = None,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra_context = extra_context if isinstance(extra_context, dict) else {}
    fields = _canonical_field_list(
        action.params.get("fields")
        or run_spec.get("selected_fields")
        or profile.get("target_fields")
        or extra_context.get("selected_fields")
        or DEFAULT_PRODUCT_FIELDS
    )
    if not fields:
        fields = list(DEFAULT_PRODUCT_FIELDS)
    selectors = {}
    should_reanalyze = bool(action.params.get("reanalyze") or advisor is not None)
    if should_reanalyze:
        result = _execute_reanalyze_site(
            ManagedCrawlAction(
                action="reanalyze_site",
                reason=action.reason,
                priority=action.priority,
                params={
                    "target_url": target_url,
                    "field_goal": action.params.get("field_goal") or ", ".join(fields),
                    "imported_catalog": extra_context.get("imported_catalog"),
                },
            ),
            target_url=target_url,
            advisor=advisor,
            extra_context=extra_context,
        )
        if isinstance(result.get("patch"), dict):
            selectors = result["patch"].get("selectors") if isinstance(result["patch"].get("selectors"), dict) else {}
    elif isinstance(profile.get("selectors"), dict):
        selectors = dict(profile.get("selectors") or {})
    selector_patch = _fallback_selector_patch(fields, selectors)
    patch = {
        "target_fields": fields,
        "selectors": selector_patch,
        "quality_expectations": {
            "required_fields": fields,
            "min_field_coverage": float(action.params.get("min_field_coverage") or 0.8),
        },
    }
    overrides = {
        **patch,
        "selected_fields": fields,
    }
    return {
        "action": action.action,
        "ok": True,
        "summary": f"field probe prepared {len(fields)} target fields",
        "fields": fields,
        "patch": patch,
        "overrides": overrides,
    }


def _execute_inspect_access(
    action: ManagedCrawlAction,
    *,
    target_url: str,
    profile: dict[str, Any],
    job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    access = dict(profile.get("access_config") or {})
    browser = dict(access.get("browser_config") or {})
    mode = str(access.get("mode") or access.get("runtime_mode") or "dynamic").strip().lower()
    if mode not in {"dynamic", "protected"}:
        mode = "dynamic"
    access["mode"] = mode
    access["wait_until"] = "networkidle"
    browser["capture_api"] = True
    browser["capture_js"] = bool(action.params.get("capture_js", True))
    browser["auto_accept_cookies"] = True
    browser["render_time_ms"] = max(
        3000,
        int(action.params.get("render_time_ms") or browser.get("render_time_ms") or 0),
    )
    browser["max_wait_ms"] = max(30000, int(browser.get("max_wait_ms") or 0))
    access["browser_config"] = browser
    patch["access_config"] = access
    sample_limit = max(1, min(int(action.params.get("sample_limit") or 3), 10))
    live_probe = _should_collect_live_access_probe(action)
    evidence_request = {
        "target_url": target_url,
        "mode": mode,
        "capture_api": True,
        "capture_xhr": action.params.get("capture_xhr") or "",
        "capture_js": bool(action.params.get("capture_js", True)),
        "capture_dom": bool(action.params.get("capture_dom", True)),
        "extract_challenge": True,
        "extract_network": True,
        "extract_browser": True,
    }
    snapshot = build_access_evidence_snapshot(job) if isinstance(job, dict) else {}
    probe_snapshot = {}
    if live_probe:
        probe_snapshot = _collect_access_probe_snapshot(
            target_url=target_url,
            mode=mode,
            profile=profile,
            action=action,
            browser_config=browser,
            sample_limit=sample_limit,
        )
    evidence = {
        "target_url": target_url,
        "access_mode": access.get("mode", "dynamic"),
        "browser_config": browser,
        "sample_limit": sample_limit,
        "signals": [
            "challenge",
            "captcha",
            "xhr",
            "api",
            "js_shell",
            "fingerprint",
        ],
        "profile_summary": {
            "name": profile.get("name", ""),
            "seed_kind": (profile.get("crawl_preferences") or {}).get("seed_kind", ""),
            "target_fields": list(profile.get("target_fields") or []),
        },
        "request": evidence_request,
        "snapshot": probe_snapshot or snapshot,
        "base_snapshot": snapshot,
        "live_probe": live_probe,
    }
    selected_fields = [
        str(item)
        for item in (
            action.params.get("selected_fields")
            or profile.get("target_fields")
            or []
        )
        if str(item).strip()
    ]
    api_promotion = promote_api_replay_from_access_evidence(
        evidence,
        target_url=target_url,
        selected_fields=selected_fields,
    )
    if api_promotion.promoted:
        patch = _deep_merge(patch, api_promotion.profile_patch)
    evidence["api_replay_promotion"] = api_promotion.to_dict()
    return {
        "action": action.action,
        "ok": True,
        "summary": "runtime access probe completed" if probe_snapshot else "runtime access knobs and evidence snapshot prepared",
        "evidence": evidence,
        "api_replay_promotion": api_promotion.to_dict(),
        "patch": patch,
        "overrides": patch,
    }


def _should_collect_live_access_probe(action: ManagedCrawlAction) -> bool:
    if str(action.params.get("live_probe") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if str(action.params.get("live_probe") or "").strip().lower() in {"0", "false", "no", "off"}:
        return False
    env_default = str(os.environ.get("CLM_LIVE_ACCESS_PROBE", "")).strip().lower()
    if env_default in {"1", "true", "yes", "on"}:
        return True
    return False


def _collect_access_probe_snapshot(
    *,
    target_url: str,
    mode: str,
    profile: dict[str, Any],
    action: ManagedCrawlAction,
    browser_config: dict[str, Any],
    sample_limit: int,
) -> dict[str, Any]:
    profile_access = profile.get("access_config") if isinstance(profile.get("access_config"), dict) else {}
    profile_session = profile_access.get("session_profile") if isinstance(profile_access.get("session_profile"), dict) else {}
    probe_request = RuntimeRequest.from_dict({
        "url": target_url,
        "mode": mode if mode in {"dynamic", "protected"} else "dynamic",
        "wait_until": "networkidle",
        "timeout_ms": max(30000, int(action.params.get("timeout_ms") or 0)),
        "capture_xhr": str(action.params.get("capture_xhr") or ""),
        "browser_config": {
            **dict(browser_config),
            "capture_api": True,
            "capture_js": bool(action.params.get("capture_js", True)),
            "auto_accept_cookies": True,
            "render_time_ms": max(3000, int(action.params.get("render_time_ms") or browser_config.get("render_time_ms") or 0)),
            "max_captures": max(6, sample_limit * 6),
        },
        "session_profile": {
            "name": str(profile.get("name") or "managed-access-probe"),
            "headers": dict(profile_session.get("headers") or {}),
            "cookies": dict(profile_session.get("cookies") or {}),
            "storage_state_path": str(profile_session.get("storage_state_path") or ""),
        },
    })
    runtime = NativeBrowserRuntime()
    response = runtime.render(probe_request)
    try:
        response_dict = response.to_dict()
    except Exception:
        response_dict = {}
    html = str(response.html or "")
    recon = build_recon_report(response.final_url or target_url, html) if html else {}
    engine_result = response_dict.get("engine_result") if isinstance(response_dict.get("engine_result"), dict) else {}
    failure_classification = engine_result.get("failure_classification") if isinstance(engine_result.get("failure_classification"), dict) else {}
    status_code = int(response.status_code or 0)
    challenge_like = bool(
        failure_classification.get("category") in {"challenge_like", "playwright_missing"}
        or status_code in {401, 403, 407, 429, 444, 500, 502, 503, 504}
        or _text_has_probe_challenge_signal(response.error)
        or _text_has_probe_challenge_signal(html)
    )
    recent_failures: list[dict[str, Any]] = []
    if response.error or challenge_like:
        recent_failures.append({
            "url": response.final_url or target_url,
            "bucket": "challenge_like" if challenge_like else "access_probe",
            "error": str(response.error or failure_classification.get("category") or "probe_failed")[:300],
            "status": status_code or None,
        })
    runtime_events = [
        _probe_event_sample(item)
        for item in (response_dict.get("runtime_events") or [])
        if isinstance(item, dict)
    ]
    runtime_events = [item for item in runtime_events if item]
    xhr_samples = [
        _probe_xhr_sample(item)
        for item in (response_dict.get("captured_xhr") or [])
        if isinstance(item, dict)
    ]
    xhr_samples = [item for item in xhr_samples if item]
    artifact_samples = [
        _probe_artifact_sample(item)
        for item in (response_dict.get("artifacts") or [])
        if isinstance(item, dict)
    ]
    artifact_samples = [item for item in artifact_samples if item]
    summary = {
        "challenge_like": challenge_like,
        "recommended_runtime": "protected_browser" if challenge_like else (
            "api_replay_or_browser_network" if xhr_samples else (mode or "dynamic_browser_probe")
        ),
        "access_mode": mode,
        "html_chars": len(html),
        "captured_xhr": len(xhr_samples),
        "runtime_events": len(runtime_events),
        "artifacts": len(artifact_samples),
        "dom_item_count": int((recon.get("dom_structure") or {}).get("item_count") or 0),
        "framework": str(recon.get("frontend_framework") or ""),
        "rendering": str(recon.get("rendering") or ""),
        "anti_bot": bool((recon.get("anti_bot") or {}).get("detected", False)),
    }
    decision_hints = [
        "collect_small_browser_sample_before_bulk_rerun",
        "enable_api_capture" if not xhr_samples else "prefer_api_or_xhr_replay_if_product_payload_is_visible",
    ]
    if challenge_like:
        decision_hints.extend([
            "use_protected_browser_profile",
            "persist_browser_session",
            "lower_concurrency_and_prepare_proxy_rotation",
        ])
    probe_snapshot = {
        "schema_version": "access-probe/v1",
        "target_url": target_url,
        "final_url": response.final_url or target_url,
        "status_code": status_code,
        "ok": bool(response.ok),
        "error": str(response.error or ""),
        "summary": summary,
        "request": probe_request.to_safe_dict(),
        "runtime_events": runtime_events[:12],
        "xhr_samples": xhr_samples[:10],
        "artifact_samples": artifact_samples[:10],
        "recent_failures": recent_failures[:5],
        "challenge_evidence": recent_failures[:5],
        "decision_hints": list(dict.fromkeys(decision_hints))[:10],
        "recon_summary": {
            "framework": recon.get("frontend_framework", ""),
            "rendering": recon.get("rendering", ""),
            "anti_bot": recon.get("anti_bot", {}),
            "item_count": (recon.get("dom_structure") or {}).get("item_count", 0),
            "field_selectors": (recon.get("dom_structure") or {}).get("field_selectors", {}),
            "product_selector": (recon.get("dom_structure") or {}).get("product_selector", ""),
        },
        "engine_result": engine_result,
    }
    return probe_snapshot


def _probe_event_sample(value: dict[str, Any]) -> dict[str, Any]:
    event_type = str(value.get("type") or value.get("event") or value.get("name") or "")[:120]
    message = str(value.get("message") or value.get("error") or value.get("reason") or "")[:300]
    data = value.get("data") if isinstance(value.get("data"), dict) else {}
    if not any([event_type, message, data]):
        return {}
    sample = {
        "type": event_type,
        "message": message,
    }
    if data:
        sample["data"] = dict(data)
    return sample


def _probe_xhr_sample(value: dict[str, Any]) -> dict[str, Any]:
    url = str(value.get("url") or "")[:500]
    method = str(value.get("method") or "GET").upper()[:12]
    status = value.get("status_code") or value.get("status")
    content_type = str(value.get("content_type") or value.get("resource_type") or "")[:120]
    preview = value.get("body_preview") or value.get("json_preview") or value.get("preview") or ""
    post_data = value.get("post_data") or value.get("post_data_preview") or value.get("request_body") or ""
    if isinstance(preview, (dict, list)):
        preview = str(preview)
    if isinstance(post_data, (dict, list)):
        post_data = json.dumps(post_data, ensure_ascii=False, default=str)
    sample = {
        "method": method,
        "url": url,
        "status": status,
        "content_type": content_type,
        "preview": _truncate_probe_text(str(preview), 500),
    }
    if str(post_data or "").strip():
        sample["post_data_preview"] = _truncate_probe_text(str(post_data), 2000)
    if isinstance(value.get("request_headers"), dict):
        sample["request_headers"] = _safe_probe_headers(value.get("request_headers") or {})
    return sample if any(sample.values()) else {}


def _safe_probe_headers(headers: dict[str, Any]) -> dict[str, str]:
    allowed = {
        "accept", "accept-language", "content-type", "origin", "referer",
        "x-requested-with", "x-csrf-token", "x-xsrf-token", "x-magento-cache-id",
        "x-store", "store",
    }
    output: dict[str, str] = {}
    for key, value in dict(headers or {}).items():
        name = str(key).strip()
        lowered = name.lower()
        if lowered in allowed or lowered.startswith("x-"):
            text = str(value or "").strip()
            if text and len(text) <= 1000 and "\x00" not in text:
                output[name] = text
    return output


def _probe_artifact_sample(value: dict[str, Any]) -> dict[str, Any]:
    kind = str(value.get("kind") or value.get("type") or "")[:80]
    path = str(value.get("path") or "")[:500]
    url = str(value.get("url") or "")[:500]
    meta = value.get("meta") if isinstance(value.get("meta"), dict) else {}
    sample = {"kind": kind, "path": path, "url": url}
    if meta:
        sample["meta"] = dict(meta)
    return sample if any(sample.values()) else {}


def _text_has_probe_challenge_signal(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("captcha", "recaptcha", "challenge", "cloudflare", "blocked", "403", "429"))


def _truncate_probe_text(text: str, max_chars: int) -> str:
    text = str(text or "")
    return text[:max_chars]


def _execute_repair_selectors(action: ManagedCrawlAction, *, profile: dict[str, Any]) -> dict[str, Any]:
    selectors = dict(profile.get("selectors") or {})
    fields = [str(item) for item in action.params.get("fields") or profile.get("target_fields") or ["title"]]
    detail = dict(selectors.get("detail") or {}) if isinstance(selectors.get("detail"), dict) else {}
    for field in fields:
        normalized = _normalize_field(field)
        if normalized == "title":
            detail.setdefault("title", {
                "selector_type": "xpath",
                "selector": "string((//h1 | //*[@itemprop='name'] | //meta[@property='og:title']/@content | //title)[1])",
            })
        elif normalized in {"highest_price", "price"}:
            detail.setdefault("highest_price", {
                "selector_type": "xpath",
                "selector": "string((//meta[@property='product:price:amount']/@content | //*[@itemprop='price']/@content | //*[@itemprop='price'])[1])",
            })
        elif normalized in {"description", "desc"}:
            detail.setdefault("description", {
                "selector_type": "xpath",
                "selector": "string((//*[@itemprop='description'] | //meta[@name='description']/@content |//*[contains(@class,'description')])[1])",
            })
        elif normalized in {"image_urls", "image"}:
            detail.setdefault("image_urls", {
                "selector_type": "xpath",
                "selector": "//meta[@property='og:image']/@content | //*[@itemprop='image']/@src | //img/@src",
            })
    if detail:
        selectors["detail"] = detail
    patch = {"selectors": selectors}
    return {
        "action": action.action,
        "ok": True,
        "summary": "selector fallbacks prepared",
        "patch": patch,
        "overrides": patch,
    }


def _execute_adjust_runtime(action: ManagedCrawlAction) -> dict[str, Any]:
    mode = str(action.params.get("mode") or "dynamic").lower()
    if mode not in {"static", "dynamic", "protected"}:
        mode = "dynamic"
    browser_config = {
        "capture_api": bool(action.params.get("capture_api", True)),
        "auto_accept_cookies": True,
        "render_time_ms": 5000 if mode == "protected" else 3000,
        "max_wait_ms": 45000 if mode == "protected" else 30000,
    }
    if bool(action.params.get("protected") or mode == "protected"):
        browser_config.update({
            "persistent_context": True,
            "close_persistent_context": False,
            "pool_enabled": True,
            "pool_id": "managed-protected",
            "capture_api": True,
        })
    patch = {
        "access_config": {
            "mode": mode,
            "wait_until": str(action.params.get("wait_until") or "networkidle"),
            "browser_config": browser_config,
        }
    }
    overrides: dict[str, Any] = dict(patch)
    if action.params.get("item_workers") is not None:
        try:
            overrides["item_workers"] = max(1, min(int(action.params.get("item_workers")), 128))
        except (TypeError, ValueError):
            pass
    if action.params.get("rotate_proxy"):
        overrides.setdefault("proxy_policy", {})
        overrides["proxy_policy"].update({"strategy": "rotate_on_challenge", "reason": "challenge_like_failure"})
    return {
        "action": action.action,
        "ok": True,
        "summary": "runtime configuration adjusted",
        "patch": patch,
        "overrides": overrides,
    }


def _execute_evaluate_quality(
    action: ManagedCrawlAction,
    *,
    profile: dict[str, Any],
    run_spec: dict[str, Any],
) -> dict[str, Any]:
    fields = _canonical_field_list(
        action.params.get("required_fields")
        or run_spec.get("selected_fields")
        or profile.get("target_fields")
        or DEFAULT_PRODUCT_FIELDS
    )
    min_records = max(1, int(action.params.get("min_records") or run_spec.get("test_limit") or 1))
    min_coverage = float(action.params.get("min_field_coverage") or 0.8)
    patch = {
        "quality_expectations": {
            "required_fields": fields,
            "min_records": min_records,
            "min_field_coverage": min(max(min_coverage, 0.0), 1.0),
        }
    }
    return {
        "action": action.action,
        "ok": True,
        "summary": "quality expectations prepared",
        "patch": patch,
        "overrides": patch,
    }


def _execute_prepare_export(
    action: ManagedCrawlAction,
    *,
    run_spec: dict[str, Any],
    extra_context: dict[str, Any],
) -> dict[str, Any]:
    current = run_spec.get("export") if isinstance(run_spec.get("export"), dict) else {}
    requested = extra_context.get("export") if isinstance(extra_context.get("export"), dict) else {}
    params = dict(action.params or {})
    fmt = str(params.get("format") or requested.get("format") or current.get("format") or "xlsx").strip().lower()
    if fmt not in {"csv", "xlsx", "json", "sqlite", "db"}:
        fmt = "xlsx"
    output_path = str(params.get("output_path") or requested.get("output_path") or current.get("output_path") or "").strip()
    field_mapping = params.get("field_mapping") or requested.get("field_mapping") or current.get("field_mapping") or {}
    export = {
        "format": fmt,
        "output_path": output_path,
        "field_mapping": {str(k): str(v) for k, v in dict(field_mapping).items()},
    }
    if params.get("template_path") or requested.get("template_path") or current.get("template_path"):
        export["template_path"] = str(params.get("template_path") or requested.get("template_path") or current.get("template_path"))
    return {
        "action": action.action,
        "ok": True,
        "summary": "export settings prepared",
        "patch": {},
        "overrides": {"export": export},
    }


def _execute_patch_profile(action: ManagedCrawlAction) -> dict[str, Any]:
    patch = action.params.get("profile_patch")
    if not isinstance(patch, dict):
        patch = action.params.get("patch") if isinstance(action.params.get("patch"), dict) else {}
    safe_patch = _sanitize_profile_patch(patch)
    return {
        "action": action.action,
        "ok": bool(safe_patch),
        "summary": "safe profile patch prepared" if safe_patch else "profile patch was empty after validation",
        "patch": safe_patch,
        "overrides": safe_patch,
    }


def _execute_follow_pagination(
    action: ManagedCrawlAction,
    *,
    target_url: str,
    profile: dict[str, Any],
    extra_context: dict[str, Any],
) -> dict[str, Any]:
    """Detect and follow pagination links from the current page.

    Uses HTML pagination detection to find next-page URLs and adds them
    to the crawl queue.
    """
    from ..tools.pagination import detect_pagination_links

    html = str(action.params.get("html") or extra_context.get("html") or "")
    max_pages = int(action.params.get("max_pages") or profile.get("max_pages") or 5)

    if not html:
        return {
            "action": "follow_pagination",
            "ok": False,
            "error": "No HTML provided for pagination detection",
            "patch": {},
            "overrides": {},
        }

    try:
        next_urls = detect_pagination_links(html, target_url, max_pages=max_pages)
        if next_urls:
            return {
                "action": "follow_pagination",
                "ok": True,
                "patch": {
                    "pagination_urls": next_urls,
                    "pagination_detected": True,
                },
                "overrides": {
                    "follow_pagination": True,
                    "pagination_urls": next_urls,
                },
            }
        else:
            return {
                "action": "follow_pagination",
                "ok": True,
                "patch": {"pagination_detected": False},
                "overrides": {},
            }
    except Exception as exc:
        return {
            "action": "follow_pagination",
            "ok": False,
            "error": str(exc)[:500],
            "patch": {},
            "overrides": {},
        }


def _execute_render_with_browser(
    action: ManagedCrawlAction,
    *,
    target_url: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Render a page with Playwright browser and extract content.

    Used for SPA/JS-heavy sites that don't work with static fetch.
    """
    from ..runtime.native_browser import NativeBrowserConfig

    url = str(action.params.get("target_url") or target_url)
    wait_until = str(action.params.get("wait_until") or "networkidle")
    timeout_ms = int(action.params.get("timeout_ms") or 30000)
    max_items = int(action.params.get("max_items") or 0)

    try:
        config = NativeBrowserConfig(
            headless=True,
            wait_until=wait_until,
            timeout_ms=timeout_ms,
        )
        runtime = NativeBrowserRuntime(config=config)
        request = RuntimeRequest(
            url=url,
            mode="browser",
            wait_until=wait_until,
            timeout_ms=timeout_ms,
            max_items=max_items,
        )
        response = runtime.render(request)
        runtime.close()

        html = response.html or ""
        items = response.items or []
        return {
            "action": "render_with_browser",
            "ok": bool(html),
            "patch": {
                "browser_rendered": True,
                "browser_html_length": len(html),
                "browser_items_count": len(items),
            },
            "overrides": {
                "browser_html": html[:50000],
                "browser_items": items[:max_items] if max_items else items,
                "use_browser": True,
            },
        }
    except Exception as exc:
        return {
            "action": "render_with_browser",
            "ok": False,
            "error": str(exc)[:500],
            "patch": {},
            "overrides": {},
        }


def _execute_extract_from_contract(action: ManagedCrawlAction) -> dict[str, Any]:
    contract = action.params.get("contract") if isinstance(action.params.get("contract"), dict) else {}
    evidence = action.params.get("evidence")
    max_items = max(1, min(int(action.params.get("max_items") or 20), 1000))
    if not contract:
        return {"action": action.action, "ok": False, "error": "missing extraction contract", "patch": {}, "overrides": {}}
    if evidence in (None, ""):
        return {"action": action.action, "ok": False, "error": "missing extraction evidence", "patch": {}, "overrides": {}}
    try:
        items = extract_items_from_contract(
            evidence,
            contract,
            source_url=str(action.params.get("source_url") or contract.get("source_url") or ""),
        )
    except UnsupportedExtractorContract as exc:
        return {"action": action.action, "ok": False, "error": str(exc), "patch": {}, "overrides": {}}
    except Exception as exc:
        return {"action": action.action, "ok": False, "error": f"{type(exc).__name__}: {exc}", "patch": {}, "overrides": {}}

    items = items[:max_items]
    fields_found = sorted({
        key for item in items
        for key, value in item.items()
        if key not in {"source_evidence", "missing_reasons"} and value not in (None, "", [])
    })
    result_payload = {
        "schema_version": "contract-extraction-result/v1",
        "site": contract.get("site", ""),
        "parser_strategy": (contract.get("parser_strategy") or {}).get("name") if isinstance(contract.get("parser_strategy"), dict) else "",
        "item_count": len(items),
        "fields_found": fields_found,
        "items": items,
    }
    evidence_payload = {
        "action": action.action,
        "contract_site": result_payload["site"],
        "parser_strategy": result_payload["parser_strategy"],
        "item_count": len(items),
        "fields_found": fields_found,
        "sample_items": items[:5],
    }
    if isinstance(action.params.get("contract_discovery"), dict):
        evidence_payload["contract_discovery"] = action.params["contract_discovery"]
    return {
        "action": action.action,
        "ok": bool(items),
        "summary": f"contract extractor produced {len(items)} items",
        "extracted_items": items,
        "fields_found": fields_found,
        "evidence": evidence_payload,
        "patch": {},
        "overrides": {"extraction_result": result_payload} if items else {},
    }


def _hydrate_extract_from_contract_action(
    action: ManagedCrawlAction,
    extra_context: dict[str, Any],
) -> ManagedCrawlAction:
    context = extra_context if isinstance(extra_context, dict) else {}
    params = dict(action.params or {})
    if not isinstance(params.get("contract"), dict):
        contract = context.get("extraction_contract")
        if not isinstance(contract, dict):
            contract = context.get("contract")
        if isinstance(contract, dict):
            params["contract"] = contract
    if params.get("evidence") in (None, ""):
        evidence = context.get("extraction_evidence")
        if evidence in (None, ""):
            evidence = context.get("evidence")
        if evidence not in (None, ""):
            params["evidence"] = evidence
    if not isinstance(params.get("contract"), dict) and params.get("evidence") not in (None, ""):
        discovery = discover_extraction_contracts(
            params.get("evidence"),
            source_url=str(params.get("source_url") or context.get("source_url") or ""),
            site=str(context.get("site") or ""),
            sample_items=5,
        )
        contract = discovery.get("best_contract")
        if isinstance(contract, dict):
            params["contract"] = contract
            params["contract_discovery"] = {
                "schema_version": discovery.get("schema_version", ""),
                "best_confidence": discovery.get("best_confidence", 0.0),
                "best_sample_count": discovery.get("best_sample_count", 0),
                "candidate_count": discovery.get("candidate_count", 0),
            }
    if not params.get("source_url"):
        source_url = context.get("source_url")
        contract = params.get("contract") if isinstance(params.get("contract"), dict) else {}
        if not source_url and isinstance(contract, dict):
            source_url = contract.get("source_url")
        if source_url:
            params["source_url"] = source_url
    if not params.get("max_items") and context.get("max_items"):
        params["max_items"] = context.get("max_items")
    return ManagedCrawlAction(
        action=action.action,
        reason=action.reason,
        priority=action.priority,
        params=params,
    )


def _title_selector(profile: dict[str, Any]) -> str:
    selectors = profile.get("selectors") if isinstance(profile.get("selectors"), dict) else {}
    detail = selectors.get("detail") if isinstance(selectors.get("detail"), dict) else selectors
    value = detail.get("title") if isinstance(detail, dict) else ""
    if isinstance(value, dict):
        return str(value.get("selector") or "")
    return str(value or "")


def _normalize_field(value: str) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "price": "highest_price",
        "original_price": "highest_price",
        "images": "image_urls",
        "image": "image_urls",
        "desc": "description",
    }
    return aliases.get(text, text)


def _coerce_plan_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"actions": [], "reasoning_summary": text[:1000], "source": "llm"}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _validate_action_payload(payload: Any, *, index: int | None = None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    raw_action = str(data.get("action") or data.get("type") or "").strip().lower()
    priority = str(data.get("priority") or "medium").strip().lower()
    reason = str(data.get("reason") or data.get("rationale") or "")[:800]
    if priority not in {"low", "medium", "high"}:
        priority = "medium"
    canonical = ACTION_ALIASES.get(raw_action, raw_action)
    if canonical not in EXECUTABLE_ACTIONS:
        return {
            "accepted": False,
            "index": index,
            "raw_action": raw_action,
            "action": canonical,
            "reason": reason,
            "errors": [f"unsupported action: {raw_action or '<missing>'}"],
        }
    raw_params = data.get("params") if isinstance(data.get("params"), dict) else {}
    sanitized, errors, warnings = _sanitize_action_params(canonical, raw_params)
    if errors:
        return {
            "accepted": False,
            "index": index,
            "raw_action": raw_action,
            "action": canonical,
            "reason": reason,
            "errors": errors,
            "warnings": warnings,
        }
    return {
        "accepted": True,
        "index": index,
        "raw_action": raw_action,
        "action": canonical,
        "reason": reason,
        "priority": priority,
        "params": sanitized,
        "warnings": warnings,
    }


def _sanitize_action_params(action: str, params: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    allowed = ACTION_ALLOWED_PARAMS.get(action, set())
    clean: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []
    for key, value in dict(params or {}).items():
        key_text = str(key).strip()
        if key_text not in allowed:
            warnings.append(f"ignored unsupported param: {key_text}")
            continue
        if key_text in {"target_url", "source_url", "output_path", "template_path"}:
            text = _safe_text(value, max_len=800)
            if key_text in {"target_url", "source_url"} and text and not _looks_like_url(text):
                errors.append(f"{key_text} must be http(s), mock, file, or local URL")
                continue
            clean[key_text] = text
        elif key_text in {"field_goal", "reason", "capture_xhr", "target_selector"}:
            clean[key_text] = _safe_text(value, max_len=1000)
        elif key_text in {"imported_catalog", "field_mapping", "overrides"}:
            if isinstance(value, dict):
                clean[key_text] = _bounded_mapping(value)
            elif isinstance(value, list) and key_text == "imported_catalog":
                clean[key_text] = _bounded_list(value, max_items=200)
        elif key_text in {"contract"}:
            if isinstance(value, dict):
                clean[key_text] = _bounded_mapping(value, max_items=120, max_depth=6)
            else:
                errors.append("contract must be an object")
        elif key_text in {"evidence"}:
            if isinstance(value, (dict, list)):
                clean[key_text] = _bounded_value(value, max_items=500, max_depth=8)
            elif isinstance(value, str):
                clean[key_text] = _safe_text(value, max_len=500_000)
            else:
                errors.append("evidence must be string, object, or array")
        elif key_text in {"fields", "required_fields", "selected_fields"}:
            fields = _canonical_field_list(value)
            if not fields:
                errors.append(f"{key_text} must include at least one field")
            clean[key_text] = fields
        elif key_text in {"selectors", "selector_patch"}:
            selectors = _sanitize_selector_mapping(value)
            if not selectors:
                warnings.append(f"{key_text} was empty after selector validation")
            clean[key_text] = selectors
        elif key_text in {"mode"}:
            mode = str(value or "").strip().lower()
            if mode not in SAFE_RUNTIME_MODES:
                errors.append(f"invalid runtime mode: {mode}")
            else:
                clean[key_text] = mode
        elif key_text in {"wait_until"}:
            wait_until = str(value or "").strip().lower()
            if wait_until not in SAFE_WAIT_UNTIL:
                errors.append(f"invalid wait_until: {wait_until}")
            else:
                clean[key_text] = wait_until
        elif key_text in {"format"}:
            fmt = str(value or "").strip().lower()
            if fmt not in SAFE_EXPORT_FORMATS:
                errors.append(f"invalid export format: {fmt}")
            else:
                clean[key_text] = fmt
        elif key_text in {
            "capture_api",
            "protected",
            "persistent_context",
            "rotate_proxy",
            "reanalyze",
            "live_probe",
            "capture_js",
            "capture_dom",
            "apply_profile_patch",
        }:
            clean[key_text] = _safe_bool(value)
        elif key_text in {"item_workers", "sample_limit", "render_time_ms", "max_wait_ms", "timeout_ms", "min_records", "max_depth", "max_nodes", "max_items"}:
            bounds = _numeric_bounds_for_param(key_text)
            clean[key_text] = _safe_int(value, minimum=bounds[0], maximum=bounds[1])
        elif key_text in {"min_field_coverage"}:
            clean[key_text] = _safe_float(value, minimum=0.0, maximum=1.0)
        elif key_text in {"profile_patch", "patch"}:
            patch = _sanitize_profile_patch(value if isinstance(value, dict) else {})
            if not patch:
                warnings.append("profile patch was empty after allowlist filtering")
            clean["profile_patch"] = patch
        elif key_text in {"run_kind"}:
            run_kind = str(value or "").strip().lower()
            if run_kind not in {"test", "full"}:
                errors.append(f"invalid run_kind: {run_kind}")
            else:
                clean[key_text] = run_kind
    return clean, errors, warnings


def _sanitize_profile_patch(value: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for key, item in dict(value or {}).items():
        key_text = str(key).strip()
        if key_text not in SAFE_PROFILE_PATCH_KEYS:
            continue
        if key_text == "selectors":
            selectors = _sanitize_selector_mapping(item)
            if selectors:
                patch[key_text] = selectors
        elif key_text == "target_fields":
            fields = _canonical_field_list(item)
            if fields:
                patch[key_text] = fields
        elif key_text == "access_config":
            access = _sanitize_access_config(item if isinstance(item, dict) else {})
            if access:
                patch[key_text] = access
        elif key_text == "quality_expectations":
            quality = _sanitize_quality_expectations(item if isinstance(item, dict) else {})
            if quality:
                patch[key_text] = quality
        elif key_text in {"crawl_preferences", "api_hints", "pagination_hints"}:
            if isinstance(item, dict):
                patch[key_text] = _bounded_mapping(item, max_items=80, max_depth=4)
    return patch


def _sanitize_selector_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, Any] = {}
    source = value.get("detail") if isinstance(value.get("detail"), dict) else value
    detail: dict[str, Any] = {}
    for key, item in dict(source).items():
        field = _normalize_field(str(key or ""))
        if field not in SAFE_SELECTOR_FIELDS:
            continue
        selector_value = item
        if isinstance(item, dict):
            selector_value = item.get("selector") or item.get("value") or ""
        selector = _safe_selector_text(selector_value)
        if not selector:
            continue
        if isinstance(item, dict):
            selector_type = str(item.get("selector_type") or "").strip().lower()
            if selector_type not in {"css", "xpath", "text", "jsonpath", ""}:
                selector_type = ""
            entry = {"selector": selector}
            if selector_type:
                entry["selector_type"] = selector_type
            detail[field] = entry
        else:
            detail[field] = selector
    if detail:
        output["detail"] = detail
    if isinstance(value.get("list"), dict):
        list_selectors = _sanitize_selector_mapping(value.get("list"))
        if list_selectors.get("detail"):
            output["list"] = list_selectors["detail"]
    return output


def _sanitize_access_config(value: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    mode = str(value.get("mode") or value.get("runtime_mode") or "").strip().lower()
    if mode in SAFE_RUNTIME_MODES:
        output["mode"] = mode
    wait_until = str(value.get("wait_until") or "").strip().lower()
    if wait_until in SAFE_WAIT_UNTIL:
        output["wait_until"] = wait_until
    browser = value.get("browser_config") if isinstance(value.get("browser_config"), dict) else {}
    browser_out: dict[str, Any] = {}
    for key in ("capture_api", "capture_js", "auto_accept_cookies", "persistent_context", "pool_enabled"):
        if key in browser:
            browser_out[key] = _safe_bool(browser.get(key))
    for key in ("render_time_ms", "max_wait_ms", "max_captures"):
        if key in browser:
            bounds = _numeric_bounds_for_param(key)
            browser_out[key] = _safe_int(browser.get(key), minimum=bounds[0], maximum=bounds[1])
    if browser_out:
        output["browser_config"] = browser_out
    return output


def _sanitize_quality_expectations(value: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    if "required_fields" in value:
        fields = _canonical_field_list(value.get("required_fields"))
        if fields:
            output["required_fields"] = fields
    if "min_records" in value:
        output["min_records"] = _safe_int(value.get("min_records"), minimum=1, maximum=1_000_000)
    if "min_field_coverage" in value:
        output["min_field_coverage"] = _safe_float(value.get("min_field_coverage"), minimum=0.0, maximum=1.0)
    return output


def _protocol_acceptance_record(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": parsed.get("index"),
        "raw_action": parsed.get("raw_action", ""),
        "action": parsed.get("action", ""),
        "param_keys": sorted(str(key) for key in dict(parsed.get("params") or {}).keys()),
        "warnings": list(parsed.get("warnings") or []),
    }


def _protocol_rejection_record(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": parsed.get("index"),
        "raw_action": parsed.get("raw_action", ""),
        "action": parsed.get("action", ""),
        "errors": list(parsed.get("errors") or []),
        "warnings": list(parsed.get("warnings") or []),
    }


def _safe_text(value: Any, *, max_len: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    return text[:max_len]


def _safe_selector_text(value: Any) -> str:
    text = _safe_text(value, max_len=300)
    if not text or any(ord(ch) < 32 and ch not in "\t\n\r" for ch in text):
        return ""
    if re.search(r"<\s*script|javascript:", text, flags=re.I):
        return ""
    return text


def _looks_like_url(value: str) -> bool:
    if value.startswith(("mock://", "file://", "http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")):
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: Any, *, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(number, maximum))


def _safe_float(value: Any, *, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(number, maximum))


def _numeric_bounds_for_param(key: str) -> tuple[int, int]:
    bounds = {
        "item_workers": (1, 128),
        "sample_limit": (1, 50),
        "render_time_ms": (0, 120_000),
        "max_wait_ms": (1_000, 180_000),
        "timeout_ms": (1_000, 180_000),
        "min_records": (1, 1_000_000),
        "max_depth": (1, 8),
        "max_nodes": (1, 100_000),
        "max_captures": (1, 500),
    }
    return bounds.get(key, (0, 1_000_000))


def _bounded_list(value: list[Any], *, max_items: int) -> list[Any]:
    output: list[Any] = []
    for item in value[:max_items]:
        output.append(_bounded_value(item, max_items=40, max_depth=2))
    return output


def _bounded_value(value: Any, *, max_items: int = 60, max_depth: int = 3) -> Any:
    if max_depth <= 0:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return _safe_text(value, max_len=2000) if isinstance(value, str) else value
        return _safe_text(value, max_len=500)
    if isinstance(value, dict):
        return _bounded_mapping(value, max_items=max_items, max_depth=max_depth)
    if isinstance(value, list):
        return _bounded_list(value, max_items=max_items)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _safe_text(value, max_len=2000) if isinstance(value, str) else value
    return _safe_text(value, max_len=500)


def _bounded_mapping(value: dict[str, Any], *, max_items: int = 60, max_depth: int = 3) -> dict[str, Any]:
    if max_depth <= 0:
        return {}
    output: dict[str, Any] = {}
    for index, (key, item) in enumerate(dict(value or {}).items()):
        if index >= max_items:
            output["_truncated"] = True
            break
        key_text = _safe_text(key, max_len=120)
        if not key_text:
            continue
        output[key_text] = _bounded_value(item, max_items=max_items, max_depth=max_depth - 1)
    return output


def _canonical_field_list(value: Any) -> list[str]:
    raw = value if isinstance(value, list) else [value]
    fields: list[str] = []
    seen: set[str] = set()
    for item in raw:
        field = _normalize_field(str(item or ""))
        if not field or field in {"auto", "*"} or field in seen:
            continue
        seen.add(field)
        fields.append(field)
    return fields[:50]


def _failure_buckets(
    progress: dict[str, Any],
    diagnostics: dict[str, Any],
    supervision: dict[str, Any],
) -> dict[str, int]:
    candidates: list[Any] = []
    candidates.append(progress.get("failure_buckets"))
    quality = progress.get("quality") if isinstance(progress.get("quality"), dict) else {}
    candidates.append(quality.get("failure_buckets"))
    runner = diagnostics.get("runner_summary") if isinstance(diagnostics.get("runner_summary"), dict) else {}
    candidates.append(runner.get("failure_buckets"))
    candidates.append(diagnostics.get("failure_buckets"))
    last_event = supervision.get("last_event") if isinstance(supervision.get("last_event"), dict) else {}
    candidates.append(last_event.get("failure_buckets"))
    merged: dict[str, int] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key, value in candidate.items():
            try:
                merged[str(key)] = merged.get(str(key), 0) + int(value)
            except (TypeError, ValueError):
                continue
    return merged


def _fallback_selector_patch(fields: list[str], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    selectors = dict(existing or {})
    detail = dict(selectors.get("detail") or {}) if isinstance(selectors.get("detail"), dict) else {}
    for field in fields:
        normalized = _normalize_field(field)
        if normalized in detail:
            continue
        if normalized == "title":
            detail["title"] = {
                "selector_type": "xpath",
                "selector": "string((//h1 | //*[@itemprop='name'] | //meta[@property='og:title']/@content | //title)[1])",
            }
        elif normalized == "highest_price":
            detail["highest_price"] = {
                "selector_type": "xpath",
                "selector": "string((//meta[@property='product:price:amount']/@content | //*[@itemprop='price']/@content | //*[@itemprop='price'])[1])",
            }
        elif normalized == "description":
            detail["description"] = {
                "selector_type": "xpath",
                "selector": "string((//*[@itemprop='description'] | //meta[@name='description']/@content |//*[contains(@class,'description')])[1])",
            }
        elif normalized == "image_urls":
            detail["image_urls"] = {
                "selector_type": "xpath",
                "selector": "//meta[@property='og:image']/@content | //*[@itemprop='image']/@src | //img/@src",
            }
        elif normalized == "colors":
            detail["colors"] = "[class*='color'], [data-color], [aria-label*='color'], [aria-label*='colour']"
        elif normalized == "sizes":
            detail["sizes"] = "[class*='size'], [data-size], [aria-label*='size']"
    if detail:
        selectors["detail"] = detail
    return selectors


def _dedupe_actions(actions: list[ManagedCrawlAction]) -> list[ManagedCrawlAction]:
    seen: set[str] = set()
    output: list[ManagedCrawlAction] = []
    for action in actions:
        if action.action in seen:
            continue
        seen.add(action.action)
        output.append(action)
    return output


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(patch or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged
