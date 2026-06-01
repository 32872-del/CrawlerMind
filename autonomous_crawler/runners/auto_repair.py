"""Failure Diagnosis and Auto-Repair Loop for AI Managed Crawl Loop v2.

This module closes the gap between "execution finished" and "AI knows what
went wrong and how to fix it". It takes execution results, classifies failures,
generates targeted repair actions, and orchestrates re-execution.

The loop:
    execute -> diagnose -> repair_plan -> re_execute -> compare -> report
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .managed_actions import (
    ManagedActionPlan,
    ManagedCrawlAction,
    execute_managed_action_plan,
    build_deterministic_action_plan,
)
from .managed_state import build_managed_crawl_state, compact_managed_state_for_llm


# ---------------------------------------------------------------------------
# Failure Categories
# ---------------------------------------------------------------------------

class FailureCategory(str, Enum):
    """Classified failure types with mapped repair strategies."""
    NO_RECORDS = "no_records"
    LOW_COVERAGE = "low_coverage"
    SELECTOR_MISS = "selector_miss"
    ACCESS_CHALLENGE = "access_challenge"
    ACCESS_BLOCKED = "access_blocked"
    API_REPLAY_FAILED = "api_replay_failed"
    TIMEOUT = "timeout"
    BROWSER_CRASH = "browser_crash"
    EMPTY_HTML = "empty_html"
    PAGINATION_STUCK = "pagination_stuck"
    QUALITY_FAIL = "quality_fail"
    PROXY_ERROR = "proxy_error"
    UNKNOWN = "unknown"


# Maps failure categories to repair action types
REPAIR_ACTION_MAP: dict[str, list[str]] = {
    FailureCategory.NO_RECORDS: ["repair_selectors", "adjust_runtime", "inspect_access"],
    FailureCategory.LOW_COVERAGE: ["probe_fields", "repair_selectors"],
    FailureCategory.SELECTOR_MISS: ["repair_selectors", "reanalyze_site"],
    FailureCategory.ACCESS_CHALLENGE: ["adjust_runtime", "inspect_access"],
    FailureCategory.ACCESS_BLOCKED: ["adjust_runtime", "inspect_access"],
    FailureCategory.API_REPLAY_FAILED: ["inspect_access", "adjust_runtime"],
    FailureCategory.TIMEOUT: ["adjust_runtime"],
    FailureCategory.BROWSER_CRASH: ["adjust_runtime"],
    FailureCategory.EMPTY_HTML: ["adjust_runtime", "inspect_access"],
    FailureCategory.PAGINATION_STUCK: ["inspect_access", "repair_selectors"],
    FailureCategory.QUALITY_FAIL: ["evaluate_quality", "probe_fields"],
    FailureCategory.PROXY_ERROR: ["adjust_runtime"],
}

# Priority order for failure diagnosis (check most specific first)
CATEGORY_PRIORITY = [
    FailureCategory.ACCESS_BLOCKED,
    FailureCategory.ACCESS_CHALLENGE,
    FailureCategory.BROWSER_CRASH,
    FailureCategory.PROXY_ERROR,
    FailureCategory.TIMEOUT,
    FailureCategory.EMPTY_HTML,
    FailureCategory.API_REPLAY_FAILED,
    FailureCategory.NO_RECORDS,
    FailureCategory.PAGINATION_STUCK,
    FailureCategory.SELECTOR_MISS,
    FailureCategory.LOW_COVERAGE,
    FailureCategory.QUALITY_FAIL,
]


# ---------------------------------------------------------------------------
# Diagnosis Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FailureDiagnosis:
    """One diagnosed failure with evidence and repair suggestion."""
    category: FailureCategory
    severity: str  # "critical", "warning", "info"
    evidence: str
    affected_fields: list[str] = field(default_factory=list)
    repair_actions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity,
            "evidence": self.evidence[:500],
            "affected_fields": list(self.affected_fields),
            "repair_actions": list(self.repair_actions),
            "confidence": round(self.confidence, 3),
        }


@dataclass
class DiagnosisReport:
    """Full diagnosis of a crawl execution result."""
    diagnoses: list[FailureDiagnosis] = field(default_factory=list)
    overall_health: str = "unknown"  # "healthy", "degraded", "critical"
    recommended_focus: list[str] = field(default_factory=list)
    auto_repairable: bool = False
    repair_plan_actions: list[ManagedCrawlAction] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return any(d.severity == "critical" for d in self.diagnoses)

    @property
    def critical_count(self) -> int:
        return sum(1 for d in self.diagnoses if d.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for d in self.diagnoses if d.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "overall_health": self.overall_health,
            "recommended_focus": list(self.recommended_focus),
            "auto_repairable": self.auto_repairable,
            "repair_action_count": len(self.repair_plan_actions),
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
        }


# ---------------------------------------------------------------------------
# Failure Diagnoser
# ---------------------------------------------------------------------------

class FailureDiagnoser:
    """Analyzes execution results and classifies failures."""

    def diagnose(
        self,
        *,
        job: dict[str, Any],
        execution_result: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> DiagnosisReport:
        """Run full diagnosis on a job's execution state."""
        profile = profile if isinstance(profile, dict) else {}
        execution_result = execution_result if isinstance(execution_result, dict) else {}

        diagnoses: list[FailureDiagnosis] = []

        # Gather evidence from multiple sources
        progress = _extract_progress(job)
        error_log = job.get("error_log") or []
        if isinstance(error_log, str):
            error_log = [error_log]
        failure_buckets = progress.get("failure_buckets") or {}
        quality = progress.get("quality") or {}
        quality_indicator = str(progress.get("quality_indicator") or "unknown").lower()
        records_saved = int(progress.get("records_saved") or 0)
        status = str(job.get("status") or "").lower()

        # Get execution-level evidence
        exec_status = str(execution_result.get("status") or "").lower()
        exec_errors = execution_result.get("error_log") or []
        if isinstance(exec_errors, str):
            exec_errors = [exec_errors]
        engine_result = execution_result.get("engine_result") or {}
        failure_classification = engine_result.get("failure_classification") or {}

        # --- Diagnosis checks (ordered by priority) ---

        # 1. Access blocked (403, 429, etc.)
        diagnoses.extend(_check_access_blocked(
            failure_buckets=failure_buckets,
            error_log=error_log + exec_errors,
            failure_classification=failure_classification,
        ))

        # 2. Challenge/CAPTCHA detected
        diagnoses.extend(_check_access_challenge(
            failure_buckets=failure_buckets,
            error_log=error_log + exec_errors,
            execution_result=execution_result,
        ))

        # 3. Browser crash
        diagnoses.extend(_check_browser_crash(
            failure_buckets=failure_buckets,
            error_log=error_log + exec_errors,
            failure_classification=failure_classification,
        ))

        # 4. Proxy errors
        diagnoses.extend(_check_proxy_error(
            failure_buckets=failure_buckets,
            error_log=error_log + exec_errors,
        ))

        # 5. Timeout
        diagnoses.extend(_check_timeout(
            failure_buckets=failure_buckets,
            error_log=error_log + exec_errors,
        ))

        # 6. Empty HTML
        diagnoses.extend(_check_empty_html(
            execution_result=execution_result,
            error_log=error_log + exec_errors,
        ))

        # 7. API replay failed
        diagnoses.extend(_check_api_replay_failed(
            failure_buckets=failure_buckets,
            execution_result=execution_result,
        ))

        # 8. No records produced
        diagnoses.extend(_check_no_records(
            records_saved=records_saved,
            quality_indicator=quality_indicator,
            status=status,
            exec_status=exec_status,
        ))

        # 9. Pagination stuck
        diagnoses.extend(_check_pagination_stuck(
            job=job,
            progress=progress,
        ))

        # 10. Selector miss
        diagnoses.extend(_check_selector_miss(
            quality=quality,
            execution_result=execution_result,
        ))

        # 11. Low field coverage
        diagnoses.extend(_check_low_coverage(
            quality=quality,
            quality_indicator=quality_indicator,
        ))

        # 12. Quality gate failed
        diagnoses.extend(_check_quality_fail(
            quality_indicator=quality_indicator,
            quality=quality,
        ))

        # Deduplicate and sort
        diagnoses = _dedupe_diagnoses(diagnoses)
        diagnoses.sort(key=lambda d: (
            {"critical": 0, "warning": 1, "info": 2}.get(d.severity, 3),
            -d.confidence,
        ))

        # Determine overall health
        overall_health = _assess_health(diagnoses, records_saved)

        # Determine recommended focus
        recommended_focus = _recommend_focus(diagnoses)

        # Generate repair plan
        repair_actions = _generate_repair_actions(diagnoses, profile, job)

        # Can we auto-repair?
        auto_repairable = bool(
            repair_actions
            and overall_health != "healthy"
            and not _requires_manual_intervention(diagnoses)
        )

        return DiagnosisReport(
            diagnoses=diagnoses,
            overall_health=overall_health,
            recommended_focus=recommended_focus,
            auto_repairable=auto_repairable,
            repair_plan_actions=repair_actions,
        )


