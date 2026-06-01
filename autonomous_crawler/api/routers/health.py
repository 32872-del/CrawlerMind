"""Health check and workbench config endpoints."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from ..deps import _job_retention_seconds, _max_active_jobs

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/workbench/config")
def workbench_config() -> dict[str, Any]:
    return {
        "version": "0.3.0",
        "supported_export_formats": ["json", "csv", "xlsx", "sqlite", "db"],
        "max_active_jobs": _max_active_jobs(),
        "default_retention_seconds": _job_retention_seconds(),
        "endpoints": {
            "catalog_import": "/catalog/import",
            "site_analyze": "/site/analyze",
            "fields_resolve": "/fields/resolve",
            "runs_test": "/runs/test",
            "runs_full": "/runs/full",
            "runs_status": "/runs/{task_id}/status",
            "runs_events": "/runs/{task_id}/events",
            "access_probe": "/runs/{task_id}/access-probe",
            "managed_control_loop": "/runs/{task_id}/managed-control-loop",
            "exports": "/exports",
            "exports_validate_path": "/exports/validate-path",
            "exports_resolve_path": "/exports/resolve-path",
            "llm_models": "/llm/models",
            "llm_health": "/llm/health",
            "profile_runs": "/profile-runs",
            "jobs": "/jobs",
            "health": "/health",
        },
    }
