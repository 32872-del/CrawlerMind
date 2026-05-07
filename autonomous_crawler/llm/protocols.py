"""Provider-neutral advisor protocols for Planner and Strategy nodes."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PlanningAdvisor(Protocol):
    """Advisor that suggests normalized crawl intent from a user goal."""

    def plan(self, user_goal: str, target_url: str) -> dict[str, Any]:
        """Return a dict with optional intent fields.

        Allowed keys: task_type, target_fields, max_items,
        crawl_preferences, constraints, reasoning_summary.
        """
        ...


@runtime_checkable
class StrategyAdvisor(Protocol):
    """Advisor that suggests crawl strategy from planner and recon output."""

    def choose_strategy(
        self,
        planner_output: dict[str, Any],
        recon_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a dict with optional strategy fields.

        Allowed keys: mode, engine, selectors, wait_selector, wait_until,
        max_items, reasoning_summary.
        """
        ...
