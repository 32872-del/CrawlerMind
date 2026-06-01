"""LLM model list and health endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ...llm.model_list import check_provider_health, fetch_model_list
from ..schemas import LLMModelsRequest

router = APIRouter()


@router.post("/llm/models")
def llm_models(request: LLMModelsRequest) -> dict[str, Any]:
    if not request.base_url.strip():
        raise HTTPException(status_code=400, detail="base_url is required")
    result = fetch_model_list(
        base_url=request.base_url,
        api_key=request.api_key,
        provider=request.provider,
    )
    return result.to_dict()


@router.post("/llm/health")
def llm_health(request: LLMModelsRequest) -> dict[str, Any]:
    if not request.base_url.strip():
        raise HTTPException(status_code=400, detail="base_url is required")
    return check_provider_health(
        base_url=request.base_url,
        api_key=request.api_key,
        provider=request.provider,
    )
