"""Tests for optional LLM advisor interfaces (Phase A).

All tests use fake advisors.  No API key.  No network.
"""
from __future__ import annotations

import unittest
from typing import Any

from autonomous_crawler.llm.audit import build_decision_record, redact_preview
from autonomous_crawler.llm.protocols import PlanningAdvisor, StrategyAdvisor
from autonomous_crawler.agents.planner import make_planner_node, planner_node
from autonomous_crawler.agents.strategy import make_strategy_node, strategy_node
from autonomous_crawler.workflows.crawl_graph import (
    build_crawl_graph,
    compile_crawl_graph,
)


# --- Fake advisors ---


class _FakePlanningAdvisor:
    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self._output = output or {
            "task_type": "ranking_list",
            "target_fields": ["rank", "title", "hot_score"],
            "max_items": 10,
            "reasoning_summary": "fake plan",
        }

    def plan(self, user_goal: str, target_url: str) -> dict[str, Any]:
        return self._output


class _FailingPlanningAdvisor:
    def plan(self, user_goal: str, target_url: str) -> dict[str, Any]:
        raise RuntimeError("LLM unavailable")


class _FakeStrategyAdvisor:
    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self._output = output or {
            "mode": "browser",
            "max_items": 5,
            "reasoning_summary": "fake strategy",
        }

    def choose_strategy(
        self,
        planner_output: dict[str, Any],
        recon_report: dict[str, Any],
    ) -> dict[str, Any]:
        return self._output


class _FailingStrategyAdvisor:
    def choose_strategy(
        self,
        planner_output: dict[str, Any],
        recon_report: dict[str, Any],
    ) -> dict[str, Any]:
        raise RuntimeError("strategy LLM timeout")


class _UnsafeStrategyAdvisor:
    """Advisor that tries to set fnspider on a ranking_list task."""

    def choose_strategy(
        self,
        planner_output: dict[str, Any],
        recon_report: dict[str, Any],
    ) -> dict[str, Any]:
        return {"engine": "fnspider", "mode": "http"}


# --- Shared state helpers ---


def _base_state(**overrides: Any) -> dict[str, Any]:
    state = {
        "user_goal": "采集百度热搜榜前30条",
        "target_url": "https://top.baidu.com/board?tab=realtime",
        "messages": [],
        "retries": 0,
        "max_retries": 3,
    }
    state.update(overrides)
    return state


def _planned_state(**overrides: Any) -> dict[str, Any]:
    """State after deterministic planner has run."""
    state = _base_state(**overrides)
    det = planner_node(state)
    merged = {**state, **det}
    merged.setdefault("llm_enabled", False)
    merged.setdefault("llm_decisions", [])
    merged.setdefault("llm_errors", [])
    return merged


# --- Tests ---


class TestDeterministicNoAdvisor(unittest.TestCase):
    """No advisor -> deterministic graph still works."""

    def test_planner_factory_no_advisor_produces_deterministic_output(self) -> None:
        node = make_planner_node(None)
        state = _base_state()
        result = node(state)

        self.assertEqual(result["status"], "planned")
        self.assertIn("recon_report", result)
        self.assertFalse(result["llm_enabled"])
        self.assertEqual(result["llm_decisions"], [])
        self.assertEqual(result["llm_errors"], [])

    def test_strategy_factory_no_advisor_produces_deterministic_output(self) -> None:
        node = make_strategy_node(None)
        state = _planned_state()
        result = node(state)

        self.assertEqual(result["status"], "strategized")
        self.assertIn("crawl_strategy", result)
        self.assertEqual(result["llm_decisions"], [])

    def test_compile_crawl_graph_no_advisor(self) -> None:
        graph = compile_crawl_graph()
        self.assertIsNotNone(graph)

    def test_build_crawl_graph_no_advisor(self) -> None:
        graph = build_crawl_graph()
        self.assertIsNotNone(graph)

    def test_no_advisor_llm_fields_present_in_planner_output(self) -> None:
        node = make_planner_node(None)
        result = node(_base_state())
        self.assertIn("llm_enabled", result)
        self.assertIn("llm_decisions", result)
        self.assertIn("llm_errors", result)


