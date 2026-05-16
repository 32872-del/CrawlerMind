#!/usr/bin/env python3
"""Browser Scenario Training Harness (SCRAPLING-HARDEN-2B).

Runs CLM native browser runtime through scroll, virtualization, and mobile
viewport training scenarios using deterministic local fixtures and optional
real public demo sites.

Evidence captured per scenario:
- profile_health (from BrowserProfileRotator)
- scroll_events (page-injected tracking)
- network_candidates (resource_counts, captured_xhr)
- rendered_item_count (page-injected counter)
- failure_classification
- viewport_info, ua_info (mobile scenarios)

No site-specific rules in core runtime. Site differences live in
scenario definitions, profiles, and training artifacts.
"""
from __future__ import annotations

import http.server
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("dev_logs") / "training"

# ---------------------------------------------------------------------------
# Fixture server
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent / "autonomous_crawler" / "tests" / "fixtures" / "browser_scenarios"


class FixtureServer:
    """Minimal HTTP server for local fixture files."""

    def __init__(self, fixture_dir: Path | str | None = None, port: int = 0) -> None:
        self._fixture_dir = Path(fixture_dir) if fixture_dir else FIXTURE_DIR
        self._port = port
        self._server: http.server.HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._actual_port: int = 0

    def start(self) -> str:
        handler = self._make_handler(self._fixture_dir)
        self._server = http.server.HTTPServer(("127.0.0.1", self._port), handler)
        self._actual_port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._actual_port}"

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None

    @staticmethod
    def _make_handler(fixture_dir: Path) -> type:
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(fixture_dir), **kwargs)

            def log_message(self, format: str, *args: Any) -> None:
                pass  # suppress log noise

        return Handler

    def __enter__(self) -> str:
        return self.start()

    def __exit__(self, *args: Any) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCROLL_JS = """
(function() {
    var viewport = arguments[0];
    var maxScrolls = arguments[1] || 10;
    var delay = arguments[2] || 300;
    var scrollCount = 0;

    return new Promise(function(resolve) {
        function doScroll() {
            if (scrollCount >= maxScrolls) {
                resolve({ scrolls: scrollCount, reason: 'max_reached' });
                return;
            }
            viewport.scrollTop += viewport.clientHeight * 0.8;
            scrollCount++;
            setTimeout(function() {
                // Check if sentinel is still visible (for infinite scroll)
                var sentinel = document.getElementById('sentinel');
                if (sentinel) {
                    var rect = sentinel.getBoundingClientRect();
                    if (rect.top > window.innerHeight + 500) {
                        resolve({ scrolls: scrollCount, reason: 'sentinel_out_of_view' });
                        return;
                    }
                }
                doScroll();
            }, delay);
        }
        doScroll();
    });
})()
"""

EVAL_SCROLLEVENTS_JS = "window.__scroll_events || []"
EVAL_RENDERED_COUNT_JS = "window.__rendered_count || 0"
EVAL_VIEWPORT_INFO_JS = "window.__viewport_info || {}"
EVAL_UA_INFO_JS = "window.__ua_info || {}"
EVAL_VISIBLE_RANGE_JS = "window.__visible_range || {}"
EVAL_TOTAL_ITEMS_JS = "window.__total_items || 0"


@dataclass
class ScenarioDefinition:
    id: str
    name: str
    url: str = ""
    url_path: str = ""  # relative path for local fixtures (composed with base_url)
    mode: str = "dynamic"
    selectors: dict[str, str] = field(default_factory=dict)
    wait_selector: str = ""
    wait_until: str = "domcontentloaded"
    timeout_ms: int = 30000
    browser_config: dict[str, Any] = field(default_factory=dict)
    risk: str = "low"
    expected: dict[str, Any] = field(default_factory=dict)
    # Scroll training
    scroll_enabled: bool = False
    scroll_max: int = 10
    scroll_delay_ms: int = 300
    scroll_target: str = ""  # CSS selector for scroll container (empty = window)
    # Mobile training
    mobile_profile: dict[str, Any] = field(default_factory=dict)


