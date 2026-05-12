"""Tests for browser_fingerprint — deterministic, no browser launch."""
from __future__ import annotations

import unittest

from autonomous_crawler.tools.browser_context import BrowserContextConfig, DEFAULT_USER_AGENT
from autonomous_crawler.tools.browser_fingerprint import (
    FingerprintFinding,
    FingerprintProfile,
    FingerprintReport,
    _check_consistency,
    _compute_risk_level,
    _extract_profile,
    _is_mobile_ua,
    build_fingerprint_report,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _desktop_config(**overrides: object) -> BrowserContextConfig:
    """Return a realistic desktop BrowserContextConfig with optional overrides."""
    base: dict[str, object] = {
        "user_agent": DEFAULT_USER_AGENT,
        "viewport": {"width": 1365, "height": 768},
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "color_scheme": "light",
        "java_script_enabled": True,
    }
    base.update(overrides)
    return BrowserContextConfig.from_dict(base)


def _mobile_config(**overrides: object) -> BrowserContextConfig:
    """Return a realistic mobile BrowserContextConfig with optional overrides."""
    base: dict[str, object] = {
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.4 Mobile/15E148 Safari/604.1"
        ),
        "viewport": {"width": 390, "height": 844},
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "color_scheme": "light",
        "java_script_enabled": True,
    }
    base.update(overrides)
    return BrowserContextConfig.from_dict(base)


# ── profile extraction ──────────────────────────────────────────────────────

class ProfileExtractionTests(unittest.TestCase):
    def test_extracts_all_fields_from_config(self) -> None:
        config = _desktop_config(
            locale="de-DE",
            timezone_id="Europe/Berlin",
            color_scheme="dark",
            java_script_enabled=False,
            proxy_url="http://user:pass@proxy.example:8080",
            storage_state_path="state.json",
            headless=False,
        )
        profile = _extract_profile(config)

        self.assertEqual(profile.user_agent, DEFAULT_USER_AGENT)
        self.assertEqual(profile.viewport_width, 1365)
        self.assertEqual(profile.viewport_height, 768)
        self.assertEqual(profile.locale, "de-DE")
        self.assertEqual(profile.timezone_id, "Europe/Berlin")
        self.assertEqual(profile.color_scheme, "dark")
        self.assertFalse(profile.java_script_enabled)
        self.assertTrue(profile.proxy_present)
        self.assertIn("***", profile.proxy_redacted)
        self.assertNotIn("pass", profile.proxy_redacted)
        self.assertTrue(profile.storage_state_present)
        self.assertFalse(profile.headless)

    def test_defaults_when_no_optional_fields(self) -> None:
        config = BrowserContextConfig.from_dict({})
        profile = _extract_profile(config)

        self.assertFalse(profile.proxy_present)
        self.assertEqual(profile.proxy_redacted, "")
        self.assertFalse(profile.storage_state_present)

    def test_to_dict_round_trip(self) -> None:
        config = _desktop_config()
        profile = _extract_profile(config)
        d = profile.to_dict()

        self.assertIn("user_agent", d)
        self.assertIn("viewport", d)
        self.assertEqual(d["viewport"]["width"], 1365)
        self.assertIn("locale", d)
        self.assertIn("proxy_present", d)


# ── mobile UA detection ────────────────────────────────────────────────────

class MobileUaDetectionTests(unittest.TestCase):
    def test_iphone_is_mobile(self) -> None:
        self.assertTrue(_is_mobile_ua("Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 ...)"))

    def test_android_is_mobile(self) -> None:
        self.assertTrue(_is_mobile_ua("Mozilla/5.0 (Linux; Android 14; Pixel 8) ..."))

    def test_chrome_desktop_is_not_mobile(self) -> None:
        self.assertFalse(_is_mobile_ua(DEFAULT_USER_AGENT))

    def test_empty_ua_is_not_mobile(self) -> None:
        self.assertFalse(_is_mobile_ua(""))

    def test_ipad_is_mobile(self) -> None:
        self.assertTrue(_is_mobile_ua("Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) ..."))


# ── UA / viewport mismatch ─────────────────────────────────────────────────

