"""CrawlTaskState - Core state schema for the autonomous crawler LangGraph workflow.

Reference: README.md Section 6 - Core State Schema
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class CrawlTaskState(BaseModel):
    """State that flows through the entire crawl workflow graph."""

    # --- Task identity ---
    task_id: str = ""
    user_goal: str = ""
    target_url: str = ""

    # --- Recon output ---
    recon_report: dict[str, Any] = Field(default_factory=dict)
    # Expected keys:
    #   frontend_framework: str  (e.g. "react", "vue", "nextjs", "unknown")
    #   rendering: str           ("spa", "ssr", "static")
    #   anti_bot: dict           ({detected: bool, type: str, severity: str})
    #   api_endpoints: list[str] (discovered XHR/GraphQL endpoints)
    #   dom_structure: dict      ({has_pagination: bool, product_selector: str, ...})

    # --- Strategy output ---
    crawl_strategy: dict[str, Any] = Field(default_factory=dict)
    # Expected keys:
    #   mode: str                ("http", "browser", "api_intercept")
    #   extraction_method: str   ("api_json", "hydration_data", "dom_parse", "browser_render")
    #   selectors: dict          (CSS selectors for each field)
    #   pagination: dict         (pagination config)
    #   headers: dict            (custom headers if needed)
    #   rationale: str           (why this strategy was chosen)

    # --- Execution output ---
    visited_urls: list[str] = Field(default_factory=list)
    raw_html: dict[str, str] = Field(default_factory=dict)  # url -> html
    api_responses: list[dict[str, Any]] = Field(default_factory=list)

    # --- Extraction output ---
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    # Expected keys:
    #   items: list[dict]        (extracted product records)
    #   fields_found: list[str]  (which fields were successfully extracted)
    #   confidence: float        (extraction confidence score)

    # --- Validation output ---
    validation_result: dict[str, Any] = Field(default_factory=dict)
    # Expected keys:
    #   is_valid: bool
    #   completeness: float      (0-1, percentage of fields filled)
    #   anomalies: list[str]     (detected issues)
    #   needs_retry: bool

    # --- Control flow ---
    retries: int = 0
    max_retries: int = 3
    status: str = "pending"
    # Status values: pending, planning, recon, strategizing, executing,
    #                extracting, validating, retrying, completed, failed
    error_log: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)  # Human-readable log

    class Config:
        arbitrary_types_allowed = True
