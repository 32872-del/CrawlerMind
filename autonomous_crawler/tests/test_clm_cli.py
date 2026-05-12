from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import clm


class CLMEasyModeTests(unittest.TestCase):
    def test_init_creates_disabled_config_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "clm_config.json"
            exit_code = clm.main(["init", "--config", str(config_path)])

            self.assertEqual(exit_code, 0)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertFalse(config["llm"]["enabled"])
            self.assertEqual(config["llm"]["model"], clm.DEFAULT_LLM_MODEL)

    def test_init_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "clm_config.json"
            config_path.write_text("{}", encoding="utf-8")

            exit_code = clm.main(["init", "--config", str(config_path)])

            self.assertEqual(exit_code, 1)
            self.assertEqual(config_path.read_text(encoding="utf-8"), "{}")

    def test_check_runs_without_real_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "clm_config.json"
            clm.main(["init", "--config", str(config_path)])

            exit_code = clm.main(["check", "--config", str(config_path)])

            self.assertEqual(exit_code, 0)

    def test_smoke_plan_is_non_network_command(self) -> None:
        exit_code = clm.main(["smoke", "--kind", "runner", "--plan"])

        self.assertEqual(exit_code, 0)

    def test_train_round_prints_command(self) -> None:
        exit_code = clm.main(["train", "--round", "1"])

        self.assertEqual(exit_code, 0)

    def test_crawl_rejects_conflicting_llm_flags(self) -> None:
        exit_code = clm.main([
            "crawl",
            "collect product titles",
            "mock://catalog",
            "--llm",
            "--no-llm",
        ])

        self.assertEqual(exit_code, 2)

    def test_crawl_preserves_goal_and_url_for_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "clm_config.json"
            output_path = Path(temp_dir) / "result.json"
            clm.main(["init", "--config", str(config_path)])

            with patch("clm.run_crawl") as run_crawl:
                run_crawl.return_value = {
                    "status": "completed",
                    "extracted_data": {"items": [{"title": "A"}]},
                }
                exit_code = clm.main([
                    "crawl",
                    "collect product titles",
                    "mock://catalog",
                    "--config",
                    str(config_path),
                    "--limit",
                    "3",
                    "--output",
                    str(output_path),
                ])

            self.assertEqual(exit_code, 0)
            run_crawl.assert_called_once()
            self.assertEqual(run_crawl.call_args.args[0], "collect product titles limit 3")
            self.assertEqual(run_crawl.call_args.args[1], "mock://catalog")
            self.assertFalse(run_crawl.call_args.kwargs["use_llm"])
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
