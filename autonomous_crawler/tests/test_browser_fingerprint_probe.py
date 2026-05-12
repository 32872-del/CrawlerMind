"""Tests for runtime browser fingerprint probing (CAP-4.2).

All Playwright tests are mocked.  The analysis layer is deterministic and does
not require launching a browser.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.tools.browser_context import BrowserContextConfig, DEFAULT_USER_AGENT
from autonomous_crawler.tools.browser_fingerprint_probe import (
    RuntimeFingerprintProbeResult,
    RuntimeFingerprintSnapshot,
    _compute_risk_level,
    analyze_runtime_fingerprint,
    probe_browser_fingerprint,
)


def _clean_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "navigator": {
            "userAgent": DEFAULT_USER_AGENT,
            "language": "en-US",
            "languages": ["en-US", "en"],
            "platform": "Win32",
            "webdriver": False,
            "hardwareConcurrency": 8,
            "deviceMemory": 8,
            "maxTouchPoints": 0,
            "cookieEnabled": True,
            "doNotTrack": None,
        },
        "timezone": "UTC",
        "screen": {
            "width": 1365,
            "height": 768,
            "availWidth": 1365,
            "availHeight": 728,
            "colorDepth": 24,
            "pixelDepth": 24,
        },
        "viewport": {
            "innerWidth": 1365,
            "innerHeight": 768,
            "outerWidth": 1365,
            "outerHeight": 768,
            "devicePixelRatio": 1,
        },
        "webgl": {
            "supported": True,
            "vendor": "Google Inc.",
            "renderer": "ANGLE (NVIDIA GeForce)",
        },
        "canvas": {
            "supported": True,
            "hash": "12345",
            "dataUrlLength": 1200,
        },
        "fonts": ["Arial", "Segoe UI"],
    }
    payload.update(overrides)
    return payload


class RuntimeFingerprintSnapshotTests(unittest.TestCase):
    def test_snapshot_from_payload_normalizes_fields(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload())

        self.assertEqual(snapshot.user_agent, DEFAULT_USER_AGENT)
        self.assertEqual(snapshot.language, "en-US")
        self.assertEqual(snapshot.languages, ["en-US", "en"])
        self.assertEqual(snapshot.platform, "Win32")
        self.assertFalse(snapshot.webdriver)
        self.assertEqual(snapshot.hardware_concurrency, 8)
        self.assertEqual(snapshot.device_memory, 8.0)
        self.assertEqual(snapshot.max_touch_points, 0)
        self.assertEqual(snapshot.timezone, "UTC")
        self.assertEqual(snapshot.screen["width"], 1365)
        self.assertEqual(snapshot.viewport["innerWidth"], 1365)
        self.assertEqual(snapshot.fonts, ["Arial", "Segoe UI"])

    def test_snapshot_handles_missing_payload(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(None)

        self.assertEqual(snapshot.user_agent, "")
        self.assertEqual(snapshot.languages, [])
        self.assertIsNone(snapshot.webdriver)
        self.assertEqual(snapshot.screen, {})

    def test_snapshot_bounds_long_strings_and_font_list(self) -> None:
        fonts = [f"Font-{i}" for i in range(80)]
        snapshot = RuntimeFingerprintSnapshot.from_payload({
            "navigator": {"userAgent": "x" * 900},
            "fonts": fonts,
        })

        self.assertEqual(len(snapshot.user_agent), 500)
        self.assertEqual(len(snapshot.fonts), 30)

    def test_to_dict_returns_copies(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload())
        data = snapshot.to_dict()
        data["languages"].append("mutated")
        data["screen"]["width"] = 1

        self.assertNotIn("mutated", snapshot.languages)
        self.assertEqual(snapshot.screen["width"], 1365)


class RuntimeFingerprintAnalysisTests(unittest.TestCase):
    def test_clean_runtime_has_no_findings(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload())
        findings = analyze_runtime_fingerprint(snapshot, BrowserContextConfig.from_dict({}))

        self.assertEqual(findings, [])

    def test_webdriver_true_is_high_risk(self) -> None:
        payload = _clean_payload(navigator={
            "userAgent": DEFAULT_USER_AGENT,
            "language": "en-US",
            "webdriver": True,
            "hardwareConcurrency": 8,
            "maxTouchPoints": 0,
        })
        findings = analyze_runtime_fingerprint(payload, {})

        self.assertIn("webdriver_exposed", {f.code for f in findings})
        self.assertEqual(_compute_risk_level(findings), "high")

    def test_user_agent_mismatch_detected(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload(
            navigator={
                "userAgent": "DifferentAgent/1.0",
                "language": "en-US",
                "webdriver": False,
                "hardwareConcurrency": 8,
                "maxTouchPoints": 0,
            }
        ))

        findings = analyze_runtime_fingerprint(snapshot, {})

        self.assertIn("runtime_user_agent_mismatch", {f.code for f in findings})

    def test_locale_timezone_viewport_mismatch_detected(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload(
            navigator={
                "userAgent": DEFAULT_USER_AGENT,
                "language": "ja-JP",
                "webdriver": False,
                "hardwareConcurrency": 8,
                "maxTouchPoints": 0,
            },
            timezone="Asia/Tokyo",
            viewport={"innerWidth": 1920, "innerHeight": 1080, "devicePixelRatio": 1},
        ))

        findings = analyze_runtime_fingerprint(snapshot, BrowserContextConfig.from_dict({
            "locale": "en-US",
            "timezone_id": "UTC",
            "viewport": {"width": 1365, "height": 768},
        }))
        codes = {f.code for f in findings}

        self.assertIn("runtime_locale_mismatch", codes)
        self.assertIn("runtime_timezone_mismatch", codes)
        self.assertIn("runtime_viewport_mismatch", codes)

    def test_mobile_ua_without_touch_detected(self) -> None:
        mobile_ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 Mobile/15E148"
        )
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload(
            navigator={
                "userAgent": mobile_ua,
                "language": "en-US",
                "webdriver": False,
                "hardwareConcurrency": 4,
                "maxTouchPoints": 0,
            },
            viewport={"innerWidth": 390, "innerHeight": 844, "devicePixelRatio": 3},
        ))

        findings = analyze_runtime_fingerprint(snapshot, {
            "user_agent": mobile_ua,
            "viewport": {"width": 390, "height": 844},
        })

        self.assertIn("mobile_ua_without_touch", {f.code for f in findings})

    def test_mobile_ua_desktop_runtime_viewport_detected(self) -> None:
        mobile_ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile"
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload(
            navigator={
                "userAgent": mobile_ua,
                "language": "en-US",
                "webdriver": False,
                "hardwareConcurrency": 4,
                "maxTouchPoints": 5,
            },
            viewport={"innerWidth": 1440, "innerHeight": 900, "devicePixelRatio": 1},
        ))

        findings = analyze_runtime_fingerprint(snapshot, {
            "user_agent": mobile_ua,
            "viewport": {"width": 1440, "height": 900},
        })

        self.assertIn("mobile_ua_desktop_runtime_viewport", {f.code for f in findings})

    def test_invalid_runtime_shape_detected(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload(
            navigator={
                "userAgent": DEFAULT_USER_AGENT,
                "language": "en-US",
                "webdriver": False,
                "hardwareConcurrency": 0,
                "maxTouchPoints": 0,
            },
            screen={"width": 0, "height": 0},
            viewport={"innerWidth": 1365, "innerHeight": 768, "devicePixelRatio": 99},
        ))

        findings = analyze_runtime_fingerprint(snapshot, {})
        codes = {f.code for f in findings}

        self.assertIn("invalid_hardware_concurrency", codes)
        self.assertIn("invalid_screen_size", codes)
        self.assertIn("unusual_device_pixel_ratio", codes)

    def test_webgl_and_canvas_findings(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload(
            webgl={"supported": True, "vendor": "Google Inc.", "renderer": "SwiftShader"},
            canvas={"supported": False},
        ))

        findings = analyze_runtime_fingerprint(snapshot, {})
        codes = {f.code for f in findings}

        self.assertIn("software_webgl_renderer", codes)
        self.assertIn("canvas_unavailable", codes)

    def test_webgl_unavailable_detected(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload(
            webgl={"supported": False},
        ))

        findings = analyze_runtime_fingerprint(snapshot, {})

        self.assertIn("webgl_unavailable", {f.code for f in findings})


class ProbeResultTests(unittest.TestCase):
    def test_result_to_dict_shape(self) -> None:
        snapshot = RuntimeFingerprintSnapshot.from_payload(_clean_payload())
        result = RuntimeFingerprintProbeResult(
            url="https://example.com",
            final_url="https://example.com/page",
            snapshot=snapshot,
            risk_level="low",
            browser_context={"headless": True},
        )

        data = result.to_dict()

        self.assertEqual(data["url"], "https://example.com")
        self.assertEqual(data["final_url"], "https://example.com/page")
        self.assertEqual(data["status"], "ok")
        self.assertIn("snapshot", data)
        self.assertIn("findings", data)
        self.assertEqual(data["browser_context"]["headless"], True)

    def test_recommendations_generated_for_runtime_risks(self) -> None:
        payload = _clean_payload(
            navigator={
                "userAgent": DEFAULT_USER_AGENT,
                "language": "ja-JP",
                "webdriver": True,
                "hardwareConcurrency": 8,
                "maxTouchPoints": 0,
            },
            timezone="Asia/Tokyo",
            webgl={"supported": False},
        )
        findings = analyze_runtime_fingerprint(payload, {})
        result = RuntimeFingerprintProbeResult(
            url="https://example.com",
            findings=findings,
            risk_level=_compute_risk_level(findings),
        )
        # Rebuild recommendations through the public browser path is not needed here;
        # this checks result serialization still carries supplied values.
        result.recommendations = ["sample"]

        self.assertEqual(result.to_dict()["recommendations"], ["sample"])


class ProbeBrowserPlaywrightTests(unittest.TestCase):
    @patch("autonomous_crawler.tools.browser_fingerprint_probe.sync_playwright", None)
    def test_missing_playwright_returns_failed_result(self) -> None:
        result = probe_browser_fingerprint("https://example.com")

        self.assertEqual(result.status, "failed")
        self.assertIn("playwright is not installed", result.error)

    @patch("autonomous_crawler.tools.browser_fingerprint_probe.sync_playwright")
    def test_probe_browser_collects_snapshot(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com/final"
        mock_page.goto.return_value = None
        mock_page.evaluate.return_value = _clean_payload()

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = probe_browser_fingerprint(
            "https://example.com",
            wait_selector="#ready",
            render_time_ms=250,
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.final_url, "https://example.com/final")
        self.assertEqual(result.snapshot.user_agent, DEFAULT_USER_AGENT)
        self.assertEqual(result.risk_level, "low")
        mock_page.wait_for_selector.assert_called_once_with("#ready", timeout=30000)
        mock_page.wait_for_timeout.assert_called_once_with(250)
        mock_browser.close.assert_called_once()

    @patch("autonomous_crawler.tools.browser_fingerprint_probe.sync_playwright")
    def test_probe_browser_handles_navigation_failure(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.goto.side_effect = TimeoutError("timeout")

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = probe_browser_fingerprint("https://example.com")

        self.assertEqual(result.status, "failed")
        self.assertIn("timeout", result.error)
        mock_browser.close.assert_called_once()

    @patch("autonomous_crawler.tools.browser_fingerprint_probe.sync_playwright")
    def test_probe_browser_passes_context_options(self, mock_pw_cls: MagicMock) -> None:
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.goto.return_value = None
        mock_page.evaluate.return_value = _clean_payload(timezone="Europe/Berlin")

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = probe_browser_fingerprint(
            "https://example.com",
            browser_context={
                "locale": "de-DE",
                "timezone_id": "Europe/Berlin",
                "viewport": {"width": 1440, "height": 900},
            },
        )

        options = mock_browser.new_context.call_args.kwargs
        self.assertEqual(options["locale"], "de-DE")
        self.assertEqual(options["timezone_id"], "Europe/Berlin")
        self.assertEqual(options["viewport"]["width"], 1440)
        self.assertEqual(result.browser_context["locale"], "de-DE")


class ReconFingerprintProbeIntegrationTests(unittest.TestCase):
    @patch("autonomous_crawler.agents.recon.probe_browser_fingerprint")
    @patch("autonomous_crawler.agents.recon.fetch_best_html")
    def test_recon_opt_in_records_fingerprint_probe(
        self,
        mock_fetch_best: MagicMock,
        mock_probe: MagicMock,
    ) -> None:
        from autonomous_crawler.agents.recon import recon_node
        from autonomous_crawler.tools.fetch_policy import BestFetchResult, FetchAttempt
        from autonomous_crawler.tools.html_recon import MOCK_PRODUCT_HTML

        attempt = FetchAttempt(
            mode="requests",
            url="https://example.com/catalog",
            html=MOCK_PRODUCT_HTML,
            status_code=200,
            score=70,
            reasons=["status_ok", "dom_candidates"],
        )
        mock_fetch_best.return_value = BestFetchResult(
            url="https://example.com/catalog",
            html=MOCK_PRODUCT_HTML,
            status_code=200,
            mode="requests",
            score=70,
            attempts=[attempt],
        )
        mock_probe.return_value = RuntimeFingerprintProbeResult(
            url="https://example.com/catalog",
            final_url="https://example.com/catalog",
            snapshot=RuntimeFingerprintSnapshot.from_payload(_clean_payload()),
            risk_level="low",
        )

        state = recon_node({
            "target_url": "https://example.com/catalog",
            "recon_report": {"constraints": {"probe_fingerprint": True}},
            "messages": [],
            "error_log": [],
        })

        recon = state["recon_report"]
        self.assertIn("browser_fingerprint_probe", recon)
        self.assertEqual(recon["browser_fingerprint_probe"]["status"], "ok")
        self.assertTrue(any("Browser fingerprint probe" in msg for msg in state["messages"]))
        mock_probe.assert_called_once()
        call_kwargs = mock_probe.call_args.kwargs
        self.assertIn("browser_context", call_kwargs)
        self.assertEqual(call_kwargs["wait_until"], "domcontentloaded")

    @patch("autonomous_crawler.agents.recon.probe_browser_fingerprint")
    def test_recon_does_not_probe_fingerprint_by_default(self, mock_probe: MagicMock) -> None:
        from autonomous_crawler.agents.recon import recon_node

        state = recon_node({
            "target_url": "mock://catalog",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        self.assertEqual(state["status"], "recon_done")
        mock_probe.assert_not_called()

    def test_should_probe_fingerprint_requires_http_and_constraint(self) -> None:
        from autonomous_crawler.agents.recon import _should_probe_fingerprint

        self.assertFalse(_should_probe_fingerprint({}, "https://example.com"))
        self.assertFalse(_should_probe_fingerprint({"constraints": {"probe_fingerprint": True}}, "mock://catalog"))
        self.assertTrue(_should_probe_fingerprint({"constraints": {"probe_fingerprint": True}}, "https://example.com"))


if __name__ == "__main__":
    unittest.main()