# ---------------------------------------------------------------------------
# Individual Failure Checkers
# ---------------------------------------------------------------------------

def _check_access_blocked(
    *,
    failure_buckets: dict[str, Any],
    error_log: list[Any],
    failure_classification: dict[str, Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    blocked_count = sum(
        int(failure_buckets.get(k, 0))
        for k in ("http_blocked", "blocked", "access_blocked")
    )
    category = str(failure_classification.get("category") or "").lower()
    if category in {"http_blocked", "challenge_like"}:
        blocked_count += 1
    for entry in error_log:
        text = str(entry).lower()
        if any(kw in text for kw in ("403", "429", "forbidden", "blocked", "rate limit")):
            blocked_count += 1
    if blocked_count > 0:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.ACCESS_BLOCKED,
            severity="critical",
            evidence=f"Detected {blocked_count} access-blocked signals (403/429/blocked).",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.ACCESS_BLOCKED],
            confidence=min(0.9, 0.5 + blocked_count * 0.1),
        ))
    return diagnoses


def _check_access_challenge(
    *,
    failure_buckets: dict[str, Any],
    error_log: list[Any],
    execution_result: dict[str, Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    challenge_count = sum(
        int(failure_buckets.get(k, 0))
        for k in ("challenge_like", "captcha", "managed_challenge")
    )
    for entry in error_log:
        text = str(entry).lower()
        if any(kw in text for kw in ("captcha", "challenge", "cloudflare", "recaptcha", "turnstile")):
            challenge_count += 1
    # Check execution result for challenge signals
    engine_result = execution_result.get("engine_result") or {}
    failure_class = engine_result.get("failure_classification") or {}
    if str(failure_class.get("category") or "") == "challenge_like":
        challenge_count += 1
    if challenge_count > 0:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.ACCESS_CHALLENGE,
            severity="critical",
            evidence=f"Challenge/CAPTCHA detected ({challenge_count} signals). Protected browser mode recommended.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.ACCESS_CHALLENGE],
            confidence=min(0.95, 0.6 + challenge_count * 0.1),
        ))
    return diagnoses


