#!/usr/bin/env python3
"""Real dynamic and protected training runner (SCRAPLING-ABSORB-2I).

Runs the native browser backend through real dynamic/protected training sites
and produces structured evidence for gap analysis.

Scenarios:
1. JS-rendered catalog (quotes.toscrape.com/js/)
2. Infinite scroll / delayed content (quotes.toscrape.com/js/ with scroll)
3. Protected/challenge-like (httpbin.org or bot detection site)

Evidence captured per scenario:
- rendered HTML length
- selector hit counts
- XHR count
- profile/pool evidence
- failure classification
- screenshot path when enabled

No site-specific extraction rules in core runtime.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("dev_logs") / "training"

# ---------------------------------------------------------------------------
# Training scenarios
# ---------------------------------------------------------------------------

TRAINING_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "js_rendered_quotes",
        "name": "JS Rendered Quotes (quotes.toscrape.com/js/)",
        "url": "https://quotes.toscrape.com/js/",
        "mode": "dynamic",
        "selectors": {
            "quote": ".quote",
            "text": ".quote .text",
            "author": ".quote .author",
            "tag": ".quote .tag",
        },
        "wait_selector": ".quote",
        "wait_until": "networkidle",
        "timeout_ms": 30000,
        "risk": "low-public-training-site",
        "expected": {
            "min_html_chars": 5000,
            "min_selector_hits": {"quote": 1, "text": 1},
        },
    },
    {
        "id": "js_rendered_scroll",
        "name": "JS Rendered with Scroll Loading",
        "url": "https://quotes.toscrape.com/js/",
        "mode": "dynamic",
        "selectors": {
            "quote": ".quote",
            "text": ".quote .text",
            "author": ".quote .author",
        },
        "wait_selector": ".quote",
        "wait_until": "networkidle",
        "timeout_ms": 45000,
        "browser_config": {
            "render_time_ms": 3000,
        },
        "risk": "low-public-training-site",
        "expected": {
            "min_html_chars": 5000,
            "min_selector_hits": {"quote": 1},
        },
    },
    {
        "id": "protected_challenge_like",
        "name": "Protected/Challenge-Like Page",
        "url": "https://httpbin.org/status/403",
        "mode": "dynamic",
        "selectors": {
            "body": "body",
        },
        "wait_selector": "",
        "wait_until": "domcontentloaded",
        "timeout_ms": 15000,
        "risk": "medium-expected-failure",
        "expected": {
            "failure_category": "http_blocked",
            "status_code": 403,
        },
    },
    {
        "id": "dynamic_with_headers",
        "name": "Dynamic Page with Custom Headers",
        "url": "https://httpbin.org/headers",
        "mode": "dynamic",
        "selectors": {
            "body": "body",
        },
        "wait_selector": "pre",
        "wait_until": "networkidle",
        "timeout_ms": 15000,
        "headers": {"X-Training-Test": "clm-native-v1"},
        "risk": "low-public-api",
        "expected": {
            "min_html_chars": 100,
        },
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _build_result(
    scenario: dict[str, Any],
    response: Any,
    elapsed: float,
) -> dict[str, Any]:
    """Build structured result from a RuntimeResponse."""
    scenario_id = scenario["id"]
    selectors = scenario.get("selectors", {})
    expected = scenario.get("expected", {})

    engine = response.engine_result or {}
    failure = engine.get("failure_classification", {})
    resource_counts = engine.get("resource_counts", {})
    pool_data = engine.get("pool")
    profile_data = engine.get("profile")
    rotator_data = engine.get("rotator")

    html = response.html or ""
    selector_matches: dict[str, int] = {}
    if html.strip():
        try:
            from lxml import html as lxml_html
            doc = lxml_html.fromstring(html.encode("utf-8", errors="replace"))
            for name, selector in selectors.items():
                if "@attr" in selector:
                    continue
                try:
                    elements = doc.cssselect(selector)
                    selector_matches[name] = len(elements)
                except Exception:
                    clean = selector.lstrip(".#")
                    selector_matches[name] = html.count(clean)
        except (ImportError, Exception):
            for name, selector in selectors.items():
                if "@attr" in selector:
                    continue
                clean = selector.lstrip(".#")
                selector_matches[name] = html.count(clean)

    result: dict[str, Any] = {
        "id": scenario_id,
        "name": scenario.get("name", scenario_id),
        "url": scenario["url"],
        "risk": scenario.get("risk", "unknown"),
        "status": "ok" if response.ok else "failed",
        "elapsed_seconds": round(elapsed, 3),
        "final_url": response.final_url,
        "status_code": response.status_code,
        "html_chars": len(html),
        "selector_matches": selector_matches,
        "xhr_count": len(response.captured_xhr or []),
        "resource_counts": resource_counts,
        "failure_classification": failure,
        "profile_evidence": {
            "profile_id": profile_data.get("profile_id") if profile_data else None,
            "profile": profile_data,
            "pool_active": pool_data.get("active_count") if pool_data else None,
            "rotator": rotator_data,
        },
        "engine": engine.get("engine", ""),
        "mode": engine.get("mode", ""),
        "session_mode": engine.get("session_mode", ""),
        "error": response.error or "",
        "ok": response.ok,
    }
    result["expected_checks"] = _check_expected(result, expected)
    return result


def run_scenario_with_runtime(
    scenario: dict[str, Any],
    runtime: Any,
    pool: Any,
) -> dict[str, Any]:
    """Run a scenario using a shared runtime (for profile rotation across scenarios)."""
    from autonomous_crawler.runtime import RuntimeRequest

    scenario_id = scenario["id"]
    url = scenario["url"]
    mode = scenario.get("mode", "dynamic")
    selectors = scenario.get("selectors", {})
    wait_selector = scenario.get("wait_selector", "")
    wait_until = scenario.get("wait_until", "domcontentloaded")
    timeout_ms = scenario.get("timeout_ms", 30000)
    headers = scenario.get("headers", {})
    browser_config = dict(scenario.get("browser_config", {}))

    request = RuntimeRequest.from_dict({
        "url": url,
        "mode": mode,
        "selectors": selectors,
        "wait_selector": wait_selector,
        "wait_until": wait_until,
        "timeout_ms": timeout_ms,
        "headers": headers,
        "browser_config": browser_config,
    })

    start_time = time.time()
    try:
        response = runtime.render(request)
    except Exception as exc:
        elapsed = time.time() - start_time
        return {
            "id": scenario_id,
            "name": scenario.get("name", scenario_id),
            "url": url,
            "risk": scenario.get("risk", "unknown"),
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(elapsed, 3),
        }

    elapsed = time.time() - start_time
    return _build_result(scenario, response, elapsed)


def run_scenario(scenario: dict[str, Any], *, use_profile: bool = False) -> dict[str, Any]:
    """Run a single training scenario and capture evidence."""
    from autonomous_crawler.runtime import (
        BrowserPoolConfig,
        BrowserPoolManager,
        BrowserProfile,
        BrowserProfileRotator,
        NativeBrowserRuntime,
        RuntimeRequest,
    )

    scenario_id = scenario["id"]
    url = scenario["url"]
    mode = scenario.get("mode", "dynamic")
    selectors = scenario.get("selectors", {})
    wait_selector = scenario.get("wait_selector", "")
    wait_until = scenario.get("wait_until", "domcontentloaded")
    timeout_ms = scenario.get("timeout_ms", 30000)
    headers = scenario.get("headers", {})
    browser_config = dict(scenario.get("browser_config", {}))

    # Set up pool and optional profile rotation
    pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
    rotator = None
    if use_profile:
        rotator = BrowserProfileRotator([
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
        ])

    runtime = NativeBrowserRuntime(pool=pool, rotator=rotator)

    request = RuntimeRequest.from_dict({
        "url": url,
        "mode": mode,
        "selectors": selectors,
        "wait_selector": wait_selector,
        "wait_until": wait_until,
        "timeout_ms": timeout_ms,
        "headers": headers,
        "browser_config": browser_config,
    })

    start_time = time.time()
    try:
        response = runtime.render(request)
    except Exception as exc:
        elapsed = time.time() - start_time
        return {
            "id": scenario_id,
            "name": scenario.get("name", scenario_id),
            "url": url,
            "risk": scenario.get("risk", "unknown"),
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(elapsed, 3),
        }
    finally:
        runtime.close()

    elapsed = time.time() - start_time
    return _build_result(scenario, response, elapsed)


def _check_expected(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    if "min_html_chars" in expected:
        checks["min_html_chars"] = {
            "expected": expected["min_html_chars"],
            "actual": result["html_chars"],
            "pass": result["html_chars"] >= expected["min_html_chars"],
        }
    if "min_selector_hits" in expected:
        for sel_name, min_count in expected["min_selector_hits"].items():
            actual = result.get("selector_matches", {}).get(sel_name, 0)
            checks[f"min_selector_hits.{sel_name}"] = {
                "expected": min_count,
                "actual": actual,
                "pass": actual >= min_count,
            }
    if "failure_category" in expected:
        actual_cat = result.get("failure_classification", {}).get("category", "none")
        checks["failure_category"] = {
            "expected": expected["failure_category"],
            "actual": actual_cat,
            "pass": actual_cat == expected["failure_category"],
        }
    if "status_code" in expected:
        checks["status_code"] = {
            "expected": expected["status_code"],
            "actual": result["status_code"],
            "pass": result["status_code"] == expected["status_code"],
        }
    return checks


def run_training(
    scenarios: list[dict[str, Any]] | None = None,
    use_profile: bool = False,
    output_name: str = "",
) -> dict[str, Any]:
    """Run all training scenarios and produce evidence JSON."""
    scenarios = scenarios or TRAINING_SCENARIOS
    results: list[dict[str, Any]] = []

    # Use a shared runtime when profile rotation is enabled
    shared_runtime = None
    shared_pool = None
    if use_profile:
        from autonomous_crawler.runtime import (
            BrowserPoolConfig,
            BrowserPoolManager,
            BrowserProfile,
            BrowserProfileRotator,
            NativeBrowserRuntime,
        )
        shared_pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        shared_runtime = NativeBrowserRuntime(
            pool=shared_pool,
            rotator=BrowserProfileRotator([
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
            ]),
        )

    for i, scenario in enumerate(scenarios):
        print(f"\n[{i+1}/{len(scenarios)}] {scenario['name']}")
        print(f"  URL: {scenario['url']}")
        if shared_runtime is not None:
            result = run_scenario_with_runtime(scenario, shared_runtime, shared_pool)
        else:
            result = run_scenario(scenario, use_profile=False)
        results.append(result)

        status_icon = "OK" if result["ok"] else "FAIL"
        print(f"  [{status_icon}] status={result['status_code']} html={result['html_chars']} xhr={result['xhr_count']}")
        if result.get("failure_classification", {}).get("category", "none") != "none":
            print(f"  failure: {result['failure_classification']['category']}")
        if result.get("profile_evidence", {}).get("profile_id"):
            print(f"  profile: {result['profile_evidence']['profile_id']}")

        for check_name, check in result.get("expected_checks", {}).items():
            icon = "PASS" if check["pass"] else "FAIL"
            print(f"  [{icon}] {check_name}: expected={check['expected']} actual={check['actual']}")

    # Summary
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = sum(1 for r in results if not r["ok"])
    failure_categories = [
        r.get("failure_classification", {}).get("category", "none")
        for r in results
        if r.get("failure_classification", {}).get("category", "none") != "none"
    ]

    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "SCRAPLING-ABSORB-2I real dynamic/protected training",
        "use_profile_rotation": use_profile,
        "summary": {
            "total": len(results),
            "ok": ok_count,
            "failed": fail_count,
            "failure_categories": list(set(failure_categories)),
        },
        "results": results,
    }

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not output_name:
        output_name = "2026-05-14_real_dynamic_training.json"
    output_path = OUTPUT_DIR / output_name
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Training complete: {ok_count} ok, {fail_count} failed")
    print(f"Failure categories: {failure_categories or 'none'}")
    print(f"Evidence saved: {output_path}")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Real dynamic/protected training runner")
    parser.add_argument("--profile", action="store_true", help="Enable profile rotation")
    parser.add_argument("--output", default="", help="Output filename")
    parser.add_argument("--scenario", default="", help="Run single scenario by ID")
    args = parser.parse_args()

    scenarios = TRAINING_SCENARIOS
    if args.scenario:
        scenarios = [s for s in TRAINING_SCENARIOS if s["id"] == args.scenario]
        if not scenarios:
            print(f"[ERROR] Unknown scenario: {args.scenario}")
            print(f"Available: {[s['id'] for s in TRAINING_SCENARIOS]}")
            sys.exit(1)

    report = run_training(scenarios, use_profile=args.profile, output_name=args.output)
    sys.exit(0 if report["summary"]["ok"] > 0 else 1)


if __name__ == "__main__":
    main()