class UaViewportMismatchTests(unittest.TestCase):
    def test_mobile_ua_desktop_viewport(self) -> None:
        config = _mobile_config(viewport={"width": 1920, "height": 1080})
        report = build_fingerprint_report(config)

        codes = [f.code for f in report.findings]
        self.assertIn("ua_viewport_mismatch", codes)
        finding = next(f for f in report.findings if f.code == "ua_viewport_mismatch")
        self.assertEqual(finding.severity, "high")
        self.assertIn("1920", finding.message)

    def test_desktop_ua_mobile_viewport(self) -> None:
        config = _desktop_config(viewport={"width": 375, "height": 667})
        report = build_fingerprint_report(config)

        codes = [f.code for f in report.findings]
        self.assertIn("ua_viewport_mismatch", codes)
        finding = next(f for f in report.findings if f.code == "ua_viewport_mismatch")
        self.assertEqual(finding.severity, "high")

    def test_mobile_ua_mobile_viewport_no_mismatch(self) -> None:
        config = _mobile_config(viewport={"width": 390, "height": 844})
        report = build_fingerprint_report(config)

        codes = [f.code for f in report.findings]
        self.assertNotIn("ua_viewport_mismatch", codes)

    def test_desktop_ua_desktop_viewport_no_mismatch(self) -> None:
        config = _desktop_config(viewport={"width": 1440, "height": 900})
        report = build_fingerprint_report(config)

        codes = [f.code for f in report.findings]
        self.assertNotIn("ua_viewport_mismatch", codes)

    def test_empty_ua_skips_viewport_check(self) -> None:
        config = BrowserContextConfig.from_dict({"user_agent": "", "viewport": {"width": 1920, "height": 1080}})
        report = build_fingerprint_report(config)

        codes = [f.code for f in report.findings]
        self.assertNotIn("ua_viewport_mismatch", codes)

    def test_mobile_ua_borderline_width_no_mismatch(self) -> None:
        # 1024 is the boundary; only > 1024 triggers
        config = _mobile_config(viewport={"width": 1024, "height": 768})
        report = build_fingerprint_report(config)

        codes = [f.code for f in report.findings]
        self.assertNotIn("ua_viewport_mismatch", codes)

    def test_desktop_ua_borderline_width_no_mismatch(self) -> None:
        # 800 is the boundary; only < 800 triggers
        config = _desktop_config(viewport={"width": 800, "height": 600})
        report = build_fingerprint_report(config)

        codes = [f.code for f in report.findings]
        self.assertNotIn("ua_viewport_mismatch", codes)


# ── locale / timezone mismatch ─────────────────────────────────────────────

class LocaleTimezoneMismatchTests(unittest.TestCase):
    def test_utc_timezone_non_english_locale(self) -> None:
        config = _desktop_config(locale="de-DE", timezone_id="UTC")
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "locale_timezone_mismatch"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "low")
        self.assertIn("UTC", findings[0].message)

    def test_english_locale_utc_timezone_no_finding(self) -> None:
        config = _desktop_config(locale="en", timezone_id="UTC")
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "locale_timezone_mismatch"]
        self.assertEqual(len(findings), 0)

    def test_known_mapping_violation(self) -> None:
        config = _desktop_config(locale="ja-JP", timezone_id="America/New_York")
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "locale_timezone_mismatch"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "medium")
        self.assertIn("ja-JP", findings[0].message)
        self.assertIn("Asia/Tokyo", findings[0].message)

    def test_matching_locale_timezone_no_finding(self) -> None:
        config = _desktop_config(locale="de-DE", timezone_id="Europe/Berlin")
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "locale_timezone_mismatch"]
        self.assertEqual(len(findings), 0)

    def test_zh_locale_hong_kong_timezone_ok(self) -> None:
        config = _desktop_config(locale="zh-CN", timezone_id="Asia/Hong_Kong")
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "locale_timezone_mismatch"]
        self.assertEqual(len(findings), 0)

    def test_unknown_locale_no_timezone_finding(self) -> None:
        config = _desktop_config(locale="xx-YY", timezone_id="Europe/Berlin")
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "locale_timezone_mismatch"]
        self.assertEqual(len(findings), 0)


# ── default UA with custom profile ─────────────────────────────────────────

class DefaultUaCustomProfileTests(unittest.TestCase):
    def test_default_ua_with_two_custom_fields(self) -> None:
        config = _desktop_config(locale="de-DE", timezone_id="Europe/Berlin")
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "default_ua_custom_profile"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "medium")
        self.assertIn("locale", findings[0].message)
        self.assertIn("timezone", findings[0].message)

    def test_default_ua_with_only_one_custom_field_no_finding(self) -> None:
        # _desktop_config sets timezone_id="America/New_York" (non-default),
        # so only changing locale still counts as two custom fields.
        # Use a truly minimal config to get only one custom field.
        config = BrowserContextConfig.from_dict({"locale": "de-DE"})
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "default_ua_custom_profile"]
        self.assertEqual(len(findings), 0)

    def test_custom_ua_no_finding(self) -> None:
        config = _desktop_config(
            user_agent="CustomBot/1.0",
            locale="de-DE",
            timezone_id="Europe/Berlin",
        )
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "default_ua_custom_profile"]
        self.assertEqual(len(findings), 0)

    def test_default_ua_with_proxy_and_viewport_custom(self) -> None:
        config = _desktop_config(
            viewport={"width": 1920, "height": 1080},
            proxy_url="http://proxy.example:8080",
        )
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "default_ua_custom_profile"]
        self.assertEqual(len(findings), 1)