def _check_browser_crash(
    *,
    failure_buckets: dict[str, Any],
    error_log: list[Any],
    failure_classification: dict[str, Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    crash_count = int(failure_buckets.get("browser_crash", 0))
    category = str(failure_classification.get("category") or "").lower()
    if category in {"playwright_missing", "browser_install_or_launch"}:
        crash_count += 1
    for entry in error_log:
        text = str(entry).lower()
        if any(kw in text for kw in ("playwright", "browser", "chromium", "launch failed")):
            crash_count += 1
    if crash_count > 0:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.BROWSER_CRASH,
            severity="critical",
            evidence=f"Browser execution failed ({crash_count} signals). May need runtime fallback.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.BROWSER_CRASH],
            confidence=0.7,
        ))
    return diagnoses


def _check_proxy_error(
    *,
    failure_buckets: dict[str, Any],
    error_log: list[Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    proxy_count = int(failure_buckets.get("proxy_error", 0))
    for entry in error_log:
        text = str(entry).lower()
        if any(kw in text for kw in ("proxy", "tunnel", "connection refused", "connect timeout")):
            proxy_count += 1
    if proxy_count > 0:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.PROXY_ERROR,
            severity="warning",
            evidence=f"Proxy errors detected ({proxy_count} signals).",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.PROXY_ERROR],
            confidence=0.6,
        ))
    return diagnoses


def _check_timeout(
    *,
    failure_buckets: dict[str, Any],
    error_log: list[Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    timeout_count = int(failure_buckets.get("navigation_timeout", 0))
    for entry in error_log:
        text = str(entry).lower()
        if any(kw in text for kw in ("timeout", "timed out", "deadline exceeded")):
            timeout_count += 1
    if timeout_count > 0:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.TIMEOUT,
            severity="warning",
            evidence=f"Timeouts detected ({timeout_count} signals). May need longer wait or simpler runtime.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.TIMEOUT],
            confidence=0.6,
        ))
    return diagnoses


