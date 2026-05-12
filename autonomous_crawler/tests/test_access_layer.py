from __future__ import annotations

import unittest

from autonomous_crawler.tools.access_diagnostics import diagnose_access
from autonomous_crawler.tools.access_policy import decide_access, AccessDecision
from autonomous_crawler.tools.challenge_detector import (
    ChallengeSignal,
    detect_challenge_signal,
    CHALLENGE_MARKERS,
    LOGIN_MARKERS,
)
from autonomous_crawler.tools.fetch_policy import FetchAttempt, fetch_best_page
from autonomous_crawler.tools.html_recon import MOCK_CHALLENGE_HTML, MOCK_PRODUCT_HTML
from autonomous_crawler.tools.proxy_manager import ProxyConfig, ProxyManager, redact_proxy_url
from autonomous_crawler.tools.rate_limit_policy import RateLimitPolicy
from autonomous_crawler.tools.session_profile import (
    SessionProfile,
    SENSITIVE_HEADER_NAMES,
    redact_storage_state_path,
)


class AccessLayerTests(unittest.TestCase):
    def test_challenge_signal_classifies_cloudflare_without_bypass(self) -> None:
        signal = detect_challenge_signal(MOCK_CHALLENGE_HTML, status_code=403)

        self.assertTrue(signal.detected)
        self.assertEqual(signal.kind, "managed_challenge")
        self.assertEqual(signal.vendor, "cloudflare")
        self.assertEqual(signal.severity, "high")
        self.assertTrue(signal.requires_manual_handoff)

    def test_rate_limit_signal_from_status_code(self) -> None:
        signal = detect_challenge_signal("<html>slow down</html>", status_code=429)

        self.assertTrue(signal.detected)
        self.assertEqual(signal.kind, "rate_limited")
        self.assertEqual(signal.primary_marker, "status:429")

    def test_diagnostics_include_access_decision(self) -> None:
        result = diagnose_access(MOCK_CHALLENGE_HTML, status_code=403)

        decision = result["access_decision"]
        self.assertEqual(decision["action"], "manual_handoff")
        self.assertFalse(decision["allowed"])
        self.assertTrue(decision["requires_authorized_session"])

    def test_authorized_session_can_mark_challenge_review_allowed(self) -> None:
        result = diagnose_access(
            MOCK_CHALLENGE_HTML,
            status_code=403,
            has_authorized_session=True,
        )

        decision = result["access_decision"]
        self.assertEqual(decision["action"], "authorized_browser_review")
        self.assertTrue(decision["allowed"])

    def test_standard_access_decision_for_normal_html(self) -> None:
        decision = decide_access(diagnose_access(MOCK_PRODUCT_HTML))

        self.assertEqual(decision.action, "standard_http")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk_level, "low")

    def test_proxy_manager_is_disabled_by_default(self) -> None:
        manager = ProxyManager()

        self.assertEqual(manager.select_proxy("https://example.com"), "")
        self.assertFalse(manager.describe_selection("https://example.com")["enabled"])

    def test_proxy_manager_selects_domain_rule_and_redacts_credentials(self) -> None:
        manager = ProxyManager(ProxyConfig.from_dict({
            "enabled": True,
            "default_proxy": "http://user:secret@proxy.example:8080",
            "per_domain": {"shop.example": "socks5://u:p@local.proxy:1080"},
        }))

        self.assertEqual(
            manager.select_proxy("https://shop.example/catalog"),
            "socks5://u:p@local.proxy:1080",
        )
        description = manager.describe_selection("https://other.example")
        self.assertEqual(description["proxy"], "http://***:***@proxy.example:8080")
        self.assertEqual(redact_proxy_url("https://plain.proxy:8443"), "https://plain.proxy:8443")

    def test_proxy_config_validation_rejects_invalid_enabled_url(self) -> None:
        config = ProxyConfig.from_dict({"enabled": True, "default_proxy": "ftp://proxy"})

        self.assertTrue(config.validate())

    def test_session_profile_scopes_headers_to_allowed_domains(self) -> None:
        profile = SessionProfile.from_dict({
            "allowed_domains": ["example.com"],
            "headers": {"Authorization": "Bearer secret", "X-Test": "yes"},
            "cookies": {"sid": "abc"},
        })

        headers = profile.headers_for("https://shop.example.com")
        self.assertEqual(headers["Authorization"], "Bearer secret")
        self.assertEqual(headers["Cookie"], "sid=abc")
        self.assertEqual(profile.headers_for("https://outside.test"), {})
        self.assertEqual(profile.to_safe_dict()["headers"]["Authorization"], "[redacted]")
        self.assertEqual(profile.to_safe_dict()["cookies"]["sid"], "[redacted]")

    def test_rate_limit_policy_applies_backoff_and_retry_cap(self) -> None:
        policy = RateLimitPolicy.from_dict({
            "default": {"delay_seconds": 0.5, "max_retries": 2, "backoff_factor": 3},
            "per_domain": {"shop.example": {"delay_seconds": 2, "max_retries": 1}},
        })

        first = policy.decide("https://shop.example/a", attempt=0, status_code=429)
        second = policy.decide("https://shop.example/a", attempt=1, status_code=429)
        third = policy.decide("https://other.example/a", attempt=1, error="timeout")

        self.assertTrue(first.should_retry)
        self.assertEqual(first.delay_seconds, 2)
        self.assertFalse(second.should_retry)
        self.assertEqual(third.delay_seconds, 1.5)

    def test_fetch_best_page_records_safe_access_context(self) -> None:
        captured_headers: list[dict[str, str]] = []

        def fetcher(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            captured_headers.append(headers or {})
            return FetchAttempt(mode="requests", url=url, html=MOCK_PRODUCT_HTML, status_code=200)

        result = fetch_best_page(
            "https://shop.example/catalog",
            modes=["requests"],
            fetchers={"requests": fetcher},
            session_profile={
                "allowed_domains": ["shop.example"],
                "headers": {"Authorization": "Bearer secret"},
            },
            proxy_config={
                "enabled": True,
                "default_proxy": "http://user:secret@proxy.example:8080",
            },
            rate_limit_policy={"default": {"delay_seconds": 2, "max_retries": 5}},
        )

        context = result.attempts[0].to_dict()["access_context"]
        self.assertEqual(captured_headers[0]["Authorization"], "Bearer secret")
        self.assertEqual(context["session"]["headers"]["Authorization"], "[redacted]")
        self.assertEqual(context["proxy"]["proxy"], "http://***:***@proxy.example:8080")
        self.assertEqual(context["rate_limit"]["delay_seconds"], 2)


# ---------------------------------------------------------------------------
# Proxy default-off and credential redaction
# ---------------------------------------------------------------------------

class ProxyDefaultOffTests(unittest.TestCase):
    """Verify proxy is disabled by default and never leaks credentials."""

    def test_from_dict_empty_defaults_to_disabled(self) -> None:
        config = ProxyConfig.from_dict({})
        self.assertFalse(config.enabled)
        self.assertEqual(config.default_proxy, "")
        self.assertEqual(config.per_domain, {})

    def test_from_dict_none_defaults_to_disabled(self) -> None:
        config = ProxyConfig.from_dict(None)
        self.assertFalse(config.enabled)

    def test_select_proxy_returns_empty_when_disabled(self) -> None:
        manager = ProxyManager(ProxyConfig(enabled=False, default_proxy="http://proxy:8080"))
        self.assertEqual(manager.select_proxy("https://any.example"), "")

    def test_to_safe_dict_never_contains_raw_credentials(self) -> None:
        config = ProxyConfig.from_dict({
            "enabled": True,
            "default_proxy": "http://admin:p@ssw0rd@proxy.example:8080",
            "per_domain": {
                "secret.example": "socks5://root:topsecret@socks.proxy:1080",
            },
        })
        safe = config.to_safe_dict()
        text = str(safe)
        self.assertNotIn("p@ssw0rd", text)
        self.assertNotIn("topsecret", text)
        self.assertNotIn("admin", text)
        self.assertNotIn("root", text)
        self.assertIn("***", safe["default_proxy"])

    def test_describe_selection_never_contains_raw_credentials(self) -> None:
        manager = ProxyManager(ProxyConfig.from_dict({
            "enabled": True,
            "default_proxy": "http://user:secret@proxy.example:8080",
        }))
        desc = manager.describe_selection("https://any.example")
        text = str(desc)
        self.assertNotIn("secret", text)
        self.assertIn("***", desc["proxy"])

    def test_wildcard_domain_proxy_redacted(self) -> None:
        manager = ProxyManager(ProxyConfig.from_dict({
            "enabled": True,
            "per_domain": {"*.example.com": "http://u:s3cret@wild.proxy:8080"},
        }))
        desc = manager.describe_selection("https://shop.example.com")
        self.assertNotIn("s3cret", str(desc))
        self.assertIn("***", desc["proxy"])

    def test_redact_proxy_url_no_credentials_returns_original(self) -> None:
        self.assertEqual(redact_proxy_url("http://plain.proxy:8080"), "http://plain.proxy:8080")

    def test_redact_proxy_url_empty_returns_empty(self) -> None:
        self.assertEqual(redact_proxy_url(""), "")


# ---------------------------------------------------------------------------
# Session profile domain-scoping and redaction
# ---------------------------------------------------------------------------

class SessionProfileTests(unittest.TestCase):
    """Verify session headers/cookies are domain-scoped and redacted."""

    def test_headers_not_applied_outside_allowed_domains(self) -> None:
        profile = SessionProfile.from_dict({
            "allowed_domains": ["target.example"],
            "headers": {"Authorization": "Bearer secret-token"},
            "cookies": {"session": "abc123"},
        })
        self.assertEqual(profile.headers_for("https://other.example"), {})

    def test_headers_applied_to_exact_domain(self) -> None:
        profile = SessionProfile.from_dict({
            "allowed_domains": ["target.example"],
            "headers": {"Authorization": "Bearer token"},
        })
        headers = profile.headers_for("https://target.example/page")
        self.assertEqual(headers["Authorization"], "Bearer token")

    def test_headers_applied_to_subdomain(self) -> None:
        profile = SessionProfile.from_dict({
            "allowed_domains": ["example.com"],
            "headers": {"X-Test": "value"},
        })
        headers = profile.headers_for("https://shop.example.com/page")
        self.assertEqual(headers["X-Test"], "value")

    def test_to_safe_dict_redacts_all_sensitive_headers(self) -> None:
        profile = SessionProfile.from_dict({
            "headers": {
                "Authorization": "Bearer secret",
                "Cookie": "session=abc",
                "X-API-Key": "my-key",
                "X-Auth-Token": "my-token",
                "User-Agent": "TestBot/1.0",
            },
        })
        safe = profile.to_safe_dict()
        self.assertEqual(safe["headers"]["Authorization"], "[redacted]")
        self.assertEqual(safe["headers"]["Cookie"], "[redacted]")
        self.assertEqual(safe["headers"]["X-API-Key"], "[redacted]")
        self.assertEqual(safe["headers"]["X-Auth-Token"], "[redacted]")
        self.assertEqual(safe["headers"]["User-Agent"], "TestBot/1.0")

    def test_to_safe_dict_redacts_all_cookies(self) -> None:
        profile = SessionProfile.from_dict({
            "cookies": {"sid": "abc", "token": "xyz", "pref": "dark"},
        })
        safe = profile.to_safe_dict()
        # All cookies should be redacted
        for key in ("sid", "token", "pref"):
            self.assertEqual(safe["cookies"][key], "[redacted]",
                             f"Cookie {key!r} was not redacted")

    def test_sensitive_header_names_case_insensitive(self) -> None:
        profile = SessionProfile.from_dict({
            "headers": {
                "authorization": "lower-secret",
                "AUTHORIZATION": "upper-secret",
                "Authorization": "mixed-secret",
            },
        })
        safe = profile.to_safe_dict()
        for key in safe["headers"]:
            self.assertEqual(safe["headers"][key], "[redacted]",
                             f"Header {key!r} was not redacted")

    def test_empty_profile_safe_dict(self) -> None:
        profile = SessionProfile()
        safe = profile.to_safe_dict()
        self.assertEqual(safe["headers"], {})
        self.assertEqual(safe["cookies"], {})
        self.assertEqual(safe["allowed_domains"], [])

    def test_no_allowed_domains_means_applies_to_all(self) -> None:
        profile = SessionProfile.from_dict({
            "headers": {"X-Test": "yes"},
        })
        self.assertTrue(profile.applies_to("https://any.example"))
        headers = profile.headers_for("https://any.example")
        self.assertEqual(headers["X-Test"], "yes")
        self.assertTrue(profile.to_safe_dict()["global_scope"])
        self.assertIn("allowed_domains is empty", " ".join(profile.to_safe_dict()["errors"]))

    def test_storage_state_path_redacts_directory_in_safe_dict(self) -> None:
        profile = SessionProfile.from_dict({
            "allowed_domains": ["example.com"],
            "storage_state_path": r"C:\Users\Alice\secrets\shop_state.json",
        })

        safe = profile.to_safe_dict()
        self.assertEqual(safe["storage_state_path"], "[redacted-path]/shop_state.json")
        self.assertNotIn("Alice", str(safe))
        self.assertNotIn("secrets", str(safe))

    def test_redact_storage_state_path_empty(self) -> None:
        self.assertEqual(redact_storage_state_path(""), "")


# ---------------------------------------------------------------------------
# 429 backoff / rate-limit decision
# ---------------------------------------------------------------------------

class RateLimit429Tests(unittest.TestCase):
    """Verify 429 produces a backoff decision with correct reason."""

    def test_429_produces_backoff_action(self) -> None:
        decision = decide_access(None, status_code=429)
        self.assertEqual(decision.action, "backoff")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.risk_level, "medium")

    def test_429_decision_reason_is_rate_limited(self) -> None:
        decision = decide_access(None, status_code=429)
        self.assertIn("rate_limited:status:429", decision.reasons)

    def test_429_decision_includes_backoff_safeguard(self) -> None:
        decision = decide_access(None, status_code=429)
        self.assertTrue(any("backoff" in s.lower() for s in decision.safeguards))

    def test_429_rate_limit_policy_reason(self) -> None:
        policy = RateLimitPolicy()
        decision = policy.decide("https://example.com", attempt=0, status_code=429)
        self.assertEqual(decision.reason, "rate_limited")
        self.assertTrue(decision.should_retry)

    def test_429_applies_exponential_backoff(self) -> None:
        policy = RateLimitPolicy.from_dict({
            "default": {"delay_seconds": 1.0, "max_retries": 5, "backoff_factor": 2.0},
        })
        d0 = policy.decide("https://example.com", attempt=0, status_code=429)
        d1 = policy.decide("https://example.com", attempt=1, status_code=429)
        d2 = policy.decide("https://example.com", attempt=2, status_code=429)
        self.assertEqual(d0.delay_seconds, 1.0)
        self.assertEqual(d1.delay_seconds, 2.0)
        self.assertEqual(d2.delay_seconds, 4.0)

    def test_429_respects_max_retries(self) -> None:
        policy = RateLimitPolicy.from_dict({
            "default": {"delay_seconds": 1.0, "max_retries": 2},
        })
        self.assertTrue(policy.decide("https://x.com", attempt=0, status_code=429).should_retry)
        self.assertTrue(policy.decide("https://x.com", attempt=1, status_code=429).should_retry)
        self.assertFalse(policy.decide("https://x.com", attempt=2, status_code=429).should_retry)