# ── proxy with defaults ────────────────────────────────────────────────────

class ProxyWithDefaultsTests(unittest.TestCase):
    def test_proxy_with_default_locale_and_timezone(self) -> None:
        config = BrowserContextConfig.from_dict({
            "proxy_url": "http://proxy.example:8080",
            "locale": "en-US",
            "timezone_id": "UTC",
        })
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "proxy_default_locale_tz"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "low")
        self.assertIn("locale", findings[0].message)
        self.assertIn("timezone", findings[0].message)

    def test_proxy_with_custom_locale_no_finding(self) -> None:
        config = BrowserContextConfig.from_dict({
            "proxy_url": "http://proxy.example:8080",
            "locale": "de-DE",
            "timezone_id": "Europe/Berlin",
        })
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "proxy_default_locale_tz"]
        self.assertEqual(len(findings), 0)

    def test_no_proxy_no_finding(self) -> None:
        config = _desktop_config()
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "proxy_default_locale_tz"]
        self.assertEqual(len(findings), 0)

    def test_proxy_with_only_default_timezone(self) -> None:
        config = BrowserContextConfig.from_dict({
            "proxy_url": "http://proxy.example:8080",
            "locale": "de-DE",
            "timezone_id": "UTC",
        })
        report = build_fingerprint_report(config)

        findings = [f for f in report.findings if f.code == "proxy_default_locale_tz"]
        self.assertEqual(len(findings), 1)
        # The variable part says "timezone is left at default"
        self.assertIn("timezone is left at default", findings[0].message)
        self.assertNotIn("locale and timezone", findings[0].message)


# ── risk level ─────────────────────────────────────────────────────────────

class RiskLevelTests(unittest.TestCase):
    def test_no_findings_low_risk(self) -> None:
        self.assertEqual(_compute_risk_level([]), "low")

    def test_low_findings_only(self) -> None:
        findings = [FingerprintFinding(code="x", severity="low", message="m")]
        self.assertEqual(_compute_risk_level(findings), "low")

    def test_medium_finding(self) -> None:
        findings = [
            FingerprintFinding(code="x", severity="low", message="m"),
            FingerprintFinding(code="y", severity="medium", message="m"),
        ]
        self.assertEqual(_compute_risk_level(findings), "medium")

    def test_high_finding(self) -> None:
        findings = [
            FingerprintFinding(code="x", severity="medium", message="m"),
            FingerprintFinding(code="y", severity="high", message="m"),
        ]
        self.assertEqual(_compute_risk_level(findings), "high")

    def test_consistent_profile_low_risk(self) -> None:
        config = _desktop_config(timezone_id="America/New_York")
        report = build_fingerprint_report(config)
        self.assertEqual(report.risk_level, "low")

    def test_inconsistent_profile_high_risk(self) -> None:
        config = _mobile_config(viewport={"width": 1920, "height": 1080})
        report = build_fingerprint_report(config)
        self.assertEqual(report.risk_level, "high")


# ── recommendations ────────────────────────────────────────────────────────

class RecommendationTests(unittest.TestCase):
    def test_no_findings_no_recommendations(self) -> None:
        report = build_fingerprint_report(_desktop_config(timezone_id="America/New_York"))
        self.assertEqual(report.recommendations, [])

    def test_ua_viewport_recommendation(self) -> None:
        config = _mobile_config(viewport={"width": 1920, "height": 1080})
        report = build_fingerprint_report(config)
        self.assertTrue(any("Align user-agent" in r for r in report.recommendations))

    def test_locale_timezone_recommendation(self) -> None:
        config = _desktop_config(locale="ja-JP", timezone_id="America/New_York")
        report = build_fingerprint_report(config)
        self.assertTrue(any("timezone" in r.lower() for r in report.recommendations))

    def test_default_ua_recommendation(self) -> None:
        config = _desktop_config(locale="de-DE", timezone_id="Europe/Berlin")
        report = build_fingerprint_report(config)
        self.assertTrue(any("custom user-agent" in r.lower() for r in report.recommendations))

    def test_proxy_recommendation(self) -> None:
        config = BrowserContextConfig.from_dict({
            "proxy_url": "http://proxy.example:8080",
        })
        report = build_fingerprint_report(config)
        self.assertTrue(any("proxy" in r.lower() for r in report.recommendations))

    def test_no_duplicate_recommendations(self) -> None:
        # Two ua_viewport_mismatch findings should produce one recommendation
        config = _mobile_config(viewport={"width": 1920, "height": 1080})
        report = build_fingerprint_report(config)
        ua_recs = [r for r in report.recommendations if "Align user-agent" in r]
        self.assertEqual(len(ua_recs), 1)


