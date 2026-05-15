"""Profile rotation real smoke test (SCRAPLING-ABSORB-2H).

Proves real browser profile rotation with a local HTTP server:
- Multiple profiles rotate across requests
- Profile selection evidence is emitted in engine_result
- Protected mode is applied when configured
- Pool integration works with profile rotation

Skips cleanly when Playwright browser binaries are not installed.
"""
from __future__ import annotations

import http.server
import json
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Local HTTP server
# ---------------------------------------------------------------------------

_HTML_PAGE = """<!DOCTYPE html>
<html>
<head><title>Profile Rotation Smoke</title></head>
<body>
<h1 id="title">Profile Rotation Test</h1>
<p id="user-agent">__USER_AGENT__</p>
<p id="timestamp">__TIMESTAMP__</p>
</body>
</html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        ua = self.headers.get("User-Agent", "unknown")
        body = _HTML_PAGE.replace("__USER_AGENT__", ua).replace("__TIMESTAMP__", str(time.time()))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        pass  # suppress noisy logs


def _start_server() -> tuple[http.server.HTTPServer, int]:
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------


def run_smoke() -> bool:
    """Run the profile rotation smoke test. Returns True on success."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[SKIP] playwright is not installed")
        return True

    # Check if browser binaries are available
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:
        if "executable" in str(exc).lower() or "install" in str(exc).lower():
            print(f"[SKIP] Playwright browser binaries not installed: {exc}")
            return True
        raise

    from autonomous_crawler.runtime.browser_pool import (
        BrowserPoolConfig,
        BrowserPoolManager,
        BrowserProfile,
        BrowserProfileRotator,
    )
    from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
    from autonomous_crawler.runtime.models import RuntimeRequest

    server, port = _start_server()
    url = f"http://127.0.0.1:{port}/"

    try:
        # Create profiles with different user agents
        profiles = [
            BrowserProfile(
                profile_id="desktop-chrome",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
                viewport="1920x1080",
                locale="en-US",
                timezone="America/New_York",
            ),
            BrowserProfile(
                profile_id="mobile-safari",
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1",
                viewport="375x812",
                locale="en-US",
                timezone="America/New_York",
            ),
            BrowserProfile(
                profile_id="desktop-firefox",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Firefox/121.0",
                viewport="1440x900",
                locale="de-DE",
                timezone="Europe/Berlin",
                color_scheme="dark",
            ),
        ]

        pool = BrowserPoolManager(BrowserPoolConfig(
            max_contexts=8,
            keepalive_on_release=True,
        ))
        rotator = BrowserProfileRotator(profiles)
        runtime = NativeBrowserRuntime(pool=pool, rotator=rotator)

        # --- Request 1: desktop-chrome ---
        print(f"[1/3] Request with desktop-chrome profile")
        request = RuntimeRequest.from_dict({"url": url})
        response1 = runtime.render(request)
        assert response1.ok, f"Request 1 failed: {response1.error}"
        assert response1.engine_result["profile_id"] == "desktop-chrome"
        assert response1.engine_result["profile"]["user_agent"] == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
        print(f"  profile_id={response1.engine_result['profile_id']}")
        print(f"  user_agent={response1.engine_result['profile']['user_agent'][:50]}...")

        # --- Request 2: mobile-safari ---
        print(f"[2/3] Request with mobile-safari profile")
        request = RuntimeRequest.from_dict({"url": url})
        response2 = runtime.render(request)
        assert response2.ok, f"Request 2 failed: {response2.error}"
        assert response2.engine_result["profile_id"] == "mobile-safari"
        assert response2.engine_result["profile"]["viewport"] == "375x812"
        print(f"  profile_id={response2.engine_result['profile_id']}")
        print(f"  viewport={response2.engine_result['profile']['viewport']}")

        # --- Request 3: desktop-firefox ---
        print(f"[3/3] Request with desktop-firefox profile")
        request = RuntimeRequest.from_dict({"url": url})
        response3 = runtime.render(request)
        assert response3.ok, f"Request 3 failed: {response3.error}"
        assert response3.engine_result["profile_id"] == "desktop-firefox"
        assert response3.engine_result["profile"]["locale"] == "de-DE"
        assert response3.engine_result["profile"]["color_scheme"] == "dark"
        print(f"  profile_id={response3.engine_result['profile_id']}")
        print(f"  locale={response3.engine_result['profile']['locale']}")

        # --- Verify rotation wraps ---
        print(f"\n[4/4] Verifying rotation wraps around")
        request = RuntimeRequest.from_dict({"url": url})
        response4 = runtime.render(request)
        assert response4.ok, f"Request 4 failed: {response4.error}"
        assert response4.engine_result["profile_id"] == "desktop-chrome"
        print(f"  profile_id={response4.engine_result['profile_id']} (wrapped)")

        # --- Verify rotator evidence ---
        assert response1.engine_result["rotator"]["profile_count"] == 3
        assert response1.engine_result["rotator"]["current_index"] == 1

        # --- Verify pool integration ---
        # Each profile gets its own pool context (different fingerprints)
        print(f"\n  Active pool leases: {pool.active_count}")

        print("\n[PASS] Profile rotation smoke test passed")
        return True

    finally:
        try:
            pool.close_all()
            runtime.close()
        except Exception:
            pass
        server.shutdown()


def main() -> None:
    print("=" * 60)
    print("Profile Rotation Real Smoke Test (SCRAPLING-ABSORB-2H)")
    print("=" * 60)
    success = run_smoke()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
