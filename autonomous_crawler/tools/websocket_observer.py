"""WebSocket observation MVP.

Deterministic WebSocket connection and frame capture using Playwright's
``page.on("websocket", ...)`` event. Captures connection metadata, frame
direction, text/binary marker, bounded preview, and byte length.

This module does NOT connect to external sites, replay frames, or bypass
any access controls. It provides the data foundation for future WS
analysis and integration with the Recon layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_FRAME_PREVIEW = 500
DEFAULT_MAX_FRAMES = 200
DEFAULT_MAX_CONNECTIONS = 50
FRAME_DIRECTION_SENT = "sent"
FRAME_DIRECTION_RECEIVED = "received"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WebSocketFrame:
    """A single WebSocket frame (sent or received)."""
    direction: str  # "sent" or "received"
    data_type: str  # "text" or "binary"
    preview: str  # truncated payload preview
    byte_length: int
    timestamp_ms: float = 0.0


@dataclass(frozen=True)
class WebSocketConnection:
    """A single WebSocket connection observed on the page."""
    url: str
    is_alive: bool = False
    frame_count: int = 0
    frames: tuple[WebSocketFrame, ...] = ()
    error: str = ""


@dataclass
class WebSocketObservationResult:
    """Result of WebSocket observation for a page load."""
    page_url: str = ""
    status: str = "ok"
    error: str = ""
    connections: list[WebSocketConnection] = field(default_factory=list)
    total_frames: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_url": self.page_url,
            "status": self.status,
            "error": self.error,
            "connections": [
                {
                    "url": c.url,
                    "is_alive": c.is_alive,
                    "frame_count": c.frame_count,
                    "frames": [
                        {
                            "direction": f.direction,
                            "data_type": f.data_type,
                            "preview": f.preview,
                            "byte_length": f.byte_length,
                            "timestamp_ms": f.timestamp_ms,
                        }
                        for f in c.frames
                    ],
                    "error": c.error,
                }
                for c in self.connections
            ],
            "total_frames": self.total_frames,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Frame payload helpers
# ---------------------------------------------------------------------------

def normalize_frame_payload(
    payload: Any,
    max_preview: int = DEFAULT_MAX_FRAME_PREVIEW,
) -> tuple[str, str, int]:
    """Normalize a WebSocket frame payload into (preview, data_type, byte_length).

    Handles str and bytes payloads. Truncates preview to max_preview chars.
    Never leaks full payloads.
    """
    if isinstance(payload, (bytes, bytearray)):
        data_type = "binary"
        byte_length = len(payload)
        try:
            text = payload.decode("utf-8", errors="replace")
        except Exception:
            text = repr(payload[:100])
        preview = truncate_preview(text, max_preview)
        return preview, data_type, byte_length

    if isinstance(payload, str):
        data_type = "text"
        byte_length = len(payload.encode("utf-8"))
        preview = truncate_preview(payload, max_preview)
        return preview, data_type, byte_length

    # Fallback for other types
    text = str(payload)
    data_type = "text"
    byte_length = len(text.encode("utf-8"))
    preview = truncate_preview(text, max_preview)
    return preview, data_type, byte_length


def truncate_preview(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, appending a marker if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


def redact_sensitive_preview(preview: str) -> str:
    """Redact potentially sensitive tokens from frame previews.

    Replaces values that look like auth tokens, API keys, or session IDs
    with a redaction marker. This is a best-effort heuristic.
    """
    import re
    # Redact long hex strings (session IDs, tokens)
    preview = re.sub(r"\b[0-9a-f]{32,}\b", "[redacted_hex]", preview, flags=re.I)
    # Redact Bearer tokens
    preview = re.sub(
        r"(Bearer\s+)\S{20,}",
        r"\1[redacted_token]",
        preview,
        flags=re.I,
    )
    # Redact key=value patterns with long values
    preview = re.sub(
        r"((?:api_key|apikey|token|secret|password|session_id|sid)=)\S{20,}",
        r"\1[redacted]",
        preview,
        flags=re.I,
    )
    return preview


# ---------------------------------------------------------------------------
# Shared-state observer (used by tests and real browser)
# ---------------------------------------------------------------------------

class _WebSocketCollector:
    """Collects WebSocket frames via Playwright event callbacks.

    This class holds mutable state so that frame callbacks can accumulate
    frames across multiple WebSocket connections during a page load.
    """

    def __init__(
        self,
        max_frames: int = DEFAULT_MAX_FRAMES,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        max_frame_preview: int = DEFAULT_MAX_FRAME_PREVIEW,
        redact: bool = True,
    ) -> None:
        self.max_frames = max_frames
        self.max_connections = max_connections
        self.max_frame_preview = max_frame_preview
        self.redact = redact
        self.connections: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.total_frames = 0

    def on_websocket(self, ws: Any) -> None:
        if len(self.connections) >= self.max_connections:
            return

        ws_url = str(getattr(ws, "url", ""))
        entry: dict[str, Any] = {
            "url": ws_url,
            "frames": [],
            "error": "",
            "is_alive": True,
        }
        self.connections.append(entry)

        def on_frame_sent(payload: Any) -> None:
            self._record_frame(entry, FRAME_DIRECTION_SENT, payload)

        def on_frame_received(payload: Any) -> None:
            self._record_frame(entry, FRAME_DIRECTION_RECEIVED, payload)

        def on_close() -> None:
            entry["is_alive"] = False

        try:
            ws.on("framesent", on_frame_sent)
            ws.on("framereceived", on_frame_received)
            ws.on("close", on_close)
        except Exception as exc:
            entry["error"] = str(exc)
            self.errors.append(f"ws_event_bind_error:{ws_url}:{exc}")

    def _record_frame(self, entry: dict[str, Any], direction: str, payload: Any) -> None:
        if self.total_frames >= self.max_frames:
            return
        preview, data_type, byte_length = normalize_frame_payload(
            payload, max_preview=self.max_frame_preview,
        )
        if self.redact:
            preview = redact_sensitive_preview(preview)
        entry["frames"].append(WebSocketFrame(
            direction=direction,
            data_type=data_type,
            preview=preview,
            byte_length=byte_length,
        ))
        self.total_frames += 1

    def build_connections(self) -> list[WebSocketConnection]:
        result: list[WebSocketConnection] = []
        for entry in self.connections:
            result.append(WebSocketConnection(
                url=entry["url"],
                is_alive=entry["is_alive"],
                frame_count=len(entry["frames"]),
                frames=tuple(entry["frames"]),
                error=entry["error"],
            ))
        return result


def observe_websocket(
    page_url: str,
    wait_ms: int = 3000,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_connections: int = DEFAULT_MAX_CONNECTIONS,
    max_frame_preview: int = DEFAULT_MAX_FRAME_PREVIEW,
    redact: bool = True,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 30000,
    wait_selector: str = "",
) -> WebSocketObservationResult:
    """Observe WebSocket connections on a page.

    Uses ``_WebSocketCollector`` to accumulate frames across connections
    during the page load and wait period.
    """
    if sync_playwright is None:
        return WebSocketObservationResult(
            page_url=page_url,
            status="failed",
            error="playwright is not installed",
        )

    collector = _WebSocketCollector(
        max_frames=max_frames,
        max_connections=max_connections,
        max_frame_preview=max_frame_preview,
        redact=redact,
    )

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page()
                page.on("websocket", collector.on_websocket)
                page.goto(page_url, wait_until=wait_until, timeout=timeout_ms)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                if wait_ms > 0:
                    page.wait_for_timeout(wait_ms)

                connections = collector.build_connections()
                return WebSocketObservationResult(
                    page_url=page_url,
                    connections=connections,
                    total_frames=collector.total_frames,
                    errors=collector.errors,
                )
            finally:
                browser.close()
    except Exception as exc:
        connections = collector.build_connections()
        return WebSocketObservationResult(
            page_url=page_url,
            status="failed",
            error=str(exc),
            connections=connections,
            total_frames=collector.total_frames,
            errors=collector.errors,
        )


# ---------------------------------------------------------------------------
# Summary helper
# ---------------------------------------------------------------------------

def build_ws_summary(result: WebSocketObservationResult) -> dict[str, Any]:
    """Build a compact summary dict from an observation result."""
    all_urls = [c.url for c in result.connections]
    sent_count = 0
    received_count = 0
    text_count = 0
    binary_count = 0
    total_bytes = 0
    for conn in result.connections:
        for f in conn.frames:
            if f.direction == FRAME_DIRECTION_SENT:
                sent_count += 1
            else:
                received_count += 1
            if f.data_type == "text":
                text_count += 1
            else:
                binary_count += 1
            total_bytes += f.byte_length

    return {
        "page_url": result.page_url,
        "status": result.status,
        "connection_count": len(result.connections),
        "ws_urls": all_urls,
        "total_frames": result.total_frames,
        "sent_frames": sent_count,
        "received_frames": received_count,
        "text_frames": text_count,
        "binary_frames": binary_count,
        "total_bytes": total_bytes,
        "error_count": len(result.errors),
    }
