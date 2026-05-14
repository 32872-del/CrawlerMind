from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_crawler.storage import CrawlResultStore
from autonomous_crawler.tools.anti_bot_report import AntiBotFinding, AntiBotReport


class CrawlResultStoreTests(unittest.TestCase):
    def test_store_saves_and_loads_final_state_with_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CrawlResultStore(Path(tmpdir) / "results.sqlite3")
            task_id = store.save_final_state(_sample_state())

            self.assertEqual(task_id, "task-1")
            loaded = store.get_task("task-1")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["status"], "completed")
            self.assertEqual(loaded["item_count"], 2)
            self.assertTrue(loaded["is_valid"])
            self.assertIn("anti_bot_summary", loaded)
            self.assertEqual(loaded["anti_bot_summary"]["recommended_action"], "standard_http")
            self.assertEqual(loaded["final_state"]["target_url"], "mock://ranking")
            self.assertEqual(loaded["items"][0]["title"], "Alpha Topic")
            self.assertEqual(loaded["items"][1]["rank"], "2")

    def test_store_upserts_task_and_replaces_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CrawlResultStore(Path(tmpdir) / "results.sqlite3")
            state = _sample_state()
            store.save_final_state(state)

            state["status"] = "failed"
            state["extracted_data"]["items"] = [state["extracted_data"]["items"][0]]
            state["extracted_data"]["item_count"] = 1
            state["validation_result"] = {"is_valid": False}
            store.save_final_state(state)

            loaded = store.get_task("task-1")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["status"], "failed")
            self.assertEqual(loaded["item_count"], 1)
            self.assertFalse(loaded["is_valid"])
            self.assertEqual(len(loaded["items"]), 1)

    def test_store_persists_anti_bot_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CrawlResultStore(Path(tmpdir) / "results.sqlite3")
            state = _sample_state()
            state["crawl_strategy"] = {
                "anti_bot_report": AntiBotReport(
                    detected=True,
                    risk_level="high",
                    risk_score=88,
                    recommended_action="manual_handoff",
                    categories=["challenge"],
                    findings=[AntiBotFinding(
                        code="access_managed_challenge",
                        category="challenge",
                        severity="high",
                        source="access_diagnostics",
                        summary="Managed challenge detected.",
                    )],
                ).to_dict()
            }

            store.save_final_state(state)
            loaded = store.get_task("task-1")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["anti_bot_summary"]["recommended_action"], "manual_handoff")
            self.assertIn("challenge", loaded["anti_bot_summary"]["categories"])

    def test_store_backfills_missing_summary_from_final_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CrawlResultStore(Path(tmpdir) / "results.sqlite3")
            state = _sample_state()
            store.save_final_state(state)

            loaded = store.get_task("task-1")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["anti_bot_summary"]["recommended_action"], "standard_http")

    def test_store_lists_recent_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CrawlResultStore(Path(tmpdir) / "results.sqlite3")
            first = _sample_state(task_id="task-1")
            second = _sample_state(task_id="task-2")
            store.save_final_state(first)
            store.save_final_state(second)

            tasks = store.list_tasks(limit=10)

            self.assertEqual([task["task_id"] for task in tasks], ["task-2", "task-1"])
            self.assertNotIn("final_state", tasks[0])
            self.assertIn("anti_bot_summary", tasks[0])
            self.assertEqual(tasks[0]["anti_bot_summary"]["recommended_action"], "standard_http")


def _sample_state(task_id: str = "task-1") -> dict:
    return {
        "task_id": task_id,
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
        "messages": ["done"],
    }


if __name__ == "__main__":
    unittest.main()
