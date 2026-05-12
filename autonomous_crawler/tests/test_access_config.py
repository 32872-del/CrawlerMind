from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from autonomous_crawler.agents.executor import executor_node
from autonomous_crawler.agents.recon import recon_node
from autonomous_crawler.tools.access_config import AccessConfig, resolve_access_config
from autonomous_crawler.tools.artifact_manifest import (
    build_browser_artifact_manifest,
    build_recon_artifact_manifest,
    persist_artifact_bundle,
)


class AccessConfigResolverTests(unittest.TestCase):
    def test_resolve_merges_constraints_then_state_overrides(self) -> None:
        config = resolve_access_config(
            state={
                "access_config": {
                    "browser_context": {"locale": "de-DE"},
                    "proxy": {"enabled": True, "default_proxy": "http://state.proxy:8080"},
                },
            },
            recon_report={
                "constraints": {
                    "access_config": {
                        "browser_context": {"viewport": {"width": 390, "height": 844}},
                        "proxy": {"enabled": False, "default_proxy": "http://old.proxy:8080"},
                    },
                },
            },
        )

        self.assertEqual(config.browser_context.locale, "de-DE")
        self.assertEqual(config.browser_context.viewport.width, 390)
        self.assertTrue(config.proxy.enabled)
        self.assertEqual(config.proxy.default_proxy, "http://state.proxy:8080")

    def test_safe_dict_redacts_storage_path_and_proxy(self) -> None:
        config = AccessConfig.from_dict({
            "session_profile": {
                "storage_state_path": r"C:\Users\Alice\secret\state.json",
            },
            "proxy": {
                "enabled": True,
                "default_proxy": "http://user:pass@proxy.example:8080",
            },
        })

        safe = config.to_safe_dict("https://example.com")
        text = str(safe)
        self.assertIn("[redacted-path]/state.json", text)
        self.assertNotIn("Alice", text)
        self.assertNotIn("user:pass", text)

    def test_has_authorized_session_for_respects_domain_scope(self) -> None:
        config = AccessConfig.from_dict({
            "session_profile": {
                "allowed_domains": ["example.com"],
                "headers": {"Authorization": "Bearer token"},
            },
        })

        self.assertTrue(config.has_authorized_session_for("https://shop.example.com"))
        self.assertFalse(config.has_authorized_session_for("https://other.test"))


class ArtifactManifestTests(unittest.TestCase):
    def test_browser_manifest_contains_core_fields(self) -> None:
        manifest = build_browser_artifact_manifest(
            target_url="https://example.com",
            final_url="https://example.com/final",
            browser_context={"locale": "en-US"},
            screenshot_path="shot.png",
            access_decision={"action": "browser_render"},
        )

        self.assertEqual(manifest["stage"], "browser_fetch")
        self.assertEqual(manifest["fetch_mode"], "browser")
        self.assertEqual(manifest["screenshot_path"], "shot.png")
        self.assertEqual(manifest["access_decision"]["action"], "browser_render")

    def test_recon_manifest_summarizes_fetch_trace(self) -> None:
        manifest = build_recon_artifact_manifest(
            target_url="https://example.com",
            fetch_trace={
                "selected_mode": "browser",
                "selected_url": "https://example.com/final",
                "attempts": [{}, {}],
            },
            access_config={"browser_context": {"viewport": {"width": 390}}},
        )

        self.assertEqual(manifest["stage"], "recon")
        self.assertEqual(manifest["fetch_mode"], "browser")
        self.assertEqual(manifest["final_url"], "https://example.com/final")
        self.assertEqual(manifest["notes"], ["attempts=2"])

    def test_persist_artifact_bundle_writes_manifest_and_snapshot(self) -> None:
        with TemporaryDirectory() as temp_dir:
            manifest = build_browser_artifact_manifest(
                target_url="https://example.com/products",
                final_url="https://example.com/products",
            )

            persisted = persist_artifact_bundle(
                manifest,
                run_id="run-123",
                html="<html>ok</html>",
                network_trace={"entries": []},
                artifact_root=temp_dir,
            )

            manifest_path = Path(persisted["manifest_path"])
            html_path = Path(persisted["html_path"])
            network_path = Path(persisted["network_trace_path"])
            self.assertTrue(manifest_path.exists())
            self.assertTrue(html_path.exists())
            self.assertTrue(network_path.exists())
            self.assertEqual(html_path.read_text(encoding="utf-8"), "<html>ok</html>")


class AccessConfigWorkflowTests(unittest.TestCase):
    @patch("autonomous_crawler.agents.executor.fetch_rendered_html")
    def test_executor_passes_resolved_session_proxy_and_browser_context(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = MagicMock(
            status="ok",
            url="https://example.com/final",
            html="<html>ok</html>",
            screenshot_path="shot.png",
            browser_context={"locale": "nl-NL"},
        )

        state = executor_node({
            "target_url": "https://example.com",
            "crawl_strategy": {"mode": "browser", "screenshot": True},
            "access_config": {
                "session_profile": {
                    "allowed_domains": ["example.com"],
                    "headers": {"Authorization": "Bearer token"},
                    "storage_state_path": "state.json",
                },
                "proxy": {
                    "enabled": True,
                    "default_proxy": "http://proxy.example:8080",
                },
                "browser_context": {"locale": "nl-NL"},
            },
            "recon_report": {
                "access_diagnostics": {
                    "access_decision": {"action": "browser_render"},
                },
            },
            "messages": [],
        })

        kwargs = mock_fetch.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token")
        self.assertEqual(kwargs["storage_state_path"], "state.json")
        self.assertEqual(kwargs["proxy_url"], "http://proxy.example:8080")
        self.assertEqual(kwargs["browser_context"].locale, "nl-NL")
        self.assertEqual(state["artifact_manifest"]["stage"], "browser_fetch")
        self.assertEqual(state["artifact_manifest"]["access_decision"]["action"], "browser_render")

    def test_recon_records_artifact_manifest_for_mock(self) -> None:
        state = recon_node({
            "target_url": "mock://js-shell",
            "recon_report": {},
            "messages": [],
            "error_log": [],
        })

        manifest = state["recon_report"]["artifact_manifest"]
        self.assertEqual(manifest["stage"], "recon")
        self.assertEqual(manifest["fetch_mode"], "browser")
        self.assertEqual(manifest["target_url"], "mock://js-shell")


if __name__ == "__main__":
    unittest.main()
