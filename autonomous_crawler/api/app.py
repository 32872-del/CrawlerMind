"""FastAPI service boundary for the autonomous crawler MVP."""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..llm.openai_compatible import (
    LLMConfigurationError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
)
from ..storage import list_crawl_results, load_crawl_result, save_crawl_result
from ..workflows.crawl_graph import compile_crawl_graph


class LLMConfig(BaseModel):
    enabled: bool = False
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    provider: str = "openai-compatible"
    timeout_seconds: float = Field(default=30.0, gt=0)
    temperature: float = Field(default=0.0, ge=0)
    max_tokens: int = Field(default=800, gt=0)
    use_response_format: bool = True


class CrawlRequest(BaseModel):
    user_goal: str = Field(..., min_length=1)
    target_url: str = Field(..., min_length=1)
    max_retries: int = Field(default=3, ge=0, le=10)
    llm: LLMConfig | None = None


class CrawlResponse(BaseModel):
    task_id: str
    status: str
    item_count: int
    is_valid: bool
    error_code: str | None = None


# ---------------------------------------------------------------------------
# In-memory job registry
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _register_job(task_id: str, user_goal: str, target_url: str) -> None:
    with _jobs_lock:
        _jobs[task_id] = _new_job_record(task_id, user_goal, target_url)


def _try_register_job(task_id: str, user_goal: str, target_url: str) -> bool:
    """Register a running job if the active-job limit has not been reached."""
    with _jobs_lock:
        active_jobs = sum(1 for job in _jobs.values() if job["status"] == "running")
        if active_jobs >= _max_active_jobs():
            return False
        _jobs[task_id] = _new_job_record(task_id, user_goal, target_url)
        return True


def _update_job(task_id: str, **kwargs: Any) -> None:
    with _jobs_lock:
        if task_id in _jobs:
            kwargs["updated_at"] = _utc_now_iso()
            _jobs[task_id].update(kwargs)


def _get_job(task_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        return _jobs.get(task_id)


def _remove_job(task_id: str) -> None:
    with _jobs_lock:
        _jobs.pop(task_id, None)


def _new_job_record(task_id: str, user_goal: str, target_url: str) -> dict[str, Any]:
    now = _utc_now_iso()
    return {
        "task_id": task_id,
        "status": "running",
        "user_goal": user_goal,
        "target_url": target_url,
        "item_count": 0,
        "is_valid": False,
        "error": "",
        "error_code": None,
        "created_at": now,
        "updated_at": now,
    }


def _max_active_jobs() -> int:
    """Return the maximum number of concurrent active jobs."""
    raw = os.environ.get("CLM_MAX_ACTIVE_JOBS", "4")
    try:
        val = int(raw)
        return val if val > 0 else 4
    except ValueError:
        return 4


def _count_active_jobs() -> int:
    """Count jobs that are still actively running."""
    with _jobs_lock:
        return sum(1 for j in _jobs.values() if j["status"] == "running")


def _job_retention_seconds() -> int:
    """Return how long completed/failed jobs stay in the registry."""
    raw = os.environ.get("CLM_JOB_RETENTION_SECONDS", "3600")
    try:
        val = int(raw)
        return val if val > 0 else 3600
    except ValueError:
        return 3600


def _cleanup_stale_jobs() -> None:
    """Remove completed/failed jobs older than the retention TTL."""
    ttl = _job_retention_seconds()
    cutoff = datetime.now(timezone.utc).timestamp() - ttl
    with _jobs_lock:
        stale = [
            tid for tid, job in _jobs.items()
            if job["status"] != "running"
            and _parse_iso(job.get("updated_at", "")) < cutoff
        ]
        for tid in stale:
            del _jobs[tid]


def _parse_iso(iso_str: str) -> float:
    """Parse an ISO timestamp to epoch seconds; return 0.0 on failure."""
    try:
        return datetime.fromisoformat(iso_str).timestamp()
    except (ValueError, TypeError):
        return 0.0


def _build_advisor_from_config(config: LLMConfig) -> OpenAICompatibleAdvisor:
    """Build an advisor from request-level LLM config.

    Raises LLMConfigurationError if required fields are missing.
    """
    if not config.base_url.strip():
        raise LLMConfigurationError("llm.base_url is required when llm.enabled is true")
    if not config.model.strip():
        raise LLMConfigurationError("llm.model is required when llm.enabled is true")
    llm_config = OpenAICompatibleConfig(
        base_url=config.base_url.strip(),
        model=config.model.strip(),
        api_key=config.api_key.strip(),
        provider=config.provider.strip() or "openai-compatible",
        timeout_seconds=config.timeout_seconds,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        use_response_format=config.use_response_format,
    )
    return OpenAICompatibleAdvisor(llm_config)


def _background_crawl(
    task_id: str,
    user_goal: str,
    target_url: str,
    max_retries: int,
    llm_config: LLMConfig | None = None,
) -> None:
    """Run the crawl workflow in a background thread."""
    try:
        final_state = run_crawl_workflow(
            user_goal=user_goal,
            target_url=target_url,
            max_retries=max_retries,
            llm_config=llm_config,
        )
        save_crawl_result(final_state)

        extracted = final_state.get("extracted_data") or {}
        validation = final_state.get("validation_result") or {}
        _update_job(
            task_id,
            status=final_state.get("status", "completed"),
            item_count=int(extracted.get("item_count") or 0),
            is_valid=bool(validation.get("is_valid")),
            error_code=final_state.get("error_code"),
        )
    except Exception as exc:
        from ..errors import classify_llm_error
        _update_job(task_id, status="failed", error=str(exc),
                    error_code=classify_llm_error(exc))


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
        _cleanup_stale_jobs()

        # Validate LLM config eagerly so bad requests get a clear 400
        llm_config: LLMConfig | None = None
        if request.llm is not None and request.llm.enabled:
            try:
                _build_advisor_from_config(request.llm)
            except LLMConfigurationError as exc:
                from ..errors import LLM_CONFIG_INVALID
                raise HTTPException(
                    status_code=400,
                    detail={"error_code": LLM_CONFIG_INVALID, "message": str(exc)},
                )
            llm_config = request.llm

        task_id = str(uuid.uuid4())[:8]

        if not _try_register_job(task_id, request.user_goal, request.target_url):
            raise HTTPException(
                status_code=429,
                detail=f"too many active jobs ({_max_active_jobs()} max)",
            )

        thread = threading.Thread(
            target=_background_crawl,
            args=(task_id, request.user_goal, request.target_url, request.max_retries, llm_config),
            daemon=True,
        )
        thread.start()

        return {
            "task_id": task_id,
            "status": "running",
            "item_count": 0,
            "is_valid": False,
            "error_code": None,
        }

    @app.get("/crawl/{task_id}")
    def get_crawl(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()

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
                "error_code": job.get("error_code"),
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


def run_crawl_workflow(
    user_goal: str,
    target_url: str,
    max_retries: int = 3,
    llm_config: LLMConfig | None = None,
) -> dict[str, Any]:
    advisor = None
    if llm_config is not None and llm_config.enabled:
        advisor = _build_advisor_from_config(llm_config)

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
    app = compile_crawl_graph(
        planning_advisor=advisor,
        strategy_advisor=advisor,
    )
    return app.invoke(initial_state)


app = create_app()