class TestPlanningAdvisorSuccess(unittest.TestCase):
    """Planning advisor success -> accepted fields merge."""

    def test_advisor_fields_merged_into_recon_report(self) -> None:
        output = {
            "task_type": "ranking_list",
            "target_fields": ["rank", "title", "hot_score"],
            "reasoning_summary": "fake plan",
        }
        advisor = _FakePlanningAdvisor(output)
        node = make_planner_node(advisor)
        # Use a goal without a deterministic max_items
        result = node(_base_state(user_goal="collect ranking list"))

        recon = result["recon_report"]
        self.assertEqual(recon["task_type"], "ranking_list")
        self.assertEqual(recon["target_fields"], ["rank", "title", "hot_score"])
        self.assertTrue(result["llm_enabled"])

    def test_decision_record_created(self) -> None:
        advisor = _FakePlanningAdvisor()
        node = make_planner_node(advisor)
        result = node(_base_state())

        self.assertEqual(len(result["llm_decisions"]), 1)
        decision = result["llm_decisions"][0]
        self.assertEqual(decision["node"], "planner")
        self.assertFalse(decision["fallback_used"])
        self.assertIn("task_type", decision["accepted_fields"])
        self.assertEqual(result["llm_errors"], [])

    def test_advisor_max_items_accepted_when_no_conflict(self) -> None:
        output = {
            "task_type": "ranking_list",
            "max_items": 10,
            "reasoning_summary": "no conflict",
        }
        advisor = _FakePlanningAdvisor(output)
        node = make_planner_node(advisor)
        # Goal without a deterministic max_items pattern
        result = node(_base_state(user_goal="collect ranking list"))

        recon = result["recon_report"]
        self.assertEqual(recon["constraints"]["max_items"], 10)

    def test_unknown_fields_rejected(self) -> None:
        output = {
            "task_type": "ranking_list",
            "unknown_field": "should be rejected",
            "reasoning_summary": "test",
        }
        advisor = _FakePlanningAdvisor(output)
        node = make_planner_node(advisor)
        result = node(_base_state())

        decision = result["llm_decisions"][0]
        self.assertIn("unknown_field", decision["rejected_fields"])
        self.assertNotIn("unknown_field", decision["accepted_fields"])

    def test_invalid_target_fields_are_rejected(self) -> None:
        output = {
            "target_fields": ["title", "drop_database"],
            "task_type": "product_list",
        }
        advisor = _FakePlanningAdvisor(output)
        node = make_planner_node(advisor)
        result = node(_base_state(user_goal="collect products"))

        recon = result["recon_report"]
        self.assertEqual(recon["target_fields"], ["title"])
        decision = result["llm_decisions"][0]
        self.assertIn("target_fields.drop_database", decision["rejected_fields"])

    def test_invalid_task_type_is_rejected(self) -> None:
        output = {
            "task_type": "delete_everything",
            "target_fields": ["title"],
        }
        advisor = _FakePlanningAdvisor(output)
        node = make_planner_node(advisor)
        result = node(_base_state(user_goal="collect products"))

        self.assertEqual(result["recon_report"]["task_type"], "product_list")
        decision = result["llm_decisions"][0]
        self.assertIn("task_type", decision["rejected_fields"])

    def test_crawl_preferences_are_promoted_to_top_level_state(self) -> None:
        output = {
            "task_type": "product_list",
            "crawl_preferences": {"engine": "fnspider"},
        }
        advisor = _FakePlanningAdvisor(output)
        node = make_planner_node(advisor)
        result = node(_base_state(user_goal="collect products"))

        self.assertEqual(result["crawl_preferences"], {"engine": "fnspider"})
        self.assertIn("crawl_preferences", result["llm_decisions"][0]["accepted_fields"])

    def test_max_items_conflict_preserves_deterministic_value(self) -> None:
        state = _base_state()
        # Force a deterministic max_items
        state["user_goal"] = "采集百度热搜榜前20条"
        output = {
            "task_type": "ranking_list",
            "max_items": 10,
            "reasoning_summary": "conflict test",
        }
        advisor = _FakePlanningAdvisor(output)
        node = make_planner_node(advisor)
        result = node(state)

        recon = result["recon_report"]
        # Deterministic value should be preserved on conflict
        self.assertEqual(recon["constraints"]["max_items"], 20)
        decision = result["llm_decisions"][0]
        self.assertIn("max_items (conflict)", decision["rejected_fields"])


