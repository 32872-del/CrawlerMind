"""FastAPI service boundary for the autonomous crawler MVP."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..storage import list_crawl_results, load_crawl_result, save_crawl_result
from ..workflows.crawl_graph import compile_crawl_graph


class CrawlRequest(BaseModel):
    user_goal: str = Field(..., min_length=1)
    target_url: str = Field(..., min_length=1)
    max_retries: int = Field(default=3, ge=0, le=10)


class CrawlResponse(BaseModel):
    task_id: str
    status: str
    item_count: int
    is_valid: bool


# ---------------------------------------------------------------------------
# In-memory job registry
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _register_job(task_id: str, user_goal: str, target_url: str) -> None:
    with _jobs_lock:
        _jobs[task_id] = {
            "task_id": task_id,
            "status": "running",
            "user_goal": user_goal,
            "target_url": target_url,
            "item_count": 0,
            "is_valid": False,
            "error": "",
            "created_at": _utc_now_iso(),
        }


def _update_job(task_id: str, **kwargs: Any) -> None:
    with _jobs_lock:
        if task_id in _jobs:
            _jobs[task_id].update(kwargs)


def _get_job(task_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        return _jobs.get(task_id)


def _remove_job(task_id: str) -> None:
    with _jobs_lock:
        _jobs.pop(task_id, None)


def _background_crawl(task_id: str, user_goal: str, target_url: str, max_retries: int) -> None:
    """Run the crawl workflow in a background thread."""
    try:
        final_state = run_crawl_workflow(
            user_goal=user_goal,
            target_url=target_url,
            max_retries=max_retries,
        )
        save_crawl_result(final_state)

        extracted = final_state.get("extracted_data") or {}
        validation = final_state.get("validation_result") or {}
        _update_job(
            task_id,
            status=final_state.get("status", "completed"),
            item_count=int(extracted.get("item_count") or 0),
            is_valid=bool(validation.get("is_valid")),
        )
    except Exception as exc:
        _update_job(task_id, status="failed", error=str(exc))


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(title="Autonomous Crawl Agent", version="0.2.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/crawl", response_model=CrawlResponse)
    def crawl(request: CrawlRequest) -> dict[str, Any]:
        task_id = str(uuid.uuid4())[:8]

        _register_job(task_id, request.user_goal, request.target_url)

        thread = threading.Thread(
            target=_background_crawl,
            args=(task_id, request.user_goal, request.target_url, request.max_retries),
            daemon=True,
        )
        thread.start()

        return {
            "task_id": task_id,
            "status": "running",
            "item_count": 0,
            "is_valid": False,
        }

    @app.get("/crawl/{task_id}")
    def get_crawl(task_id: str) -> dict[str, Any]:
        # Check in-memory registry first (running/queued jobs)
        job = _get_job(task_id)
        if job:
            return {
                "task_id": job["task_id"],
                "user_goal": job["user_goal"],
                "target_url": job["target_url"],
                "status": job["status"],
                "item_count": job["item_count"],
                "is_valid": job["is_valid"],
                "error": job.get("error", ""),
            }

        # Fall back to persisted result
        result = load_crawl_result(task_id)
        if result:
            return result

        raise HTTPException(status_code=404, detail="crawl task not found")

    @app.get("/history")
    def history(limit: int = 20) -> dict[str, Any]:
        return {"items": list_crawl_results(limit=limit)}

    return app


def run_crawl_workflow(user_goal: str, target_url: str, max_retries: int = 3) -> dict[str, Any]:
    initial_state = {
        "user_goal": user_goal,
        "target_url": target_url,
        "recon_report": {},
        "crawl_strategy": {},
        "visited_urls": [],
        "raw_html": {},
        "api_responses": [],
        "extracted_data": {},
        "validation_result": {},
        "retries": 0,
        "max_retries": max_retries,
        "status": "pending",
        "error_log": [],
        "messages": [],
    }
    app = compile_crawl_graph()
    return app.invoke(initial_state)


app = create_app()