# ── report serialization ───────────────────────────────────────────────────

class ReportSerializationTests(unittest.TestCase):
    def test_to_dict_structure(self) -> None:
        config = _mobile_config(viewport={"width": 1920, "height": 1080})
        report = build_fingerprint_report(config)
        d = report.to_dict()

        self.assertIn("profile", d)
        self.assertIn("findings", d)
        self.assertIn("risk_level", d)
        self.assertIn("recommendations", d)
        self.assertIsInstance(d["findings"], list)
        self.assertIsInstance(d["recommendations"], list)

    def test_finding_to_dict(self) -> None:
        finding = FingerprintFinding(code="test", severity="low", message="msg")
        d = finding.to_dict()
        self.assertEqual(d["code"], "test")
        self.assertEqual(d["severity"], "low")
        self.assertEqual(d["message"], "msg")

    def test_fingerprint_profile_to_dict(self) -> None:
        profile = _extract_profile(_desktop_config())
        d = profile.to_dict()
        self.assertIn("user_agent", d)
        self.assertIn("viewport", d)
        self.assertIn("proxy_present", d)


# ── build_fingerprint_report entry point ────────────────────────────────────

class BuildReportTests(unittest.TestCase):
    def test_accepts_browser_context_config(self) -> None:
        config = _desktop_config()
        report = build_fingerprint_report(config)
        self.assertIsInstance(report, FingerprintReport)
        self.assertEqual(report.profile.user_agent, DEFAULT_USER_AGENT)

    def test_accepts_dict(self) -> None:
        report = build_fingerprint_report({
            "user_agent": "TestAgent/1.0",
            "viewport": {"width": 800, "height": 600},
            "locale": "en-US",
            "timezone_id": "UTC",
        })
        self.assertIsInstance(report, FingerprintReport)
        self.assertEqual(report.profile.user_agent, "TestAgent/1.0")

    def test_accepts_none(self) -> None:
        report = build_fingerprint_report(None)
        self.assertIsInstance(report, FingerprintReport)
        self.assertEqual(report.profile.user_agent, DEFAULT_USER_AGENT)

    def test_frozen_config_does_not_mutate(self) -> None:
        config = _desktop_config()
        _ = build_fingerprint_report(config)
        # Config should still be usable — frozen prevents mutation anyway
        self.assertEqual(config.user_agent, DEFAULT_USER_AGENT)


# ── combined scenarios ─────────────────────────────────────────────────────

class CombinedScenarioTests(unittest.TestCase):
    def test_clean_desktop_profile_no_findings(self) -> None:
        config = _desktop_config(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        report = build_fingerprint_report(config)
        self.assertEqual(report.findings, [])
        self.assertEqual(report.risk_level, "low")
        self.assertEqual(report.recommendations, [])

    def test_clean_mobile_profile_no_findings(self) -> None:
        config = _mobile_config(viewport={"width": 390, "height": 844})
        report = build_fingerprint_report(config)
        self.assertEqual(report.findings, [])
        self.assertEqual(report.risk_level, "low")

    def test_maximally_inconsistent_profile(self) -> None:
        """Mobile UA + desktop viewport + locale/timezone mismatch + proxy defaults."""
        config = BrowserContextConfig.from_dict({
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X)",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "ja-JP",
            "timezone_id": "UTC",
            "proxy_url": "http://proxy.example:8080",
        })
        report = build_fingerprint_report(config)

        self.assertEqual(report.risk_level, "high")
        codes = {f.code for f in report.findings}
        self.assertIn("ua_viewport_mismatch", codes)
        self.assertIn("locale_timezone_mismatch", codes)
        self.assertIn("proxy_default_locale_tz", codes)
        self.assertTrue(len(report.recommendations) >= 3)

    def test_custom_profile_with_all_fields_consistent(self) -> None:
        config = BrowserContextConfig.from_dict({
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
            "viewport": {"width": 1440, "height": 900},
            "locale": "de-DE",
            "timezone_id": "Europe/Berlin",
            "color_scheme": "dark",
            "proxy_url": "http://proxy.example:8080",
        })
        report = build_fingerprint_report(config)
        self.assertEqual(report.risk_level, "low")


if __name__ == "__main__":
    unittest.main()
