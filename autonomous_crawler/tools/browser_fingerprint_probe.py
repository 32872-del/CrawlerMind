"""Runtime browser fingerprint probing (CAP-4.2).

This module launches a real Playwright browser context and samples browser-side
fingerprint evidence such as ``navigator``, ``screen``, ``Intl`` timezone,
WebGL renderer, canvas hash, and a small font availability probe.

It complements ``browser_fingerprint.py``:

* ``browser_fingerprint.py`` checks whether the configured profile is internally
  consistent.
* this module checks what the browser runtime actually exposes.

The probe is evidence-only. It does not implement stealth, spoofing, CAPTCHA
solving, or challenge bypass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .browser_context import BrowserContextConfig, normalize_wait_until
from .browser_fingerprint import _is_mobile_ua

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore[assignment]


MAX_STRING_LEN = 500
MAX_FINDINGS = 50
MAX_FONTS = 30


@dataclass(frozen=True)
class RuntimeFingerprintSnapshot:
    """Normalized browser-side fingerprint sample."""

    user_agent: str = ""
    language: str = ""
    languages: list[str] = field(default_factory=list)
    platform: str = ""
    webdriver: bool | None = None
    hardware_concurrency: int | None = None
    device_memory: float | None = None
    max_touch_points: int | None = None
    cookie_enabled: bool | None = None
    do_not_track: str = ""
    timezone: str = ""
    screen: dict[str, Any] = field(default_factory=dict)
    viewport: dict[str, Any] = field(default_factory=dict)
    webgl: dict[str, Any] = field(default_factory=dict)
    canvas: dict[str, Any] = field(default_factory=dict)
    fonts: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "RuntimeFingerprintSnapshot":
        payload = payload or {}
        navigator = payload.get("navigator") if isinstance(payload.get("navigator"), dict) else {}
        screen = payload.get("screen") if isinstance(payload.get("screen"), dict) else {}
        viewport = payload.get("viewport") if isinstance(payload.get("viewport"), dict) else {}
        webgl = payload.get("webgl") if isinstance(payload.get("webgl"), dict) else {}
        canvas = payload.get("canvas") if isinstance(payload.get("canvas"), dict) else {}
        fonts = payload.get("fonts") if isinstance(payload.get("fonts"), list) else []
        return cls(
            user_agent=_clean_string(navigator.get("userAgent")),
            language=_clean_string(navigator.get("language")),
            languages=_clean_string_list(navigator.get("languages")),
            platform=_clean_string(navigator.get("platform")),
            webdriver=_optional_bool(navigator.get("webdriver")),
            hardware_concurrency=_optional_int(navigator.get("hardwareConcurrency")),
            device_memory=_optional_float(navigator.get("deviceMemory")),
            max_touch_points=_optional_int(navigator.get("maxTouchPoints")),
            cookie_enabled=_optional_bool(navigator.get("cookieEnabled")),
            do_not_track=_clean_string(navigator.get("doNotTrack")),
            timezone=_clean_string(payload.get("timezone")),
            screen=_safe_dict(screen),
            viewport=_safe_dict(viewport),
            webgl=_safe_dict(webgl),
            canvas=_safe_dict(canvas),
            fonts=_clean_string_list(fonts, limit=MAX_FONTS),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_agent": self.user_agent,
            "language": self.language,
            "languages": list(self.languages),
            "platform": self.platform,
            "webdriver": self.webdriver,
            "hardware_concurrency": self.hardware_concurrency,
            "device_memory": self.device_memory,
            "max_touch_points": self.max_touch_points,
            "cookie_enabled": self.cookie_enabled,
            "do_not_track": self.do_not_track,
            "timezone": self.timezone,
            "screen": dict(self.screen),
            "viewport": dict(self.viewport),
            "webgl": dict(self.webgl),
            "canvas": dict(self.canvas),
            "fonts": list(self.fonts),
        }


@dataclass(frozen=True)
class RuntimeFingerprintFinding:
    """A browser-runtime fingerprint finding."""

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
class RuntimeFingerprintProbeResult:
    """Serializable result for runtime fingerprint probing."""

    url: str
    final_url: str = ""
    status: str = "ok"
    error: str = ""
    snapshot: RuntimeFingerprintSnapshot = field(default_factory=RuntimeFingerprintSnapshot)
    findings: list[RuntimeFingerprintFinding] = field(default_factory=list)
    risk_level: str = "low"
    recommendations: list[str] = field(default_factory=list)
    browser_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "error": self.error,
            "snapshot": self.snapshot.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "risk_level": self.risk_level,
            "recommendations": list(self.recommendations),
            "browser_context": dict(self.browser_context),
        }


def probe_browser_fingerprint(
    url: str = "about:blank",
    browser_context: BrowserContextConfig | dict[str, Any] | None = None,
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 30000,
    wait_selector: str = "",
    render_time_ms: int = 0,
    headers: dict[str, str] | None = None,
    storage_state_path: str = "",
    proxy_url: str = "",
) -> RuntimeFingerprintProbeResult:
    """Launch a browser and collect runtime fingerprint evidence."""
    if sync_playwright is None:
        return RuntimeFingerprintProbeResult(
            url=url,
            status="failed",
            error="playwright is not installed",
        )

    context_config = (
        browser_context
        if isinstance(browser_context, BrowserContextConfig)
        else BrowserContextConfig.from_dict(browser_context)
    )
    context_config = context_config.with_runtime_overrides(
        headers=headers,
        storage_state_path=storage_state_path,
        proxy_url=proxy_url,
    )
    wait_until = normalize_wait_until(wait_until, default="domcontentloaded")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**context_config.launch_options())
            try:
                context = browser.new_context(**context_config.context_options())
                page = context.new_page()
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)
                if render_time_ms > 0:
                    page.wait_for_timeout(render_time_ms)

                raw_snapshot = page.evaluate(_FINGERPRINT_PROBE_SCRIPT)
                snapshot = RuntimeFingerprintSnapshot.from_payload(raw_snapshot)
                findings = analyze_runtime_fingerprint(snapshot, context_config)
                return RuntimeFingerprintProbeResult(
                    url=url,
                    final_url=str(getattr(page, "url", url) or url),
                    snapshot=snapshot,
                    findings=findings,
                    risk_level=_compute_risk_level(findings),
                    recommendations=_build_recommendations(findings),
                    browser_context=context_config.to_safe_dict(),
                )
            finally:
                browser.close()
    except Exception as exc:
        return RuntimeFingerprintProbeResult(
            url=url,
            status="failed",
            error=str(exc),
            browser_context=context_config.to_safe_dict(),
        )


def analyze_runtime_fingerprint(
    snapshot: RuntimeFingerprintSnapshot | dict[str, Any] | None,
    expected_config: BrowserContextConfig | dict[str, Any] | None = None,
) -> list[RuntimeFingerprintFinding]:
    """Analyze a runtime snapshot against expected browser context settings."""
    if not isinstance(snapshot, RuntimeFingerprintSnapshot):
        snapshot = RuntimeFingerprintSnapshot.from_payload(snapshot)
    config = BrowserContextConfig.from_dict(expected_config)

    findings: list[RuntimeFingerprintFinding] = []
    findings.extend(_check_webdriver(snapshot))
    findings.extend(_check_expected_config_mismatch(snapshot, config))
    findings.extend(_check_runtime_shape(snapshot))
    findings.extend(_check_mobile_consistency(snapshot))
    findings.extend(_check_webgl_canvas(snapshot))
    return findings[:MAX_FINDINGS]


def _check_webdriver(snapshot: RuntimeFingerprintSnapshot) -> list[RuntimeFingerprintFinding]:
    if snapshot.webdriver is True:
        return [
            RuntimeFingerprintFinding(
                code="webdriver_exposed",
                severity="high",
                message="navigator.webdriver is true; many bot defenses treat this as automation evidence.",
            )
        ]
    return []


def _check_expected_config_mismatch(
    snapshot: RuntimeFingerprintSnapshot,
    config: BrowserContextConfig,
) -> list[RuntimeFingerprintFinding]:
    findings: list[RuntimeFingerprintFinding] = []

    if snapshot.user_agent and snapshot.user_agent != config.user_agent:
        findings.append(RuntimeFingerprintFinding(
            code="runtime_user_agent_mismatch",
            severity="high",
            message="Runtime userAgent does not match configured browser context user_agent.",
        ))

    if snapshot.language and config.locale:
        expected_lang = config.locale.split("-")[0].lower()
        actual_lang = snapshot.language.split("-")[0].lower()
        if expected_lang and actual_lang and expected_lang != actual_lang:
            findings.append(RuntimeFingerprintFinding(
                code="runtime_locale_mismatch",
                severity="medium",
                message=(
                    f"Runtime navigator.language '{snapshot.language}' does not match "
                    f"configured locale '{config.locale}'."
                ),
            ))

    if snapshot.timezone and config.timezone_id and snapshot.timezone != config.timezone_id:
        findings.append(RuntimeFingerprintFinding(
            code="runtime_timezone_mismatch",
            severity="medium",
            message=(
                f"Runtime timezone '{snapshot.timezone}' does not match configured "
                f"timezone_id '{config.timezone_id}'."
            ),
        ))

    width = _optional_int(snapshot.viewport.get("innerWidth"))
    height = _optional_int(snapshot.viewport.get("innerHeight"))
    if width and height:
        width_delta = abs(width - config.viewport.width)
        height_delta = abs(height - config.viewport.height)
        if width_delta > 80 or height_delta > 120:
            findings.append(RuntimeFingerprintFinding(
                code="runtime_viewport_mismatch",
                severity="medium",
                message=(
                    f"Runtime viewport is {width}x{height}, configured viewport is "
                    f"{config.viewport.width}x{config.viewport.height}."
                ),
            ))

    return findings


def _check_runtime_shape(snapshot: RuntimeFingerprintSnapshot) -> list[RuntimeFingerprintFinding]:
    findings: list[RuntimeFingerprintFinding] = []

    if snapshot.hardware_concurrency is not None and snapshot.hardware_concurrency <= 0:
        findings.append(RuntimeFingerprintFinding(
            code="invalid_hardware_concurrency",
            severity="medium",
            message="navigator.hardwareConcurrency is zero or negative.",
        ))

    dpr = _optional_float(snapshot.viewport.get("devicePixelRatio"))
    if dpr is not None and (dpr < 0.5 or dpr > 8):
        findings.append(RuntimeFingerprintFinding(
            code="unusual_device_pixel_ratio",
            severity="low",
            message=f"devicePixelRatio {dpr} is outside a typical browser range.",
        ))

    screen_width = _optional_int(snapshot.screen.get("width"))
    screen_height = _optional_int(snapshot.screen.get("height"))
    if screen_width is not None and screen_height is not None:
        if screen_width <= 0 or screen_height <= 0:
            findings.append(RuntimeFingerprintFinding(
                code="invalid_screen_size",
                severity="medium",
                message="screen.width or screen.height is zero or negative.",
            ))

    return findings


def _check_mobile_consistency(snapshot: RuntimeFingerprintSnapshot) -> list[RuntimeFingerprintFinding]:
    findings: list[RuntimeFingerprintFinding] = []
    if not snapshot.user_agent:
        return findings

    is_mobile = _is_mobile_ua(snapshot.user_agent)
    touch_points = snapshot.max_touch_points
    viewport_width = _optional_int(snapshot.viewport.get("innerWidth"))

    if is_mobile and touch_points == 0:
        findings.append(RuntimeFingerprintFinding(
            code="mobile_ua_without_touch",
            severity="high",
            message="Mobile userAgent is exposed but navigator.maxTouchPoints is 0.",
        ))

    if is_mobile and viewport_width and viewport_width > 1024:
        findings.append(RuntimeFingerprintFinding(
            code="mobile_ua_desktop_runtime_viewport",
            severity="high",
            message=f"Mobile userAgent is exposed with desktop-like viewport width {viewport_width}.",
        ))

    if not is_mobile and touch_points and touch_points > 5:
        findings.append(RuntimeFingerprintFinding(
            code="desktop_ua_many_touch_points",
            severity="low",
            message="Desktop userAgent exposes many touch points; verify this is intentional.",
        ))

    return findings


def _check_webgl_canvas(snapshot: RuntimeFingerprintSnapshot) -> list[RuntimeFingerprintFinding]:
    findings: list[RuntimeFingerprintFinding] = []

    if snapshot.webgl.get("supported") is False:
        findings.append(RuntimeFingerprintFinding(
            code="webgl_unavailable",
            severity="medium",
            message="WebGL is unavailable in the runtime browser context.",
        ))
    elif snapshot.webgl.get("supported") is True:
        renderer = str(snapshot.webgl.get("renderer") or "").lower()
        vendor = str(snapshot.webgl.get("vendor") or "").lower()
        if "swiftshader" in renderer or "llvmpipe" in renderer or "software" in renderer:
            findings.append(RuntimeFingerprintFinding(
                code="software_webgl_renderer",
                severity="medium",
                message="WebGL renderer appears to be software-based; this can increase automation risk.",
            ))
        if not renderer or not vendor:
            findings.append(RuntimeFingerprintFinding(
                code="incomplete_webgl_identity",
                severity="low",
                message="WebGL is supported but vendor or renderer is missing.",
            ))

    if snapshot.canvas.get("supported") is False:
        findings.append(RuntimeFingerprintFinding(
            code="canvas_unavailable",
            severity="low",
            message="Canvas fingerprint probe could not run in this browser context.",
        ))

    return findings


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _compute_risk_level(findings: list[RuntimeFingerprintFinding]) -> str:
    if not findings:
        return "low"
    return max((f.severity for f in findings), key=lambda s: _RISK_ORDER.get(s, 0))


def _build_recommendations(findings: list[RuntimeFingerprintFinding]) -> list[str]:
    recommendations: list[str] = []
    codes = {finding.code for finding in findings}

    if "webdriver_exposed" in codes:
        recommendations.append("Investigate browser launch/runtime settings; navigator.webdriver should not be exposed for high-risk targets.")
    if any(code.startswith("runtime_") for code in codes):
        recommendations.append("Compare configured browser context with runtime evidence and keep userAgent, locale, timezone, and viewport aligned.")
    if "mobile_ua_without_touch" in codes or "mobile_ua_desktop_runtime_viewport" in codes:
        recommendations.append("Use a coherent mobile profile: mobile viewport, touch support, locale/timezone, and matching userAgent.")
    if "software_webgl_renderer" in codes or "webgl_unavailable" in codes:
        recommendations.append("Treat WebGL evidence as a risk signal; consider a different browser environment for browser-protected targets.")
    if "canvas_unavailable" in codes:
        recommendations.append("Verify JavaScript/canvas availability before relying on browser-mode extraction.")

    return recommendations


def _clean_string(value: Any, default: str = "", *, max_len: int = MAX_STRING_LEN) -> str:
    text = str(value if value is not None else default).strip()
    return text[:max_len]


def _clean_string_list(value: Any, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[:limit]:
        text = _clean_string(item)
        if text:
            result.append(text)
    return result


def _safe_dict(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, val in value.items():
        clean_key = _clean_string(key, max_len=100)
        if isinstance(val, (int, float, bool)) or val is None:
            result[clean_key] = val
        else:
            result[clean_key] = _clean_string(val)
    return result


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_FINGERPRINT_PROBE_SCRIPT = r"""() => {
  const safe = (fn, fallback) => {
    try { return fn(); } catch (e) { return fallback; }
  };

  const simpleHash = (text) => {
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0;
    }
    return String(hash >>> 0);
  };

  const webglInfo = safe(() => {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    if (!gl) return { supported: false };
    const dbg = gl.getExtension("WEBGL_debug_renderer_info");
    return {
      supported: true,
      vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
      renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
    };
  }, { supported: false });

  const canvasInfo = safe(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 240;
    canvas.height = 60;
    const ctx = canvas.getContext("2d");
    if (!ctx) return { supported: false };
    ctx.textBaseline = "top";
    ctx.font = "16px Arial";
    ctx.fillStyle = "#f60";
    ctx.fillRect(0, 0, 240, 60);
    ctx.fillStyle = "#069";
    ctx.fillText("CLM fingerprint probe 0123456789", 4, 8);
    const data = canvas.toDataURL();
    return { supported: true, hash: simpleHash(data), dataUrlLength: data.length };
  }, { supported: false });

  const detectFonts = safe(() => {
    const fonts = ["Arial", "Times New Roman", "Courier New", "Segoe UI", "Roboto", "Noto Sans", "Noto Sans CJK SC"];
    const baseFonts = ["monospace", "sans-serif", "serif"];
    const sample = "mmmmmmmmmmlli";
    const size = "72px";
    const span = document.createElement("span");
    span.style.position = "absolute";
    span.style.left = "-9999px";
    span.style.fontSize = size;
    span.textContent = sample;
    document.body.appendChild(span);
    const base = {};
    for (const baseFont of baseFonts) {
      span.style.fontFamily = baseFont;
      base[baseFont] = `${span.offsetWidth}:${span.offsetHeight}`;
    }
    const detected = [];
    for (const font of fonts) {
      let matched = false;
      for (const baseFont of baseFonts) {
        span.style.fontFamily = `"${font}",${baseFont}`;
        if (`${span.offsetWidth}:${span.offsetHeight}` !== base[baseFont]) {
          matched = true;
        }
      }
      if (matched) detected.push(font);
    }
    span.remove();
    return detected;
  }, []);

  return {
    navigator: {
      userAgent: navigator.userAgent,
      language: navigator.language,
      languages: Array.from(navigator.languages || []),
      platform: navigator.platform,
      webdriver: navigator.webdriver,
      hardwareConcurrency: navigator.hardwareConcurrency,
      deviceMemory: navigator.deviceMemory,
      maxTouchPoints: navigator.maxTouchPoints,
      cookieEnabled: navigator.cookieEnabled,
      doNotTrack: navigator.doNotTrack,
    },
    timezone: safe(() => Intl.DateTimeFormat().resolvedOptions().timeZone, ""),
    screen: {
      width: screen.width,
      height: screen.height,
      availWidth: screen.availWidth,
      availHeight: screen.availHeight,
      colorDepth: screen.colorDepth,
      pixelDepth: screen.pixelDepth,
    },
    viewport: {
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight,
      outerWidth: window.outerWidth,
      outerHeight: window.outerHeight,
      devicePixelRatio: window.devicePixelRatio,
    },
    webgl: webglInfo,
    canvas: canvasInfo,
    fonts: detectFonts,
  };
}"""
