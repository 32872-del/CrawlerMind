"""Browser pool real smoke test (SCRAPLING-ABSORB-2G).

Proves real Playwright context reuse with a local HTTP server:
- Two sequential requests with the same pool_id reuse the same context
- pool_request_count goes from 1 to 2
- Pool events are recorded

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
<head><title>Pool Smoke Test</title></head>
<body>
<h1 id="title">Browser Pool Smoke</h1>
<p>Timestamp: __TIMESTAMP__</p>
</body>
</html>"""


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = _HTML_PAGE.replace("__TIMESTAMP__", str(time.time()))
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
    """Run the browser pool smoke test. Returns True on success."""
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

    from autonomous_crawler.runtime.browser_pool import BrowserPoolConfig, BrowserPoolManager
    from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
    from autonomous_crawler.runtime.models import RuntimeRequest

    server, port = _start_server()
    url = f"http://127.0.0.1:{port}/"

    try:
        pool = BrowserPoolManager(BrowserPoolConfig(
            max_contexts=4,
            max_requests_per_context=50,
            keepalive_on_release=True,
        ))
        runtime = NativeBrowserRuntime(pool=pool)

        request = RuntimeRequest.from_dict({
            "url": url,
            "browser_config": {"pool_id": "smoke-profile"},
        })

        # --- Request 1: acquire new context ---
        print(f"[1/2] First request to {url}")
        response1 = runtime.render(request)
        assert response1.ok, f"First request failed: {response1.error}"
        assert response1.engine_result["pool_id"] == "smoke-profile"
        assert response1.engine_result["pool_request_count"] == 1, (
            f"Expected pool_request_count=1, got {response1.engine_result['pool_request_count']}"
        )

        pool_acquire_events = [e for e in response1.runtime_events if e.type == "pool_acquire"]
        pool_release_events = [e for e in response1.runtime_events if e.type == "pool_release"]
        assert len(pool_acquire_events) == 1, f"Expected 1 pool_acquire event, got {len(pool_acquire_events)}"
        assert len(pool_release_events) == 1, f"Expected 1 pool_release event, got {len(pool_release_events)}"
        print(f"  pool_request_count={response1.engine_result['pool_request_count']}")
        print(f"  pool_acquire event: {pool_acquire_events[0].data}")
        print(f"  pool_release event: {pool_release_events[0].data}")

        # --- Request 2: reuse existing context ---
        print(f"[2/2] Second request to {url}")
        response2 = runtime.render(request)
        assert response2.ok, f"Second request failed: {response2.error}"
        assert response2.engine_result["pool_request_count"] == 2, (
            f"Expected pool_request_count=2, got {response2.engine_result['pool_request_count']}"
        )

        pool_reuse_events = [e for e in response2.runtime_events if e.type == "pool_reuse"]
        assert len(pool_reuse_events) == 1, f"Expected 1 pool_reuse event, got {len(pool_reuse_events)}"
        print(f"  pool_request_count={response2.engine_result['pool_request_count']}")
        print(f"  pool_reuse event: {pool_reuse_events[0].data}")

        # --- Verify pool state ---
        assert pool.active_count == 1, f"Expected 1 active lease, got {pool.active_count}"
        safe = pool.to_safe_dict()
        assert len(safe["leases"]) == 1
        assert safe["leases"][0]["request_count"] == 2

        # --- Verify events recorded in pool ---
        pool_events = pool._events
        event_types = [e["type"] for e in pool_events]
        assert "pool_acquire" in event_types
        assert "pool_reuse" in event_types
        assert "pool_release" in event_types

        print("\n[PASS] Browser pool smoke test passed")
        print(f"  Pool events: {event_types}")
        print(f"  Active leases: {pool.active_count}")
        return True

    finally:
        try:
            pool.close_all()
        except Exception:
            pass
        server.shutdown()


def main() -> None:
    print("=" * 60)
    print("Browser Pool Real Smoke Test (SCRAPLING-ABSORB-2G)")
    print("=" * 60)
    success = run_smoke()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
