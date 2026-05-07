from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from autonomous_crawler.storage import CrawlResultStore
from run_results import main


class RunResultsCLITests(unittest.TestCase):
    def test_list_show_and_items_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _seed_db(Path(tmpdir))

            list_code, list_out, _ = _run_cli(["--db-path", str(db_path), "list"])
            show_code, show_out, _ = _run_cli(["--db-path", str(db_path), "show", "task-1"])
            items_code, items_out, _ = _run_cli(["--db-path", str(db_path), "items", "task-1"])

            self.assertEqual(list_code, 0)
            self.assertIn("task-1", list_out)
            self.assertIn("completed", list_out)
            self.assertEqual(show_code, 0)
            self.assertIn("item_count: 2", show_out)
            self.assertIn("mock://ranking", show_out)
            self.assertEqual(items_code, 0)
            self.assertIn("Alpha Topic", items_out)
            self.assertIn("/s?wd=beta", items_out)

    def test_json_outputs_are_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = _seed_db(Path(tmpdir))

            code, out, _ = _run_cli(["--db-path", str(db_path), "items", "task-1", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(out)
            self.assertEqual(payload[0]["title"], "Alpha Topic")

    def test_exports_json_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            db_path = _seed_db(tmp_path)
            json_path = tmp_path / "items.json"
            csv_path = tmp_path / "items.csv"

            json_code, _, _ = _run_cli(
                ["--db-path", str(db_path), "export-json", "task-1", str(json_path)]
            )
            csv_code, _, _ = _run_cli(
                ["--db-path", str(db_path), "export-csv", "task-1", str(csv_path)]
            )

            self.assertEqual(json_code, 0)
            self.assertEqual(csv_code, 0)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))[1]["rank"], "2")
            self.assertIn("Alpha Topic", csv_path.read_text(encoding="utf-8-sig"))

    def test_missing_task_returns_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "results.sqlite3"

            code, _, err = _run_cli(["--db-path", str(db_path), "show", "missing"])

            self.assertEqual(code, 1)
            self.assertIn("Task not found: missing", err)


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def _seed_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "results.sqlite3"
    CrawlResultStore(db_path).save_final_state(
        {
            "task_id": "task-1",
            "user_goal": "\u91c7\u96c6\u767e\u5ea6\u70ed\u641c\u699c\u524d2\u6761",
            "target_url": "mock://ranking",
            "status": "completed",
            "extracted_data": {
                "items": [
                    {
                        "rank": "1",
                        "title": "Alpha Topic",
                        "link": "/s?wd=alpha",
                        "hot_score": "12345",
                    },
                    {
                        "rank": "2",
                        "title": "Beta Topic",
                        "link": "/s?wd=beta",
                        "hot_score": "67890",
                    },
                ],
                "item_count": 2,
                "confidence": 1.0,
            },
            "validation_result": {"is_valid": True, "completeness": 1.0},
            "error_log": [],
            "messages": [],
        }
    )
    return db_path


if __name__ == "__main__":
    unittest.main()