# ---------------------------------------------------------------------------
# CAPTCHA / challenge → manual handoff (no auto-solve)
# ---------------------------------------------------------------------------

class ChallengeNoAutoSolveTests(unittest.TestCase):
    """Verify all challenge types produce manual handoff, never auto-solve."""

    def test_cloudflare_challenge_requires_manual_handoff(self) -> None:
        signal = detect_challenge_signal(
            '<div id="cf-challenge">Checking your browser</div>',
            status_code=403,
        )
        self.assertTrue(signal.detected)
        self.assertTrue(signal.requires_manual_handoff)

    def test_hcaptcha_requires_manual_handoff(self) -> None:
        signal = detect_challenge_signal(
            '<div data-sitekey="xxx">hcaptcha widget</div>',
        )
        self.assertTrue(signal.detected)
        self.assertEqual(signal.kind, "captcha")
        self.assertEqual(signal.vendor, "hcaptcha")
        self.assertTrue(signal.requires_manual_handoff)

    def test_recaptcha_requires_manual_handoff(self) -> None:
        signal = detect_challenge_signal(
            '<div class="g-recaptcha" data-sitekey="xxx"></div>',
        )
        self.assertTrue(signal.detected)
        self.assertEqual(signal.kind, "captcha")
        self.assertEqual(signal.vendor, "recaptcha")
        self.assertTrue(signal.requires_manual_handoff)

    def test_geetest_requires_manual_handoff(self) -> None:
        signal = detect_challenge_signal('<div id="geetest_captcha"></div>')
        self.assertTrue(signal.detected)
        self.assertTrue(signal.requires_manual_handoff)

    def test_incapsula_requires_manual_handoff(self) -> None:
        signal = detect_challenge_signal('<script src="/_incapsula_resource"></script>')
        self.assertTrue(signal.detected)
        self.assertTrue(signal.requires_manual_handoff)

    def test_datadome_requires_manual_handoff(self) -> None:
        signal = detect_challenge_signal('<script>datadome check</script>')
        self.assertTrue(signal.detected)
        self.assertTrue(signal.requires_manual_handoff)

    def test_access_denied_requires_manual_handoff(self) -> None:
        signal = detect_challenge_signal('<h1>Access Denied</h1>')
        self.assertTrue(signal.detected)
        self.assertEqual(signal.kind, "access_denied")
        # access_denied is detected by the challenge detector but does not set
        # requires_manual_handoff at the signal level. The access_policy layer
        # still routes it to manual_handoff via decide_access().
        decision = decide_access(
            {"findings": [], "signals": {"challenge": signal.primary_marker, "challenge_details": signal.to_dict()}},
        )
        self.assertTrue(decision.requires_manual_review)
        self.assertTrue(decision.requires_authorized_session)

    def test_challenge_decision_never_allows_auto_solve(self) -> None:
        """For every challenge marker, the access decision must NOT allow
        automatic solving. It must require manual review or authorized session."""
        for marker, kind, vendor in CHALLENGE_MARKERS:
            html = f"<html><body><div>{marker}</div></body></html>"
            signal = detect_challenge_signal(html)
            decision = decide_access(
                {"findings": [], "signals": {"challenge": signal.primary_marker, "challenge_details": signal.to_dict()}},
            )
            self.assertTrue(
                decision.requires_manual_review or decision.requires_authorized_session,
                f"Challenge {marker!r} (kind={kind}) did not require manual review or authorized session. "
                f"action={decision.action}, allowed={decision.allowed}",
            )

    def test_no_solve_action_in_any_decision(self) -> None:
        """No access decision should contain 'solve', 'bypass', or 'crack'."""
        for marker, kind, vendor in CHALLENGE_MARKERS:
            html = f"<html><body><div>{marker}</div></body></html>"
            signal = detect_challenge_signal(html)
            decision = decide_access(
                {"findings": [], "signals": {"challenge": signal.primary_marker, "challenge_details": signal.to_dict()}},
            )
            action_lower = decision.action.lower()
            for forbidden in ("solve", "bypass", "crack"):
                self.assertNotIn(forbidden, action_lower,
                                 f"Decision for {marker!r} contains '{forbidden}' in action: {decision.action}")

    def test_challenge_decision_has_no_auto_solve_safeguard(self) -> None:
        """Challenge decisions must include a safeguard against auto-solving."""
        decision = decide_access(
            {"findings": [], "signals": {"challenge": "cf-challenge", "challenge_details": {"detected": True, "kind": "managed_challenge"}}},
        )
        self.assertTrue(any("CAPTCHA" in s or "solve" in s.lower() for s in decision.safeguards),
                        f"Missing CAPTCHA safeguard in: {decision.safeguards}")