# Local fixture scenarios
LOCAL_SCENARIOS: list[ScenarioDefinition] = [
    ScenarioDefinition(
        id="infinite_scroll_fixture",
        name="Infinite Scroll — Local Fixture",
        url_path="infinite_scroll.html",
        selectors={
            "item": ".item",
            "item_title": ".item h3",
            "category": ".category",
        },
        wait_selector=".item",
        wait_until="domcontentloaded",
        timeout_ms=20000,
        scroll_enabled=True,
        scroll_max=8,
        scroll_delay_ms=200,
        expected={
            "min_rendered_items": 20,
            "min_scroll_events": 2,
        },
    ),
    ScenarioDefinition(
        id="virtualized_list_fixture",
        name="Virtualized List — Local Fixture",
        url_path="virtualized_list.html",
        selectors={
            "virtual_item": ".virtual-item",
            "item_price": ".item-price",
        },
        wait_selector=".virtual-item",
        wait_until="domcontentloaded",
        timeout_ms=20000,
        scroll_enabled=True,
        scroll_max=15,
        scroll_delay_ms=150,
        scroll_target="#virtual-viewport",
        expected={
            "min_rendered_items": 5,
            "min_scroll_events": 3,
        },
    ),
    ScenarioDefinition(
        id="mobile_viewport_fixture",
        name="Mobile Viewport — Local Fixture",
        url_path="mobile_viewport.html",
        selectors={
            "card": ".card",
            "card_title": ".card-title",
            "nav_item": ".nav-item",
        },
        wait_selector=".card",
        wait_until="domcontentloaded",
        timeout_ms=20000,
        mobile_profile={
            "profile_id": "mobile-training",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "viewport": "375x812",
            "locale": "en-US",
            "timezone": "America/New_York",
            "is_mobile": True,
            "has_touch": True,
            "device_scale_factor": 3,
        },
        expected={
            "min_rendered_items": 4,
        },
    ),
]


# ---------------------------------------------------------------------------
# Evidence builder
# ---------------------------------------------------------------------------


def build_evidence(
    scenario: ScenarioDefinition,
    response: Any,
    elapsed: float,
    scroll_result: dict[str, Any] | None = None,
    scroll_events: list[dict[str, Any]] | None = None,
    rendered_count: int = 0,
    viewport_info: dict[str, Any] | None = None,
    ua_info: dict[str, Any] | None = None,
    visible_range: dict[str, Any] | None = None,
    total_items: int = 0,
    stop_reason: str = "completed",
) -> dict[str, Any]:
    engine = response.engine_result or {}
    failure = engine.get("failure_classification", {})
    resource_counts = engine.get("resource_counts", {})
    profile_data = engine.get("profile")
    health_update = engine.get("profile_health_update")

    html = response.html or ""

    # Selector matching via lxml
    selector_matches: dict[str, int] = {}
    if html.strip():
        try:
            from lxml import html as lxml_html
            doc = lxml_html.fromstring(html.encode("utf-8", errors="replace"))
            for name, sel in scenario.selectors.items():
                try:
                    elements = doc.cssselect(sel)
                    selector_matches[name] = len(elements)
                except Exception:
                    selector_matches[name] = html.count(sel.lstrip(".#"))
        except (ImportError, Exception):
            for name, sel in scenario.selectors.items():
                selector_matches[name] = html.count(sel.lstrip(".#"))

    evidence: dict[str, Any] = {
        "id": scenario.id,
        "name": scenario.name,
        "url": scenario.url,
        "risk": scenario.risk,
        "status": "ok" if response.ok else "failed",
        "ok": response.ok,
        "elapsed_seconds": round(elapsed, 3),
        "final_url": response.final_url,
        "status_code": response.status_code,
        "html_chars": len(html),
        "selector_matches": selector_matches,
        "rendered_item_count": rendered_count,
        "total_items_in_dataset": total_items,
        "scroll_events": scroll_events or [],
        "scroll_result": scroll_result,
        "network_candidates": {
            "resource_counts": resource_counts,
            "xhr_count": len(response.captured_xhr or []),
            "captured_xhr": (response.captured_xhr or [])[:20],
        },
        "viewport_info": viewport_info,
        "ua_info": ua_info,
        "visible_range": visible_range,
        "profile_health": health_update,
        "failure_classification": failure,
        "profile_evidence": {
            "profile_id": profile_data.get("profile_id") if profile_data else None,
            "profile": profile_data,
        },
        "engine": engine.get("engine", ""),
        "mode": engine.get("mode", ""),
        "session_mode": engine.get("session_mode", ""),
        "error": response.error or "",
        "stop_reason": stop_reason,
    }

    # Expected checks
    evidence["expected_checks"] = _check_expected(evidence, scenario.expected)
    return evidence


