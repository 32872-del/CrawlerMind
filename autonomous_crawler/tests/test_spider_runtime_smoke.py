from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from run_spider_runtime_smoke_2026_05_14 import run


class SpiderRuntimeSmokeTests(unittest.TestCase):
    def test_pause_resume_smoke_uses_local_fixtures_and_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "summary.json"

            summary = run(output_path=summary_path)

            self.assertTrue(summary["accepted"])
            self.assertTrue(summary_path.exists())
            self.assertEqual(summary["config"]["network"], "none")
            self.assertEqual(summary["frontier_add"]["list"]["added"], 1)
            self.assertEqual(summary["frontier_add"]["failure_seed"]["added"], 1)
            self.assertEqual(summary["first_pass"]["claimed"], 1)
            self.assertEqual(summary["first_pass"]["discovered_urls"], 2)
            self.assertEqual(summary["first_frontier_stats"], {"done": 1, "queued": 3})
            self.assertEqual(summary["resume_pass"]["claimed"], 3)
            self.assertEqual(summary["resume_pass"]["succeeded"], 2)
            self.assertEqual(summary["resume_pass"]["failed"], 1)
            self.assertEqual(summary["final_frontier_stats"], {"done": 3, "failed": 1})
            self.assertEqual(summary["checkpoint_latest"]["run"]["status"], "completed")
            self.assertEqual(summary["checkpoint_latest"]["item_count"], 2)
            self.assertEqual(summary["checkpoint_latest"]["failure_count"], 1)
            self.assertEqual(summary["checkpoint_latest"]["latest_checkpoint"]["batch_id"], "resume")
            self.assertEqual(
                {item["record"]["title"] for item in summary["items"]},
                {"Alpha Runner", "Beta Trail"},
            )
            self.assertEqual(summary["failures"][0]["bucket"], "runtime_error")


if __name__ == "__main__":
    unittest.main()
