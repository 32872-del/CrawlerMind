"""Tests for the LLM decision loop in managed crawl execution.

Covers:
- LLM advisor plan selection via choose_managed_actions()
- llm_decide parameter threading
- Decision and trace callbacks
- Fallback to deterministic plan on LLM failure
- Integration with execute_managed_action_plan()
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from autonomous_crawler.runners.managed_actions import (
    EXECUTABLE_ACTIONS,
    ManagedActionPlan,
    ManagedCrawlAction,
    SUPPORTED_ACTIONS,
    build_deterministic_action_plan,
    execute_managed_action_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_plan_response(*action_names: str, reasoning: str = "llm chosen") -> dict[str, Any]:
    """Build a raw dict that looks like advisor.choose_managed_actions() output."""
    return {
        "schema_version": "managed-action-plan/v2",
        "reasoning_summary": reasoning,
        "actions": [
            {"action": name, "priority": "high", "reason": f"LLM chose {name}"}
            for name in action_names
        ],
    }


def _make_advisor(
    return_value: dict[str, Any] | None = None,
    side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock advisor that behaves like OpenAICompatibleAdvisor."""
    advisor = MagicMock()
    advisor.provider = "test-provider"
    advisor.model = "test-model"
    if side_effect is not None:
        advisor.choose_managed_actions.side_effect = side_effect
    else:
        advisor.choose_managed_actions.return_value = (
            return_value or _make_llm_plan_response("adjust_runtime", "prepare_rerun")
        )
    return advisor


def _simple_plan() -> ManagedActionPlan:
    """Return a simple deterministic plan for testing."""
    return ManagedActionPlan(actions=[
        ManagedCrawlAction(action="evaluate_quality", priority="medium", reason="deterministic"),
        ManagedCrawlAction(action="prepare_rerun", priority="medium", reason="deterministic"),
    ], source="deterministic")


def _basic_profile() -> dict[str, Any]:
    return {
        "name": "test-shop",
        "target_fields": ["title", "highest_price"],
        "selectors": {},
        "crawl_preferences": {"seed_urls": ["https://shop.test/list"]},
    }


