#!/usr/bin/env python3
"""Browser Profile Health Scoring smoke test (SCRAPLING-HARDEN-2).

Validates:
- BrowserProfileHealth scoring and recording
- Health-aware rotator selection (healthiest strategy)
- NativeBrowserRuntime profile_health_update in engine_result

Uses mocked Playwright — no browser install or network required.
"""
from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch


def test_profile_health_scoring() -> bool:
    """Test BrowserProfileHealth tracks outcomes and computes score."""
    from autonomous_crawler.runtime.browser_pool import BrowserProfileHealth

    health = BrowserProfileHealth(profile_id="smoke-p1")
    assert health.health_score == 1.0, "empty health should be 1.0"

    # Success keeps score high
    health.record(ok=True, elapsed_seconds=1.0)
    assert health.health_score == 1.0
    assert health.success_count == 1

    # Timeout penalises
    health.record(ok=False, elapsed_seconds=30.0, failure_category="navigation_timeout")
    assert health.timeout_count == 1
    assert health.health_score < 1.0, "timeout should reduce health score"

    # Challenge penalises more
    health2 = BrowserProfileHealth(profile_id="smoke-p2")
    health2.record(ok=False, elapsed_seconds=5.0, failure_category="challenge_like")
    assert health2.challenge_count == 1

    # HTTP blocked penalises less
    health3 = BrowserProfileHealth(profile_id="smoke-p3")
    health3.record(ok=False, elapsed_seconds=2.0, failure_category="http_blocked")
    assert health3.http_blocked_count == 1

    d = health.to_dict()
    assert d["profile_id"] == "smoke-p1"
    assert d["total_requests"] == 2
    assert "health_score" in d
    print(f"  [PASS] health scoring: score={health.health_score:.3f} rate={health.success_rate:.3f}")
    return True


def test_healthiest_rotator_strategy() -> bool:
    """Test rotator picks the healthiest profile."""
    from autonomous_crawler.runtime.browser_pool import BrowserProfile, BrowserProfileRotator

    rotator = BrowserProfileRotator([
        BrowserProfile(profile_id="weak"),
        BrowserProfile(profile_id="strong"),
    ])

    # Make "weak" unhealthy
    for _ in range(5):
        rotator.update_health("weak", ok=False, elapsed_seconds=30.0, failure_category="navigation_timeout")

    # "strong" stays at default 1.0
    best = rotator.next_profile(strategy="healthiest")
    assert best.profile_id == "strong", f"expected strong, got {best.profile_id}"

    # Round-robin still works
    rr1 = rotator.next_profile(strategy="round_robin")
    rr2 = rotator.next_profile(strategy="round_robin")
    assert rr1.profile_id == "weak"
    assert rr2.profile_id == "strong"

    safe = rotator.to_safe_dict()
    assert "health" in safe
    assert "weak" in safe["health"]
    print(f"  [PASS] healthiest strategy: selected={best.profile_id}")
    return True


def test_healthiest_recovery() -> bool:
    """Test that a recovered profile becomes selectable again."""
    from autonomous_crawler.runtime.browser_pool import BrowserProfile, BrowserProfileRotator

    rotator = BrowserProfileRotator([
        BrowserProfile(profile_id="p1"),
        BrowserProfile(profile_id="p2"),
    ])

    # p1 starts bad, p2 also gets some failures
    rotator.update_health("p1", ok=False, elapsed_seconds=30.0, failure_category="navigation_timeout")
    rotator.update_health("p2", ok=False, elapsed_seconds=5.0, failure_category="challenge_like")
    rotator.update_health("p2", ok=False, elapsed_seconds=5.0, failure_category="challenge_like")

    # p2 is worse (challenge penalties are higher)
    best = rotator.next_profile(strategy="healthiest")
    assert best.profile_id == "p1", f"expected p1, got {best.profile_id}"

    # p2 recovers
    for _ in range(10):
        rotator.update_health("p2", ok=True, elapsed_seconds=1.0)
    best = rotator.next_profile(strategy="healthiest")
    assert best.profile_id == "p2", f"expected p2 after recovery, got {best.profile_id}"
    print(f"  [PASS] recovery: p1={rotator.get_health('p1').health_score:.3f} p2={rotator.get_health('p2').health_score:.3f}")
    return True