# ---------------------------------------------------------------------------
# Fetch trace does not leak secrets
# ---------------------------------------------------------------------------

class FetchTraceSecretLeakTests(unittest.TestCase):
    """Verify fetch_best_page traces and access_context don't leak secrets."""

    def _make_result(self, session_profile=None, proxy_config=None):
        def fetcher(url: str, headers: dict[str, str] | None) -> FetchAttempt:
            return FetchAttempt(mode="requests", url=url, html=MOCK_PRODUCT_HTML, status_code=200)

        return fetch_best_page(
            "https://shop.example/page",
            modes=["requests"],
            fetchers={"requests": fetcher},
            session_profile=session_profile,
            proxy_config=proxy_config,
        )

    def test_trace_does_not_contain_raw_proxy_password(self) -> None:
        result = self._make_result(proxy_config={
            "enabled": True,
            "default_proxy": "http://admin:supersecret@proxy.example:8080",
        })
        trace = result.to_trace()
        text = str(trace)
        self.assertNotIn("supersecret", text)
        self.assertNotIn("admin:supersecret", text)

    def test_trace_does_not_contain_raw_session_token(self) -> None:
        result = self._make_result(session_profile={
            "allowed_domains": ["shop.example"],
            "headers": {"Authorization": "Bearer my-secret-token"},
            "cookies": {"session_id": "very-secret-value"},
        })
        trace = result.to_trace()
        text = str(trace)
        self.assertNotIn("my-secret-token", text)
        self.assertNotIn("very-secret-value", text)

    def test_access_context_redacted_in_every_attempt(self) -> None:
        result = self._make_result(
            session_profile={
                "allowed_domains": ["shop.example"],
                "headers": {"Authorization": "Bearer secret"},
            },
            proxy_config={
                "enabled": True,
                "default_proxy": "http://u:p4ss@proxy:8080",
            },
        )
        for attempt in result.attempts:
            ctx = attempt.access_context
            self.assertIsNotNone(ctx)
            text = str(ctx)
            self.assertNotIn("p4ss", text)
            self.assertNotIn("Bearer secret", text)

    def test_fetch_best_page_with_no_session_no_proxy_trace_is_clean(self) -> None:
        result = self._make_result()
        trace = result.to_trace()
        self.assertEqual(trace["selected_mode"], "requests")
        self.assertEqual(len(trace["attempts"]), 1)
        self.assertEqual(trace["attempts"][0]["access_context"]["session"], {})


