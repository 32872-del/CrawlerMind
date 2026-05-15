"""Visual recon evidence for persisted browser screenshots.

This is the first CAP-5.2 slice.  It intentionally keeps the core small:
inspect screenshot artifacts, normalize optional OCR provider output, and
return credential-safe evidence that later OCR/layout modules can extend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


MAX_TEXT_PREVIEW = 2000
MAX_FINDINGS = 50
MAX_PROVIDER_ERROR = 300
IMAGE_HEADERS = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "gif": b"GIF",
    "bmp": b"BM",
    "webp": b"RIFF",
}


@runtime_checkable
class OcrProvider(Protocol):
    """Optional OCR provider contract used by visual recon."""

    name: str

    def extract_text(self, image_path: str) -> str | dict[str, Any]:
        """Return OCR text or a provider-specific dict with text/confidence."""


@dataclass(frozen=True)
class VisualFinding:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class VisualReconReport:
    """Serializable visual evidence for one screenshot artifact."""

    status: str = "ok"
    image_path: str = ""
    image_kind: str = ""
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    aspect_ratio: float = 0.0
    layout: dict[str, Any] = field(default_factory=dict)
    ocr: dict[str, Any] = field(default_factory=dict)
    findings: list[VisualFinding] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "image_path": _safe_path(self.image_path),
            "image_kind": self.image_kind,
            "size_bytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
            "aspect_ratio": self.aspect_ratio,
            "layout": dict(self.layout),
            "ocr": dict(self.ocr),
            "findings": [finding.to_dict() for finding in self.findings[:MAX_FINDINGS]],
        }
        if self.error:
            payload["error"] = self.error[:MAX_PROVIDER_ERROR]
        return payload


def analyze_screenshot(
    image_path: str | Path,
    *,
    ocr_provider: OcrProvider | None = None,
) -> VisualReconReport:
    """Inspect a screenshot and return visual evidence.

    The default implementation is dependency-light.  It detects common image
    headers, PNG/JPEG dimensions, basic layout buckets, and optional OCR
    provider output.
    """
    path = Path(image_path)
    findings: list[VisualFinding] = []
    if not path.exists():
        return VisualReconReport(
            status="failed",
            image_path=str(path),
            findings=[VisualFinding("screenshot_missing", "high", "Screenshot artifact does not exist.")],
            error="screenshot artifact does not exist",
        )
    if not path.is_file():
        return VisualReconReport(
            status="failed",
            image_path=str(path),
            findings=[VisualFinding("screenshot_not_file", "high", "Screenshot path is not a file.")],
            error="screenshot path is not a file",
        )

    data = path.read_bytes()
    size_bytes = len(data)
    if size_bytes == 0:
        findings.append(VisualFinding("screenshot_empty", "high", "Screenshot file is empty."))
        return VisualReconReport(
            status="failed",
            image_path=str(path),
            size_bytes=0,
            findings=findings,
            error="screenshot file is empty",
        )

    image_kind = _detect_image_kind(data, path)
    width, height = _image_dimensions(data, image_kind)
    if not image_kind:
        findings.append(VisualFinding("unknown_image_format", "medium", "Screenshot format could not be detected."))
    if width <= 0 or height <= 0:
        findings.append(VisualFinding("image_dimensions_unknown", "medium", "Image dimensions could not be read."))
    if size_bytes < 1024:
        findings.append(VisualFinding("tiny_screenshot", "medium", "Screenshot artifact is unusually small."))

    layout = _layout_summary(width, height, size_bytes)
    ocr = _run_ocr_provider(path, ocr_provider)
    if ocr.get("status") == "unavailable":
        findings.append(VisualFinding("ocr_provider_missing", "info", "No OCR provider configured."))
    elif ocr.get("status") == "failed":
        findings.append(VisualFinding("ocr_provider_failed", "medium", "OCR provider failed."))
    elif ocr.get("text_preview"):
        layout["has_visible_text_evidence"] = True

    return VisualReconReport(
        status="ok" if not any(f.severity == "high" for f in findings) else "degraded",
        image_path=str(path),
        image_kind=image_kind,
        size_bytes=size_bytes,
        width=width,
        height=height,
        aspect_ratio=round(width / height, 4) if width and height else 0.0,
        layout=layout,
        ocr=ocr,
        findings=findings,
    )


def analyze_runtime_artifacts(
    artifacts: list[Any],
    *,
    ocr_provider: OcrProvider | None = None,
) -> list[dict[str, Any]]:
    """Run visual recon for screenshot artifacts in a runtime response."""
    reports: list[dict[str, Any]] = []
    for artifact in artifacts:
        kind = getattr(artifact, "kind", "")
        path = getattr(artifact, "path", "")
        if isinstance(artifact, dict):
            kind = str(artifact.get("kind") or "")
            path = str(artifact.get("path") or "")
        if kind == "screenshot" and path:
            reports.append(analyze_screenshot(path, ocr_provider=ocr_provider).to_dict())
    return reports


def _detect_image_kind(data: bytes, path: Path) -> str:
    for kind, header in IMAGE_HEADERS.items():
        if data.startswith(header):
            return "jpg" if kind == "jpeg" else kind
    extension = path.suffix.lower().lstrip(".")
    return extension if extension in {"png", "jpg", "jpeg", "gif", "bmp", "webp"} else ""


def _image_dimensions(data: bytes, image_kind: str) -> tuple[int, int]:
    if image_kind == "png" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if image_kind == "gif" and len(data) >= 10:
        return int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    if image_kind == "jpg":
        return _jpeg_dimensions(data)
    return 0, 0


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(data[index + 3:index + 5], "big")
            width = int.from_bytes(data[index + 5:index + 7], "big")
            return width, height
        index += length
    return 0, 0


def _layout_summary(width: int, height: int, size_bytes: int) -> dict[str, Any]:
    orientation = "unknown"
    if width and height:
        if width > height * 1.15:
            orientation = "landscape"
        elif height > width * 1.15:
            orientation = "portrait"
        else:
            orientation = "square"
    viewport_class = "unknown"
    if width and height:
        if width < 600:
            viewport_class = "mobile"
        elif width < 1024:
            viewport_class = "tablet"
        else:
            viewport_class = "desktop"
    return {
        "orientation": orientation,
        "viewport_class": viewport_class,
        "megapixels": round((width * height) / 1_000_000, 3) if width and height else 0.0,
        "bytes_per_pixel": round(size_bytes / (width * height), 4) if width and height else 0.0,
        "has_visible_text_evidence": False,
    }


def _run_ocr_provider(path: Path, provider: OcrProvider | None) -> dict[str, Any]:
    if provider is None:
        return {
            "status": "unavailable",
            "provider": "",
            "text_preview": "",
            "text_chars": 0,
            "confidence": None,
        }
    provider_name = str(getattr(provider, "name", provider.__class__.__name__) or "ocr_provider")
    try:
        raw = provider.extract_text(str(path))
    except Exception as exc:
        return {
            "status": "failed",
            "provider": provider_name,
            "text_preview": "",
            "text_chars": 0,
            "confidence": None,
            "error": f"{type(exc).__name__}: {exc}"[:MAX_PROVIDER_ERROR],
        }
    text = ""
    confidence: Any = None
    if isinstance(raw, dict):
        text = str(raw.get("text") or raw.get("text_preview") or "")
        confidence = raw.get("confidence")
    else:
        text = str(raw or "")
    return {
        "status": "ok",
        "provider": provider_name,
        "text_preview": text[:MAX_TEXT_PREVIEW],
        "text_chars": len(text),
        "confidence": confidence,
        "text_truncated": len(text) > MAX_TEXT_PREVIEW,
    }


def _safe_path(value: str) -> str:
    path = str(value or "")
    if not path:
        return ""
    try:
        return str(Path(path).resolve())
    except Exception:
        return path
