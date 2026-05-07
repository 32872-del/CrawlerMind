"""Playwright-based browser fetch for rendering SPA / JS-heavy pages.

This is the minimal MVP browser executor. It opens a page, waits for
domcontentloaded (or a configured wait_until), optionally waits for a CSS
selector, and returns the rendered HTML.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright, Error as PlaywrightError
except ImportError:
    sync_playwright = None  # type: ignore[assignment]
    PlaywrightError = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path(__file__).resolve().parent / "runtime" / "screenshots"


@dataclass
class BrowserFetchResult:
    url: str
    html: str
    status: str
    error: str = ""
    screenshot_path: str = ""


def fetch_rendered_html(
    url: str,
    wait_selector: str = "",
    wait_until: str = "domcontentloaded",
    timeout_ms: int = 30000,
    screenshot: bool = False,
) -> BrowserFetchResult:
    """Fetch a page using Playwright and return rendered HTML.

    Args:
        url: Target URL.
        wait_selector: Optional CSS selector to wait for after navigation.
        wait_until: Playwright load state: "domcontentloaded", "load", or "networkidle".
        timeout_ms: Navigation timeout in milliseconds.
        screenshot: If True, save a screenshot and return its path.

    Returns:
        BrowserFetchResult with rendered HTML or error details.
    """
    if sync_playwright is None:
        return BrowserFetchResult(
            url=url,
            html="",
            status="failed",
            error="playwright is not installed",
        )

    valid_wait_until = {"domcontentloaded", "load", "networkidle"}
    if wait_until not in valid_wait_until:
        wait_until = "domcontentloaded"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)

                if wait_selector:
                    page.wait_for_selector(wait_selector, timeout=timeout_ms)

                final_url = page.url
                html = page.content()

                screenshot_path = ""
                if screenshot:
                    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                    safe_name = (
                        final_url.replace("https://", "")
                        .replace("http://", "")
                        .replace("/", "_")
                        .replace("?", "_")[:80]
                    )
                    path = SCREENSHOT_DIR / f"{safe_name}.png"
                    page.screenshot(path=str(path), full_page=True)
                    screenshot_path = str(path)

                return BrowserFetchResult(
                    url=final_url,
                    html=html,
                    status="ok",
                    screenshot_path=screenshot_path,
                )
            finally:
                browser.close()
    except Exception as exc:
        logger.warning("Browser fetch failed for %s: %s", url, exc)
        return BrowserFetchResult(
            url=url,
            html="",
            status="failed",
            error=str(exc),
        )
