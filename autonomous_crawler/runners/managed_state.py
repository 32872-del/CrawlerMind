"""Unified state packet for AI-managed crawl loops.

The managed loop needs one stable state shape that both LLM advisors and the
frontend can consume. This module turns the existing job/profile/evidence data
into that packet without introducing another crawler path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from .product_workflow import build_run_evidence_pack, events_for_job, summarize_run_progress


MANAGED_CRAWL_STATE_VERSION = "managed-crawl-state/v1"


@dataclass(frozen=True)
class ManagedCrawlState:
    task: dict[str, Any]
    user_input: dict[str, Any]
    workflow: dict[str, Any]
    input_snapshot: dict[str, Any]
    profile_snapshot: dict[str, Any]
    progress: dict[str, Any]
    evidence_pack: dict[str, Any]
    quality_context: dict[str, Any]
    runtime_context: dict[str, Any]
    extraction_context: dict[str, Any]
    decision_context: dict[str, Any]
    action_context: dict[str, Any]
    repair_context: dict[str, Any]
    export_context: dict[str, Any]
    timeline: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MANAGED_CRAWL_STATE_VERSION,
            "task": dict(self.task),
            "user_input": dict(self.user_input),
            "workflow": dict(self.workflow),
            "input_snapshot": dict(self.input_snapshot),
            "profile_snapshot": dict(self.profile_snapshot),
            "progress": dict(self.progress),
            "evidence_pack": dict(self.evidence_pack),
            "quality_context": dict(self.quality_context),
            "runtime_context": dict(self.runtime_context),
            "extraction_context": dict(self.extraction_context),
            "decision_context": dict(self.decision_context),
            "action_context": dict(self.action_context),
            "repair_context": dict(self.repair_context),
            "export_context": dict(self.export_context),
            "timeline": [dict(item) for item in self.timeline],
        }


def build_managed_crawl_state(job: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical state packet for one product workflow job."""
    job = job if isinstance(job, dict) else {}
    progress = summarize_run_progress(job)
    evidence_pack = build_run_evidence_pack(job)
    run_spec = job.get("product_run_spec") if isinstance(job.get("product_run_spec"), dict) else {}
    profile = _profile_from_job(job, run_spec, evidence_pack)
    timeline = _managed_timeline(job)
    focus = list(evidence_pack.get("recommended_focus") or [])
    current_stage = str(progress.get("current_stage") or job.get("status") or "unknown")

    state = ManagedCrawlState(
        task=_task_context(job, run_spec, progress),
        user_input=_user_input_context(job, run_spec),
        workflow={
            "loop_name": "AI Managed Crawl Loop v2",
            "loop_position": _loop_position(current_stage, focus, job),
            "current_stage": current_stage,
            "status": job.get("status", ""),
            "recommended_focus": focus,
            "next_expected_steps": _next_expected_steps(progress, focus, job),
            "is_closed_loop_ready": _closed_loop_ready(job, evidence_pack),
            "state_coverage": _state_coverage(job, run_spec, profile, evidence_pack, timeline),
        },
        input_snapshot=_input_snapshot(run_spec),
        profile_snapshot=_profile_snapshot(profile),
        progress=progress,
        evidence_pack=evidence_pack,
        quality_context=_quality_context(progress, evidence_pack),
        runtime_context=_runtime_context(job, evidence_pack),
        extraction_context=_extraction_context(job, run_spec),
        decision_context=_decision_context(job, evidence_pack),
        action_context=_action_context(job),
        repair_context=_repair_context(job, evidence_pack),
        export_context=_export_context(job, run_spec),
        timeline=timeline,
    )
    return state.to_dict()