def _check_empty_html(
    *,
    execution_result: dict[str, Any],
    error_log: list[Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    raw_html = execution_result.get("raw_html") or {}
    visited = execution_result.get("visited_urls") or []
    if visited and not raw_html:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.EMPTY_HTML,
            severity="critical",
            evidence="Execution visited URLs but returned no HTML content.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.EMPTY_HTML],
            confidence=0.8,
        ))
    elif raw_html:
        for url, html in raw_html.items():
            if isinstance(html, str) and len(html.strip()) < 100:
                diagnoses.append(FailureDiagnosis(
                    category=FailureCategory.EMPTY_HTML,
                    severity="warning",
                    evidence=f"HTML from {url} is suspiciously short ({len(html)} chars).",
                    repair_actions=REPAIR_ACTION_MAP[FailureCategory.EMPTY_HTML],
                    confidence=0.6,
                ))
                break
    return diagnoses


def _check_api_replay_failed(
    *,
    failure_buckets: dict[str, Any],
    execution_result: dict[str, Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    api_failures = int(failure_buckets.get("api_replay_failed", 0))
    api_responses = execution_result.get("api_responses") or []
    for resp in api_responses:
        if isinstance(resp, dict) and not resp.get("ok", True):
            api_failures += 1
    if api_failures > 0:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.API_REPLAY_FAILED,
            severity="warning",
            evidence=f"API replay failed ({api_failures} responses). May need different headers or auth.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.API_REPLAY_FAILED],
            confidence=0.6,
        ))
    return diagnoses


def _check_no_records(
    *,
    records_saved: int,
    quality_indicator: str,
    status: str,
    exec_status: str,
) -> list[FailureDiagnosis]:
    diagnoses = []
    if records_saved == 0 and status in {"completed", "failed"}:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.NO_RECORDS,
            severity="critical",
            evidence=f"Zero records saved. Job status={status}, quality={quality_indicator}.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.NO_RECORDS],
            confidence=0.9,
        ))
    elif records_saved == 0 and exec_status == "executed":
        # Execution succeeded but no extraction
        extracted = {}
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.NO_RECORDS,
            severity="warning",
            evidence="Execution completed but no records were extracted.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.NO_RECORDS],
            confidence=0.7,
        ))
    return diagnoses


def _check_pagination_stuck(
    *,
    job: dict[str, Any],
    progress: dict[str, Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    # Check if multiple pages were visited but records didn't grow
    profile_run = job.get("profile_run") or {}
    runner_summary = profile_run.get("runner_summary") or {}
    batches_processed = int(runner_summary.get("batches_processed") or 0)
    records_saved = int(progress.get("records_saved") or 0)
    if batches_processed > 2 and records_saved < 5:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.PAGINATION_STUCK,
            severity="warning",
            evidence=f"Processed {batches_processed} batches but only {records_saved} records. Pagination may be stuck.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.PAGINATION_STUCK],
            confidence=0.5,
        ))
    return diagnoses


def _check_selector_miss(
    *,
    quality: dict[str, Any],
    execution_result: dict[str, Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    # Check engine result for selector failures
    engine_result = execution_result.get("engine_result") or {}
    selector_results = engine_result.get("selector_results") or []
    miss_count = 0
    for sr in selector_results:
        if isinstance(sr, dict) and sr.get("match_count", 0) == 0:
            miss_count += 1
    if miss_count > 0 and miss_count >= max(1, len(selector_results) // 2):
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.SELECTOR_MISS,
            severity="warning",
            evidence=f"{miss_count}/{len(selector_results)} selectors returned no matches.",
            affected_fields=[
                sr.get("name", "") for sr in selector_results
                if isinstance(sr, dict) and sr.get("match_count", 0) == 0
            ],
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.SELECTOR_MISS],
            confidence=0.7,
        ))
    return diagnoses


def _check_low_coverage(
    *,
    quality: dict[str, Any],
    quality_indicator: str,
) -> list[FailureDiagnosis]:
    diagnoses = []
    coverage = float(quality.get("field_coverage") or quality.get("completeness") or 1.0)
    if coverage < 0.5 and quality_indicator in {"fail", "warn"}:
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.LOW_COVERAGE,
            severity="warning",
            evidence=f"Field coverage is {coverage:.1%}. Many fields are missing data.",
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.LOW_COVERAGE],
            confidence=0.6,
        ))
    return diagnoses