def _check_expected(evidence: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    if "min_rendered_items" in expected:
        actual = evidence.get("rendered_item_count", 0)
        checks["min_rendered_items"] = {
            "expected": expected["min_rendered_items"],
            "actual": actual,
            "pass": actual >= expected["min_rendered_items"],
        }
    if "min_scroll_events" in expected:
        actual = len(evidence.get("scroll_events", []))
        checks["min_scroll_events"] = {
            "expected": expected["min_scroll_events"],
            "actual": actual,
            "pass": actual >= expected["min_scroll_events"],
        }
    if "min_html_chars" in expected:
        actual = evidence.get("html_chars", 0)
        checks["min_html_chars"] = {
            "expected": expected["min_html_chars"],
            "actual": actual,
            "pass": actual >= expected["min_html_chars"],
        }
    if "failure_category" in expected:
        actual_cat = evidence.get("failure_classification", {}).get("category", "none")
        checks["failure_category"] = {
            "expected": expected["failure_category"],
            "actual": actual_cat,
            "pass": actual_cat == expected["failure_category"],
        }
    return checks


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


def run_scenario(
    scenario: ScenarioDefinition,
    runtime: Any,
    base_url: str = "",
) -> dict[str, Any]:
    """Run a single scenario and collect evidence."""
    from autonomous_crawler.runtime.models import RuntimeRequest
    from autonomous_crawler.runtime import BrowserProfile

    url = scenario.url if scenario.url.startswith("http") else f"{base_url}/{scenario.url_path}"

    # Build browser_config
    bc = dict(scenario.browser_config)

    # Apply mobile profile if specified
    profile = None
    if scenario.mobile_profile:
        profile = BrowserProfile.from_dict(scenario.mobile_profile)
        if profile:
            ctx_opts = profile.to_context_options()
            if ctx_opts.get("user_agent"):
                bc["user_agent"] = ctx_opts["user_agent"]
            if ctx_opts.get("viewport"):
                bc["viewport"] = ctx_opts["viewport"]
            if ctx_opts.get("locale"):
                bc["locale"] = ctx_opts["locale"]
            if ctx_opts.get("timezone_id"):
                bc["timezone_id"] = ctx_opts["timezone_id"]

    request = RuntimeRequest.from_dict({
        "url": url,
        "mode": scenario.mode,
        "selectors": scenario.selectors,
        "wait_selector": scenario.wait_selector,
        "wait_until": scenario.wait_until,
        "timeout_ms": scenario.timeout_ms,
        "browser_config": bc,
    })

    start_time = time.time()
    try:
        response = runtime.render(request)
    except Exception as exc:
        elapsed = time.time() - start_time
        return {
            "id": scenario.id,
            "name": scenario.name,
            "url": url,
            "risk": scenario.risk,
            "status": "error",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(elapsed, 3),
            "failure_classification": {"category": "runtime_error"},
            "expected_checks": _check_expected({}, scenario.expected),
            "stop_reason": "runtime_error",
        }

    elapsed = time.time() - start_time

    # Post-render: collect page state
    scroll_result = None
    scroll_events = None
    rendered_count = 0
    viewport_info = None
    ua_info = None
    visible_range = None
    total_items = 0

    if response.ok:
        html = response.html or ""

        # Extract training state from hidden DOM element (fixtures write this)
        state = _extract_training_state(html)
        if state:
            rendered_count = state.get("rendered_count", 0)
            scroll_events = state.get("scroll_events", [])
            viewport_info = state.get("viewport_info")
            ua_info = state.get("ua_info")
            visible_range = state.get("visible_range")
            total_items = state.get("total_items", 0)

        # Count items from selectors as fallback
        if rendered_count == 0:
            for _name, sel in scenario.selectors.items():
                try:
                    from lxml import html as lxml_html
                    doc = lxml_html.fromstring(html.encode("utf-8", errors="replace"))
                    elements = doc.cssselect(sel)
                    rendered_count = max(rendered_count, len(elements))
                except Exception:
                    rendered_count = max(rendered_count, html.count(sel.lstrip(".#")))

    # Scroll training: second render pass with scrolling init_script
    if response.ok and scenario.scroll_enabled:
        scroll_result, scroll_events, rendered_count = _run_scroll_training(
            runtime, request, scenario, elapsed
        )

    if response.ok and not viewport_info:
        # Fallback: extract from engine_result profile data
        er = response.engine_result or {}
        profile = er.get("profile")
        if profile:
            viewport_info = {"viewport": profile.get("viewport", ""), "locale": profile.get("locale", "")}

    # Determine stop_reason
    stop_reason = "completed"
    if not response.ok:
        fail_cat = (response.engine_result or {}).get("failure_classification", {}).get("category", "")
        stop_reason = fail_cat if fail_cat else "render_failed"
    elif scenario.scroll_enabled and scroll_result is None:
        stop_reason = "scroll_error"
    elif scenario.scroll_enabled and rendered_count == 0:
        stop_reason = "scroll_no_items"
    elif rendered_count == 0 and scenario.selectors:
        stop_reason = "no_items_matched"

    return build_evidence(
        scenario, response, elapsed,
        scroll_result=scroll_result,
        scroll_events=scroll_events,
        rendered_count=rendered_count,
        viewport_info=viewport_info,
        ua_info=ua_info,
        visible_range=visible_range,
        total_items=total_items,
        stop_reason=stop_reason,
    )


def _extract_training_state(html: str) -> dict[str, Any]:
    """Extract training state from the hidden __training_state element in HTML."""
    import re
    match = re.search(
        r'id="__training_state"[^>]*>(.*?)</pre>',
        html,
        re.DOTALL,
    )
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def _run_scroll_training(
    runtime: Any,
    base_request: Any,
    scenario: ScenarioDefinition,
    first_elapsed: float,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], int]:
    """Run scroll training via a second render pass with scroll init_script.

    The init_script waits for DOMContentLoaded, then scrolls the target
    element to trigger lazy-loading / IntersectionObserver in the fixture.
    After scrolling completes, it writes results to a hidden DOM element
    (__training_state) which we parse from the returned HTML.
    """
    from autonomous_crawler.runtime.models import RuntimeRequest

    bc = dict(base_request.browser_config or {})

    scroll_target = scenario.scroll_target or "window"
    if scroll_target == "window":
        target_js = "document.scrollingElement || document.body"
    else:
        target_js = f"document.querySelector('{scroll_target}') || document.scrollingElement || document.body"

    # This script waits for DOM, scrolls, then writes state to a hidden element
    scroll_script = f"""
    (function() {{
        function doScroll() {{
            var target = {target_js};
            var maxScrolls = {scenario.scroll_max};
            var delay = {scenario.scroll_delay_ms};
            var scrollCount = 0;

            function next() {{
                if (scrollCount >= maxScrolls) {{
                    writeState();
                    return;
                }}
                target.scrollTop += (target.clientHeight || window.innerHeight) * 0.8;
                scrollCount++;
                setTimeout(function() {{
                    // Update __training_state after each scroll
                    writeState();
                    next();
                }}, delay);
            }}

            function writeState() {{
                var el = document.getElementById('__training_state');
                if (el) {{
                    el.textContent = JSON.stringify({{
                        scroll_events: window.__scroll_events || [],
                        rendered_count: window.__rendered_count || 0,
                        total_pages: window.__total_pages || 0,
                        total_items: window.__total_items || 0,
                        visible_range: window.__visible_range || {{}},
                        viewport_info: window.__viewport_info || {{}},
                        ua_info: window.__ua_info || {{}},
                        scroll_count: scrollCount
                    }});
                }}
            }}

            next();
        }}

        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', doScroll);
        }} else {{
            doScroll();
        }}
    }})();
    """

    bc["init_script"] = scroll_script
    # Give enough render_time for all scrolls to complete
    total_scroll_time = scenario.scroll_max * scenario.scroll_delay_ms + 2000
    bc["render_time_ms"] = max(bc.get("render_time_ms", 0), total_scroll_time)

    request = RuntimeRequest.from_dict({
        "url": base_request.url,
        "mode": base_request.mode,
        "selectors": base_request.selectors,
        "wait_selector": base_request.wait_selector,
        "wait_until": base_request.wait_until,
        "timeout_ms": max(scenario.timeout_ms, total_scroll_time + 15000),
        "browser_config": bc,
    })

    try:
        response = runtime.render(request)
        if not response.ok:
            return None, [], 0

        html = response.html or ""

        # Extract training state from the hidden DOM element
        state = _extract_training_state(html)
        scroll_events: list[dict[str, Any]] = state.get("scroll_events", [])
        rendered_count = state.get("rendered_count", 0)

        # Also count items from HTML selectors as fallback
        if rendered_count == 0:
            for _name, sel in scenario.selectors.items():
                try:
                    from lxml import html as lxml_html
                    doc = lxml_html.fromstring(html.encode("utf-8", errors="replace"))
                    elements = doc.cssselect(sel)
                    rendered_count = max(rendered_count, len(elements))
                except Exception:
                    rendered_count = max(rendered_count, html.count(sel.lstrip(".#")))

        scroll_result = {
            "scrolls": state.get("scroll_count", 0),
            "reason": "completed",
        }
        return scroll_result, scroll_events, rendered_count
    except Exception:
        return None, [], 0