def compact_managed_state_for_llm(state: dict[str, Any]) -> dict[str, Any]:
    """Return a smaller packet suitable for one LLM decision turn."""
    state = state if isinstance(state, dict) else {}
    return {
        "schema_version": "managed-crawl-llm-context/v1",
        "task": state.get("task") or {},
        "workflow": state.get("workflow") or {},
        "input_snapshot": _compact_value(state.get("input_snapshot"), max_items=20),
        "profile_snapshot": _compact_value(state.get("profile_snapshot"), max_items=30),
        "progress": state.get("progress") or {},
        "quality_context": state.get("quality_context") or {},
        "runtime_context": _compact_value(state.get("runtime_context"), max_items=40),
        "extraction_context": _compact_value(state.get("extraction_context"), max_items=30),
        "decision_context": _compact_value(state.get("decision_context"), max_items=30),
        "action_context": _compact_value(state.get("action_context"), max_items=30),
        "repair_context": state.get("repair_context") or {},
        "recent_timeline": list(state.get("timeline") or [])[-20:],
    }


def _task_context(job: dict[str, Any], run_spec: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": job.get("task_id", ""),
        "parent_task_id": job.get("parent_task_id", ""),
        "repair_source": job.get("repair_source", ""),
        "kind": job.get("kind", ""),
        "status": job.get("status", ""),
        "current_stage": progress.get("current_stage", ""),
        "target_url": run_spec.get("target_url") or job.get("target_url") or "",
        "run_id": job.get("run_id", ""),
        "profile_name": job.get("profile_name", ""),
        "created_at": job.get("created_at", ""),
        "updated_at": job.get("updated_at", ""),
    }


def _user_input_context(job: dict[str, Any], run_spec: dict[str, Any]) -> dict[str, Any]:
    export = run_spec.get("export") if isinstance(run_spec.get("export"), dict) else {}
    return {
        "goal": job.get("user_goal", ""),
        "target_url": run_spec.get("target_url") or job.get("target_url") or "",
        "selected_fields": list(run_spec.get("selected_fields") or []),
        "catalog_node_count": len(run_spec.get("catalog_nodes") or []) if isinstance(run_spec.get("catalog_nodes"), list) else 0,
        "run_mode": run_spec.get("run_mode", ""),
        "item_workers": run_spec.get("item_workers"),
        "test_limit": run_spec.get("test_limit"),
        "export": dict(export),
        "managed_ai": job.get("managed_ai") if isinstance(job.get("managed_ai"), dict) else {"enabled": False},
    }


def _input_snapshot(run_spec: dict[str, Any]) -> dict[str, Any]:
    catalog_nodes = run_spec.get("catalog_nodes") if isinstance(run_spec.get("catalog_nodes"), list) else []
    return {
        "target_url": run_spec.get("target_url", ""),
        "selected_fields": list(run_spec.get("selected_fields") or []),
        "catalog_nodes": [_catalog_node_summary(item) for item in catalog_nodes[:50] if isinstance(item, dict)],
        "catalog_node_count": len(catalog_nodes),
        "runtime_dir": run_spec.get("runtime_dir", ""),
        "supervision_mode": run_spec.get("supervision_mode", ""),
    }


def _catalog_node_summary(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": str(node.get("label") or node.get("name") or "")[:160],
        "url": str(node.get("url") or "")[:500],
        "path": list(node.get("path") or [])[:6] if isinstance(node.get("path"), list) else [],
        "level1": node.get("level1", ""),
        "level2": node.get("level2", ""),
        "level3": node.get("level3", ""),
    }


