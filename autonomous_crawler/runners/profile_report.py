"""Stable report helpers for profile-driven training runs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_profile_run_report(
    *,
    profile_name: str,
    profile_path: str = "",
    run_id: str = "",
    runner_summary: Any = None,
    quality_summary: dict[str, Any] | None = None,
    sample_records: list[dict[str, Any]] | None = None,
    failures: list[dict[str, Any]] | None = None,
    runtime_backend: str = "",
    parser_backend: str = "",
    stop_reason: str = "",
    target: str = "",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a product-like report payload from a profile training case.

    The helper intentionally returns plain JSON-serializable data so training
    scripts can persist it without knowing the internal runner object shape.
    """
    quality = dict(quality_summary or {})
    runner = runner_summary_as_dict(runner_summary)
    failed_urls = list(quality.get("failed_urls") or [])
    if not failed_urls:
        failed_urls = [
            str(failure.get("url"))
            for failure in list(failures or [])
            if isinstance(failure, dict) and failure.get("url")
        ]
    report = {
        "schema_version": "profile-run-report/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "name": profile_name,
            "path": profile_path,
            "target": target,
        },
        "run": {
            "run_id": run_id,
            "runtime_backend": runtime_backend,
            "parser_backend": parser_backend,
            "runner_summary": runner,
            "stop_reason": stop_reason or str(quality.get("pagination_stop_reason") or "not_recorded"),
        },
        "metrics": {
            "record_count": int(quality.get("total_records") or runner.get("records_saved") or 0),
            "field_completeness": dict(quality.get("field_completeness") or {}),
            "duplicate_rate": float(quality.get("duplicate_rate") or 0.0),
            "duplicate_count": int(quality.get("duplicate_count") or 0),
            "failed_url_count": int(quality.get("failed_url_count") or len(failed_urls)),
            "failed_urls": failed_urls,
            "frontier_stats": dict(quality.get("frontier_stats") or {}),
        },
        "quality_gate": dict(quality.get("quality_gate") or {}),
        "quality_policy": dict(quality.get("quality_policy") or {}),
        "duplicate_key_strategy": dict(quality.get("duplicate_key_strategy") or {}),
        "samples": list(sample_records or []),
        "failures": list(failures or []),
        "next_actions": next_actions_for_quality(quality),
        "notes": list(notes or []),
    }
    report["accepted"] = not bool(report["quality_gate"].get("should_fail"))
    return report


def runner_summary_as_dict(summary: Any) -> dict[str, Any]:
    if summary is None:
        return {}
    if isinstance(summary, dict):
        return dict(summary)
    if hasattr(summary, "as_dict"):
        return dict(summary.as_dict())
    return {
        key: value
        for key, value in vars(summary).items()
        if not key.startswith("_")
    }


def next_actions_for_quality(quality: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    gate = dict(quality.get("quality_gate") or {})
    for check in list(gate.get("checks") or []):
        if not isinstance(check, dict) or check.get("passed"):
            continue
        name = str(check.get("name") or "")
        if name == "min_items":
            actions.append("Increase page depth, pagination coverage, or seed URLs to meet min_items.")
        elif name.startswith("field:"):
            field = str(check.get("field") or name.split(":", 1)[-1])
            actions.append(f"Improve profile mapping or selectors for `{field}` completeness.")
        elif name == "duplicate_rate":
            actions.append("Review canonical URL mapping and category-aware dedupe behavior.")
        elif name == "failed_url_count":
            actions.append("Inspect failed URLs and retry/access diagnostics before scaling.")
    if not actions:
        actions.append("No immediate quality gate action required; continue broader real-site regression.")
    return actions


def render_profile_markdown_report(report: dict[str, Any]) -> str:
    profile = dict(report.get("profile") or {})
    metrics = dict(report.get("metrics") or {})
    gate = dict(report.get("quality_gate") or {})
    lines = [
        f"# Profile Run Report: {profile.get('name', '')}",
        "",
        f"- Target: {profile.get('target', '')}",
        f"- Records: {metrics.get('record_count', 0)}",
        f"- Quality gate: {gate.get('severity', 'unknown')}",
        f"- Duplicate rate: {metrics.get('duplicate_rate', 0.0)}",
        f"- Failed URLs: {metrics.get('failed_url_count', 0)}",
        "",
        "## Next Actions",
    ]
    lines.extend(f"- {action}" for action in list(report.get("next_actions") or []))
    return "\n".join(lines) + "\n"