# ---------------------------------------------------------------------------
# Training runner
# ---------------------------------------------------------------------------


def run_training(
    scenarios: list[ScenarioDefinition] | None = None,
    use_profile: bool = False,
    public_url: str = "",
    output_name: str = "",
) -> dict[str, Any]:
    """Run all training scenarios and produce evidence JSON."""
    from autonomous_crawler.runtime import (
        BrowserPoolConfig,
        BrowserPoolManager,
        BrowserProfile,
        BrowserProfileRotator,
        NativeBrowserRuntime,
    )

    scenarios = scenarios or LOCAL_SCENARIOS
    results: list[dict[str, Any]] = []

    # Set up rotator with desktop + mobile profiles
    profiles = [
        BrowserProfile(
            profile_id="training-desktop",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            viewport="1920x1080",
            locale="en-US",
            timezone="America/New_York",
        ),
        BrowserProfile(
            profile_id="training-mobile",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15",
            viewport="375x812",
            locale="en-US",
            timezone="America/New_York",
        ),
    ]
    pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
    rotator = BrowserProfileRotator(profiles) if use_profile else None
    runtime = NativeBrowserRuntime(pool=pool, rotator=rotator)

    # Start fixture server for local scenarios
    has_local = any(not s.url.startswith("http") for s in scenarios)
    fixture_server = FixtureServer() if has_local else None
    base_url = ""
    if fixture_server:
        base_url = fixture_server.start()

    try:
        for i, scenario in enumerate(scenarios):
            print(f"\n[{i+1}/{len(scenarios)}] {scenario.name}")
            print(f"  URL: {scenario.url if scenario.url.startswith('http') else base_url + '/' + scenario.url_path}")

            result = run_scenario(scenario, runtime, base_url=base_url)
            results.append(result)

            status_icon = "OK" if result.get("ok") else "FAIL"
            print(f"  [{status_icon}] status={result.get('status_code', '?')} html={result.get('html_chars', 0)}")
            print(f"  rendered_items={result.get('rendered_item_count', 0)} scroll_events={len(result.get('scroll_events', []))}")

            if result.get("failure_classification", {}).get("category", "none") != "none":
                print(f"  failure: {result['failure_classification']['category']}")

            if result.get("profile_health"):
                ph = result["profile_health"]
                print(f"  profile_health: score={ph.get('health_score', '?')} requests={ph.get('total_requests', 0)}")

            if result.get("profile_evidence", {}).get("profile_id"):
                print(f"  profile: {result['profile_evidence']['profile_id']}")

            for check_name, check in result.get("expected_checks", {}).items():
                icon = "PASS" if check["pass"] else "FAIL"
                print(f"  [{icon}] {check_name}: expected={check['expected']} actual={check['actual']}")
    finally:
        runtime.close()
        if fixture_server:
            fixture_server.stop()

    # Summary
    ok_count = sum(1 for r in results if r.get("ok"))
    fail_count = sum(1 for r in results if not r.get("ok"))
    total_checks = sum(len(r.get("expected_checks", {})) for r in results)
    passed_checks = sum(
        1 for r in results
        for c in r.get("expected_checks", {}).values()
        if c.get("pass")
    )

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "SCRAPLING-HARDEN-2B browser scenario training",
        "use_profile_rotation": use_profile,
        "summary": {
            "total": len(results),
            "ok": ok_count,
            "failed": fail_count,
            "checks_total": total_checks,
            "checks_passed": passed_checks,
        },
        "results": results,
    }

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not output_name:
        output_name = "2026-05-15_browser_scenario_training.json"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Training complete: {ok_count} ok, {fail_count} failed")
    print(f"Checks: {passed_checks}/{total_checks} passed")
    print(f"Evidence saved: {output_path}")

    return report


