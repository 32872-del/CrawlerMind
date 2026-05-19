"""Managed crawl action planning and execution.

This module gives CLM's managed mode a concrete tool space. Actions are
serializable, bounded, and map to existing crawler capabilities such as site
analysis, access tuning, selector repair, and executable rerun preparation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .product_workflow import (
    DEFAULT_PRODUCT_FIELDS,
    analyze_site_for_product_workflow,
)


SUPPORTED_ACTIONS = {
    "reanalyze_site",
    "discover_catalog",
    "probe_fields",
    "inspect_access",
    "repair_selectors",
    "adjust_runtime",
    "evaluate_quality",
    "prepare_export",
    "prepare_rerun",
}


@dataclass(frozen=True)
class ManagedCrawlAction:
    action: str
    reason: str = ""
    priority: str = "medium"
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Any) -> "ManagedCrawlAction":
        data = payload if isinstance(payload, dict) else {}
        action = str(data.get("action") or "").strip().lower()
        if action not in SUPPORTED_ACTIONS:
            action = "prepare_rerun"
        priority = str(data.get("priority") or "medium").strip().lower()
        if priority not in {"low", "medium", "high"}:
            priority = "medium"
        params = data.get("params") if isinstance(data.get("params"), dict) else {}
        return cls(
            action=action,
            reason=str(data.get("reason") or "")[:800],
            priority=priority,
            params=dict(params),
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

    @classmethod
    def from_dict(cls, payload: Any) -> "ManagedActionPlan":
        data = payload if isinstance(payload, dict) else {}
        raw_actions = data.get("actions") if isinstance(data.get("actions"), list) else []
        actions = [ManagedCrawlAction.from_dict(item) for item in raw_actions[:20]]
        return cls(
            actions=actions,
            source=str(data.get("source") or "llm")[:80],
            reasoning_summary=str(data.get("reasoning_summary") or "")[:1000],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "reasoning_summary": self.reasoning_summary,
            "actions": [action.to_dict() for action in self.actions],
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
    if not selected_fields or any(str(item).strip().lower() in {"", "auto", "*"} for item in selected_fields):
        actions.append(ManagedCrawlAction(
            action="probe_fields",
            priority="high",
            reason="Selected fields are missing or too vague; probe product fields before rerun.",
            params={"field_goal": str(extra_context.get("field_goal") or "")},
        ))

    last_supervision = supervision.get("last_event") if isinstance(supervision.get("last_event"), dict) else {}
    quality = str(progress.get("quality_indicator") or "").lower()
    records_saved = int(progress.get("records_saved") or progress.get("record_count") or 0)
    failed = int(progress.get("failed") or 0)
    reason_text = str(last_supervision.get("reason") or diagnostics.get("recommendation") or "").lower()
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
            params={"mode": "dynamic", "capture_api": True, "wait_until": "networkidle"},
        ))
    if quality in {"fail", "warn", "unknown"} or records_saved == 0:
        actions.append(ManagedCrawlAction(
            action="evaluate_quality",
            priority="medium",
            reason="Quality gate needs explicit required fields and success thresholds.",
            params={"required_fields": selected_fields or DEFAULT_PRODUCT_FIELDS},
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
) -> dict[str, Any]:
    """Execute bounded managed actions and return profile/run overrides."""
    run_spec = run_spec if isinstance(run_spec, dict) else {}
    extra_context = extra_context if isinstance(extra_context, dict) else {}
    results: list[dict[str, Any]] = []
    profile_patch: dict[str, Any] = {}
    run_overrides: dict[str, Any] = {}

    for action in plan.actions:
        if action.action == "reanalyze_site":
            result = _execute_reanalyze_site(action, target_url=target_url, advisor=advisor, extra_context=extra_context)
        elif action.action == "discover_catalog":
            result = _execute_discover_catalog(action, target_url=target_url, advisor=advisor, extra_context=extra_context)
        elif action.action == "probe_fields":
            result = _execute_probe_fields(action, target_url=target_url, profile=profile, run_spec=run_spec, advisor=advisor, extra_context=extra_context)
        elif action.action == "inspect_access":
            result = _execute_inspect_access(action, target_url=target_url, profile=profile)
        elif action.action == "repair_selectors":
            result = _execute_repair_selectors(action, profile=profile)
        elif action.action == "adjust_runtime":
            result = _execute_adjust_runtime(action)
        elif action.action == "evaluate_quality":
            result = _execute_evaluate_quality(action, profile=profile, run_spec=run_spec)
        elif action.action == "prepare_export":
            result = _execute_prepare_export(action, run_spec=run_spec, extra_context=extra_context)
        else:
            result = {"action": action.action, "ok": True, "patch": {}, "overrides": {}}
        profile_patch = _deep_merge(profile_patch, result.get("patch") if isinstance(result.get("patch"), dict) else {})
        run_overrides = _deep_merge(run_overrides, result.get("overrides") if isinstance(result.get("overrides"), dict) else {})
        results.append(result)

    if not run_overrides and profile_patch:
        run_overrides = dict(profile_patch)
    return {
        "schema_version": "managed-action-result/v1",
        "plan": plan.to_dict(),
        "results": results,
        "profile_patch": profile_patch,
        "run_overrides": run_overrides,
        "rerun_ready": bool(profile_patch or run_overrides),
    }


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
        for key in ("selectors", "crawl_preferences", "access_config", "pagination_hints", "quality_expectations"):
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
    return {
        "action": action.action,
        "ok": True,
        "summary": f"field probe prepared {len(fields)} target fields",
        "fields": fields,
        "patch": patch,
        "overrides": patch,
    }


def _execute_inspect_access(
    action: ManagedCrawlAction,
    *,
    target_url: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    access = dict(profile.get("access_config") or {})
    browser = dict(access.get("browser_config") or {})
    access["mode"] = "dynamic"
    access["wait_until"] = "networkidle"
    browser["capture_api"] = True
    browser["auto_accept_cookies"] = True
    browser["render_time_ms"] = max(3000, int(browser.get("render_time_ms") or 0))
    browser["max_wait_ms"] = max(30000, int(browser.get("max_wait_ms") or 0))
    access["browser_config"] = browser
    patch["access_config"] = access
    return {
        "action": action.action,
        "ok": True,
        "summary": "runtime access knobs prepared",
        "patch": patch,
        "overrides": patch,
    }


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
    patch = {
        "access_config": {
            "mode": mode,
            "wait_until": str(action.params.get("wait_until") or "networkidle"),
            "browser_config": {
                "capture_api": bool(action.params.get("capture_api", True)),
                "auto_accept_cookies": True,
                "render_time_ms": 3000,
                "max_wait_ms": 30000,
            },
        }
    }
    return {
        "action": action.action,
        "ok": True,
        "summary": "runtime configuration adjusted",
        "patch": patch,
        "overrides": patch,
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
