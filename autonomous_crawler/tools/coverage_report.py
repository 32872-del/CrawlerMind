"""Coverage diagnostics for long-running crawl jobs.

This module turns crawl counters into an explicit loss funnel.  It is intended
for real-site training and production profile runs where "exported N rows" is
not enough; CLM needs to explain where missing inventory was lost and what
recovery action should run next.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


STAGE_INVENTORY = "inventory"
STAGE_DISCOVERY = "discovery"
STAGE_SCHEDULE = "schedule"
STAGE_ACCESS = "access"
STAGE_RENDER = "render"
STAGE_PARSE = "parse"
STAGE_QUALITY = "quality"
STAGE_EXPORT = "export"


@dataclass
class CoverageCounters:
    """Raw counters for the crawl coverage funnel."""

    estimated_inventory: int = 0
    discovered_urls: int = 0
    attempted_fetches: int = 0
    time_budget_exhausted: bool = False
    fetched_success: int = 0
    blocked_or_challenged: int = 0
    fetch_failed: int = 0
    render_attempted: int = 0
    render_success: int = 0
    render_failed: int = 0
    parsed_records: int = 0
    quality_passed: int = 0
    quality_failed: int = 0
    exported_unique: int = 0
    duplicate_dropped: int = 0
    stale_or_invalid_pages: int = 0
    missing_required_fields: int = 0
    catalog_exhausted: bool = False


@dataclass
class CoverageLoss:
    stage: str
    expected: int
    actual: int
    lost: int
    rate: float
    reason: str


@dataclass
class CoverageReport:
    schema_version: str
    counters: CoverageCounters
    rates: dict[str, float]
    losses: list[CoverageLoss] = field(default_factory=list)
    main_loss_reason: str = ""
    recommended_recovery: list[str] = field(default_factory=list)
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "counters": asdict(self.counters),
            "rates": dict(self.rates),
            "losses": [asdict(loss) for loss in self.losses],
            "main_loss_reason": self.main_loss_reason,
            "recommended_recovery": list(self.recommended_recovery),
            "accepted": self.accepted,
        }


def build_coverage_report(
    counters: CoverageCounters,
    *,
    target_records: int = 0,
    min_coverage_rate: float = 0.95,
) -> CoverageReport:
    """Build a staged coverage report and recovery suggestions."""

    estimated = max(int(counters.estimated_inventory or 0), 0)
    target = max(int(target_records or 0), 0)
    denominator = estimated or target or counters.discovered_urls or counters.exported_unique
    losses = [
        _loss(STAGE_DISCOVERY, denominator, counters.discovered_urls, "missing_inventory_discovery"),
        _loss(STAGE_SCHEDULE, counters.discovered_urls, counters.attempted_fetches, "time_budget_or_frontier_pending"),
        _loss(STAGE_ACCESS, counters.attempted_fetches, counters.fetched_success, "access_or_transport_loss"),
        _loss(STAGE_RENDER, counters.render_attempted, counters.render_success, "rendering_or_automation_loss"),
        _loss(STAGE_PARSE, counters.fetched_success, counters.parsed_records, "parser_or_selector_loss"),
        _loss(STAGE_QUALITY, counters.parsed_records, counters.quality_passed, "quality_gate_loss"),
        _loss(STAGE_EXPORT, counters.quality_passed, counters.exported_unique, "dedupe_or_export_loss"),
    ]
    losses = [loss for loss in losses if loss.expected > 0]
    rates = {
        "discovery_rate": _ratio(counters.discovered_urls, denominator),
        "fetch_success_rate": _ratio(counters.fetched_success, counters.attempted_fetches or counters.discovered_urls),
        "block_rate": _ratio(counters.blocked_or_challenged, counters.attempted_fetches or counters.discovered_urls),
        "render_success_rate": _ratio(counters.render_success, counters.render_attempted),
        "parse_success_rate": _ratio(counters.parsed_records, counters.fetched_success),
        "quality_pass_rate": _ratio(counters.quality_passed, counters.parsed_records),
        "export_rate": _ratio(counters.exported_unique, counters.quality_passed),
        "overall_coverage_rate": _ratio(counters.exported_unique, denominator),
        "target_completion_rate": _ratio(counters.exported_unique, target) if target else 0.0,
    }
    main = max(losses, key=lambda loss: loss.lost, default=None)
    recommended = recovery_actions(counters, losses)
    accepted = (
        counters.exported_unique >= target
        if target
        else rates["overall_coverage_rate"] >= min_coverage_rate
    )
    if counters.catalog_exhausted and estimated and counters.exported_unique >= estimated:
        accepted = True
    return CoverageReport(
        schema_version="coverage-report/v1",
        counters=counters,
        rates=rates,
        losses=losses,
        main_loss_reason=main.reason if main and main.lost > 0 else "no_major_loss",
        recommended_recovery=recommended,
        accepted=accepted,
    )


def recovery_actions(counters: CoverageCounters, losses: list[CoverageLoss]) -> list[str]:
    actions: list[str] = []
    by_stage = {loss.stage: loss for loss in losses}
    if by_stage.get(STAGE_DISCOVERY, CoverageLoss("", 0, 0, 0, 0.0, "")).lost > 0:
        actions.append("expand_catalog_discovery: sitemap + category tree + pagination/load-more/API total reconciliation")
    if counters.time_budget_exhausted or by_stage.get(STAGE_SCHEDULE, CoverageLoss("", 0, 0, 0, 0.0, "")).lost:
        actions.append("increase_throughput: cache catalog discovery + parallel fetch + adaptive concurrency + resume pending frontier")
    if counters.blocked_or_challenged or by_stage.get(STAGE_ACCESS, CoverageLoss("", 0, 0, 0, 0.0, "")).rate < 0.95:
        actions.append("harden_access: transport fallback + browser profile rotation + proxy/session/backoff diagnostics")
    if counters.render_attempted and by_stage.get(STAGE_RENDER, CoverageLoss("", 0, 0, 0, 0.0, "")).lost:
        actions.append("harden_rendering: wait strategy + scroll/load-more automation + XHR capture")
    if by_stage.get(STAGE_PARSE, CoverageLoss("", 0, 0, 0, 0.0, "")).lost:
        actions.append("repair_parsing: adaptive selectors + JSON-LD/hydration/API fallback + selector memory")
    if counters.quality_failed or counters.stale_or_invalid_pages or counters.missing_required_fields:
        actions.append("recover_quality: reject invalid pages, clean media, enqueue replacement URLs until valid target is met")
    if counters.duplicate_dropped:
        actions.append("review_export_granularity: product vs SKU/variant dedupe policy")
    if counters.catalog_exhausted:
        actions.append("record_catalog_exhausted: report true discovered inventory instead of duplicating rows")
    return actions


def _loss(stage: str, expected: int, actual: int, reason: str) -> CoverageLoss:
    expected = max(int(expected or 0), 0)
    actual = max(int(actual or 0), 0)
    lost = max(expected - actual, 0)
    return CoverageLoss(stage=stage, expected=expected, actual=actual, lost=lost, rate=_ratio(actual, expected), reason=reason)


def _ratio(value: int, total: int) -> float:
    if not total:
        return 0.0
    return round(max(value, 0) / max(total, 1), 4)
