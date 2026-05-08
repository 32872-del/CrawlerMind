"""Fetch quality scoring and mode escalation policy.

This is the local CLM equivalent of a lightweight ``fetch_best_page``.  It
tries permitted fetch modes, scores returned HTML, and records why a mode was
selected or skipped.  It does not bypass challenges; challenge pages are scored
low and surfaced as diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import httpx
from bs4 import BeautifulSoup

from .access_diagnostics import diagnose_access
from .browser_fetch import fetch_rendered_html


FetchFn = Callable[[str, dict[str, str] | None], "FetchAttempt"]


@dataclass
class FetchAttempt:
    mode: str
    url: str
    html: str = ""
    status_code: int | None = None
    error: str = ""
    score: int = 0
    reasons: list[str] | None = None
    diagnostics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "url": self.url,
            "status_code": self.status_code,
            "error": self.error,
            "html_chars": len(self.html or ""),
            "score": self.score,
            "reasons": list(self.reasons or []),
            "diagnostics": self.diagnostics or {},
        }


@dataclass
class BestFetchResult:
    url: str
    html: str
    status_code: int | None
    mode: str
    score: int
    attempts: list[FetchAttempt]
    error: str = ""

    def to_trace(self) -> dict[str, Any]:
        return {
            "selected_mode": self.mode,
            "selected_url": self.url,
            "selected_score": self.score,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "error": self.error,
        }


def fetch_best_page(
    url: str,
    headers: dict[str, str] | None = None,
    modes: list[str] | None = None,
    fetchers: dict[str, FetchFn] | None = None,
    browser_options: dict[str, Any] | None = None,
) -> BestFetchResult:
    """Try fetch modes in order and return the highest-quality HTML."""
    selected_modes = modes or ["requests", "curl_cffi", "browser"]
    attempts: list[FetchAttempt] = []
    custom_fetchers = fetchers or {}
    options = browser_options or {}

    for mode in selected_modes:
        if mode == "browser" and _should_skip_browser_after_transport_errors(attempts):
            attempt = FetchAttempt(
                mode="browser",
                url=url,
                error="skipped after transport-level fetch errors",
            )
            attempt.score, attempt.reasons = score_html_attempt(attempt)
            attempts.append(attempt)
            break
        if mode == "browser":
            attempt = custom_fetchers.get(mode, _fetch_browser)(url, headers, options)  # type: ignore[arg-type]
        else:
            fetcher = custom_fetchers.get(mode, _fetch_requests if mode == "requests" else _fetch_curl_cffi)
            attempt = fetcher(url, headers)
        attempt.score, attempt.reasons = score_html_attempt(attempt)
        attempts.append(attempt)

        if _is_good_enough(attempt):
            break

    best = max(attempts, key=lambda item: item.score, default=None)
    if best is None:
        return BestFetchResult(
            url=url,
            html="",
            status_code=None,
            mode="none",
            score=0,
            attempts=[],
            error="no fetch modes attempted",
        )
    if best.error and not best.html:
        return BestFetchResult(
            url=best.url,
            html="",
            status_code=best.status_code,
            mode=best.mode,
            score=best.score,
            attempts=attempts,
            error=best.error,
        )
    return BestFetchResult(
        url=best.url,
        html=best.html,
        status_code=best.status_code,
        mode=best.mode,
        score=best.score,
        attempts=attempts,
        error="",
    )


def score_html_attempt(attempt: FetchAttempt) -> tuple[int, list[str]]:
    """Score one fetch attempt by status, body quality, and diagnostics."""
    reasons: list[str] = []
    if attempt.error:
        return -100, [f"error:{attempt.error}"]

    html = attempt.html or ""
    diagnostics = diagnose_access(html, url=attempt.url)
    attempt.diagnostics = diagnostics
    signals = diagnostics.get("signals", {})
    text_chars = int(signals.get("text_chars") or 0)
    html_chars = len(html)
    challenge = signals.get("challenge", "")
    structured = signals.get("structured_data", {})
    api_hints = signals.get("api_hints", [])
    soup = BeautifulSoup(html, "lxml")

    score = 0
    if attempt.status_code and 200 <= attempt.status_code < 300:
        score += 25
        reasons.append("status_ok")
    elif attempt.status_code in {403, 429, 503}:
        score -= 25
        reasons.append(f"block_status:{attempt.status_code}")
    elif attempt.status_code:
        score -= 10
        reasons.append(f"status:{attempt.status_code}")

    if html_chars >= 1000:
        score += 15
        reasons.append("html_size_ok")
    elif html_chars:
        score += 3
        reasons.append("html_size_small")
    else:
        score -= 40
        reasons.append("empty_html")

    if text_chars >= 500:
        score += 20
        reasons.append("text_content_ok")
    elif text_chars >= 80:
        score += 8
        reasons.append("some_text")
    else:
        score -= 8
        reasons.append("low_text")

    if soup.select("article, li, [class*=product], [class*=item], [class*=card], [class*=title]"):
        score += 12
        reasons.append("dom_candidates")

    if structured.get("json_ld_count") or structured.get("next_data") or structured.get("nuxt_data"):
        score += 10
        reasons.append("structured_data")

    if api_hints:
        score += 4
        reasons.append("api_hints")

    if challenge:
        score -= 80
        reasons.append(f"challenge:{challenge}")

    if "js_rendering_likely_required" in diagnostics.get("findings", []):
        score -= 20
        reasons.append("js_shell")

    return score, reasons


def _is_good_enough(attempt: FetchAttempt) -> bool:
    reasons = set(attempt.reasons or [])
    if attempt.score >= 60 and "js_shell" not in reasons:
        return True
    return False


def _should_skip_browser_after_transport_errors(attempts: list[FetchAttempt]) -> bool:
    """Avoid launching browser when every earlier mode failed before HTML."""
    if not attempts:
        return False
    return all(attempt.error and not attempt.html for attempt in attempts)


def _fetch_requests(url: str, headers: dict[str, str] | None = None) -> FetchAttempt:
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
            headers=headers,
        ) as client:
            response = client.get(url)
            return FetchAttempt(
                mode="requests",
                url=str(response.url),
                html=response.text,
                status_code=response.status_code,
            )
    except httpx.HTTPError as exc:
        return FetchAttempt(mode="requests", url=url, error=str(exc))


def _fetch_curl_cffi(url: str, headers: dict[str, str] | None = None) -> FetchAttempt:
    try:
        import curl_cffi.requests as curl_requests

        response = curl_requests.get(
            url,
            headers=headers,
            timeout=20,
            impersonate="chrome124",
            allow_redirects=True,
        )
        return FetchAttempt(
            mode="curl_cffi",
            url=str(response.url),
            html=response.text,
            status_code=response.status_code,
        )
    except Exception as exc:
        return FetchAttempt(mode="curl_cffi", url=url, error=str(exc))


def _fetch_browser(
    url: str,
    headers: dict[str, str] | None = None,
    options: dict[str, Any] | None = None,
) -> FetchAttempt:
    options = options or {}
    result = fetch_rendered_html(
        url=url,
        wait_selector=str(options.get("wait_selector", "")),
        wait_until=str(options.get("wait_until", "domcontentloaded")),
        timeout_ms=int(options.get("timeout_ms", 30000)),
        screenshot=bool(options.get("screenshot", False)),
    )
    if result.status == "ok":
        return FetchAttempt(
            mode="browser",
            url=result.url,
            html=result.html,
            status_code=200,
        )
    return FetchAttempt(mode="browser", url=url, error=result.error)
