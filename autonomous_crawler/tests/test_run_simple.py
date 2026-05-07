"""Tests for the simplified user entrypoint."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.llm import OpenAICompatibleAdvisor
from run_simple import build_simple_advisor, load_simple_config


class RunSimpleConfigTests(unittest.TestCase):
    def test_missing_config_defaults_to_no_llm(self) -> None:
        missing = Path(tempfile.gettempdir()) / "clm_missing_config_for_test.json"
        if missing.exists():
            missing.unlink()

        config = load_simple_config(missing)

        self.assertEqual(config, {"llm": {"enabled": False}})

    def test_load_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clm_config.json"
            path.write_text(
                json.dumps({"llm": {"enabled": True, "model": "m"}}),
                encoding="utf-8",
            )

            config = load_simple_config(path)

        self.assertTrue(config["llm"]["enabled"])
        self.assertEqual(config["llm"]["model"], "m")

    def test_disabled_llm_returns_none(self) -> None:
        self.assertIsNone(build_simple_advisor({"llm": {"enabled": False}}))

    def test_enabled_llm_builds_advisor(self) -> None:
        advisor = build_simple_advisor({
            "llm": {
                "enabled": True,
                "base_url": "https://llm.example/v1",
                "model": "test-model",
                "api_key": "test-key",
            }
        })

        self.assertIsInstance(advisor, OpenAICompatibleAdvisor)

    def test_placeholder_key_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            build_simple_advisor({
                "llm": {
                    "enabled": True,
                    "base_url": "https://llm.example/v1",
                    "model": "test-model",
                    "api_key": "replace-with-your-api-key",
                }
            })


if __name__ == "__main__":
    unittest.main()
