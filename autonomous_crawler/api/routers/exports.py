"""Export endpoints."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from ...runners.product_workflow import ExportSpec, ExportTemplate, export_product_records
from ..schemas import ExportRequest, ExportPathRequest, ExportResolvePathRequest

router = APIRouter()


def _export_suffix(fmt: str) -> str:
    value = str(fmt or "xlsx").lower()
    return "sqlite3" if value in {"sqlite", "db"} else value


@router.post("/exports")
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
                template=ExportTemplate.from_dict(request.template) if request.template else ExportTemplate(),
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/exports/validate-path")
def export_validate_path(request: ExportPathRequest) -> dict[str, Any]:
    if not request.directory.strip():
        raise HTTPException(status_code=400, detail="directory is required")
    dir_path = Path(request.directory.strip())
    created = False
    try:
        if request.create and not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created = True
        exists = dir_path.exists()
        writable = exists and os.access(dir_path, os.W_OK)
        return {
            "exists": exists,
            "created": created,
            "writable": writable,
            "normalized_path": str(dir_path.resolve()),
            "error": "" if writable else ("directory does not exist" if not exists else "directory is not writable"),
        }
    except Exception as exc:
        return {
            "exists": False,
            "created": False,
            "writable": False,
            "normalized_path": str(dir_path),
            "error": str(exc)[:200],
        }


@router.post("/exports/resolve-path")
def export_resolve_path(request: ExportResolvePathRequest) -> dict[str, Any]:
    if not request.directory.strip():
        raise HTTPException(status_code=400, detail="directory is required")
    if not request.run_id.strip():
        raise HTTPException(status_code=400, detail="run_id is required")
    fmt = request.format.strip().lower() or "xlsx"
    suffix = _export_suffix(fmt)
    filename = request.filename.strip() or f"{request.run_id}.{suffix}"
    if not filename.endswith(f".{suffix}"):
        filename = f"{filename}.{suffix}"
    dir_path = Path(request.directory.strip())
    final = dir_path / filename
    return {
        "directory": str(dir_path.resolve()),
        "filename": filename,
        "output_path": str(final.resolve()),
        "format": fmt,
    }