def _check_quality_fail(
    *,
    quality_indicator: str,
    quality: dict[str, Any],
) -> list[FailureDiagnosis]:
    diagnoses = []
    if quality_indicator == "fail":
        missing_fields = quality.get("missing_fields") or quality.get("missing_required") or []
        diagnoses.append(FailureDiagnosis(
            category=FailureCategory.QUALITY_FAIL,
            severity="warning",
            evidence=f"Quality gate failed. Missing fields: {', '.join(str(f) for f in missing_fields[:5])}",
            affected_fields=[str(f) for f in missing_fields[:10]],
            repair_actions=REPAIR_ACTION_MAP[FailureCategory.QUALITY_FAIL],
            confidence=0.7,
        ))
    return diagnoses


# ---------------------------------------------------------------------------
# Health Assessment & Focus Recommendation
# ---------------------------------------------------------------------------

def _assess_health(diagnoses: list[FailureDiagnosis], records_saved: int) -> str:
    if not diagnoses:
        return "healthy" if records_saved > 0 else "unknown"
    critical = sum(1 for d in diagnoses if d.severity == "critical")
    warnings = sum(1 for d in diagnoses if d.severity == "warning")
    if critical > 0:
        return "critical"
    if warnings > 1:
        return "degraded"
    if warnings == 1:
        return "degraded" if records_saved == 0 else "healthy"
    return "healthy" if records_saved > 0 else "unknown"


def _recommend_focus(diagnoses: list[FailureDiagnosis]) -> list[str]:
    focus: list[str] = []
    for d in diagnoses:
        if d.category in (FailureCategory.ACCESS_BLOCKED, FailureCategory.ACCESS_CHALLENGE):
            focus.append("access_challenge")
        elif d.category == FailureCategory.NO_RECORDS:
            focus.append("zero_records")
        elif d.category in (FailureCategory.SELECTOR_MISS, FailureCategory.LOW_COVERAGE):
            focus.append("field_coverage")
        elif d.category == FailureCategory.QUALITY_FAIL:
            focus.append("quality_repair")
    return list(dict.fromkeys(focus))[:5]


def _requires_manual_intervention(diagnoses: list[FailureDiagnosis]) -> bool:
    """Check if any diagnosis requires human action."""
    for d in diagnoses:
        if d.category == FailureCategory.BROWSER_CRASH and d.severity == "critical":
            return True
        if d.category == FailureCategory.PROXY_ERROR and d.confidence > 0.8:
            return True
    return False


# ---------------------------------------------------------------------------
# Repair Action Generation
# ---------------------------------------------------------------------------

def _generate_repair_actions(
    diagnoses: list[FailureDiagnosis],
    profile: dict[str, Any],
    job: dict[str, Any],
) -> list[ManagedCrawlAction]:
    """Generate concrete repair actions from diagnoses."""
    actions: list[ManagedCrawlAction] = []
    seen_actions: set[str] = set()

    for diagnosis in diagnoses:
        for action_type in diagnosis.repair_actions:
            if action_type in seen_actions:
                continue
            seen_actions.add(action_type)

            action = _build_repair_action(
                action_type=action_type,
                diagnosis=diagnosis,
                profile=profile,
                job=job,
            )
            if action:
                actions.append(action)

    # Always add a rerun at the end if we have repair actions
    if actions:
        actions.append(ManagedCrawlAction(
            action="prepare_rerun",
            priority="medium",
            reason="Auto-repair cycle complete. Prepare rerun with accumulated patches.",
            params={"run_kind": "test"},
        ))

    return actions