# ---------------------------------------------------------------------------
# Public demo scenarios (separate from local fixtures)
# ---------------------------------------------------------------------------

PUBLIC_DEMO_SCENARIOS: list[ScenarioDefinition] = [
    ScenarioDefinition(
        id="react_virtuoso_demo",
        name="React Virtuoso — Public Demo",
        url="https://virtuoso.dev/infinite-scrolling/",
        selectors={
            "list_item": "[data-index]",
        },
        wait_selector="[data-index]",
        wait_until="networkidle",
        timeout_ms=30000,
        browser_config={"render_time_ms": 3000},
        risk="low-public-demo",
        scroll_enabled=True,
        scroll_max=5,
        scroll_delay_ms=500,
        expected={
            "min_rendered_items": 3,
        },
    ),
    ScenarioDefinition(
        id="vue_examples_spa",
        name="Vue.js Examples — SPA Doc Site",
        url="https://vuejs.org/examples/",
        selectors={
            "example_link": "a.link",
            "sidebar_group": "section.VPSidebarGroup",
        },
        wait_selector="a.link",
        wait_until="networkidle",
        timeout_ms=30000,
        browser_config={"render_time_ms": 2000},
        risk="low-public-demo",
        expected={
            "min_rendered_items": 5,
            "min_html_chars": 5000,
        },
    ),
    ScenarioDefinition(
        id="react_learn_spa",
        name="React.dev Learn — SPA Doc Site",
        url="https://react.dev/learn",
        selectors={
            "nav_link": "a.p-2.pe-2",
            "article": "article",
        },
        wait_selector="a.p-2.pe-2",
        wait_until="networkidle",
        timeout_ms=30000,
        browser_config={"render_time_ms": 2000},
        risk="low-public-demo",
        expected={
            "min_rendered_items": 10,
            "min_html_chars": 5000,
        },
    ),
    ScenarioDefinition(
        id="tanstack_virtual_docs",
        name="TanStack Virtual — SPA Doc Site",
        url="https://tanstack.com/virtual/latest/docs/introduction",
        selectors={
            "doc_content": "article, main, [role='main']",
            "code_block": "pre",
        },
        wait_selector="pre",
        wait_until="networkidle",
        timeout_ms=30000,
        browser_config={"render_time_ms": 2000},
        risk="low-public-demo",
        expected={
            "min_rendered_items": 1,
            "min_html_chars": 3000,
        },
    ),
    # --- REAL-HARDEN-4: Dynamic list / AJAX / virtual targets ---
    ScenarioDefinition(
        id="scrapethissite_ajax",
        name="ScrapeThisSite — AJAX Dynamic List",
        url="https://scrapethissite.com/pages/ajax-javascript/",
        selectors={
            "year_link": "a.year-link",
            "film_row": "tr.film",
            "film_title": "td.film-title",
        },
        wait_selector="a.year-link",
        wait_until="networkidle",
        timeout_ms=30000,
        browser_config={"render_time_ms": 2000},
        risk="low-public-demo",
        expected={
            "min_rendered_items": 6,  # year links
            "min_html_chars": 3000,
        },
    ),
    ScenarioDefinition(
        id="dummyjson_products_ssr",
        name="DummyJSON Products — Server-Rendered List",
        url="https://dummyjson.com/products",
        selectors={
            "product_card": ".product-card, [class*='product']",
            "product_title": "h3, .product-title, [class*='title']",
            "product_price": "[class*='price']",
        },
        wait_selector="body",
        wait_until="networkidle",
        timeout_ms=30000,
        browser_config={"render_time_ms": 3000},
        risk="low-public-demo",
        expected={
            "min_rendered_items": 1,
            "min_html_chars": 5000,
        },
    ),
    ScenarioDefinition(
        id="scrapethissite_countries",
        name="ScrapeThisSite Countries — AJAX Pagination",
        url="https://scrapethissite.com/pages/simple/",
        selectors={
            "country": ".country, .col-md-4.country",
            "country_name": ".country-name, h3",
            "country_capital": ".country-capital",
        },
        wait_selector="body",
        wait_until="networkidle",
        timeout_ms=30000,
        browser_config={"render_time_ms": 2000},
        risk="low-public-demo",
        expected={
            "min_rendered_items": 5,
            "min_html_chars": 3000,
        },
    ),
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Browser scenario training runner")
    parser.add_argument("--profile", action="store_true", help="Enable profile rotation")
    parser.add_argument("--output", default="", help="Output filename")
    parser.add_argument("--public", action="store_true", help="Include public demo scenarios")
    parser.add_argument("--scenario", default="", help="Run single scenario by ID")
    args = parser.parse_args()

    scenarios = list(LOCAL_SCENARIOS)
    if args.public:
        scenarios.extend(PUBLIC_DEMO_SCENARIOS)

    if args.scenario:
        all_scenarios = scenarios
        scenarios = [s for s in all_scenarios if s.id == args.scenario]
        if not scenarios:
            print(f"[ERROR] Unknown scenario: {args.scenario}")
            print(f"Available: {[s.id for s in all_scenarios]}")
            sys.exit(1)

    report = run_training(scenarios, use_profile=args.profile, output_name=args.output)
    sys.exit(0 if report["summary"]["ok"] > 0 else 1)


if __name__ == "__main__":
    main()
