from __future__ import annotations

import unittest

from autonomous_crawler.runners.managed_actions import (
    ManagedActionPlan,
    build_deterministic_action_plan,
    execute_managed_action_plan,
)


class ManagedActionPlanTests(unittest.TestCase):
    def test_deterministic_plan_adds_repair_actions_for_zero_records(self) -> None:
        plan = build_deterministic_action_plan(
            target_url="https://shop.test",
            profile={"name": "shop", "target_fields": ["title"]},
            run_spec={"selected_fields": ["title"]},
            progress={"records_saved": 0, "quality_indicator": "fail"},
            supervision={"last_event": {"action": "pause", "reason": "no records"}},
        )

        actions = [item.action for item in plan.actions]
        self.assertIn("reanalyze_site", actions)
        self.assertIn("discover_catalog", actions)
        self.assertIn("inspect_access", actions)
        self.assertIn("repair_selectors", actions)
        self.assertIn("adjust_runtime", actions)
        self.assertIn("evaluate_quality", actions)
        self.assertEqual(actions[-1], "prepare_rerun")

    def test_execute_plan_produces_profile_patch_and_overrides(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [
                {"action": "probe_fields", "params": {"fields": ["title", "colors", "sizes"]}},
                {"action": "inspect_access", "priority": "high"},
                {"action": "repair_selectors", "params": {"fields": ["title", "highest_price"]}},
                {"action": "adjust_runtime", "params": {"mode": "dynamic", "capture_api": True}},
                {"action": "evaluate_quality", "params": {"required_fields": ["title", "colors"], "min_records": 25}},
                {"action": "prepare_export", "params": {"format": "csv", "output_path": "out.xlsx"}},
            ]
        })

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile={"name": "shop", "selectors": {}, "target_fields": ["title"]},
            run_spec={"selected_fields": ["title"]},
        )

        self.assertTrue(result["rerun_ready"])
        self.assertEqual(result["profile_patch"]["access_config"]["mode"], "dynamic")
        self.assertTrue(result["profile_patch"]["access_config"]["browser_config"]["capture_api"])
        self.assertIn("title", result["profile_patch"]["selectors"]["detail"])
        self.assertIn("highest_price", result["profile_patch"]["selectors"]["detail"])
        self.assertIn("colors", result["profile_patch"]["selectors"]["detail"])
        self.assertEqual(result["profile_patch"]["quality_expectations"]["min_records"], 25)
        self.assertEqual(result["run_overrides"]["export"]["format"], "csv")
        self.assertEqual(result["run_overrides"]["export"]["output_path"], "out.xlsx")

    def test_unknown_action_is_bounded_to_prepare_rerun(self) -> None:
        plan = ManagedActionPlan.from_dict({
            "actions": [{"action": "run_arbitrary_python", "priority": "critical"}],
        })

        self.assertEqual(plan.actions[0].action, "prepare_rerun")


if __name__ == "__main__":
    unittest.main()
