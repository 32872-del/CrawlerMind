"""Artifact manifest for crawl diagnostics and replay.

Hard-site work needs evidence: what URL was visited, which strategy/context was
used, where screenshots or traces live, and what failed. This manifest is a
small serializable index that can be stored in workflow state or later written
next to run artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


ARTIFACT_ROOT = Path(__file__).resolve().parent / "runtime" / "artifacts"


@dataclass(frozen=True)
class ArtifactManifest:
    target_url: str
    stage: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    final_url: str = ""
    fetch_mode: str = ""
    browser_context: dict[str, Any] = field(default_factory=dict)
    screenshot_path: str = ""
    html_path: str = ""
    network_trace_path: str = ""
    access_decision: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_url": self.target_url,
            "stage": self.stage,
            "created_at": self.created_at,
            "final_url": self.final_url,
            "fetch_mode": self.fetch_mode,
            "browser_context": dict(self.browser_context),
            "screenshot_path": self.screenshot_path,
            "html_path": self.html_path,
            "network_trace_path": self.network_trace_path,
            "access_decision": dict(self.access_decision),
            "notes": list(self.notes),
        }


def build_browser_artifact_manifest(
    *,
    target_url: str,
    final_url: str = "",
    browser_context: dict[str, Any] | None = None,
    screenshot_path: str = "",
    access_decision: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return ArtifactManifest(
        target_url=target_url,
        stage="browser_fetch",
        final_url=final_url,
        fetch_mode="browser",
        browser_context=browser_context or {},
        screenshot_path=screenshot_path,
        access_decision=access_decision or {},
        notes=notes or [],
    ).to_dict()


def persist_artifact_bundle(
    manifest: dict[str, Any],
    *,
    run_id: str = "",
    html: str = "",
    network_trace: dict[str, Any] | list[Any] | None = None,
    artifact_root: Path | str | None = None,
) -> dict[str, Any]:
    """Persist a manifest plus optional HTML/network evidence files."""
    root = Path(artifact_root) if artifact_root else ARTIFACT_ROOT
    bundle_dir = root / _safe_bundle_name(run_id or manifest.get("target_url") or "artifact")
    bundle_dir.mkdir(parents=True, exist_ok=True)

    persisted = dict(manifest)
    if html:
        html_path = bundle_dir / "snapshot.html"
        html_path.write_text(html, encoding="utf-8")
        persisted["html_path"] = str(html_path)

    if network_trace is not None:
        network_path = bundle_dir / "network_trace.json"
        network_path.write_text(
            json.dumps(network_trace, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        persisted["network_trace_path"] = str(network_path)

    manifest_path = bundle_dir / "manifest.json"
    persisted["manifest_path"] = str(manifest_path)
    manifest_path.write_text(
        json.dumps(persisted, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return persisted


def _safe_bundle_name(value: Any) -> str:
    text = str(value or "artifact").strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"[^a-z0-9._-]+", "_", text)
    text = text.strip("._-")
    return (text or "artifact")[:80]


def build_recon_artifact_manifest(
    *,
    target_url: str,
    fetch_trace: dict[str, Any] | None = None,
    access_config: dict[str, Any] | None = None,
    access_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace = fetch_trace or {}
    return ArtifactManifest(
        target_url=target_url,
        stage="recon",
        final_url=str(trace.get("selected_url") or ""),
        fetch_mode=str(trace.get("selected_mode") or ""),
        browser_context=(access_config or {}).get("browser_context", {}),
        access_decision=access_decision or {},
        notes=[f"attempts={len(trace.get('attempts') or [])}"],
    ).to_dict()
