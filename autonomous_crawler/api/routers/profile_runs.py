"""Profile run endpoints.

Covers: /profile-runs, /profile-runs/batch, /profile-runs/{id},
/profile-runs/{id}/cancel, /profile-runs/{id}/pause, /profile-runs/{id}/resume.
"""
from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from ...runners import run_multi_profile_longrun
from ..deps import (
    _max_active_jobs,
    cleanup_stale_jobs,
    get_job,
    try_register_job,
    update_job,
)
from ..schemas import (
    MultiProfileRunRequest,
    MultiProfileRunResponse,
    ProfileRunRequest,
    ProfileRunResponse,
)
from .runs import (
    _background_profile_run,
    _load_profile_for_request,
    run_profile_longrun_workflow,
)

router = APIRouter()


def _first_profile_target(profile: Any) -> str:
    endpoint = str(profile.api_hints.get("endpoint") or "").strip()
    if endpoint:
        return endpoint
    seeds = profile.crawl_preferences.get("seed_urls") or profile.constraints.get("seed_urls") or []
    return str(seeds[0]) if seeds else ""


def _site_record_count(result: dict[str, Any]) -> int:
    if not isinstance(result, dict) or not result.get("ok"):
        return 0
    payload = result.get("result")
    if not isinstance(payload, dict):
        return 0
    stats = payload.get("product_stats")
    if isinstance(stats, dict):
        return int(stats.get("total") or 0)
    return 0


def run_multi_profile_longrun_workflow(request: MultiProfileRunRequest, *, task_id: str) -> dict[str, Any]:
    jobs: dict[str, dict[str, Any]] = {}
    for name, payload in request.jobs.items():
        job = dict(payload or {})
        job.setdefault("item_workers", request.default_item_workers)
        jobs[str(name)] = job
    summary = run_multi_profile_longrun(jobs, max_sites=request.max_sites)
    result = summary.to_dict()
    if request.output_report_path.strip():
        import json
        from pathlib import Path
        output = Path(request.output_report_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return result


def _background_multi_profile_run(task_id: str, request: MultiProfileRunRequest) -> None:
    try:
        result = run_multi_profile_longrun_workflow(request, task_id=task_id)
        if _is_cancelled_ref(task_id):
            return
        update_job(
            task_id,
            status="completed" if int(result.get("failed_sites") or 0) == 0 else "partial",
            item_count=sum(_site_record_count(item) for item in result.get("results") or []),
            is_valid=int(result.get("failed_sites") or 0) == 0,
            multi_profile_run=result,
        )
    except Exception as exc:
        if _is_cancelled_ref(task_id):
            return
        update_job(task_id, status="failed", error=str(exc), error_code="MULTI_PROFILE_RUN_FAILED")


def _is_cancelled_ref(task_id: str) -> bool:
    from ..deps import is_cancelled
    return is_cancelled(task_id)


@router.post("/profile-runs", response_model=ProfileRunResponse)
def start_profile_run(request: ProfileRunRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    try:
        profile = _load_profile_for_request(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task_id = str(uuid.uuid4())[:8]
    run_id = request.run_id.strip() or f"profile-{task_id}"
    if not try_register_job(task_id, f"profile-run:{profile.name}", _first_profile_target(profile), kind="profile_run"):
        raise HTTPException(status_code=429, detail=f"too many active jobs ({_max_active_jobs()} max)")
    update_job(task_id, run_id=run_id, profile_name=profile.name, kind="profile_run")
    thread = threading.Thread(target=_background_profile_run, args=(task_id, request), daemon=True)
    thread.start()
    return {
        "task_id": task_id, "run_id": run_id, "status": "running",
        "profile_name": profile.name, "record_count": 0, "accepted": False,
    }


@router.post("/profile-runs/batch", response_model=MultiProfileRunResponse)
def start_multi_profile_run(request: MultiProfileRunRequest) -> dict[str, Any]:
    cleanup_stale_jobs()
    if not request.jobs:
        raise HTTPException(status_code=400, detail="jobs is required")
    if len(request.jobs) > request.max_sites:
        raise HTTPException(status_code=400, detail=f"too many site jobs: {len(request.jobs)} > {request.max_sites}")

    task_id = str(uuid.uuid4())[:8]
    if not try_register_job(task_id, "multi-profile-run", f"{len(request.jobs)} sites", kind="multi_profile_run"):
        raise HTTPException(status_code=429, detail=f"too many active jobs ({_max_active_jobs()} max)")
    update_job(task_id, kind="multi_profile_run", total_sites=len(request.jobs))
    thread = threading.Thread(target=_background_multi_profile_run, args=(task_id, request), daemon=True)
    thread.start()
    return {
        "task_id": task_id, "status": "running",
        "total_sites": len(request.jobs), "ok_sites": 0, "failed_sites": 0,
    }


@router.get("/profile-runs/{task_id}")
def get_profile_run(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job or job.get("kind") != "profile_run":
        raise HTTPException(status_code=404, detail="profile run not found")
    result: dict[str, Any] = {
        "task_id": task_id, "run_id": job.get("run_id", ""),
        "status": job.get("status", ""), "profile_name": job.get("profile_name", ""),
        "record_count": job.get("item_count", 0), "accepted": job.get("is_valid", False),
        "error": job.get("error", ""), "profile_run": job.get("profile_run"),
    }
    if job.get("diagnostics"):
        result["diagnostics"] = job["diagnostics"]
    if job.get("backpressure"):
        result["backpressure"] = job["backpressure"]
    return result


@router.post("/profile-runs/{task_id}/cancel")
def cancel_profile_run(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job or job.get("kind") != "profile_run":
        raise HTTPException(status_code=404, detail="profile run not found")
    if job.get("status") != "running":
        raise HTTPException(status_code=409, detail=f"cannot cancel: current status is '{job.get('status')}'")
    update_job(task_id, status="cancelled", error="cancelled by user")
    from ..deps import get_registry
    get_registry().mark_status(task_id, "cancelled")
    return {"task_id": task_id, "status": "cancelled"}


@router.post("/profile-runs/{task_id}/pause")
def pause_profile_run(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job or job.get("kind") != "profile_run":
        raise HTTPException(status_code=404, detail="profile run not found")
    if job.get("status") != "running":
        raise HTTPException(status_code=409, detail=f"cannot pause: current status is '{job.get('status')}'")
    update_job(task_id, pause_requested=True)
    return {"task_id": task_id, "status": "pause_requested"}


@router.post("/profile-runs/{task_id}/resume")
def resume_profile_run(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job or job.get("kind") != "profile_run":
        raise HTTPException(status_code=404, detail="profile run not found")
    if job.get("status") != "paused":
        raise HTTPException(status_code=409, detail=f"cannot resume: current status is '{job.get('status')}'")
    update_job(task_id, status="running", pause_requested=False, error="")
    return {"task_id": task_id, "status": "running"}


@router.get("/profile-runs/batch/{task_id}")
def get_multi_profile_run(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job or job.get("kind") != "multi_profile_run":
        raise HTTPException(status_code=404, detail="multi profile run not found")
    result = job.get("multi_profile_run") or {}
    return {
        "task_id": task_id, "status": job.get("status", ""),
        "total_sites": job.get("total_sites", 0),
        "ok_sites": result.get("ok_sites", 0), "failed_sites": result.get("failed_sites", 0),
        "record_count": job.get("item_count", 0), "accepted": job.get("is_valid", False),
        "error": job.get("error", ""), "multi_profile_run": result,
    }
