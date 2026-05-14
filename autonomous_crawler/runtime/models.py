"""Runtime protocol data models.

These dataclasses are intentionally engine-neutral.  They form the contract
between CLM's Agent workflow and concrete crawler backends, including the
Scrapling-first runtime adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autonomous_crawler.tools.proxy_manager import redact_proxy_url
from autonomous_crawler.tools.proxy_trace import redact_error_message
from autonomous_crawler.tools.session_profile import redact_headers, redact_storage_state_path


RUNTIME_MODES = {"static", "dynamic", "protected", "spider"}
HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
SELECTOR_TYPES = {"css", "xpath", "text", "regex"}


@dataclass(frozen=True)
class RuntimeEvent:
    """A structured runtime event emitted by a crawler backend."""

    type: str
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RuntimeEvent":
        payload = payload or {}
        return cls(
            type=_clean_string(payload.get("type"), "event", max_len=80),
            message=_clean_string(payload.get("message"), "", max_len=500),
            data=_safe_dict(payload.get("data")),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type}
        if self.message:
            result["message"] = self.message
        if self.data:
            result["data"] = _redact_mapping(self.data)
        return result


@dataclass(frozen=True)
class RuntimeArtifact:
    """Runtime artifact reference, such as HTML, screenshot, HAR, or trace."""

    kind: str
    path: str = ""
    url: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RuntimeArtifact":
        payload = payload or {}
        return cls(
            kind=_clean_string(payload.get("kind"), "artifact", max_len=80),
            path=_clean_string(payload.get("path"), "", max_len=800),
            url=_clean_string(payload.get("url"), "", max_len=1000),
            meta=_safe_dict(payload.get("meta")),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind}
        if self.path:
            result["path"] = redact_storage_state_path(self.path)
        if self.url:
            result["url"] = self.url
        if self.meta:
            result["meta"] = _redact_mapping(self.meta)
        return result


@dataclass(frozen=True)
class RuntimeProxyTrace:
    """Credential-safe proxy selection snapshot for runtime responses."""

    selected: bool = False
    proxy: str = ""
    source: str = "none"
    provider: str = ""
    strategy: str = ""
    health: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RuntimeProxyTrace":
        payload = payload or {}
        errors = payload.get("errors") or ()
        if isinstance(errors, str):
            errors = (errors,)
        return cls(
            selected=bool(payload.get("selected", False)),
            proxy=redact_proxy_url(str(payload.get("proxy") or "")),
            source=_clean_string(payload.get("source"), "none", max_len=80),
            provider=_clean_string(payload.get("provider"), "", max_len=80),
            strategy=_clean_string(payload.get("strategy"), "", max_len=80),
            health=_safe_dict(payload.get("health")),
            errors=tuple(redact_error_message(str(item)) for item in errors),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "selected": self.selected,
            "proxy": redact_proxy_url(self.proxy),
            "source": self.source,
        }
        if self.provider:
            result["provider"] = self.provider
        if self.strategy:
            result["strategy"] = self.strategy
        if self.health:
            result["health"] = _redact_mapping(self.health)
        if self.errors:
            result["errors"] = [redact_error_message(item) for item in self.errors]
        return result


@dataclass(frozen=True)
class RuntimeSelectorRequest:
    """Selector extraction request for parser runtimes."""

    name: str
    selector: str
    selector_type: str = "css"
    attribute: str = ""
    many: bool = True
    required: bool = False

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeSelectorRequest":
        selector_type = _clean_string(payload.get("selector_type"), "css", max_len=20)
        if selector_type not in SELECTOR_TYPES:
            selector_type = "css"
        return cls(
            name=_clean_string(payload.get("name"), "field", max_len=80),
            selector=_clean_string(payload.get("selector"), "", max_len=500),
            selector_type=selector_type,
            attribute=_clean_string(payload.get("attribute"), "", max_len=80),
            many=bool(payload.get("many", True)),
            required=bool(payload.get("required", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "selector": self.selector,
            "selector_type": self.selector_type,
            "attribute": self.attribute,
            "many": self.many,
            "required": self.required,
        }


@dataclass(frozen=True)
class RuntimeSelectorResult:
    """Selector extraction result from parser runtimes."""

    name: str
    values: list[Any] = field(default_factory=list)
    selector: str = ""
    selector_type: str = "css"
    matched: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "RuntimeSelectorResult":
        payload = payload or {}
        values = payload.get("values") or []
        if not isinstance(values, list):
            values = [values]
        return cls(
            name=_clean_string(payload.get("name"), "field", max_len=80),
            values=values,
            selector=_clean_string(payload.get("selector"), "", max_len=500),
            selector_type=_clean_string(payload.get("selector_type"), "css", max_len=20),
            matched=_bounded_int(payload.get("matched"), default=len(values), minimum=0, maximum=1_000_000),
            error=redact_error_message(_clean_string(payload.get("error"), "", max_len=500)),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "values": list(self.values),
            "selector": self.selector,
            "selector_type": self.selector_type,
            "matched": self.matched,
        }
        if self.error:
            result["error"] = redact_error_message(self.error)
        return result


@dataclass(frozen=True)
class RuntimeRequest:
    """Unified request model for crawler runtime backends."""

    url: str
    method: str = "GET"
    mode: str = "static"
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    data: Any = None
    json: Any = None
    selectors: list[RuntimeSelectorRequest] = field(default_factory=list)
    selector_config: dict[str, Any] = field(default_factory=dict)
    browser_config: dict[str, Any] = field(default_factory=dict)
    session_profile: dict[str, Any] = field(default_factory=dict)
    proxy_config: dict[str, Any] = field(default_factory=dict)
    capture_xhr: str = ""
    wait_selector: str = ""
    wait_until: str = "domcontentloaded"
    timeout_ms: int = 30000
    max_items: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RuntimeRequest":
        mode = _clean_string(payload.get("mode"), "static", max_len=20)
        if mode not in RUNTIME_MODES:
            mode = "static"
        method = _clean_string(payload.get("method"), "GET", max_len=10).upper()
        if method not in HTTP_METHODS:
            method = "GET"
        selectors = [
            item if isinstance(item, RuntimeSelectorRequest) else RuntimeSelectorRequest.from_dict(item)
            for item in (payload.get("selectors") or [])
            if isinstance(item, (RuntimeSelectorRequest, dict))
        ]
        return cls(
            url=_clean_string(payload.get("url"), "", max_len=2000),
            method=method,
            mode=mode,
            headers=_string_dict(payload.get("headers")),
            cookies=_string_dict(payload.get("cookies")),
            params=_safe_dict(payload.get("params")),
            data=payload.get("data"),
            json=payload.get("json"),
            selectors=selectors,
            selector_config=_safe_dict(payload.get("selector_config")),
            browser_config=_safe_dict(payload.get("browser_config")),
            session_profile=_safe_dict(payload.get("session_profile")),
            proxy_config=_safe_dict(payload.get("proxy_config")),
            capture_xhr=_clean_string(payload.get("capture_xhr"), "", max_len=500),
            wait_selector=_clean_string(payload.get("wait_selector"), "", max_len=500),
            wait_until=_clean_string(payload.get("wait_until"), "domcontentloaded", max_len=30),
            timeout_ms=_bounded_int(payload.get("timeout_ms"), default=30000, minimum=1000, maximum=300000),
            max_items=_bounded_int(payload.get("max_items"), default=0, minimum=0, maximum=10_000_000),
            meta=_safe_dict(payload.get("meta")),
        )

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "mode": self.mode,
            "headers": redact_headers(self.headers),
            "cookies": {key: "[redacted]" for key in self.cookies},
            "params": _redact_mapping(self.params),
            "selectors": [selector.to_dict() for selector in self.selectors],
            "selector_config": _redact_mapping(self.selector_config),
            "browser_config": _redact_mapping(self.browser_config),
            "session_profile": _redact_mapping(self.session_profile),
            "proxy_config": _redact_mapping(self.proxy_config),
            "capture_xhr": self.capture_xhr,
            "wait_selector": self.wait_selector,
            "wait_until": self.wait_until,
            "timeout_ms": self.timeout_ms,
            "max_items": self.max_items,
            "meta": _redact_mapping(self.meta),
        }


@dataclass(frozen=True)
class RuntimeResponse:
    """Unified response model returned by crawler runtime backends."""

    ok: bool
    final_url: str = ""
    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    html: str = ""
    text: str = ""
    captured_xhr: list[dict[str, Any]] = field(default_factory=list)
    selector_results: list[RuntimeSelectorResult] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[RuntimeArtifact] = field(default_factory=list)
    proxy_trace: RuntimeProxyTrace = field(default_factory=RuntimeProxyTrace)
    runtime_events: list[RuntimeEvent] = field(default_factory=list)
    engine_result: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @classmethod
    def failure(
        cls,
        *,
        final_url: str = "",
        status_code: int = 0,
        error: str,
        engine: str = "",
        events: list[RuntimeEvent] | None = None,
        proxy_trace: RuntimeProxyTrace | dict[str, Any] | None = None,
    ) -> "RuntimeResponse":
        trace = proxy_trace if isinstance(proxy_trace, RuntimeProxyTrace) else RuntimeProxyTrace.from_dict(proxy_trace)
        engine_result = {"engine": engine} if engine else {}
        return cls(
            ok=False,
            final_url=final_url,
            status_code=status_code,
            proxy_trace=trace,
            runtime_events=events or [],
            engine_result=engine_result,
            error=redact_error_message(error),
        )

    def to_dict(self, *, include_body: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "ok": self.ok,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "headers": redact_headers(self.headers),
            "cookies": {key: "[redacted]" for key in self.cookies},
            "html": self.html,
            "text": self.text,
            "captured_xhr": [_redact_mapping(item) for item in self.captured_xhr],
            "selector_results": [item.to_dict() for item in self.selector_results],
            "items": [_redact_mapping(item) for item in self.items],
            "artifacts": [item.to_dict() for item in self.artifacts],
            "proxy_trace": self.proxy_trace.to_dict(),
            "runtime_events": [item.to_dict() for item in self.runtime_events],
            "engine_result": _redact_mapping(self.engine_result),
        }
        if include_body:
            result["body"] = self.body.decode("utf-8", errors="replace")
        if self.error:
            result["error"] = redact_error_message(self.error)
        return result


def _clean_string(value: Any, default: str, *, max_len: int) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    return text[:max_len]


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(val) for key, val in value.items()}


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _redact_mapping(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, val in value.items():
        lowered = str(key).lower()
        if lowered in {"authorization", "cookie", "x-api-key", "x-auth-token", "password", "token", "secret"}:
            result[str(key)] = "[redacted]"
        elif "proxy" in lowered and isinstance(val, str):
            result[str(key)] = redact_proxy_url(val)
        elif "storage_state_path" == lowered and isinstance(val, str):
            result[str(key)] = redact_storage_state_path(val)
        elif isinstance(val, dict):
            result[str(key)] = _redact_mapping(val)
        elif isinstance(val, list):
            result[str(key)] = [_redact_mapping(item) if isinstance(item, dict) else item for item in val]
        elif isinstance(val, str):
            result[str(key)] = redact_error_message(val)
        else:
            result[str(key)] = val
    return result
