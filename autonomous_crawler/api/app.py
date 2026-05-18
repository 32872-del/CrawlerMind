"""FastAPI service boundary for the autonomous crawler MVP."""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..runners import ProfileLongRunConfig, SiteProfile, run_multi_profile_longrun, run_profile_longrun
from ..runners.product_workflow import (
    CrawlRunSpec,
    ExportSpec,
    analyze_site_for_product_workflow,
    build_full_run_payload,
    build_run_spec,
    build_test_run_payload,
    events_for_job,
    export_product_records,
    import_catalog_tree,
    resolve_fields,
    summarize_run_progress,
)
from ..runtime import NativeFetchRuntime
from ..llm.openai_compatible import (
    LLMConfigurationError,
    OpenAICompatibleAdvisor,
    OpenAICompatibleConfig,
)
from ..storage import list_crawl_results, load_crawl_result, save_crawl_result
from ..tools.anti_bot_report import summarize_anti_bot_report
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
    anti_bot_summary: dict[str, Any] | None = None


class ProfileRunRequest(BaseModel):
    profile: dict[str, Any] | None = None
    profile_path: str = ""
    run_id: str = ""
    batch_size: int = Field(default=20, ge=1, le=200)
    max_batches: int = Field(default=0, ge=0)
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    item_workers: int = Field(default=1, ge=1, le=128)
    category: str = ""
    output_report_path: str = ""
    runtime_dir: str = ""


class ProfileRunResponse(BaseModel):
    task_id: str
    run_id: str
    status: str
    profile_name: str
    record_count: int = 0
    accepted: bool = False


class MultiProfileRunRequest(BaseModel):
    jobs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    max_sites: int = Field(default=5, ge=1, le=5)
    default_item_workers: int = Field(default=1, ge=1, le=128)
    output_report_path: str = ""


class MultiProfileRunResponse(BaseModel):
    task_id: str
    status: str
    total_sites: int = 0
    ok_sites: int = 0
    failed_sites: int = 0


class CatalogImportRequest(BaseModel):
    catalog: Any | None = None
    catalog_path: str = ""


class SiteAnalyzeRequest(BaseModel):
    target_url: str = Field(..., min_length=1)
    imported_catalog: Any | None = None
    imported_catalog_path: str = ""
    field_goal: str = ""


class FieldResolveRequest(BaseModel):
    available_fields: list[dict[str, Any]] = Field(default_factory=list)
    natural_language: str = ""
    requested_fields: list[str] = Field(default_factory=list)


class ProductRunRequest(BaseModel):
    target_url: str = Field(..., min_length=1)
    profile: dict[str, Any] = Field(default_factory=dict)
    catalog_nodes: list[dict[str, Any]] = Field(default_factory=list)
    selected_fields: list[str] = Field(default_factory=list)
    export: dict[str, Any] = Field(default_factory=dict)
    run_mode: str = "direct"
    item_workers: int = Field(default=4, ge=1, le=128)
    max_sites: int = Field(default=1, ge=1, le=5)
    test_limit: int = Field(default=100, ge=1, le=10000)
    runtime_dir: str = ""


class ExportRequest(BaseModel):
    run_id: str = Field(..., min_length=1)
    runtime_dir: str = ""
    format: str = "xlsx"
    output_path: str = ""
    template_path: str = ""
    field_mapping: dict[str, str] = Field(default_factory=dict)


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
        strategy = final_state.get("crawl_strategy") or {}
        anti_bot_report = strategy.get("anti_bot_report") or {}
        _update_job(
            task_id,
            status=final_state.get("status", "completed"),
            item_count=int(extracted.get("item_count") or 0),
            is_valid=bool(validation.get("is_valid")),
            error_code=final_state.get("error_code"),
            anti_bot_summary=summarize_anti_bot_report(anti_bot_report) if anti_bot_report else None,
        )
    except Exception as exc:
        from ..errors import classify_llm_error
        _update_job(task_id, status="failed", error=str(exc),
                    error_code=classify_llm_error(exc))