class TestPlanningAdvisorException(unittest.TestCase):
    """Planning advisor exception -> fallback used and recorded."""

    def test_fallback_used_on_exception(self) -> None:
        advisor = _FailingPlanningAdvisor()
        node = make_planner_node(advisor)
        result = node(_base_state())

        # Deterministic output should still be present
        self.assertEqual(result["status"], "planned")
        self.assertIn("recon_report", result)
        self.assertTrue(result["llm_enabled"])

        # Decision record should show fallback
        self.assertEqual(len(result["llm_decisions"]), 1)
        decision = result["llm_decisions"][0]
        self.assertTrue(decision["fallback_used"])
        self.assertIn("LLM unavailable", result["llm_errors"][0])

    def test_fallback_message_appended(self) -> None:
        advisor = _FailingPlanningAdvisor()
        node = make_planner_node(advisor)
        result = node(_base_state())

        messages = result["messages"]
        fallback_msgs = [m for m in messages if "fallback" in m.lower()]
        self.assertTrue(len(fallback_msgs) > 0)


class TestStrategyAdvisorSuccess(unittest.TestCase):
    """Strategy advisor success -> safe fields merge."""

    def test_safe_fields_merged_into_strategy(self) -> None:
        advisor = _FakeStrategyAdvisor()
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        strategy = result["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")
        self.assertNotEqual(strategy["max_items"], 5)
        self.assertTrue(result["llm_enabled"])
        decision = result["llm_decisions"][0]
        self.assertIn("mode", decision["accepted_fields"])
        self.assertIn("max_items (kept deterministic)", decision["rejected_fields"])

    def test_decision_record_created(self) -> None:
        advisor = _FakeStrategyAdvisor()
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        self.assertEqual(len(result["llm_decisions"]), 1)
        decision = result["llm_decisions"][0]
        self.assertEqual(decision["node"], "strategy")
        self.assertFalse(decision["fallback_used"])

    def test_advisor_fills_missing_selector(self) -> None:
        advisor = _FakeStrategyAdvisor({
            "selectors": {"summary": ".summary"},
        })
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        strategy = result["crawl_strategy"]
        self.assertEqual(strategy["selectors"]["summary"], ".summary")
        self.assertIn(
            "selectors.summary",
            result["llm_decisions"][0]["accepted_fields"],
        )

    def test_advisor_does_not_replace_strong_recon_selector(self) -> None:
        advisor = _FakeStrategyAdvisor({
            "selectors": {"title": ".advisor-title"},
        })
        node = make_strategy_node(advisor)
        state = _planned_state()
        state["recon_report"]["dom_structure"] = {
            "product_selector": ".catalog-card",
            "field_selectors": {"title": ".product-name"},
        }
        result = node(state)

        strategy = result["crawl_strategy"]
        self.assertEqual(strategy["selectors"]["title"], ".product-name")
        decision = result["llm_decisions"][0]
        self.assertIn(
            "selectors.title (kept deterministic)",
            decision["rejected_fields"],
        )

    def test_advisor_replaces_fallback_selector(self) -> None:
        advisor = _FakeStrategyAdvisor({
            "selectors": {"title": ".real-title"},
        })
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        strategy = result["crawl_strategy"]
        self.assertEqual(strategy["selectors"]["title"], ".real-title")
        self.assertIn(
            "selectors.title",
            result["llm_decisions"][0]["accepted_fields"],
        )

    def test_advisor_mode_does_not_downgrade_browser(self) -> None:
        advisor = _FakeStrategyAdvisor({"mode": "http"})
        node = make_strategy_node(advisor)
        state = _planned_state()
        state["recon_report"]["rendering"] = "spa"
        result = node(state)

        strategy = result["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")
        self.assertIn(
            "mode (kept deterministic)",
            result["llm_decisions"][0]["rejected_fields"],
        )