def _profile_from_job(job: dict[str, Any], run_spec: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    profile = run_spec.get("profile") if isinstance(run_spec.get("profile"), dict) else {}
    if profile:
        return profile
    profile_run = job.get("profile_run") if isinstance(job.get("profile_run"), dict) else {}
    report = profile_run.get("report") if isinstance(profile_run.get("report"), dict) else {}
    if isinstance(report.get("profile"), dict):
        return report["profile"]
    summary = evidence_pack.get("profile_summary") if isinstance(evidence_pack.get("profile_summary"), dict) else {}
    return summary


def _profile_snapshot(profile: dict[str, Any]) -> dict[str, Any]:
    profile = profile if isinstance(profile, dict) else {}
    selectors = profile.get("selectors") if isinstance(profile.get("selectors"), dict) else {}
    crawl_preferences = profile.get("crawl_preferences") if isinstance(profile.get("crawl_preferences"), dict) else {}
    api_hints = profile.get("api_hints") if isinstance(profile.get("api_hints"), dict) else {}
    pagination_hints = profile.get("pagination_hints") if isinstance(profile.get("pagination_hints"), dict) else {}
    access_config = profile.get("access_config") if isinstance(profile.get("access_config"), dict) else {}
    quality = profile.get("quality_expectations") if isinstance(profile.get("quality_expectations"), dict) else {}
    return {
        "name": profile.get("name", ""),
        "target_fields": list(profile.get("target_fields") or []),
        "selector_fields": sorted(str(key) for key in selectors.keys()),
        "selectors": _compact_value(selectors, max_items=30),
        "crawl_preferences": _compact_value(crawl_preferences, max_items=30),
        "api_hints": _safe_api_hints(api_hints),
        "pagination_hints": _compact_value(pagination_hints, max_items=30),
        "access_config": _safe_access_config(access_config),
        "quality_expectations": _compact_value(quality, max_items=30),
        "training_notes": list(profile.get("training_notes") or [])[:30],
    }


def _quality_context(progress: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    quality = progress.get("quality") if isinstance(progress.get("quality"), dict) else {}
    return {
        "indicator": progress.get("quality_indicator", "unknown"),
        "summary": _compact_value(quality, max_items=40),
        "gaps": list(evidence_pack.get("quality_gaps") or []),
        "records_saved": progress.get("records_saved", 0),
        "failure_buckets": dict(progress.get("failure_buckets") or {}),
        "last_error": progress.get("last_error", ""),
    }


def _runtime_context(job: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    access = evidence_pack.get("access_evidence") if isinstance(evidence_pack.get("access_evidence"), dict) else {}
    diagnostics = evidence_pack.get("diagnostics") if isinstance(evidence_pack.get("diagnostics"), dict) else {}
    return {
        "access_evidence": access,
        "diagnostics": diagnostics,
        "supervision": job.get("supervision") if isinstance(job.get("supervision"), dict) else {},
        "latest_access_probe": job.get("latest_access_probe") if isinstance(job.get("latest_access_probe"), dict) else {},
        "profile_run_status": _profile_run_status(job),
    }


def _profile_run_status(job: dict[str, Any]) -> dict[str, Any]:
    profile_run = job.get("profile_run") if isinstance(job.get("profile_run"), dict) else {}
    runner = profile_run.get("runner_summary") if isinstance(profile_run.get("runner_summary"), dict) else {}
    frontier = profile_run.get("frontier_stats") if isinstance(profile_run.get("frontier_stats"), dict) else {}
    product_stats = profile_run.get("product_stats") if isinstance(profile_run.get("product_stats"), dict) else {}
    return {
        "run_id": profile_run.get("run_id", job.get("run_id", "")),
        "status": profile_run.get("status", ""),
        "accepted": profile_run.get("accepted"),
        "runner_summary": _compact_value(runner, max_items=30),
        "frontier_stats": _compact_value(frontier, max_items=30),
        "product_stats": _compact_value(product_stats, max_items=30),
    }


def _decision_context(job: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    decisions = [item for item in list(job.get("ai_decisions") or []) if isinstance(item, dict)]
    traces = [item for item in list(job.get("llm_traces") or []) if isinstance(item, dict)]
    return {
        "managed_history": evidence_pack.get("managed_history") or {},
        "ai_decision_count": len(decisions),
        "llm_trace_count": len(traces),
        "latest_ai_decision": _compact_value(decisions[-1], max_items=30) if decisions else None,
        "latest_llm_trace": _compact_value(traces[-1], max_items=30) if traces else None,
        "recent_ai_decisions": [_compact_value(item, max_items=20) for item in decisions[-10:]],
        "recent_llm_traces": [_compact_value(item, max_items=20) for item in traces[-10:]],
    }


def _action_context(job: dict[str, Any]) -> dict[str, Any]:
    actions = [item for item in list(job.get("managed_actions") or []) if isinstance(item, dict)]
    steps = [item for item in list(job.get("managed_steps") or []) if isinstance(item, dict)]
    loops = [item for item in list(job.get("managed_control_loops") or []) if isinstance(item, dict)]
    latest_action = actions[-1] if actions else {}
    latest_step = steps[-1] if steps else {}
    latest_loop = job.get("latest_managed_control_loop") if isinstance(job.get("latest_managed_control_loop"), dict) else (loops[-1] if loops else {})
    return {
        "managed_action_count": len(actions),
        "managed_step_count": len(steps),
        "managed_control_loop_count": len(loops),
        "latest_managed_action": _compact_value(latest_action, max_items=40),
        "latest_managed_step": _compact_value(latest_step, max_items=40),
        "latest_managed_control_loop": _compact_value(latest_loop, max_items=40),
        "pending_action_summary": _pending_action_summary(latest_action, latest_step, latest_loop),
    }


def _extraction_context(job: dict[str, Any], run_spec: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for source in (
        job.get("extraction_contract"),
        run_spec.get("extraction_contract"),
        job.get("contract"),
        run_spec.get("contract"),
    ):
        if isinstance(source, dict):
            candidates.append(source)
    profile = run_spec.get("profile") if isinstance(run_spec.get("profile"), dict) else {}
    constraints = profile.get("constraints") if isinstance(profile.get("constraints"), dict) else {}
    if isinstance(constraints.get("extraction_contract"), dict):
        candidates.append(constraints["extraction_contract"])
    extra = job.get("extra_context") if isinstance(job.get("extra_context"), dict) else {}
    for source in (extra.get("extraction_contract"), extra.get("contract")):
        if isinstance(source, dict):
            candidates.append(source)
    contract = candidates[-1] if candidates else {}
    strategy = contract.get("parser_strategy") if isinstance(contract.get("parser_strategy"), dict) else {}
    evidence = (
        job.get("extraction_evidence")
        or run_spec.get("extraction_evidence")
        or constraints.get("extraction_evidence")
        or extra.get("extraction_evidence")
        or extra.get("evidence")
    )
    latest_extraction = _latest_extraction_result(job)
    return {
        "has_contract": bool(contract),
        "site": contract.get("site", "") if contract else "",
        "parser_strategy": strategy.get("name", "") if strategy else "",
        "source_url": contract.get("source_url", "") if contract else "",
        "has_evidence": evidence not in (None, ""),
        "evidence_type": type(evidence).__name__ if evidence not in (None, "") else "",
        "evidence_size": len(evidence) if isinstance(evidence, (str, list, dict)) else 0,
        "latest_extraction": latest_extraction,
        "can_execute_extract_from_contract": bool(contract and evidence not in (None, "")),
    }


def _repair_context(job: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    auto_repair = job.get("managed_auto_repair") if isinstance(job.get("managed_auto_repair"), dict) else {}
    suggestions = job.get("ai_repair_suggestions") if isinstance(job.get("ai_repair_suggestions"), list) else []
    return {
        "auto_repair": _compact_value(auto_repair, max_items=30),
        "ai_repair_suggestions": suggestions[-20:],
        "repair_source": job.get("repair_source", ""),
        "recommended_focus": list(evidence_pack.get("recommended_focus") or []),
        "needs_repair": _needs_repair(job, evidence_pack),
    }


def _export_context(job: dict[str, Any], run_spec: dict[str, Any]) -> dict[str, Any]:
    export = job.get("export") if isinstance(job.get("export"), dict) else {}
    requested = run_spec.get("export") if isinstance(run_spec.get("export"), dict) else {}
    return {
        "requested": dict(requested),
        "latest_result": dict(export),
        "is_ready": bool(export and not export.get("error")),
        "error": export.get("error", "") if export else "",
    }


def _managed_timeline(job: dict[str, Any]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for index, event in enumerate(events_for_job(job)):
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("type") or "event")
        timeline.append({
            "step_id": f"{index + 1:04d}",
            "time": event.get("time", ""),
            "stage": _stage_from_event_type(event_type),
            "type": event_type,
            "message": str(event.get("message") or "")[:500],
            "data": _compact_value(event.get("data"), max_items=40),
        })
    return timeline


def _stage_from_event_type(event_type: str) -> str:
    if event_type.startswith("ai_") or event_type.startswith("llm_trace"):
        return "decision"
    if event_type.startswith("managed_") or event_type.startswith("supervision_"):
        return "action"
    if event_type.startswith("access_probe"):
        return "evidence"
    if event_type.startswith("export"):
        return "export"
    if event_type == "failure":
        return "diagnosis"
    if event_type.startswith("job_"):
        return "runtime"
    return "workflow"


def _loop_position(current_stage: str, focus: list[str], job: dict[str, Any]) -> str:
    status = str(job.get("status") or "").lower()
    if status in {"completed", "failed", "cancelled"} and _needs_repair(job, {"recommended_focus": focus}):
        return "diagnose_or_repair"
    if job.get("managed_auto_repair"):
        return "repair_or_rerun"
    if job.get("export"):
        return "export"
    if current_stage in {"queued", "starting", "running", "finishing"} or status == "running":
        return "execute"
    if "zero_records" in focus or "quality_repair" in focus or "access_challenge" in focus:
        return "diagnose_or_repair"
    return "observe"


def _next_expected_steps(progress: dict[str, Any], focus: list[str], job: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    if not job.get("profile_run"):
        steps.append("run_test")
    if _has_extraction_context(job):
        steps.append("extract_from_contract")
    if "access_challenge" in focus:
        steps.extend(["inspect_access", "adjust_runtime"])
    if "zero_records" in focus:
        steps.extend(["repair_selectors", "collect_browser_or_api_sample"])
    if "field_coverage" in focus or "quality_repair" in focus:
        steps.extend(["evaluate_quality", "patch_profile"])
    if _needs_repair(job, {"recommended_focus": focus}):
        steps.append("prepare_rerun")
    if progress.get("status") == "completed" and not job.get("export"):
        steps.append("export_results")
    return list(dict.fromkeys(steps))[:10]


def _closed_loop_ready(job: dict[str, Any], evidence_pack: dict[str, Any]) -> bool:
    return bool(
        job.get("product_run_spec")
        and evidence_pack.get("schema_version") == "run-evidence-pack/v1"
        and isinstance(job.get("managed_ai"), dict)
    )


def _state_coverage(
    job: dict[str, Any],
    run_spec: dict[str, Any],
    profile: dict[str, Any],
    evidence_pack: dict[str, Any],
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = {
        "has_user_goal": bool(job.get("user_goal")),
        "has_target_url": bool(run_spec.get("target_url") or job.get("target_url")),
        "has_profile": bool(profile),
        "has_fields": bool(run_spec.get("selected_fields") or profile.get("target_fields")),
        "has_evidence_pack": evidence_pack.get("schema_version") == "run-evidence-pack/v1",
        "has_timeline": bool(timeline),
        "has_runtime_result": bool(job.get("profile_run")),
        "has_managed_history": bool(job.get("managed_actions") or job.get("managed_steps") or job.get("ai_decisions")),
    }
    ready_count = sum(1 for value in checks.values() if value)
    return {
        **checks,
        "ready_count": ready_count,
        "total": len(checks),
        "ratio": round(ready_count / len(checks), 4) if checks else 0.0,
    }


def _pending_action_summary(*records: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        result = record.get("result") if isinstance(record.get("result"), dict) else record
        plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
        for action in list(plan.get("actions") or [])[:20]:
            if isinstance(action, dict):
                actions.append({
                    "action": action.get("action", ""),
                    "priority": action.get("priority", ""),
                    "reason": str(action.get("reason") or "")[:300],
                })
    return actions[-20:]


def _latest_extraction_result(job: dict[str, Any]) -> dict[str, Any]:
    actions = [item for item in list(job.get("managed_actions") or []) if isinstance(item, dict)]
    for record in reversed(actions):
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        overrides = result.get("run_overrides") if isinstance(result.get("run_overrides"), dict) else {}
        extraction = overrides.get("extraction_result") if isinstance(overrides.get("extraction_result"), dict) else {}
        if extraction:
            return {
                "schema_version": extraction.get("schema_version", ""),
                "site": extraction.get("site", ""),
                "parser_strategy": extraction.get("parser_strategy", ""),
                "item_count": extraction.get("item_count", 0),
                "fields_found": list(extraction.get("fields_found") or [])[:30],
                "sample_items": list(extraction.get("items") or [])[:3],
            }
    return {}


def _has_extraction_context(job: dict[str, Any]) -> bool:
    """Check if the job has extraction contract context available."""
    extra = job.get("extra_context") if isinstance(job.get("extra_context"), dict) else {}
    if isinstance(extra.get("extraction_contract"), dict) and extra.get("extraction_contract"):
        evidence = extra.get("extraction_evidence") or extra.get("evidence")
        if evidence not in (None, ""):
            return True
    if isinstance(extra.get("contract"), dict) and extra.get("contract"):
        evidence = extra.get("evidence")
        if evidence not in (None, ""):
            return True
    # Check if a previous action already produced extraction results
    for record in list(job.get("managed_actions") or [])[-5:]:
        if not isinstance(record, dict):
            continue
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        overrides = result.get("run_overrides") if isinstance(result.get("run_overrides"), dict) else {}
        if isinstance(overrides.get("extraction_result"), dict):
            return True
    return False


def _needs_repair(job: dict[str, Any], evidence_pack: dict[str, Any]) -> bool:
    focus = set(evidence_pack.get("recommended_focus") or [])
    progress = summarize_run_progress(job)
    return bool(
        focus.intersection({"zero_records", "quality_repair", "field_coverage", "access_challenge"})
        or progress.get("quality_indicator") in {"fail", "unknown"}
        or int(progress.get("records_saved") or 0) == 0 and job.get("status") in {"completed", "failed"}
    )


def _safe_api_hints(api_hints: dict[str, Any]) -> dict[str, Any]:
    output = _compact_value(api_hints, max_items=40)
    if isinstance(output, dict):
        headers = output.get("headers")
        if isinstance(headers, dict):
            output["headers"] = _redact_mapping(headers)
        if "post_json" in output:
            output["post_json"] = _compact_value(output.get("post_json"), max_items=40)
    return output if isinstance(output, dict) else {}


def _safe_access_config(access_config: dict[str, Any]) -> dict[str, Any]:
    output = _compact_value(access_config, max_items=40)
    if isinstance(output, dict):
        for key in ("proxy", "proxies", "cookies", "headers", "storage_state"):
            if key in output:
                output[key] = "[REDACTED]"
    return output if isinstance(output, dict) else {}


def _redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, item in value.items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("authorization", "cookie", "token", "secret", "key")):
            output[str(key)] = "[REDACTED]"
        else:
            output[str(key)] = str(item)[:500]
    return output


def _compact_value(value: Any, *, max_items: int) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                output["_truncated"] = True
                break
            output[str(key)] = _compact_value(item, max_items=max_items)
        return output
    if isinstance(value, list):
        return [_compact_value(item, max_items=max_items) for item in value[:max_items]]
    if isinstance(value, str):
        return _redact_text(value[:4000])
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except Exception:
        return str(value)[:1000]


def _redact_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("authorization:", "bearer ", "api_key", "apikey", "password=", "secret=")):
        return "[REDACTED]"
    return text
