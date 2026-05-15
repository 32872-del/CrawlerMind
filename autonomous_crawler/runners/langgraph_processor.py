"""BatchRunner processor adapter for the existing LangGraph crawl workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from autonomous_crawler.workflows.crawl_graph import compile_crawl_graph

from .batch_runner import FrontierItem, ItemProcessResult
from .site_profile import SiteProfile, load_site_profile


class LangGraphBatchProcessor:
    """Run one frontier item through CLM's LangGraph workflow.

    This adapter lets `BatchRunner` execute the existing agent workflow while
    preserving explicit profile loading and BatchRunner pause/resume semantics.
    """

    def __init__(
        self,
        *,
        user_goal: str,
        profile: SiteProfile | None = None,
        profile_path: str | Path | None = None,
        max_retries: int = 0,
        graph: Any = None,
    ) -> None:
        if not str(user_goal or "").strip():
            raise ValueError("user_goal is required")
        if profile is not None and profile_path is not None:
            raise ValueError("choose either profile or profile_path")
        self.user_goal = user_goal
        self.profile = profile or (load_site_profile(profile_path) if profile_path else None)
        self.max_retries = max(0, int(max_retries))
        self.graph = graph or compile_crawl_graph()

    def __call__(self, item: FrontierItem) -> ItemProcessResult:
        state = self.build_state(item)
        final_state = self.graph.invoke(state)
        return self.to_item_process_result(item, final_state)

    def build_state(self, item: FrontierItem) -> dict[str, Any]:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        target_url = str(item.get("url") or payload.get("target_url") or "")
        state: dict[str, Any] = {
            "user_goal": str(payload.get("user_goal") or self.user_goal),
            "target_url": target_url,
            "max_retries": int(payload.get("max_retries") or self.max_retries),
            "retries": int(payload.get("retries") or 0),
            "messages": [],
            "recon_report": dict(payload.get("recon_report") or {}),
            "crawl_preferences": dict(payload.get("crawl_preferences") or {}),
        }
        if "task_id" in payload:
            state["task_id"] = str(payload["task_id"])
        if self.profile is not None:
            state = self.profile.apply_to_state(state)
        return state

    def to_item_process_result(self, item: FrontierItem, final_state: dict[str, Any]) -> ItemProcessResult:
        status = str(final_state.get("status") or "")
        extracted = final_state.get("extracted_data") if isinstance(final_state.get("extracted_data"), dict) else {}
        records = list(extracted.get("items") or [])
        validation = final_state.get("validation_result")
        validation_result = validation if isinstance(validation, dict) else {}
        metrics = {
            "workflow_status": status,
            "validation_result": validation_result,
            "messages": list(final_state.get("messages") or []),
            "task_id": final_state.get("task_id", ""),
            "site_profile": self.profile.to_dict() if self.profile is not None else {},
        }
        if status == "completed":
            return ItemProcessResult.success(records=records, **metrics)
        error = str(final_state.get("error_code") or final_state.get("error") or status or "workflow_failed")
        retry = bool(validation_result.get("needs_retry", False))
        if not retry:
            retry = int(item.get("attempts") or 0) < self.max_retries
        return ItemProcessResult.failure(error, retry=retry, **metrics)
