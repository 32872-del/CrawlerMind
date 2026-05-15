"""Explicit CLM site profile schema.

Profiles keep reusable crawl knowledge outside core runtime code. They are
loaded from caller-provided paths and never hidden in global state.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SiteProfile:
    name: str
    selectors: dict[str, Any] = field(default_factory=dict)
    target_fields: list[str] = field(default_factory=list)
    api_hints: dict[str, Any] = field(default_factory=dict)
    pagination_hints: dict[str, Any] = field(default_factory=dict)
    access_config: dict[str, Any] = field(default_factory=dict)
    rate_limits: dict[str, Any] = field(default_factory=dict)
    quality_expectations: dict[str, Any] = field(default_factory=dict)
    training_notes: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    crawl_preferences: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "SiteProfile":
        payload = payload or {}
        return cls(
            name=str(payload.get("name") or "site-profile"),
            selectors=_safe_dict(payload.get("selectors")),
            target_fields=[str(item) for item in (payload.get("target_fields") or []) if str(item).strip()],
            api_hints=_safe_dict(payload.get("api_hints")),
            pagination_hints=_safe_dict(payload.get("pagination_hints")),
            access_config=_safe_dict(payload.get("access_config")),
            rate_limits=_safe_dict(payload.get("rate_limits")),
            quality_expectations=_safe_dict(payload.get("quality_expectations")),
            training_notes=[str(item) for item in (payload.get("training_notes") or []) if str(item).strip()],
            constraints=_safe_dict(payload.get("constraints")),
            crawl_preferences=_safe_dict(payload.get("crawl_preferences")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "SiteProfile":
        profile_path = Path(path)
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("site profile must be a JSON object")
        return cls.from_dict(payload)

    def save(self, path: str | Path) -> None:
        profile_path = Path(path)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "selectors": dict(self.selectors),
            "target_fields": list(self.target_fields),
            "api_hints": dict(self.api_hints),
            "pagination_hints": dict(self.pagination_hints),
            "access_config": dict(self.access_config),
            "rate_limits": dict(self.rate_limits),
            "quality_expectations": dict(self.quality_expectations),
            "training_notes": list(self.training_notes),
            "constraints": dict(self.constraints),
            "crawl_preferences": dict(self.crawl_preferences),
        }

    def apply_to_state(self, state: dict[str, Any]) -> dict[str, Any]:
        recon = dict(state.get("recon_report") or {})
        constraints = dict(recon.get("constraints") or {})
        constraints.update(self.constraints)
        if self.api_hints:
            constraints.setdefault("api_hints", dict(self.api_hints))
            if self.api_hints.get("endpoint"):
                constraints.setdefault("api_endpoint", self.api_hints["endpoint"])
            if self.api_hints.get("method"):
                constraints.setdefault("api_method", self.api_hints["method"])
        if self.pagination_hints:
            constraints.setdefault("pagination", dict(self.pagination_hints))
        if self.access_config:
            constraints.setdefault("access_config", dict(self.access_config))
        if self.rate_limits:
            constraints.setdefault("rate_limit", dict(self.rate_limits))
        if self.quality_expectations:
            constraints.setdefault("quality_expectations", dict(self.quality_expectations))
        recon["constraints"] = constraints
        if self.target_fields:
            recon["target_fields"] = list(self.target_fields)
        if self.selectors:
            recon["inferred_selectors"] = dict(self.selectors)
            recon["profile_selectors"] = dict(self.selectors)
        state = dict(state)
        state["recon_report"] = recon
        if self.crawl_preferences:
            state["crawl_preferences"] = {
                **dict(state.get("crawl_preferences") or {}),
                **self.crawl_preferences,
            }
        state["site_profile"] = self.to_dict()
        return state


def load_site_profile(path: str | Path) -> SiteProfile:
    return SiteProfile.load(path)


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}