class TestStrategyAdvisorUnsafe(unittest.TestCase):
    """Strategy advisor unsafe engine/mode -> rejected and recorded."""

    def test_fnspider_rejected_for_ranking_list(self) -> None:
        advisor = _UnsafeStrategyAdvisor()
        node = make_strategy_node(advisor)
        state = _planned_state()
        state["recon_report"]["task_type"] = "ranking_list"
        result = node(state)

        strategy = result["crawl_strategy"]
        self.assertNotEqual(strategy.get("engine"), "fnspider")

        decision = result["llm_decisions"][0]
        self.assertIn("engine", decision["rejected_fields"])

    def test_fnspider_accepted_for_product_list(self) -> None:
        advisor = _UnsafeStrategyAdvisor()
        node = make_strategy_node(advisor)
        state = _planned_state()
        state["recon_report"]["task_type"] = "product_list"
        state["recon_report"]["target_url"] = "https://shop.example/products"
        result = node(state)

        strategy = result["crawl_strategy"]
        self.assertEqual(strategy.get("engine"), "fnspider")

        decision = result["llm_decisions"][0]
        self.assertIn("engine", decision["accepted_fields"])

    def test_fnspider_rejected_for_mock_url(self) -> None:
        advisor = _UnsafeStrategyAdvisor()
        node = make_strategy_node(advisor)
        state = _planned_state(target_url="mock://catalog")
        state["recon_report"]["target_url"] = "mock://catalog"
        state["recon_report"]["task_type"] = "product_list"
        result = node(state)

        strategy = result["crawl_strategy"]
        self.assertNotEqual(strategy.get("engine"), "fnspider")

        decision = result["llm_decisions"][0]
        self.assertIn("engine", decision["rejected_fields"])

    def test_invalid_mode_rejected(self) -> None:
        advisor = _FakeStrategyAdvisor({"mode": "invalid_mode"})
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        decision = result["llm_decisions"][0]
        self.assertIn("mode", decision["rejected_fields"])

    def test_invalid_wait_until_rejected(self) -> None:
        advisor = _FakeStrategyAdvisor({"wait_until": "invalid"})
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        decision = result["llm_decisions"][0]
        self.assertIn("wait_until", decision["rejected_fields"])

    def test_negative_max_items_rejected(self) -> None:
        advisor = _FakeStrategyAdvisor({"max_items": -5})
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        decision = result["llm_decisions"][0]
        self.assertIn("max_items", decision["rejected_fields"])

    def test_unknown_selector_key_rejected(self) -> None:
        advisor = _FakeStrategyAdvisor({
            "selectors": {"title": ".title", "hacker": ".evil"},
        })
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        decision = result["llm_decisions"][0]
        self.assertIn("selectors.hacker", decision["rejected_fields"])
        strategy = result["crawl_strategy"]
        self.assertIn("title", strategy.get("selectors", {}))
        self.assertNotIn("hacker", strategy.get("selectors", {}))


class TestStrategyAdvisorException(unittest.TestCase):
    """Strategy advisor exception -> fallback used and recorded."""

    def test_fallback_used_on_exception(self) -> None:
        advisor = _FailingStrategyAdvisor()
        node = make_strategy_node(advisor)
        result = node(_planned_state())

        self.assertIn("crawl_strategy", result)
        self.assertEqual(len(result["llm_decisions"]), 1)
        decision = result["llm_decisions"][0]
        self.assertTrue(decision["fallback_used"])
        self.assertIn("strategy LLM timeout", result["llm_errors"][0])


class TestDecisionsSurviveFullPipeline(unittest.TestCase):
    """Planner + strategy decisions survive in final state."""

    def test_both_decisions_present_after_planner_and_strategy(self) -> None:
        plan_advisor = _FakePlanningAdvisor()
        strat_advisor = _FakeStrategyAdvisor()

        planner = make_planner_node(plan_advisor)
        strategy = make_strategy_node(strat_advisor)

        state = _base_state()
        p_result = planner(state)
        merged_p = {**state, **p_result}

        s_result = strategy(merged_p)
        merged_s = {**merged_p, **s_result}

        self.assertEqual(len(merged_s["llm_decisions"]), 2)
        nodes = [d["node"] for d in merged_s["llm_decisions"]]
        self.assertIn("planner", nodes)
        self.assertIn("strategy", nodes)

    def test_decisions_not_lost_by_subsequent_nodes(self) -> None:
        """LLM fields set by planner survive through strategy."""
        plan_advisor = _FakePlanningAdvisor()
        planner = make_planner_node(plan_advisor)
        strategy = make_strategy_node(None)  # no strategy advisor

        state = _base_state()
        p_result = planner(state)
        merged_p = {**state, **p_result}

        s_result = strategy(merged_p)
        merged_s = {**merged_p, **s_result}

        self.assertEqual(len(merged_s["llm_decisions"]), 1)
        self.assertEqual(merged_s["llm_decisions"][0]["node"], "planner")

    def test_decisions_survive_full_compiled_graph(self) -> None:
        """Planner and strategy decisions survive through Validator."""
        plan_advisor = _FakePlanningAdvisor({
            "task_type": "product_list",
            "target_fields": ["title", "price"],
            "reasoning_summary": "full graph plan",
        })
        strat_advisor = _FakeStrategyAdvisor({
            "max_items": 1,
            "reasoning_summary": "full graph strategy",
        })
        app = compile_crawl_graph(
            planning_advisor=plan_advisor,
            strategy_advisor=strat_advisor,
        )

        final_state = app.invoke({
            "user_goal": "collect product titles and prices",
            "target_url": "mock://catalog",
            "recon_report": {},
            "crawl_strategy": {},
            "visited_urls": [],
            "raw_html": {},
            "api_responses": [],
            "extracted_data": {},
            "validation_result": {},
            "retries": 0,
            "max_retries": 0,
            "status": "pending",
            "error_log": [],
            "messages": [],
        })

        self.assertEqual(final_state["status"], "completed")
        self.assertTrue(final_state["llm_enabled"])
        self.assertEqual(len(final_state["llm_decisions"]), 2)
        self.assertEqual(
            [d["node"] for d in final_state["llm_decisions"]],
            ["planner", "strategy"],
        )
        self.assertEqual(final_state["llm_errors"], [])
        self.assertEqual(final_state["extracted_data"]["item_count"], 1)


