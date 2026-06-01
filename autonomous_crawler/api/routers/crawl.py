"""LangGraph crawl workflow endpoints.

Covers: /crawl, /crawl/{task_id}, /history.
"""
from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from ...llm.openai_compatible import LLMConfigurationError
from ...storage import list_crawl_results, load_crawl_result, save_crawl_result
from ...tools.anti_bot_report import summarize_anti_bot_report
from ...workflows.crawl_graph import compile_crawl_graph
from ..deps import (
    build_advisor_from_config,
    cleanup_stale_jobs,
    get_job,
    is_cancelled,
    try_register_job,
    update_job,
)
from ..schemas import CrawlRequest, CrawlResponse, LLMConfig
from ...errors import classify_llm_error, LLM_CONFIG_INVALID

router = APIRouter()


def run_crawl_workflow(
    user_goal: str,
    target_url: str,
    max_retries: int = 3,
    llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    advisor = None
    if llm_config is not None and llm_config.enabled:
        advisor = build_advisor_from_config(llm_config)
    initial_state = {
        "user_goal": user_goal, "target_url": target_url,
        "recon_report": {}, "crawl_strategy": {}, "visited_urls": [],
        "raw_html": {}, "api_responses": [], "extracted_data": {},
        "validation_result": {}, "retries": 0, "max_retries": max_retries,
        "status": "pending", "error_log": [], "messages": [],
    }
    app = compile_crawl_graph(planning_advisor=advisor, strategy_advisor=advisor)
    return app.invoke(initial_state)


def _background_crawl(task_id: str, user_goal: str, target_url: str, max_retries: int, llm_config: LLMConfig | None = None) -> None:
    try:
        final_state = run_crawl_workflow(
            user_goal=user_goal, target_url=target_url,
            max_retries=max_retries, llm_config=llm_config,
        )
        if is_cancelled(task_id):
            return
        save_crawl_result(final_state)
        extracted = final_state.get("extracted_data") or {}
        validation = final_state.get("validation_result") or {}
        strategy = final_state.get("crawl_strategy") or {}
        anti_bot_report = strategy.get("anti_bot_report") or {}
        update_job(
            task_id,
            status=final_state.get("status", "completed"),
            item_count=int(extracted.get("item_count") or 0),
            is_valid=bool(validation.get("is_valid")),
            error_code=final_state.get("error_code"),
            anti_bot_summary=summarize_anti_bot_report(anti_bot_report) if anti_bot_report else None,
        )
    except Exception as exc:
        if is_cancelled(task_id):
            return
        update_job(task_id, status="failed", error=str(exc), error_code=classify_llm_error(exc))


@router.post("/crawl", response_model=CrawlResponse)
def crawl(request: CrawlRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    llm_config: LLMConfig | None = None
    if request.llm is not None and request.llm.enabled:
        try:
            build_advisor_from_config(request.llm)
        except LLMConfigurationError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error_code": LLM_CONFIG_INVALID, "message": str(exc)},
            )
        llm_config = request.llm

    task_id = str(uuid.uuid4())[:8]
    if not try_register_job(task_id, request.user_goal, request.target_url):
        raise HTTPException(status_code=429, detail=f"too many active jobs max")
    thread = threading.Thread(
        target=_background_crawl,
        args=(task_id, request.user_goal, request.target_url, request.max_retries, llm_config),
        daemon=True,
    )
    thread.start()
    return {
        "task_id": task_id, "status": "running",
        "item_count": 0, "is_valid": False, "error_code": None, "anti_bot_summary": None,
    }


@router.get("/crawl/{task_id}")
def get_crawl(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if job:
        return {
            "task_id": job["task_id"], "user_goal": job["user_goal"],
            "target_url": job["target_url"], "status": job["status"],
            "item_count": job["item_count"], "is_valid": job["is_valid"],
            "error": job.get("error", ""), "error_code": job.get("error_code"),
            "anti_bot_summary": job.get("anti_bot_summary"),
        }
    result = load_crawl_result(task_id)
    if result:
        return result
    raise HTTPException(status_code=404, detail="crawl task not found")


@router.get("/history")
def history(limit: int = 20) -> dict[str, Any]:
    return {"items": list_crawl_results(limit=limit)}
