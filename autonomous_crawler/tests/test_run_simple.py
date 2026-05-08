"""Tests for the simplified user entrypoint."""
from __future__ import annotations

import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autonomous_crawler.llm import OpenAICompatibleAdvisor
from run_simple import (
    _parse_args,
    build_simple_advisor,
    check_llm_config,
    load_simple_config,
)


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
                "use_response_format": False,
            }
        })

        self.assertIsInstance(advisor, OpenAICompatibleAdvisor)
        self.assertFalse(advisor.config.use_response_format)

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

    def test_parse_args_supports_check_llm(self) -> None:
        args = _parse_args(["--check-llm"])

        self.assertTrue(args.check_llm)
        self.assertEqual(args.goal, "collect product titles")
        self.assertEqual(args.url, "mock://catalog")

    def test_parse_args_preserves_goal_and_url(self) -> None:
        args = _parse_args(["collect titles", "https://example.com"])

        self.assertFalse(args.check_llm)
        self.assertEqual(args.goal, "collect titles")
        self.assertEqual(args.url, "https://example.com")

    def test_check_llm_disabled_returns_failure_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clm_config.json"
            path.write_text(
                json.dumps({"llm": {"enabled": False}}),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                code = check_llm_config(path)

        self.assertEqual(code, 1)

    def test_check_llm_success_returns_zero(self) -> None:
        class _FakeAdvisor:
            provider = "unit-test"
            model = "test-model"
            endpoint = "https://llm.example/v1/chat/completions"
            config = type(
                "Config",
                (),
                {
                    "provider": "unit-test",
                    "model": "test-model",
                    "api_key": "secret",
                    "use_response_format": True,
                },
            )()

            def check_connection(self):
                return {"ok": True, "reasoning_summary": "connection ok"}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clm_config.json"
            path.write_text(
                json.dumps({
                    "llm": {
                        "enabled": True,
                        "base_url": "https://llm.example/v1",
                        "model": "test-model",
                    }
                }),
                encoding="utf-8",
            )

            with patch("run_simple.build_simple_advisor", return_value=_FakeAdvisor()):
                with contextlib.redirect_stdout(io.StringIO()):
                    code = check_llm_config(path)

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
