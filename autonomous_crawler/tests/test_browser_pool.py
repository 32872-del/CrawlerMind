"""Tests for CLM-native browser context pool (SCRAPLING-ABSORB-2F/2G/2H).

Validates context leasing, persistent session reuse, profile pool support,
mark_failed quarantine, pool event tracking, browser profile rotation, and
profile evidence without requiring Playwright or public network access.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from autonomous_crawler.runtime.browser_pool import (
    BrowserContextLease,
    BrowserPoolConfig,
    BrowserPoolManager,
    BrowserProfile,
    BrowserProfileRotator,
)


# ---------------------------------------------------------------------------
# BrowserPoolConfig
# ---------------------------------------------------------------------------


class BrowserPoolConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        config = BrowserPoolConfig()
        self.assertEqual(config.max_contexts, 8)
        self.assertEqual(config.max_requests_per_context, 50)
        self.assertEqual(config.max_context_age_seconds, 1800)
        self.assertTrue(config.keepalive_on_release)

    def test_from_dict_with_empty(self) -> None:
        config = BrowserPoolConfig.from_dict(None)
        self.assertEqual(config.max_contexts, 8)

    def test_from_dict_with_dict(self) -> None:
        config = BrowserPoolConfig.from_dict({
            "max_contexts": 4,
            "max_requests_per_context": 100,
            "keepalive_on_release": False,
        })
        self.assertEqual(config.max_contexts, 4)
        self.assertEqual(config.max_requests_per_context, 100)
        self.assertFalse(config.keepalive_on_release)

    def test_from_dict_passthrough_instance(self) -> None:
        original = BrowserPoolConfig(max_contexts=2)
        config = BrowserPoolConfig.from_dict(original)
        self.assertIs(config, original)

    def test_from_dict_bounds_clamping(self) -> None:
        config = BrowserPoolConfig.from_dict({"max_contexts": 0, "max_requests_per_context": 999999})
        self.assertEqual(config.max_contexts, 1)
        self.assertEqual(config.max_requests_per_context, 10000)

    def test_to_safe_dict(self) -> None:
        config = BrowserPoolConfig(max_contexts=4)
        safe = config.to_safe_dict()
        self.assertEqual(safe["max_contexts"], 4)
        self.assertEqual(safe["max_requests_per_context"], 50)


# ---------------------------------------------------------------------------
# BrowserContextLease
# ---------------------------------------------------------------------------


class BrowserContextLeaseTests(unittest.TestCase):
    def test_record_use_increments_count(self) -> None:
        lease = BrowserContextLease(profile_id="p1", context=MagicMock())
        self.assertEqual(lease.request_count, 0)
        lease.record_use()
        self.assertEqual(lease.request_count, 1)
        lease.record_use()
        self.assertEqual(lease.request_count, 2)

    def test_age_seconds(self) -> None:
        lease = BrowserContextLease(profile_id="p1", context=MagicMock())
        self.assertGreaterEqual(lease.age_seconds(), 0)

    def test_export_storage_state_calls_context(self) -> None:
        mock_context = MagicMock()
        lease = BrowserContextLease(profile_id="p1", context=mock_context)

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "state.json")
            result = lease.export_storage_state(path)
            self.assertEqual(result, path)
            mock_context.storage_state.assert_called_once_with(path=path)

    def test_export_storage_state_empty_path(self) -> None:
        lease = BrowserContextLease(profile_id="p1", context=MagicMock())
        result = lease.export_storage_state("")
        self.assertEqual(result, "")
        lease.context.storage_state.assert_not_called()

    def test_export_storage_state_handles_error(self) -> None:
        mock_context = MagicMock()
        mock_context.storage_state.side_effect = RuntimeError("closed")
        lease = BrowserContextLease(profile_id="p1", context=mock_context)
        result = lease.export_storage_state("/tmp/state.json")
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# BrowserPoolManager - fingerprint
# ---------------------------------------------------------------------------


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_deterministic(self) -> None:
        pool = BrowserPoolManager()
        fp1 = pool.compute_fingerprint(
            context_options={"user_agent": "Test/1.0", "locale": "en-US", "viewport": {"width": 1024, "height": 768}},
            launch_options={"headless": True},
            session_mode="ephemeral",
        )
        fp2 = pool.compute_fingerprint(
            context_options={"user_agent": "Test/1.0", "locale": "en-US", "viewport": {"width": 1024, "height": 768}},
            launch_options={"headless": True},
            session_mode="ephemeral",
        )
        self.assertEqual(fp1, fp2)

    def test_fingerprint_differs_by_locale(self) -> None:
        pool = BrowserPoolManager()
        fp_en = pool.compute_fingerprint(
            context_options={"locale": "en-US", "user_agent": "", "viewport": "", "timezone_id": "", "color_scheme": "", "java_script_enabled": ""},
            launch_options={"headless": True, "proxy": "", "channel": "", "executable_path": "", "args": []},
            session_mode="ephemeral",
        )
        fp_de = pool.compute_fingerprint(
            context_options={"locale": "de-DE", "user_agent": "", "viewport": "", "timezone_id": "", "color_scheme": "", "java_script_enabled": ""},
            launch_options={"headless": True, "proxy": "", "channel": "", "executable_path": "", "args": []},
            session_mode="ephemeral",
        )
        self.assertNotEqual(fp_en, fp_de)

    def test_fingerprint_differs_by_session_mode(self) -> None:
        pool = BrowserPoolManager()
        ctx = {"user_agent": "T", "viewport": "", "locale": "", "timezone_id": "", "color_scheme": "", "java_script_enabled": ""}
        launch = {"headless": True, "proxy": "", "channel": "", "executable_path": "", "args": []}
        fp_ephemeral = pool.compute_fingerprint(ctx, launch, "ephemeral")
        fp_persistent = pool.compute_fingerprint(ctx, launch, "persistent", "/tmp/profile")
        self.assertNotEqual(fp_ephemeral, fp_persistent)

    def test_fingerprint_short_and_hex(self) -> None:
        pool = BrowserPoolManager()
        fp = pool.compute_fingerprint({}, {}, "ephemeral")
        self.assertEqual(len(fp), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in fp))


# ---------------------------------------------------------------------------
# BrowserPoolManager - acquire / release
# ---------------------------------------------------------------------------


class PoolAcquireReleaseTests(unittest.TestCase):
    def test_acquire_creates_new_lease(self) -> None:
        pool = BrowserPoolManager()
        lease = pool.acquire("profile-1", "fp1", "ephemeral")
        self.assertEqual(lease.profile_id, "profile-1")
        self.assertEqual(lease.fingerprint, "fp1")
        self.assertEqual(lease.request_count, 0)
        self.assertIsNone(lease.context)

    def test_acquire_reuses_matching_fingerprint(self) -> None:
        pool = BrowserPoolManager()
        lease1 = pool.acquire("profile-1", "fp1", "ephemeral")
        lease1.context = MagicMock()
        lease2 = pool.acquire("profile-1", "fp1", "ephemeral")
        self.assertIs(lease1, lease2)

    def test_acquire_creates_new_on_fingerprint_mismatch(self) -> None:
        pool = BrowserPoolManager()
        lease1 = pool.acquire("profile-1", "fp1", "ephemeral")
        lease1.context = MagicMock()
        lease2 = pool.acquire("profile-1", "fp2", "ephemeral")
        self.assertIsNot(lease1, lease2)
        self.assertEqual(pool.active_count, 1)

    def test_acquire_reuses_without_counting_completed_use(self) -> None:
        pool = BrowserPoolManager()
        lease1 = pool.acquire("profile-1", "fp1", "ephemeral")
        lease1.context = MagicMock()
        pool.acquire("profile-1", "fp1", "ephemeral")
        self.assertEqual(lease1.request_count, 0)

    def test_release_closes_when_keepalive_off(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=False))
        mock_context = MagicMock()
        lease = pool.acquire("profile-1", "fp1", "ephemeral")
        lease.context = mock_context
        pool.release("profile-1")
        mock_context.close.assert_called_once()
        self.assertEqual(pool.active_count, 0)

    def test_release_keeps_alive_when_healthy(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        mock_context = MagicMock()
        lease = pool.acquire("profile-1", "fp1", "ephemeral")
        lease.context = mock_context
        pool.release("profile-1")
        mock_context.close.assert_not_called()
        self.assertEqual(pool.active_count, 1)

    def test_release_noop_for_missing_profile(self) -> None:
        pool = BrowserPoolManager()
        pool.release("nonexistent")

    def test_close_all(self) -> None:
        pool = BrowserPoolManager()
        c1 = MagicMock()
        c2 = MagicMock()
        l1 = pool.acquire("p1", "fp1", "ephemeral")
        l1.context = c1
        l2 = pool.acquire("p2", "fp2", "ephemeral")
        l2.context = c2
        pool.close_all()
        c1.close.assert_called_once()
        c2.close.assert_called_once()
        self.assertEqual(pool.active_count, 0)

    def test_close_all_handles_close_error(self) -> None:
        pool = BrowserPoolManager()
        mock_context = MagicMock()
        mock_context.close.side_effect = RuntimeError("already closed")
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = mock_context
        pool.close_all()
        self.assertEqual(pool.active_count, 0)


# ---------------------------------------------------------------------------
# BrowserPoolManager - eviction
# ---------------------------------------------------------------------------


class PoolEvictionTests(unittest.TestCase):
    def test_eviction_when_full(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(max_contexts=2))
        pool.acquire("p1", "fp1", "ephemeral")
        time.sleep(0.01)
        pool.acquire("p2", "fp2", "ephemeral")
        time.sleep(0.01)
        pool.acquire("p3", "fp3", "ephemeral")
        self.assertEqual(pool.active_count, 2)

    def test_eviction_removes_oldest(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(max_contexts=2))
        l1 = pool.acquire("p1", "fp1", "ephemeral")
        l1.context = MagicMock()
        time.sleep(0.01)
        l2 = pool.acquire("p2", "fp2", "ephemeral")
        l2.context = MagicMock()
        time.sleep(0.01)
        l3 = pool.acquire("p3", "fp3", "ephemeral")
        l3.context = MagicMock()
        self.assertEqual(pool.active_count, 2)
        l1.context.close.assert_called_once()

    def test_max_requests_per_context_triggers_eviction(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(max_requests_per_context=2))
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        lease.record_use()
        lease.record_use()
        new_lease = pool.acquire("p1", "fp1", "ephemeral")
        self.assertIsNot(lease, new_lease)

    def test_max_age_triggers_eviction(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(max_context_age_seconds=1))
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        lease.created_at = time.time() - 2
        new_lease = pool.acquire("p1", "fp1", "ephemeral")
        self.assertIsNot(lease, new_lease)


# ---------------------------------------------------------------------------
# BrowserPoolManager - safe dict
# ---------------------------------------------------------------------------


class PoolSafeDictTests(unittest.TestCase):
    def test_to_safe_dict(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(max_contexts=4))
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        safe = pool.to_safe_dict()
        self.assertEqual(safe["config"]["max_contexts"], 4)
        self.assertEqual(safe["active_count"], 1)
        self.assertEqual(safe["leases"][0]["profile_id"], "p1")
        self.assertEqual(safe["leases"][0]["fingerprint"], "fp1")

    def test_to_safe_dict_redacts_user_data_dir(self) -> None:
        pool = BrowserPoolManager()
        lease = pool.acquire("p1", "fp1", "persistent", user_data_dir="/tmp/chrome-profile")
        lease.context = MagicMock()
        safe = pool.to_safe_dict()
        self.assertIn("[redacted-path]", safe["leases"][0]["user_data_dir"])
        self.assertNotIn("/tmp", safe["leases"][0]["user_data_dir"])


# ---------------------------------------------------------------------------
# NativeBrowserRuntime pool integration (mocked Playwright)
# ---------------------------------------------------------------------------


class NativeBrowserRuntimePoolTests(unittest.TestCase):
    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_runtime_with_pool_acquires_and_releases(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"pool_id": "test-profile"},
        })
        response = runtime.render(request)

        self.assertTrue(response.ok)
        self.assertEqual(response.engine_result["pool_id"], "test-profile")
        self.assertIsNotNone(response.engine_result["pool"])
        self.assertEqual(pool.active_count, 1)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_pool_reuses_context_across_requests(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"pool_id": "test-profile"},
        })

        runtime.render(request)
        second = runtime.render(request)

        self.assertEqual(pool.active_count, 1)
        self.assertEqual(mock_pw.chromium.launch.call_count, 1)
        self.assertEqual(second.engine_result["pool_request_count"], 2)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_pool_without_pool_id_uses_session(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager()
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        self.assertTrue(response.ok)
        self.assertIsNone(response.engine_result["pool_id"])
        self.assertEqual(pool.active_count, 0)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_pool_persistent_context_reuse(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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
        mock_pw = MagicMock()
        mock_pw.chromium.launch_persistent_context.return_value = mock_context
        mock_pw_cls.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_cls.return_value.__exit__ = MagicMock(return_value=False)

        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        runtime = NativeBrowserRuntime(pool=pool)

        with tempfile.TemporaryDirectory() as tmp:
            udd = str(Path(tmp) / "profile")
            request = RuntimeRequest.from_dict({
                "url": "https://example.com",
                "browser_config": {
                    "pool_id": "persist-profile",
                    "user_data_dir": udd,
                },
            })
            response = runtime.render(request)

        self.assertTrue(response.ok)
        self.assertEqual(response.engine_result["session_mode"], "persistent")
        self.assertEqual(pool.active_count, 1)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_pool_release_on_failure(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"pool_id": "test-profile"},
        })
        response = runtime.render(request)

        self.assertFalse(response.ok)
        self.assertEqual(
            response.engine_result["failure_classification"]["category"],
            "navigation_timeout",
        )

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_runtime_without_pool_has_no_pool_fields(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        runtime = NativeBrowserRuntime()
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        self.assertTrue(response.ok)
        self.assertIsNone(response.engine_result["pool"])


# ---------------------------------------------------------------------------
# BrowserPoolManager - mark_failed (SCRAPLING-ABSORB-2G)
# ---------------------------------------------------------------------------


class PoolMarkFailedTests(unittest.TestCase):
    def test_mark_failed_removes_lease(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        self.assertEqual(pool.active_count, 1)
        pool.mark_failed("p1", error="navigation timeout")
        self.assertEqual(pool.active_count, 0)

    def test_mark_failed_closes_context(self) -> None:
        pool = BrowserPoolManager()
        mock_context = MagicMock()
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = mock_context
        pool.mark_failed("p1", error="crash")
        mock_context.close.assert_called_once()

    def test_mark_failed_closes_browser(self) -> None:
        pool = BrowserPoolManager()
        mock_context = MagicMock()
        mock_browser = MagicMock()
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = mock_context
        lease.browser = mock_browser
        pool.mark_failed("p1", error="crash")
        mock_browser.close.assert_called_once()

    def test_mark_failed_noop_for_missing_profile(self) -> None:
        pool = BrowserPoolManager()
        pool.mark_failed("nonexistent", error="no such profile")

    def test_mark_failed_prevents_reuse(self) -> None:
        pool = BrowserPoolManager()
        lease1 = pool.acquire("p1", "fp1", "ephemeral")
        lease1.context = MagicMock()
        pool.mark_failed("p1", error="bad context")
        lease2 = pool.acquire("p1", "fp1", "ephemeral")
        self.assertIsNot(lease1, lease2)
        self.assertIsNone(lease2.context)

    def test_mark_failed_records_event(self) -> None:
        pool = BrowserPoolManager()
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        pool.mark_failed("p1", error="selector timeout")
        events = [e for e in pool._events if e["type"] == "pool_mark_failed"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["profile_id"], "p1")
        self.assertEqual(events[0]["error"], "selector timeout")

    def test_mark_failed_truncates_error(self) -> None:
        pool = BrowserPoolManager()
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        long_error = "x" * 500
        pool.mark_failed("p1", error=long_error)
        events = [e for e in pool._events if e["type"] == "pool_mark_failed"]
        self.assertEqual(len(events[0]["error"]), 200)


# ---------------------------------------------------------------------------
# BrowserPoolManager - event tracking (SCRAPLING-ABSORB-2G)
# ---------------------------------------------------------------------------


class PoolEventTests(unittest.TestCase):
    def test_acquire_records_event(self) -> None:
        pool = BrowserPoolManager()
        pool.acquire("p1", "fp1", "ephemeral")
        events = [e for e in pool._events if e["type"] == "pool_acquire"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["profile_id"], "p1")
        self.assertEqual(events[0]["fingerprint"], "fp1")
        self.assertIn("timestamp", events[0])

    def test_reuse_records_event(self) -> None:
        pool = BrowserPoolManager()
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        pool.acquire("p1", "fp1", "ephemeral")
        events = [e for e in pool._events if e["type"] == "pool_reuse"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["profile_id"], "p1")

    def test_release_records_event_with_reason(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=False))
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        pool.release("p1")
        events = [e for e in pool._events if e["type"] == "pool_release"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["reason"], "closed")

    def test_release_keepalive_records_event(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        pool.release("p1")
        events = [e for e in pool._events if e["type"] == "pool_release"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["reason"], "keepalive")

    def test_eviction_records_event(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(max_contexts=1))
        pool.acquire("p1", "fp1", "ephemeral")
        time.sleep(0.01)
        pool.acquire("p2", "fp2", "ephemeral")
        events = [e for e in pool._events if e["type"] == "pool_evict"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["profile_id"], "p1")
        self.assertEqual(events[0]["reason"], "pool_full")

    def test_to_safe_dict_includes_events(self) -> None:
        pool = BrowserPoolManager()
        pool.acquire("p1", "fp1", "ephemeral")
        safe = pool.to_safe_dict()
        self.assertIn("events", safe)
        self.assertEqual(len(safe["events"]), 1)
        self.assertEqual(safe["events"][0]["type"], "pool_acquire")

    def test_full_lifecycle_events(self) -> None:
        pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
        lease = pool.acquire("p1", "fp1", "ephemeral")
        lease.context = MagicMock()
        pool.acquire("p1", "fp1", "ephemeral")  # reuse
        pool.release("p1")
        lease2 = pool.acquire("p2", "fp2", "ephemeral")
        lease2.context = MagicMock()
        pool.mark_failed("p2", error="crash")

        event_types = [e["type"] for e in pool._events]
        self.assertEqual(event_types, [
            "pool_acquire", "pool_reuse", "pool_release",
            "pool_acquire", "pool_mark_failed",
        ])


# ---------------------------------------------------------------------------
# NativeBrowserRuntime pool events (SCRAPLING-ABSORB-2G)
# ---------------------------------------------------------------------------


class NativeBrowserRuntimePoolEventTests(unittest.TestCase):
    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_render_emits_pool_acquire_event(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager()
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"pool_id": "test-profile"},
        })
        response = runtime.render(request)

        pool_events = [e for e in response.runtime_events if e.type == "pool_acquire"]
        self.assertEqual(len(pool_events), 1)
        self.assertEqual(pool_events[0].data["pool_id"], "test-profile")

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_render_emits_pool_reuse_event(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager()
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"pool_id": "test-profile"},
        })
        runtime.render(request)
        response2 = runtime.render(request)

        reuse_events = [e for e in response2.runtime_events if e.type == "pool_reuse"]
        self.assertEqual(len(reuse_events), 1)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_render_emits_pool_release_event(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager()
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"pool_id": "test-profile"},
        })
        response = runtime.render(request)

        release_events = [e for e in response.runtime_events if e.type == "pool_release"]
        self.assertEqual(len(release_events), 1)
        self.assertEqual(release_events[0].data["pool_request_count"], 1)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_render_calls_mark_failed_on_exception(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        pool = BrowserPoolManager()
        runtime = NativeBrowserRuntime(pool=pool)
        request = RuntimeRequest.from_dict({
            "url": "https://example.com",
            "browser_config": {"pool_id": "test-profile"},
        })
        response = runtime.render(request)

        self.assertFalse(response.ok)
        self.assertEqual(pool.active_count, 0)
        mark_failed_events = [e for e in response.runtime_events if e.type == "pool_mark_failed"]
        self.assertEqual(len(mark_failed_events), 1)
        self.assertIn("navigation timeout", mark_failed_events[0].data["error"])


# ---------------------------------------------------------------------------
# BrowserProfile (SCRAPLING-ABSORB-2H)
# ---------------------------------------------------------------------------


class BrowserProfileTests(unittest.TestCase):
    def test_from_dict_creates_profile(self) -> None:
        profile = BrowserProfile.from_dict({
            "profile_id": "test-ua",
            "user_agent": "Mozilla/5.0 Test",
            "viewport": "1920x1080",
            "locale": "en-US",
            "timezone": "America/New_York",
        })
        self.assertIsNotNone(profile)
        self.assertEqual(profile.profile_id, "test-ua")
        self.assertEqual(profile.user_agent, "Mozilla/5.0 Test")
        self.assertEqual(profile.viewport, "1920x1080")
        self.assertEqual(profile.locale, "en-US")
        self.assertEqual(profile.timezone, "America/New_York")

    def test_from_dict_none_returns_none(self) -> None:
        self.assertIsNone(BrowserProfile.from_dict(None))

    def test_from_dict_passthrough_instance(self) -> None:
        original = BrowserProfile(profile_id="p1")
        result = BrowserProfile.from_dict(original)
        self.assertIs(result, original)

    def test_from_dict_missing_profile_id_returns_none(self) -> None:
        self.assertIsNone(BrowserProfile.from_dict({"user_agent": "test"}))

    def test_defaults(self) -> None:
        profile = BrowserProfile(profile_id="p1")
        self.assertEqual(profile.locale, "en-US")
        self.assertEqual(profile.timezone, "UTC")
        self.assertEqual(profile.color_scheme, "light")
        self.assertEqual(profile.storage_state_mode, "ephemeral")
        self.assertFalse(profile.protected_mode)
        self.assertTrue(profile.headless)

    def test_to_context_options(self) -> None:
        profile = BrowserProfile(
            profile_id="p1",
            user_agent="Test/1.0",
            viewport="1280x720",
            locale="de-DE",
            timezone="Europe/Berlin",
            color_scheme="dark",
        )
        opts = profile.to_context_options()
        self.assertEqual(opts["user_agent"], "Test/1.0")
        self.assertEqual(opts["viewport"], {"width": 1280, "height": 720})
        self.assertEqual(opts["locale"], "de-DE")
        self.assertEqual(opts["timezone_id"], "Europe/Berlin")
        self.assertEqual(opts["color_scheme"], "dark")

    def test_to_context_options_empty_viewport(self) -> None:
        profile = BrowserProfile(profile_id="p1", viewport="")
        opts = profile.to_context_options()
        self.assertIsNone(opts["viewport"])

    def test_to_launch_options(self) -> None:
        profile = BrowserProfile(
            profile_id="p1",
            headless=False,
            channel="chrome",
            proxy_url="http://proxy:8080",
        )
        opts = profile.to_launch_options()
        self.assertFalse(opts["headless"])
        self.assertEqual(opts["channel"], "chrome")
        self.assertEqual(opts["proxy"], "http://proxy:8080")

    def test_to_launch_options_protected_mode(self) -> None:
        profile = BrowserProfile(profile_id="p1", protected_mode=True)
        opts = profile.to_launch_options()
        self.assertIn("--disable-blink-features=AutomationControlled", opts.get("args", []))

    def test_to_safe_dict(self) -> None:
        profile = BrowserProfile(
            profile_id="p1",
            user_agent="Test/1.0",
            viewport="1920x1080",
            proxy_url="http://secret:pass@proxy:8080",
        )
        safe = profile.to_safe_dict()
        self.assertEqual(safe["profile_id"], "p1")
        self.assertEqual(safe["user_agent"], "Test/1.0")
        self.assertTrue(safe["has_proxy"])
        self.assertNotIn("secret", str(safe))
        self.assertNotIn("pass", str(safe))

    def test_to_safe_dict_truncates_long_user_agent(self) -> None:
        profile = BrowserProfile(profile_id="p1", user_agent="A" * 200)
        safe = profile.to_safe_dict()
        self.assertIn("...", safe["user_agent"])
        self.assertLessEqual(len(safe["user_agent"]), 85)

    def test_frozen(self) -> None:
        profile = BrowserProfile(profile_id="p1")
        with self.assertRaises(AttributeError):
            profile.profile_id = "p2"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BrowserProfileRotator (SCRAPLING-ABSORB-2H)
# ---------------------------------------------------------------------------


class BrowserProfileRotatorTests(unittest.TestCase):
    def test_round_robin_rotation(self) -> None:
        p1 = BrowserProfile(profile_id="p1", user_agent="UA-1")
        p2 = BrowserProfile(profile_id="p2", user_agent="UA-2")
        p3 = BrowserProfile(profile_id="p3", user_agent="UA-3")
        rotator = BrowserProfileRotator([p1, p2, p3])

        self.assertEqual(rotator.next_profile().profile_id, "p1")
        self.assertEqual(rotator.next_profile().profile_id, "p2")
        self.assertEqual(rotator.next_profile().profile_id, "p3")
        self.assertEqual(rotator.next_profile().profile_id, "p1")  # wraps

    def test_from_dict_list(self) -> None:
        rotator = BrowserProfileRotator([
            {"profile_id": "a", "user_agent": "UA-A"},
            {"profile_id": "b", "user_agent": "UA-B"},
        ])
        self.assertEqual(rotator.profile_count, 2)
        self.assertEqual(rotator.next_profile().profile_id, "a")

    def test_empty_rotator(self) -> None:
        rotator = BrowserProfileRotator([])
        self.assertIsNone(rotator.next_profile())
        self.assertEqual(rotator.profile_count, 0)

    def test_current_profile(self) -> None:
        p1 = BrowserProfile(profile_id="p1")
        p2 = BrowserProfile(profile_id="p2")
        rotator = BrowserProfileRotator([p1, p2])

        rotator.next_profile()
        self.assertEqual(rotator.current_profile().profile_id, "p1")
        rotator.next_profile()
        self.assertEqual(rotator.current_profile().profile_id, "p2")

    def test_to_safe_dict(self) -> None:
        rotator = BrowserProfileRotator([
            BrowserProfile(profile_id="p1", user_agent="UA-1"),
            BrowserProfile(profile_id="p2", user_agent="UA-2"),
        ])
        rotator.next_profile()
        safe = rotator.to_safe_dict()
        self.assertEqual(safe["profile_count"], 2)
        self.assertEqual(safe["current_index"], 1)
        self.assertEqual(len(safe["profiles"]), 2)
        self.assertEqual(safe["profiles"][0]["profile_id"], "p1")


# ---------------------------------------------------------------------------
# NativeBrowserRuntime profile rotation (SCRAPLING-ABSORB-2H)
# ---------------------------------------------------------------------------


class NativeBrowserRuntimeProfileTests(unittest.TestCase):
    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_rotator_selects_profile(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        rotator = BrowserProfileRotator([
            BrowserProfile(profile_id="desktop", user_agent="Desktop/1.0", viewport="1920x1080"),
            BrowserProfile(profile_id="mobile", user_agent="Mobile/1.0", viewport="375x812"),
        ])
        runtime = NativeBrowserRuntime(rotator=rotator)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        self.assertTrue(response.ok)
        self.assertEqual(response.engine_result["profile_id"], "desktop")
        self.assertIsNotNone(response.engine_result["profile"])
        self.assertEqual(response.engine_result["profile"]["profile_id"], "desktop")

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_rotator_cycles_profiles(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        rotator = BrowserProfileRotator([
            BrowserProfile(profile_id="p1", user_agent="UA-1"),
            BrowserProfile(profile_id="p2", user_agent="UA-2"),
        ])
        runtime = NativeBrowserRuntime(rotator=rotator)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})

        r1 = runtime.render(request)
        r2 = runtime.render(request)

        self.assertEqual(r1.engine_result["profile_id"], "p1")
        self.assertEqual(r2.engine_result["profile_id"], "p2")

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_rotator_evidence_in_engine_result(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        rotator = BrowserProfileRotator([
            BrowserProfile(profile_id="p1", user_agent="UA-1"),
        ])
        runtime = NativeBrowserRuntime(rotator=rotator)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        self.assertIsNotNone(response.engine_result["rotator"])
        self.assertEqual(response.engine_result["rotator"]["profile_count"], 1)

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_no_rotator_has_no_profile_evidence(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        runtime = NativeBrowserRuntime()
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        self.assertIsNone(response.engine_result["profile"])
        self.assertIsNone(response.engine_result["profile_id"])
        self.assertIsNone(response.engine_result["rotator"])

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_profile_applies_protected_mode(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        rotator = BrowserProfileRotator([
            BrowserProfile(profile_id="stealth", protected_mode=True),
        ])
        runtime = NativeBrowserRuntime(rotator=rotator)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        self.assertTrue(response.ok)
        self.assertEqual(response.engine_result["mode"], "protected")

    @patch("autonomous_crawler.runtime.native_browser.sync_playwright")
    def test_profile_applies_user_agent(self, mock_pw_cls: MagicMock) -> None:
        from autonomous_crawler.runtime.native_browser import NativeBrowserRuntime
        from autonomous_crawler.runtime.models import RuntimeRequest

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

        rotator = BrowserProfileRotator([
            BrowserProfile(profile_id="custom", user_agent="CustomBot/1.0"),
        ])
        runtime = NativeBrowserRuntime(rotator=rotator)
        request = RuntimeRequest.from_dict({"url": "https://example.com"})
        response = runtime.render(request)

        self.assertTrue(response.ok)
        # Verify the context was created with the custom user agent
        call_args = mock_browser.new_context.call_args
        self.assertEqual(call_args[1]["user_agent"], "CustomBot/1.0")


if __name__ == "__main__":
    unittest.main()