class TestAuditHelpers(unittest.TestCase):
    """Tests for the audit helper functions."""

    def test_redact_preview_masks_api_key(self) -> None:
        text = 'api_key="sk-abc123secret" and more'
        redacted, modified = redact_preview(text)
        self.assertTrue(modified)
        self.assertNotIn("sk-abc123secret", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_redact_preview_masks_authorization(self) -> None:
        text = "authorization: Bearer eyJhbGciOiJIUzI1NiJ9.token"
        redacted, modified = redact_preview(text)
        self.assertTrue(modified)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9.token", redacted)

    def test_redact_preview_no_change_when_no_secrets(self) -> None:
        text = "normal text with no secrets"
        redacted, modified = redact_preview(text)
        self.assertFalse(modified)
        self.assertEqual(redacted, text)

    def test_build_decision_record_truncates_preview(self) -> None:
        long_response = {"data": "x" * 5000}
        record = build_decision_record(
            node="planner",
            advisor=object(),
            input_summary="test",
            raw_response=long_response,
            parsed_decision={},
            accepted_fields=[],
            rejected_fields=[],
            fallback_used=False,
        )
        self.assertLessEqual(len(record["raw_response_preview"]), 2000)

    def test_build_decision_record_redacts_json_secret_values(self) -> None:
        record = build_decision_record(
            node="planner",
            advisor=object(),
            input_summary="test",
            raw_response={
                "api_key": "sk-json-secret",
                "token": "json-token-secret",
            },
            parsed_decision={},
            accepted_fields=[],
            rejected_fields=[],
            fallback_used=False,
        )

        preview = record["raw_response_preview"]
        self.assertTrue(record["secrets_redacted"])
        self.assertNotIn("sk-json-secret", preview)
        self.assertNotIn("json-token-secret", preview)
        self.assertIn("[REDACTED]", preview)

    def test_build_decision_record_has_required_fields(self) -> None:
        record = build_decision_record(
            node="test",
            advisor=object(),
            input_summary="input",
            raw_response={},
            parsed_decision={},
            accepted_fields=["a"],
            rejected_fields=["b"],
            fallback_used=False,
        )
        for key in [
            "node", "provider", "model", "input_summary",
            "raw_response_preview", "parsed_decision", "accepted_fields",
            "rejected_fields", "fallback_used", "created_at",
        ]:
            self.assertIn(key, record)


class TestProtocolCompliance(unittest.TestCase):
    """Verify fake advisors satisfy the protocols."""

    def test_fake_planning_advisor_satisfies_protocol(self) -> None:
        self.assertIsInstance(_FakePlanningAdvisor(), PlanningAdvisor)

    def test_fake_strategy_advisor_satisfies_protocol(self) -> None:
        self.assertIsInstance(_FakeStrategyAdvisor(), StrategyAdvisor)

    def test_failing_planning_advisor_satisfies_protocol(self) -> None:
        self.assertIsInstance(_FailingPlanningAdvisor(), PlanningAdvisor)

    def test_failing_strategy_advisor_satisfies_protocol(self) -> None:
        self.assertIsInstance(_FailingStrategyAdvisor(), StrategyAdvisor)


if __name__ == "__main__":
    unittest.main()