def _build_repair_action(
    *,
    action_type: str,
    diagnosis: FailureDiagnosis,
    profile: dict[str, Any],
    job: dict[str, Any],
) -> ManagedCrawlAction | None:
    """Build a specific repair action based on failure type."""
    target_url = (
        (job.get("product_run_spec") or {}).get("target_url")
        or job.get("target_url")
        or ""
    )

    if action_type == "adjust_runtime":
        params: dict[str, Any] = {}
        if diagnosis.category in (FailureCategory.ACCESS_CHALLENGE, FailureCategory.ACCESS_BLOCKED):
            params = {
                "mode": "protected",
                "capture_api": True,
                "wait_until": "networkidle",
                "protected": True,
                "persistent_context": True,
                "rotate_proxy": True,
                "item_workers": 1,
            }
        elif diagnosis.category == FailureCategory.TIMEOUT:
            params = {
                "mode": "dynamic",
                "wait_until": "domcontentloaded",
                "render_time_ms": 5000,
                "max_wait_ms": 60000,
            }
        elif diagnosis.category == FailureCategory.BROWSER_CRASH:
            params = {
                "mode": "static",
                "wait_until": "domcontentloaded",
            }
        elif diagnosis.category == FailureCategory.EMPTY_HTML:
            params = {
                "mode": "dynamic",
                "capture_api": True,
                "wait_until": "networkidle",
                "render_time_ms": 5000,
            }
        elif diagnosis.category == FailureCategory.PROXY_ERROR:
            params = {
                "rotate_proxy": True,
            }
        else:
            params = {
                "mode": "dynamic",
                "capture_api": True,
                "wait_until": "networkidle",
            }
        return ManagedCrawlAction(
            action="adjust_runtime",
            priority="high" if diagnosis.severity == "critical" else "medium",
            reason=f"[Auto-repair] {diagnosis.evidence}",
            params=params,
        )

    elif action_type == "repair_selectors":
        fields = diagnosis.affected_fields or (
            profile.get("target_fields") or ["title", "highest_price", "description", "image_urls"]
        )
        return ManagedCrawlAction(
            action="repair_selectors",
            priority="high",
            reason=f"[Auto-repair] Selector failures detected: {diagnosis.evidence}",
            params={"fields": fields},
        )

    elif action_type == "inspect_access":
        return ManagedCrawlAction(
            action="inspect_access",
            priority="high",
            reason=f"[Auto-repair] Access evidence needed: {diagnosis.evidence}",
            params={
                "target_url": target_url,
                "capture_api": True,
                "capture_js": True,
                "capture_dom": True,
            },
        )

    elif action_type == "probe_fields":
        return ManagedCrawlAction(
            action="probe_fields",
            priority="high",
            reason=f"[Auto-repair] Field coverage low: {diagnosis.evidence}",
            params={
                "fields": diagnosis.affected_fields or [],
                "reanalyze": True,
            },
        )

    elif action_type == "reanalyze_site":
        return ManagedCrawlAction(
            action="reanalyze_site",
            priority="high",
            reason=f"[Auto-repair] Site re-analysis needed: {diagnosis.evidence}",
            params={"target_url": target_url},
        )

    elif action_type == "evaluate_quality":
        return ManagedCrawlAction(
            action="evaluate_quality",
            priority="medium",
            reason=f"[Auto-repair] Quality evaluation needed: {diagnosis.evidence}",
            params={
                "required_fields": diagnosis.affected_fields or [],
                "min_field_coverage": 0.6,
            },
        )

    return None


# ---------------------------------------------------------------------------
# Auto-Repair Loop
# ---------------------------------------------------------------------------

@dataclass
class AutoRepairLoopResult:
    """Result of one or more auto-repair cycles."""
    cycles: list[dict[str, Any]] = field(default_factory=list)
    final_diagnosis: DiagnosisReport | None = None
    total_cycles: int = 0
    converged: bool = False
    final_health: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cycles": self.total_cycles,
            "converged": self.converged,
            "final_health": self.final_health,
            "cycles": self.cycles,
            "final_diagnosis": self.final_diagnosis.to_dict() if self.final_diagnosis else None,
        }


