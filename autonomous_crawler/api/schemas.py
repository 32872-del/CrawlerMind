"""Pydantic request/response models for the API layer."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    reasoning_effort: str = "medium"
    stream: bool = False


class ManagedAIConfig(BaseModel):
    enabled: bool = False
    mode: str = "analysis_only"
    pre_run_review: bool = False
    post_run_diagnosis: bool = False
    apply_pre_run_patch: bool = False
    auto_repair: bool = False


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
    adaptive_item_workers: bool = True
    min_item_workers: int = Field(default=1, ge=1, le=128)
    max_item_workers: int = Field(default=0, ge=0, le=128)
    category: str = ""
    output_report_path: str = ""
    runtime_dir: str = ""
    supervision_mode: str = "off"
    managed_ai: ManagedAIConfig | None = None
    llm: LLMConfig | None = None


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
    llm: LLMConfig | None = None


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
    managed_ai: ManagedAIConfig | None = None
    llm: LLMConfig | None = None


class ExportRequest(BaseModel):
    run_id: str = Field(..., min_length=1)
    runtime_dir: str = ""
    format: str = "xlsx"
    output_path: str = ""
    template_path: str = ""
    field_mapping: dict[str, str] = Field(default_factory=dict)
    template: dict[str, Any] | None = None


class AIRerunRequest(BaseModel):
    run_kind: str = "test"
    apply_diagnostics: bool = True
    extra_overrides: dict[str, Any] = Field(default_factory=dict)
    managed_ai: ManagedAIConfig | None = None
    llm: LLMConfig | None = None


class ManagedActionsRequest(BaseModel):
    execute: bool = True
    use_llm: bool = True
    llm_decide: bool = False
    extra_context: dict[str, Any] = Field(default_factory=dict)
    llm: LLMConfig | None = None


class ManagedRepairRunRequest(ManagedActionsRequest):
    run_kind: str = "test"
    apply_diagnostics: bool = True
    extra_overrides: dict[str, Any] = Field(default_factory=dict)
    managed_ai: ManagedAIConfig | None = None


class ManagedStepRequest(ManagedActionsRequest):
    start_child_run: bool = False
    run_kind: str = "test"
    apply_diagnostics: bool = True
    extra_overrides: dict[str, Any] = Field(default_factory=dict)
    managed_ai: ManagedAIConfig | None = None


class AccessProbeRequest(BaseModel):
    target_url: str = Field(..., min_length=1)
    task_id: str = ""
    live_probe: bool = False
    sample_limit: int = Field(default=3, ge=1, le=10)
    profile: dict[str, Any] = Field(default_factory=dict)
    extra_context: dict[str, Any] = Field(default_factory=dict)
    llm: LLMConfig | None = None


class ManagedControlLoopRequest(BaseModel):
    use_llm: bool = True
    execute: bool = True
    include_access_probe: bool = True
    live_probe: bool = False
    start_child_run: bool = False
    run_kind: str = "test"
    apply_diagnostics: bool = True
    extra_context: dict[str, Any] = Field(default_factory=dict)
    extra_overrides: dict[str, Any] = Field(default_factory=dict)
    managed_ai: ManagedAIConfig | None = None
    llm: LLMConfig | None = None


class LLMModelsRequest(BaseModel):
    base_url: str = Field(..., min_length=1)
    api_key: str = ""
    provider: str = "openai-compatible"


class ExportPathRequest(BaseModel):
    directory: str = Field(..., min_length=1)
    create: bool = False


class ExportResolvePathRequest(BaseModel):
    directory: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    format: str = "xlsx"
    filename: str = ""


class AutoRepairDiagnoseRequest(BaseModel):
    """Request body for auto-repair diagnosis."""
    execution_result: dict[str, Any] | None = None


class AutoRepairLoopRequest(BaseModel):
    """Request body for auto-repair loop."""
    max_cycles: int = 3
    llm: LLMConfig | None = None
    extra_context: dict[str, Any] | None = None