def test_runtime_health_update_mocked() -> bool:
    """Test NativeBrowserRuntime emits profile_health_update via mocked Playwright."""
    from autonomous_crawler.runtime.browser_pool import BrowserProfile, BrowserProfileRotator

    with patch("autonomous_crawler.runtime.native_browser.sync_playwright") as mock_pw_cls:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.content.return_value = "<html>ok</html>"
        mock_nav = MagicMock()
        mock_nav.status = 200
        mock_nav.headers = {"content-type": "text/html"}
        mock_page.goto.return_value = mock_nav

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_context.cookies.return_value = []
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

        rotator = BrowserProfileRotator([
            BrowserProfile(profile_id="desktop"),
            BrowserProfile(profile_id="mobile"),
        ])
        runtime = NativeBrowserRuntime(rotator=rotator)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})

        r1 = runtime.render(request)
        assert r1.ok
        hu1 = r1.engine_result["profile_health_update"]
        assert hu1 is not None
        assert hu1["profile_id"] == "desktop"
        assert hu1["total_requests"] == 1
        assert hu1["success_count"] == 1
        assert hu1["health_score"] == 1.0

        r2 = runtime.render(request)
        hu2 = r2.engine_result["profile_health_update"]
        assert hu2["profile_id"] == "mobile"
        assert hu2["total_requests"] == 1

        # Health events in runtime_events
        health_events = [e for e in r1.runtime_events if e.type == "profile_health_update"]
        assert len(health_events) == 1

        # Rotator dict includes health
        rotator_dict = r1.engine_result["rotator"]
        assert "health" in rotator_dict
        assert "desktop" in rotator_dict["health"]

        print(f"  [PASS] runtime health update: desktop={hu1['health_score']:.3f} mobile={hu2['health_score']:.3f}")
    return True


def test_runtime_health_on_failure_mocked() -> bool:
    """Test health update records failure via mocked Playwright."""
    from autonomous_crawler.runtime.browser_pool import BrowserProfile, BrowserProfileRotator

    with patch("autonomous_crawler.runtime.native_browser.sync_playwright") as mock_pw_cls:
        mock_page = MagicMock()
        mock_page.goto.side_effect = TimeoutError("navigation timeout")
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

        rotator = BrowserProfileRotator([BrowserProfile(profile_id="p1")])
        runtime = NativeBrowserRuntime(rotator=rotator)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        assert not response.ok
        hu = response.engine_result["profile_health_update"]
        assert hu is not None
        assert hu["failure_count"] == 1
        assert hu["timeout_count"] == 1
        assert hu["health_score"] < 1.0
        print(f"  [PASS] runtime failure health: score={hu['health_score']:.3f} timeout={hu['timeout_count']}")
    return True


def test_no_rotator_no_health() -> bool:
    """Test that no rotator means no health update."""
    with patch("autonomous_crawler.runtime.native_browser.sync_playwright") as mock_pw_cls:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.content.return_value = "<html>ok</html>"
        mock_nav = MagicMock()
        mock_nav.status = 200
        mock_nav.headers = {"content-type": "text/html"}
        mock_page.goto.return_value = mock_nav

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_context.cookies.return_value = []
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

        runtime = NativeBrowserRuntime()
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        assert response.ok
        assert response.engine_result["profile_health_update"] is None
        print("  [PASS] no rotator → no health update")
    return True


def main() -> None:
    tests = [
        ("Profile health scoring", test_profile_health_scoring),
        ("Healthiest rotator strategy", test_healthiest_rotator_strategy),
        ("Healthiest recovery", test_healthiest_recovery),
        ("Runtime health update (mocked)", test_runtime_health_update_mocked),
        ("Runtime health on failure (mocked)", test_runtime_health_on_failure_mocked),
        ("No rotator → no health", test_no_rotator_no_health),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            if fn():
                passed += 1
            else:
                failed += 1
                print(f"  [FAIL] {name} returned False")
        except Exception as exc:
            failed += 1
            print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")

    print(f"\n{'='*60}")
    print(f"Smoke results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed:
        sys.exit(1)
    print("All smoke tests passed.")


if __name__ == "__main__":
    main()
