"""Site analysis and field resolution endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...llm.openai_compatible import LLMConfigurationError
from ...runners.product_workflow import analyze_site_for_product_workflow, resolve_fields
from ..deps import build_advisor_from_config
from ...errors import LLM_CONFIG_INVALID
from ..schemas import SiteAnalyzeRequest, FieldResolveRequest
from .catalog import _catalog_payload_from_request

router = APIRouter()


@router.post("/site/analyze")
def site_analyze(request: SiteAnalyzeRequest) -> dict[str, Any]:
    try:
        imported_catalog = _catalog_payload_from_request(request)
        advisor = None
        if request.llm is not None and request.llm.enabled:
            advisor = build_advisor_from_config(request.llm)
        return analyze_site_for_product_workflow(
            request.target_url,
            imported_catalog=imported_catalog,
            field_goal=request.field_goal,
            advisor=advisor,
        )
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error_code": LLM_CONFIG_INVALID, "message": str(exc)},
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/fields/resolve")
def fields_resolve(request: FieldResolveRequest) -> dict[str, Any]:
    return resolve_fields(
        request.available_fields,
        natural_language=request.natural_language,
        requested_fields=request.requested_fields,
    )
