"""Job CRUD endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ..deps import cleanup_stale_jobs, get_job, remove_job, update_job, get_registry

router = APIRouter()


@router.get("/jobs")
def list_jobs(
    status: str = "",
    kind: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    cleanup_stale_jobs()
    return {"jobs": get_registry().list_jobs(status=status, kind=kind, limit=limit)}


@router.get("/jobs/{task_id}")
def get_job_detail(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/jobs/{task_id}/cancel")
def cancel_job(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("status") not in ("running", "paused"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot cancel: current status is '{job.get('status')}'",
        )
    update_job(task_id, status="cancelled", error="cancelled by user")
    get_registry().mark_status(task_id, "cancelled")
    return {"task_id": task_id, "status": "cancelled"}


@router.delete("/jobs/{task_id}")
def delete_job(task_id: str) -> dict[str, Any]:
    cleanup_stale_jobs()
    job = get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    remove_job(task_id)
    return {"task_id": task_id, "deleted": True}