class AutoRepairLoop:
    """Orchestrates the diagnose -> repair -> re-execute cycle.

    Usage:
        loop = AutoRepairLoop(max_cycles=3)
        result = loop.run(
            job=job,
            profile=profile,
            target_url=target_url,
            executor_fn=my_executor,
        )
    """

    def __init__(
        self,
        *,
        max_cycles: int = 3,
        min_health: str = "degraded",
        advisor: Any = None,
    ):
        self.max_cycles = max_cycles
        self.min_health = min_health
        self.advisor = advisor
        self._diagnoser = FailureDiagnoser()

    def run(
        self,
        *,
        job: dict[str, Any],
        profile: dict[str, Any],
        target_url: str,
        executor_fn: Any = None,
        run_spec: dict[str, Any] | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> AutoRepairLoopResult:
        """Run the auto-repair loop until convergence or max cycles.

        Args:
            job: Current job state.
            profile: Current site profile.
            target_url: Target URL for the crawl.
            executor_fn: Callable that executes one crawl cycle and returns
                        a new job dict. If None, uses managed action execution.
            run_spec: Optional run specification.
            extra_context: Optional extra context for actions.
        """
        cycles: list[dict[str, Any]] = []
        current_job = dict(job)
        current_profile = dict(profile)
        converged = False
        final_diagnosis: DiagnosisReport | None = None

        for cycle_num in range(1, self.max_cycles + 1):
            # Step 1: Diagnose
            diagnosis = self._diagnoser.diagnose(
                job=current_job,
                profile=current_profile,
            )
            final_diagnosis = diagnosis

            cycle_record: dict[str, Any] = {
                "cycle": cycle_num,
                "diagnosis": diagnosis.to_dict(),
                "health": diagnosis.overall_health,
                "actions_taken": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Check if we've converged
            if diagnosis.overall_health in ("healthy", self.min_health):
                converged = True
                cycle_record["outcome"] = "converged"
                cycles.append(cycle_record)
                break

            # Check if we can auto-repair
            if not diagnosis.auto_repairable:
                cycle_record["outcome"] = "not_auto_repairable"
                cycles.append(cycle_record)
                break

            # Step 2: Execute repair actions
            if executor_fn:
                # Use custom executor (for full crawl re-execution)
                try:
                    result = executor_fn(
                        repair_actions=diagnosis.repair_plan_actions,
                        cycle=cycle_num,
                        diagnosis=diagnosis,
                    )
                    current_job = result if isinstance(result, dict) else current_job
                    cycle_record["execution_result"] = {
                        "status": current_job.get("status", "unknown"),
                        "records": _extract_progress(current_job).get("records_saved", 0),
                    }
                except Exception as exc:
                    cycle_record["execution_error"] = str(exc)[:500]
                    cycle_record["outcome"] = "execution_failed"
                    cycles.append(cycle_record)
                    break
            else:
                # Use managed action execution for patches only
                plan = ManagedActionPlan(
                    actions=diagnosis.repair_plan_actions,
                    source="auto_repair",
                )
                action_result = execute_managed_action_plan(
                    plan=plan,
                    target_url=target_url,
                    profile=current_profile,
                    run_spec=run_spec,
                    advisor=self.advisor,
                    extra_context=extra_context,
                    job=current_job,
                )
                cycle_record["action_result"] = {
                    "rerun_ready": action_result.get("rerun_ready", False),
                    "action_count": len(action_result.get("results") or []),
                    "profile_patch_keys": sorted(
                        (action_result.get("profile_patch") or {}).keys()
                    ),
                }
                # Apply patches to profile for next cycle
                patch = action_result.get("profile_patch") or {}
                if patch:
                    current_profile = _deep_merge(current_profile, patch)

            cycle_record["outcome"] = "repaired"
            cycles.append(cycle_record)

        return AutoRepairLoopResult(
            cycles=cycles,
            final_diagnosis=final_diagnosis,
            total_cycles=len(cycles),
            converged=converged,
            final_health=final_diagnosis.overall_health if final_diagnosis else "unknown",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_progress(job: dict[str, Any]) -> dict[str, Any]:
    """Extract progress info from a job dict."""
    profile_run = job.get("profile_run") or {}
    product_stats = profile_run.get("product_stats") or {}
    return {
        "records_saved": int(
            product_stats.get("records_saved")
            or product_stats.get("total_records")
            or job.get("record_count")
            or 0
        ),
        "quality_indicator": str(
            product_stats.get("quality_indicator")
            or job.get("quality_indicator")
            or "unknown"
        ).lower(),
        "quality": product_stats.get("quality") or job.get("quality") or {},
        "failure_buckets": profile_run.get("failure_buckets") or job.get("failure_buckets") or {},
        "status": job.get("status", ""),
        "current_stage": job.get("current_stage", ""),
        "last_error": job.get("last_error", ""),
    }


def _dedupe_diagnoses(diagnoses: list[FailureDiagnosis]) -> list[FailureDiagnosis]:
    """Remove duplicate diagnoses, keeping highest confidence."""
    seen: dict[str, FailureDiagnosis] = {}
    for d in diagnoses:
        key = d.category.value
        if key not in seen or d.confidence > seen[key].confidence:
            seen[key] = d
    return list(seen.values())


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Deep merge overlay into base. Overlay wins on conflicts."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