def _load_profile_for_request(request: ProfileRunRequest) -> SiteProfile:
    if request.profile is not None:
        return SiteProfile.from_dict(request.profile)
    if request.profile_path.strip():
        return SiteProfile.load(request.profile_path)
    raise ValueError("profile or profile_path is required")


def run_profile_longrun_workflow(request: ProfileRunRequest, *, task_id: str) -> dict[str, Any]:
    profile = _load_profile_for_request(request)
    run_id = request.run_id.strip() or f"profile-{task_id}"
    fetch_runtime = NativeFetchRuntime(reuse_httpx_client=request.item_workers > 1)
    try:
        result = run_profile_longrun(
            profile=profile,
            config=ProfileLongRunConfig(
                run_id=run_id,
                worker_id="api-profile-run",
                batch_size=request.batch_size,
                max_batches=request.max_batches,
                timeout_ms=request.timeout_ms,
                item_workers=request.item_workers,
                category=request.category,
                output_report_path=request.output_report_path,
            ),
            fetch_runtime=fetch_runtime,
            runtime_dir=request.runtime_dir or None,
        )
    finally:
        fetch_runtime.close()
    return result.to_dict()


def _background_profile_run(task_id: str, request: ProfileRunRequest) -> None:
    try:
        result = run_profile_longrun_workflow(request, task_id=task_id)
        _update_job(
            task_id,
            status=result.get("status", "completed"),
            item_count=int(result.get("product_stats", {}).get("total") or 0),
            is_valid=bool(result.get("accepted")),
            profile_run=result,
        )
    except Exception as exc:
        _update_job(task_id, status="failed", error=str(exc), error_code="PROFILE_RUN_FAILED")


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
        _update_job(
            task_id,
            status="completed" if int(result.get("failed_sites") or 0) == 0 else "partial",
            item_count=sum(_site_record_count(item) for item in result.get("results") or []),
            is_valid=int(result.get("failed_sites") or 0) == 0,
            multi_profile_run=result,
        )
    except Exception as exc:
        _update_job(task_id, status="failed", error=str(exc), error_code="MULTI_PROFILE_RUN_FAILED")


def _catalog_payload_from_request(request: CatalogImportRequest | SiteAnalyzeRequest) -> Any:
    payload = getattr(request, "catalog", None)
    if payload is not None:
        return payload
    imported = getattr(request, "imported_catalog", None)
    if imported is not None:
        return imported
    path = str(getattr(request, "catalog_path", "") or getattr(request, "imported_catalog_path", "") or "").strip()
    if path:
        return _load_json_file(path)
    return None


def _load_json_file(path: str) -> Any:
    file_path = Path(path)
    return json_loads_text(file_path.read_text(encoding="utf-8-sig", errors="replace"))


def json_loads_text(text: str) -> Any:
    import json

    return json.loads(text)