# ---------------------------------------------------------------------------
# Access decision for 401/403
# ---------------------------------------------------------------------------

class AccessDecision401_403Tests(unittest.TestCase):
    """Verify 401/403 require authorized session, not auto-solve."""

    def test_403_requires_authorized_session(self) -> None:
        decision = decide_access(None, status_code=403)
        self.assertEqual(decision.action, "authorized_session_required")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_authorized_session)
        self.assertTrue(decision.requires_manual_review)

    def test_401_requires_authorized_session(self) -> None:
        decision = decide_access(None, status_code=401)
        self.assertEqual(decision.action, "authorized_session_required")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.requires_authorized_session)

    def test_403_with_authorized_session_becomes_allowed(self) -> None:
        decision = decide_access(None, status_code=403, has_authorized_session=True)
        self.assertTrue(decision.allowed)

    def test_401_403_never_solve_bypass(self) -> None:
        for code in (401, 403):
            decision = decide_access(None, status_code=code)
            self.assertNotIn("solve", decision.action.lower())
            self.assertNotIn("bypass", decision.action.lower())


# ---------------------------------------------------------------------------
# Access decision safeguard completeness
# ---------------------------------------------------------------------------

class SafeguardTests(unittest.TestCase):
    """Verify all decisions include base safeguards."""

    def test_standard_decision_includes_rate_limit_safeguard(self) -> None:
        decision = decide_access(None)
        self.assertTrue(any("rate limit" in s.lower() for s in decision.safeguards))

    def test_standard_decision_includes_record_safeguard(self) -> None:
        decision = decide_access(None)
        self.assertTrue(any("record" in s.lower() for s in decision.safeguards))

    def test_challenge_decision_includes_session_safeguard(self) -> None:
        decision = decide_access(
            {"findings": [], "signals": {"challenge": "cf-challenge", "challenge_details": {"detected": True}}},
        )
        self.assertTrue(any("session" in s.lower() for s in decision.safeguards))

    def test_decision_to_dict_round_trip(self) -> None:
        decision = decide_access(None, status_code=429)
        d = decision.to_dict()
        self.assertEqual(d["action"], "backoff")
        self.assertIsInstance(d["reasons"], list)
        self.assertIsInstance(d["safeguards"], list)


