"""FastAPI application factory — thin composition root.

All business logic lives in routers/ and deps.py. This module wires
CORS, startup recovery, and router registration.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI

from .deps import (
    get_registry,
    clear_jobs as _clear_jobs,
    register_job as _register_job,
    update_job as _update_job,
    get_job as _get_job,
    try_register_job as _try_register_job,
    cleanup_stale_jobs as _cleanup_stale_jobs,
    count_active_jobs as _count_active_jobs,
    build_advisor_from_config as _build_advisor_from_config,
    _max_active_jobs,
    _job_retention_seconds,
)
from .schemas import LLMConfig

# Re-export for backward compatibility with tests and mock patches
_registry = get_registry()

# Functions that tests mock-patch via autonomous_crawler.api.app.*
from .routers.runs import run_profile_longrun_workflow  # noqa: F401
from .routers.runs import _execute_inspect_access  # noqa: F401
from .routers.crawl import run_crawl_workflow  # noqa: F401
from .routers.profile_runs import run_multi_profile_longrun_workflow  # noqa: F401
from ..storage import save_crawl_result, load_crawl_result, list_crawl_results  # noqa: F401
from ..llm.model_list import check_provider_health, fetch_model_list  # noqa: F401


def create_app() -> FastAPI:
    from starlette.middleware.cors import CORSMiddleware

    app = FastAPI(title="Autonomous Crawl Agent", version="0.3.0")

    # CORS: permissive for local dev; tighten in production via env
    _cors_origins = os.environ.get("CLM_CORS_ORIGINS", "*")
    origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins != "*" else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _recover_jobs() -> None:
        registry = get_registry()
        stale = registry.recover_running()
        for job in stale:
            registry.mark_status(job["task_id"], "failed")
            registry.update(job["task_id"], error="recovered from prior crash", error_code="CRASH_RECOVERY")
        if stale:
            logging.getLogger("autonomous_crawler.api").warning(
                "Recovered %d stale running jobs from prior session", len(stale)
            )

    # Register routers
    from .routers.health import router as health_router
    from .routers.jobs import router as jobs_router
    from .routers.crawl import router as crawl_router
    from .routers.catalog import router as catalog_router
    from .routers.site import router as site_router
    from .routers.runs import router as runs_router
    from .routers.exports import router as exports_router
    from .routers.profile_runs import router as profile_runs_router
    from .routers.llm import router as llm_router

    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(crawl_router)
    app.include_router(catalog_router)
    app.include_router(site_router)
    app.include_router(runs_router)
    app.include_router(exports_router)
    app.include_router(profile_runs_router)
    app.include_router(llm_router)

    return app


app = create_app()