def _basic_run_spec() -> dict[str, Any]:
    return {
        "target_url": "https://shop.test",
        "selected_fields": ["title", "highest_price"],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLLMDecisionLoop(unittest.TestCase):
    """Core tests for the LLM-driven decision loop."""

    def test_llm_decide_false_uses_deterministic_plan(self) -> None:
        """When llm_decide=False the advisor is never called."""
        advisor = _make_advisor()
        plan = _simple_plan()

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=False,
        )

        advisor.choose_managed_actions.assert_not_called()
        self.assertEqual(result["plan_source"], "deterministic")
        self.assertFalse(result["llm_decide"])
        self.assertEqual(result["plan"]["source"], "deterministic")

    def test_llm_decide_true_calls_advisor_choose_managed_actions(self) -> None:
        """When llm_decide=True the advisor's choose_managed_actions() is called."""
        llm_response = _make_llm_plan_response("adjust_runtime", "repair_selectors", "prepare_rerun")
        advisor = _make_advisor(return_value=llm_response)
        plan = _simple_plan()

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
        )

        advisor.choose_managed_actions.assert_called_once()
        call_kwargs = advisor.choose_managed_actions.call_args
        self.assertEqual(call_kwargs.kwargs["target_url"], "https://shop.test")
        self.assertIn("available_actions", call_kwargs.kwargs)
        self.assertEqual(result["plan_source"], "llm")
        self.assertTrue(result["llm_decide"])

    def test_llm_plan_replaces_deterministic_plan_actions(self) -> None:
        """When LLM succeeds, the executed actions come from the LLM plan."""
        llm_response = _make_llm_plan_response("adjust_runtime", "prepare_rerun")
        advisor = _make_advisor(return_value=llm_response)
        # Deterministic plan has different actions
        plan = ManagedActionPlan(actions=[
            ManagedCrawlAction(action="evaluate_quality", priority="medium", reason="det"),
            ManagedCrawlAction(action="prepare_rerun", priority="medium", reason="det"),
        ], source="deterministic")

        with patch(
            "autonomous_crawler.runners.managed_actions._execute_adjust_runtime",
            return_value={"action": "adjust_runtime", "ok": True, "patch": {}, "overrides": {}},
        ), patch(
            "autonomous_crawler.runners.managed_actions._execute_evaluate_quality",
            return_value={"action": "evaluate_quality", "ok": True, "patch": {}, "overrides": {}},
        ):
            result = execute_managed_action_plan(
                plan=plan,
                target_url="https://shop.test",
                profile=_basic_profile(),
                run_spec=_basic_run_spec(),
                advisor=advisor,
                llm_decide=True,
            )

        executed_actions = [r["action"] for r in result["results"]]
        self.assertIn("adjust_runtime", executed_actions)
        # evaluate_quality should NOT be in results since LLM plan didn't include it
        self.assertNotIn("evaluate_quality", executed_actions)

    def test_llm_decision_callback_receives_decision(self) -> None:
        """The llm_decision_callback is called with a decision dict."""
        llm_response = _make_llm_plan_response("adjust_runtime", "prepare_rerun", reasoning="test reasoning")
        advisor = _make_advisor(return_value=llm_response)
        decisions: list[dict[str, Any]] = []

        execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_decision_callback=lambda d: decisions.append(d),
        )

        self.assertEqual(len(decisions), 1)
        decision = decisions[0]
        self.assertEqual(decision["stage"], "managed_action_plan")
        self.assertTrue(decision["enabled"])
        self.assertFalse(decision["fallback_used"])
        self.assertEqual(decision["provider"], "test-provider")
        self.assertEqual(decision["model"], "test-model")
        self.assertEqual(decision["plan_source"], "llm")
        self.assertIn("adjust_runtime", decision["actions"])
        self.assertIn("created_at", decision)

    def test_llm_trace_callback_receives_trace(self) -> None:
        """The llm_trace_callback is called with a trace dict."""
        llm_response = _make_llm_plan_response("adjust_runtime", "prepare_rerun")
        advisor = _make_advisor(return_value=llm_response)
        traces: list[dict[str, Any]] = []

        execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_trace_callback=lambda t: traces.append(t),
        )

        self.assertEqual(len(traces), 1)
        trace = traces[0]
        self.assertEqual(trace["stage"], "managed_action_plan")
        self.assertEqual(trace["status"], "ok")
        self.assertEqual(trace["provider"], "test-provider")
        self.assertEqual(trace["model"], "test-model")
        self.assertIn("duration_ms", trace)
        self.assertIn("created_at", trace)

    def test_llm_failure_falls_back_to_deterministic_plan(self) -> None:
        """When advisor.choose_managed_actions() raises, the deterministic plan is used."""
        advisor = _make_advisor(side_effect=RuntimeError("LLM provider unreachable"))
        plan = _simple_plan()

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
        )

        self.assertEqual(result["plan_source"], "deterministic_fallback")
        self.assertTrue(result["llm_decide"])
        # The deterministic plan's actions should be executed
        executed_actions = [r["action"] for r in result["results"]]
        self.assertIn("evaluate_quality", executed_actions)
        self.assertIn("prepare_rerun", executed_actions)

    def test_llm_failure_records_error_trace_and_decision(self) -> None:
        """On LLM failure, both trace (error) and decision (fallback_used) are recorded."""
        advisor = _make_advisor(side_effect=RuntimeError("connection timeout"))
        decisions: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []

        execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_decision_callback=lambda d: decisions.append(d),
            llm_trace_callback=lambda t: traces.append(t),
        )

        # Trace should show error
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["status"], "error")
        self.assertIn("connection timeout", traces[0]["error"])

        # Decision should show fallback
        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0]["fallback_used"])
        self.assertEqual(decisions[0]["plan_source"], "deterministic_fallback")

    def test_llm_decide_without_advisor_uses_deterministic(self) -> None:
        """When llm_decide=True but advisor=None, deterministic plan is used."""
        plan = _simple_plan()

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=None,
            llm_decide=True,
        )

        self.assertEqual(result["plan_source"], "deterministic")
        self.assertEqual(result["plan"]["source"], "deterministic")

    def test_callback_exceptions_do_not_propagate(self) -> None:
        """Exceptions in callbacks should not break execution."""
        llm_response = _make_llm_plan_response("prepare_rerun")
        advisor = _make_advisor(return_value=llm_response)

        def bad_callback(d: dict[str, Any]) -> None:
            raise RuntimeError("callback exploded")

        # Should not raise
        result = execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_decision_callback=bad_callback,
            llm_trace_callback=bad_callback,
        )

        self.assertEqual(result["plan_source"], "llm")

    def test_result_includes_plan_source_and_llm_decide(self) -> None:
        """The result dict always includes plan_source and llm_decide keys."""
        advisor = _make_advisor()

        # With llm_decide=True
        result = execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
        )
        self.assertIn("plan_source", result)
        self.assertIn("llm_decide", result)

        # With llm_decide=False
        result = execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=False,
        )
        self.assertIn("plan_source", result)
        self.assertIn("llm_decide", result)

    def test_llm_plan_validation_rejects_unsafe_actions(self) -> None:
        """LLM plans with invalid actions are validated through ManagedActionPlan.from_dict."""
        llm_response = {
            "reasoning_summary": "risky plan",
            "actions": [
                {"action": "run_shell", "params": {"cmd": "rm -rf /"}},
                {"action": "adjust_runtime", "params": {"mode": "protected"}},
            ],
        }
        advisor = _make_advisor(return_value=llm_response)

        result = execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
        )

        executed_actions = [r["action"] for r in result["results"]]
        # run_shell should be rejected, adjust_runtime should pass
        self.assertNotIn("run_shell", executed_actions)
        self.assertIn("adjust_runtime", executed_actions)
        self.assertEqual(result["plan_source"], "llm")

    def test_llm_decision_includes_action_list(self) -> None:
        """The recorded decision includes the list of chosen actions."""
        llm_response = _make_llm_plan_response(
            "adjust_runtime", "repair_selectors", "prepare_rerun",
            reasoning="need runtime fix and selector repair",
        )
        advisor = _make_advisor(return_value=llm_response)
        decisions: list[dict[str, Any]] = []

        execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_decision_callback=lambda d: decisions.append(d),
        )

        decision = decisions[0]
        self.assertEqual(decision["actions"], ["adjust_runtime", "repair_selectors", "prepare_rerun"])
        self.assertEqual(decision["action_count"], 3)
        self.assertIn("need runtime fix", decision["reasoning_summary"])

    def test_llm_decide_with_progress_diagnostics_supervision(self) -> None:
        """Progress, diagnostics, and supervision are forwarded to the advisor."""
        llm_response = _make_llm_plan_response("prepare_rerun")
        advisor = _make_advisor(return_value=llm_response)
        progress = {"records_saved": 0, "quality_indicator": "fail"}
        diagnostics = {"recommendation": "check access"}
        supervision = {"last_event": {"action": "pause", "reason": "no records"}}

        execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            progress=progress,
            diagnostics=diagnostics,
            supervision=supervision,
        )

        call_kwargs = advisor.choose_managed_actions.call_args.kwargs
        self.assertEqual(call_kwargs["progress"], progress)
        self.assertEqual(call_kwargs["diagnostics"], diagnostics)
        self.assertEqual(call_kwargs["supervision"], supervision)

    def test_llm_decide_empty_plan_falls_back(self) -> None:
        """When the LLM returns no valid actions, a fallback prepare_rerun is created."""
        # Use an all-invalid action list to trigger the fallback in from_dict
        llm_response = {
            "reasoning_summary": "nothing useful",
            "actions": [
                {"action": "run_shell", "params": {"cmd": "echo hi"}},
                {"action": "delete_everything", "params": {}},
            ],
        }
        advisor = _make_advisor(return_value=llm_response)

        result = execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
        )

        executed_actions = [r["action"] for r in result["results"]]
        self.assertEqual(result["plan_source"], "llm")
        # ManagedActionPlan.from_dict adds fallback prepare_rerun when all actions rejected
        self.assertIn("prepare_rerun", executed_actions)
        self.assertEqual(len(executed_actions), 1)

    def test_backward_compatible_without_new_params(self) -> None:
        """Calling execute_managed_action_plan without new params still works."""
        plan = _simple_plan()

        result = execute_managed_action_plan(
            plan=plan,
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
        )

        self.assertEqual(result["plan_source"], "deterministic")
        self.assertFalse(result["llm_decide"])
        self.assertEqual(result["schema_version"], "managed-action-result/v1")


