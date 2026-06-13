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

    def test_check_can_print_capabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "clm_config.json"
            clm.main(["init", "--config", str(config_path)])

            exit_code = clm.main(["check", "--config", str(config_path), "--capabilities"])

            self.assertEqual(exit_code, 0)

    def test_license_check_reports_unlicensed_private_features(self) -> None:
        exit_code = clm.main(["license", "check", "--capability", "private.advanced_api_replay"])

        self.assertEqual(exit_code, 1)

    def test_smoke_plan_is_non_network_command(self) -> None:
        exit_code = clm.main(["smoke", "--kind", "runner", "--plan"])

        self.assertEqual(exit_code, 0)

    def test_train_round_prints_command(self) -> None:
        exit_code = clm.main(["train", "--round", "1"])

        self.assertEqual(exit_code, 0)

    def test_train_round_prints_profile_comparison_command(self) -> None:
        exit_code = clm.main(["train", "--round", "native-vs-transition-profile"])

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

    def test_demo_mock_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "demo_mock.json"

            with patch("clm.run_crawl") as run_crawl:
                run_crawl.return_value = {
                    "status": "completed",
                    "extracted_data": {"items": [{"title": "A"}, {"title": "B"}]},
                }
                exit_code = clm.main(["demo", "mock", "--output", str(output_path)])

            self.assertEqual(exit_code, 0)
            run_crawl.assert_called_once()
            self.assertEqual(run_crawl.call_args.args[0], "collect product titles and prices")
            self.assertEqual(run_crawl.call_args.args[1], "mock://catalog")
            self.assertFalse(run_crawl.call_args.kwargs["use_llm"])
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(len(payload["extracted_data"]["items"]), 2)

    def test_demo_ecommerce_uses_default_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "demo_ecommerce.json"

            class Result(dict):
                pass

            fake_summary = Result({
                "accepted": True,
                "runtime_dir": "",
                "resume_pass": {
                    "status": "completed",
                    "product_stats": {"total": 55},
                    "quality_summary": {"quality_gate": {"passed": True}},
                },
            })

            with patch("run_profile_longrun_smoke_2026_05_16.run", return_value=fake_summary) as demo_run:
                exit_code = clm.main(["demo", "--output", str(output_path)])

            self.assertEqual(exit_code, 0)
            demo_run.assert_called_once()
            self.assertEqual(demo_run.call_args.kwargs["output_path"], output_path)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["scenario"], "ecommerce")
            self.assertEqual(payload["records"], 55)

    def test_profile_run_invokes_longrun_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path = Path(temp_dir) / "profile.json"
            output_path = Path(temp_dir) / "report.json"
            profile_path.write_text(
                json.dumps({
                    "name": "cli-profile",
                    "api_hints": {"endpoint": "https://example.test/api/products"},
                    "pagination_hints": {"type": "page"},
                    "quality_expectations": {"min_items": 1},
                }),
                encoding="utf-8",
            )

            class Result:
                accepted = True
                run_id = "cli-run"
                profile_name = "cli-profile"
                status = "completed"
                product_stats = {"total": 3}
                quality_summary = {"quality_gate": {"passed": True}}
                frontier_stats = {"done": 1}

            with patch("clm.run_profile_longrun", return_value=Result()) as run_profile:
                exit_code = clm.main([
                    "profile-run",
                    "--profile",
                    str(profile_path),
                    "--run-id",
                    "cli-run",
                    "--max-batches",
                    "1",
                    "--workers",
                    "6",
                    "--output",
                    str(output_path),
                    "--runtime-dir",
                    str(Path(temp_dir) / "runtime"),
                ])

            self.assertEqual(exit_code, 0)
            run_profile.assert_called_once()
            self.assertEqual(run_profile.call_args.kwargs["config"].run_id, "cli-run")
            self.assertEqual(run_profile.call_args.kwargs["config"].max_batches, 1)
            self.assertEqual(run_profile.call_args.kwargs["config"].item_workers, 6)
            self.assertEqual(str(run_profile.call_args.kwargs["config"].output_report_path), str(output_path))

    def test_multi_profile_run_invokes_batch_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            jobs_path = Path(temp_dir) / "jobs.json"
            output_path = Path(temp_dir) / "summary.json"
            jobs_path.write_text(
                json.dumps({
                    "shop_a": {"profile": {"name": "shop-a"}, "run_id": "run-a"},
                    "shop_b": {"profile": {"name": "shop-b"}, "run_id": "run-b", "item_workers": 2},
                }),
                encoding="utf-8",
            )

            class Summary:
                failed_sites = 0

                def to_dict(self):
                    return {"total_sites": 2, "ok_sites": 2, "failed_sites": 0, "results": []}

            with patch("clm.run_multi_profile_longrun", return_value=Summary()) as run_multi:
                exit_code = clm.main([
                    "multi-profile-run",
                    "--jobs",
                    str(jobs_path),
                    "--max-sites",
                    "2",
                    "--workers",
                    "5",
                    "--output",
                    str(output_path),
                ])

            self.assertEqual(exit_code, 0)
            run_multi.assert_called_once()
            jobs_arg = run_multi.call_args.args[0]
            self.assertEqual(jobs_arg["shop_a"]["item_workers"], 5)
            self.assertEqual(jobs_arg["shop_b"]["item_workers"], 2)
            self.assertEqual(run_multi.call_args.kwargs["max_sites"], 2)
            self.assertTrue(output_path.exists())

    def test_train_round_prints_profile_longrun_smoke_command(self) -> None:
        exit_code = clm.main(["train", "--round", "profile-longrun-smoke"])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