def _register_product_run_job(
    *,
    kind: str,
    run_payload: dict[str, Any],
    spec: CrawlRunSpec,
) -> dict[str, Any]:
    profile = SiteProfile.from_dict(run_payload["profile"])
    request = ProfileRunRequest(
        profile=profile.to_dict(),
        run_id=str(run_payload.get("run_id") or ""),
        batch_size=int(run_payload.get("batch_size") or 20),
        max_batches=int(run_payload.get("max_batches") or 0),
        item_workers=int(run_payload.get("item_workers") or spec.item_workers),
        runtime_dir=str(run_payload.get("runtime_dir") or spec.runtime_dir),
    )
    task_id = str(uuid.uuid4())[:8]
    if not _try_register_job(task_id, f"{kind}:{profile.name}", first_profile_target(profile)):
        raise HTTPException(status_code=429, detail=f"too many active jobs ({_max_active_jobs()} max)")
    _update_job(
        task_id,
        run_id=request.run_id,
        profile_name=profile.name,
        kind=kind,
        product_run_spec={
            "target_url": spec.target_url,
            "selected_fields": list(spec.selected_fields),
            "run_mode": spec.run_mode,
            "item_workers": spec.item_workers,
            "runtime_dir": request.runtime_dir,
            "export": {
                "format": spec.export.format,
                "output_path": spec.export.output_path,
                "template_path": spec.export.template_path,
                "field_mapping": dict(spec.export.field_mapping),
            },
        },
    )
    thread = threading.Thread(
        target=_background_profile_run,
        args=(task_id, request),
        daemon=True,
    )
    thread.start()
    return {
        "task_id": task_id,
        "run_id": request.run_id,
        "status": "running",
        "profile_name": profile.name,
        "record_count": 0,
        "accepted": False,
    }


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
            "anti_bot_summary": None,
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
                "anti_bot_summary": job.get("anti_bot_summary"),
            }

        # Fall back to persisted result
        result = load_crawl_result(task_id)
        if result:
            return result

        raise HTTPException(status_code=404, detail="crawl task not found")

    @app.get("/history")
    def history(limit: int = 20) -> dict[str, Any]:
        return {"items": list_crawl_results(limit=limit)}

    @app.post("/catalog/import")
    def catalog_import(request: CatalogImportRequest) -> dict[str, Any]:
        try:
            payload = _catalog_payload_from_request(request)
            if payload is None:
                raise ValueError("catalog or catalog_path is required")
            nodes = import_catalog_tree(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "schema_version": "catalog-tree/v1",
            "catalog_tree": nodes,
            "node_count": _count_catalog_nodes(nodes),
            "leaf_count": _count_catalog_leaves(nodes),
        }

    @app.post("/site/analyze")
    def site_analyze(request: SiteAnalyzeRequest) -> dict[str, Any]:
        try:
            imported_catalog = _catalog_payload_from_request(request)
            return analyze_site_for_product_workflow(
                request.target_url,
                imported_catalog=imported_catalog,
                field_goal=request.field_goal,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/fields/resolve")
    def fields_resolve(request: FieldResolveRequest) -> dict[str, Any]:
        return resolve_fields(
            request.available_fields,
            natural_language=request.natural_language,
            requested_fields=request.requested_fields,
        )

    @app.post("/runs/test")
    def product_test_run(request: ProductRunRequest) -> dict[str, Any]:
        spec = build_run_spec(request.model_dump())
        return _register_product_run_job(
            kind="product_test_run",
            run_payload=build_test_run_payload(spec),
            spec=spec,
        )

    @app.post("/runs/full")
    def product_full_run(request: ProductRunRequest) -> dict[str, Any]:
        spec = build_run_spec(request.model_dump())
        return _register_product_run_job(
            kind="product_full_run",
            run_payload=build_full_run_payload(spec),
            spec=spec,
        )

    @app.get("/runs/{task_id}/status")
    def product_run_status(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="run not found")
        progress = summarize_run_progress(job)
        return {
            "task_id": task_id,
            "kind": job.get("kind", ""),
            "run_id": job.get("run_id", ""),
            "status": job.get("status", ""),
            "record_count": job.get("item_count", 0),
            "accepted": job.get("is_valid", False),
            "error": job.get("error", ""),
            "progress": progress,
        }

    @app.get("/runs/{task_id}/events")
    def product_run_events(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job:
            raise HTTPException(status_code=404, detail="run not found")
        return {"task_id": task_id, "events": events_for_job(job)}

    @app.post("/exports")
    def product_export(request: ExportRequest) -> dict[str, Any]:
        try:
            return export_product_records(
                run_id=request.run_id,
                runtime_dir=request.runtime_dir,
                export_spec=ExportSpec(
                    format=request.format,
                    output_path=request.output_path,
                    template_path=request.template_path,
                    field_mapping=dict(request.field_mapping),
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/profile-runs", response_model=ProfileRunResponse)
    def start_profile_run(request: ProfileRunRequest) -> dict[str, Any]:
        _cleanup_stale_jobs()
        try:
            profile = _load_profile_for_request(request)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        task_id = str(uuid.uuid4())[:8]
        run_id = request.run_id.strip() or f"profile-{task_id}"
        if not _try_register_job(task_id, f"profile-run:{profile.name}", first_profile_target(profile)):
            raise HTTPException(
                status_code=429,
                detail=f"too many active jobs ({_max_active_jobs()} max)",
            )
        _update_job(task_id, run_id=run_id, profile_name=profile.name, kind="profile_run")
        thread = threading.Thread(
            target=_background_profile_run,
            args=(task_id, request),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": task_id,
            "run_id": run_id,
            "status": "running",
            "profile_name": profile.name,
            "record_count": 0,
            "accepted": False,
        }

    @app.post("/profile-runs/batch", response_model=MultiProfileRunResponse)
    def start_multi_profile_run(request: MultiProfileRunRequest) -> dict[str, Any]:
        _cleanup_stale_jobs()
        if not request.jobs:
            raise HTTPException(status_code=400, detail="jobs is required")
        if len(request.jobs) > request.max_sites:
            raise HTTPException(status_code=400, detail=f"too many site jobs: {len(request.jobs)} > {request.max_sites}")

        task_id = str(uuid.uuid4())[:8]
        if not _try_register_job(task_id, "multi-profile-run", f"{len(request.jobs)} sites"):
            raise HTTPException(
                status_code=429,
                detail=f"too many active jobs ({_max_active_jobs()} max)",
            )
        _update_job(task_id, kind="multi_profile_run", total_sites=len(request.jobs))
        thread = threading.Thread(
            target=_background_multi_profile_run,
            args=(task_id, request),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": task_id,
            "status": "running",
            "total_sites": len(request.jobs),
            "ok_sites": 0,
            "failed_sites": 0,
        }

    @app.get("/profile-runs/{task_id}")
    def get_profile_run(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job or job.get("kind") != "profile_run":
            raise HTTPException(status_code=404, detail="profile run not found")
        return {
            "task_id": task_id,
            "run_id": job.get("run_id", ""),
            "status": job.get("status", ""),
            "profile_name": job.get("profile_name", ""),
            "record_count": job.get("item_count", 0),
            "accepted": job.get("is_valid", False),
            "error": job.get("error", ""),
            "profile_run": job.get("profile_run"),
        }

    @app.get("/profile-runs/batch/{task_id}")
    def get_multi_profile_run(task_id: str) -> dict[str, Any]:
        _cleanup_stale_jobs()
        job = _get_job(task_id)
        if not job or job.get("kind") != "multi_profile_run":
            raise HTTPException(status_code=404, detail="multi profile run not found")
        result = job.get("multi_profile_run") or {}
        return {
            "task_id": task_id,
            "status": job.get("status", ""),
            "total_sites": job.get("total_sites", 0),
            "ok_sites": result.get("ok_sites", 0),
            "failed_sites": result.get("failed_sites", 0),
            "record_count": job.get("item_count", 0),
            "accepted": job.get("is_valid", False),
            "error": job.get("error", ""),
            "multi_profile_run": result,
        }

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


def first_profile_target(profile: SiteProfile) -> str:
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


def _count_catalog_nodes(nodes: list[dict[str, Any]]) -> int:
    return sum(1 + _count_catalog_nodes(list(node.get("children") or [])) for node in nodes if isinstance(node, dict))


def _count_catalog_leaves(nodes: list[dict[str, Any]]) -> int:
    total = 0
    for node in nodes:
        if not isinstance(node, dict):
            continue
        children = list(node.get("children") or [])
        if node.get("url"):
            total += 1
        total += _count_catalog_leaves(children)
    return total