class TestLLMDecisionLoopIntegration(unittest.TestCase):
    """Integration tests that exercise multiple components together."""

    def test_full_loop_with_callbacks_and_execution(self) -> None:
        """Full loop: LLM chooses actions, they execute, callbacks fire."""
        llm_response = _make_llm_plan_response(
            "repair_selectors", "adjust_runtime", "prepare_rerun",
            reasoning="zero records, need selector repair and runtime switch",
        )
        advisor = _make_advisor(return_value=llm_response)
        decisions: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []

        result = execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_decision_callback=lambda d: decisions.append(d),
            llm_trace_callback=lambda t: traces.append(t),
            progress={"records_saved": 0, "quality_indicator": "fail"},
            diagnostics={},
            supervision={},
        )

        # Verify LLM was consulted
        advisor.choose_managed_actions.assert_called_once()

        # Verify callbacks fired
        self.assertEqual(len(decisions), 1)
        self.assertEqual(len(traces), 1)

        # Verify result structure
        self.assertEqual(result["plan_source"], "llm")
        self.assertTrue(result["llm_decide"])
        self.assertTrue(result["rerun_ready"])
        self.assertIn("profile_patch", result)
        self.assertIn("run_overrides", result)

        # Verify actions were executed
        executed = [r["action"] for r in result["results"]]
        self.assertIn("repair_selectors", executed)
        self.assertIn("adjust_runtime", executed)
        self.assertIn("prepare_rerun", executed)

    def test_decision_recorded_with_timestamp(self) -> None:
        """Decision records include ISO-format timestamps."""
        advisor = _make_advisor()
        decisions: list[dict[str, Any]] = []

        execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_decision_callback=lambda d: decisions.append(d),
        )

        created_at = decisions[0]["created_at"]
        # Should be a valid ISO timestamp
        parsed = datetime.fromisoformat(created_at)
        self.assertIsNotNone(parsed)

    def test_trace_records_duration_ms(self) -> None:
        """Trace records include a non-negative duration_ms."""
        advisor = _make_advisor()
        traces: list[dict[str, Any]] = []

        execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
            llm_trace_callback=lambda t: traces.append(t),
        )

        self.assertGreaterEqual(traces[0]["duration_ms"], 0)

    def test_plan_protocol_validation_preserved(self) -> None:
        """LLM plan protocol validation metadata is preserved in the result."""
        llm_response = _make_llm_plan_response("adjust_runtime", "prepare_rerun")
        advisor = _make_advisor(return_value=llm_response)

        result = execute_managed_action_plan(
            plan=_simple_plan(),
            target_url="https://shop.test",
            profile=_basic_profile(),
            run_spec=_basic_run_spec(),
            advisor=advisor,
            llm_decide=True,
        )

        plan_data = result["plan"]
        self.assertIn("protocol_validation", plan_data)
        validation = plan_data["protocol_validation"]
        self.assertEqual(validation["schema_version"], "managed-action-plan/v2")
        self.assertGreaterEqual(validation["accepted_count"], 1)


if __name__ == "__main__":
    unittest.main()