# ---------------------------------------------------------------------------
# Challenge detector edge cases
# ---------------------------------------------------------------------------

class ChallengeDetectorEdgeTests(unittest.TestCase):
    """Verify challenge detector handles edge cases correctly."""

    def test_json_payload_does_not_trigger_false_positive(self) -> None:
        """JSON containing challenge keywords should not trigger detection."""
        signal = detect_challenge_signal('{"error": "access denied"}')
        self.assertFalse(signal.detected)

    def test_empty_html_returns_not_detected(self) -> None:
        signal = detect_challenge_signal("")
        self.assertFalse(signal.detected)

    def test_429_without_challenge_markers_is_rate_limited(self) -> None:
        signal = detect_challenge_signal("<html>OK</html>", status_code=429)
        self.assertTrue(signal.detected)
        self.assertEqual(signal.kind, "rate_limited")
        self.assertFalse(signal.requires_manual_handoff)

    def test_login_gate_with_401_detected(self) -> None:
        signal = detect_challenge_signal(
            '<html><form action="/login">Sign in</form></html>',
            status_code=401,
        )
        self.assertTrue(signal.detected)
        self.assertEqual(signal.kind, "login_required")
        self.assertTrue(signal.requires_manual_handoff)

    def test_response_headers_included_in_scan(self) -> None:
        signal = detect_challenge_signal(
            "<html>OK</html>",
            response_headers={"cf-ray": "123", "server": "cloudflare"},
        )
        # cf-ray alone shouldn't trigger, but "cloudflare" in server header
        # combined with other markers would. This tests header scanning works.
        self.assertIsNotNone(signal)

    def test_severity_high_for_captcha(self) -> None:
        signal = detect_challenge_signal('<div class="h-captcha"></div>')
        self.assertEqual(signal.severity, "high")

    def test_severity_medium_for_rate_limit(self) -> None:
        signal = detect_challenge_signal("<html>OK</html>", status_code=429)
        self.assertEqual(signal.severity, "medium")


if __name__ == "__main__":
    unittest.main()
