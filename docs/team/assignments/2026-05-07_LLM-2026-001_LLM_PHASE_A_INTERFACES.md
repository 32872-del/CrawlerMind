# Assignment: LLM Advisor Phase A Interfaces

## Assignee

Employee ID: `LLM-2026-001`

Project Role: `ROLE-LLM-INTERFACE`

## Objective

Implement Phase A of the optional LLM Planner/Strategy interface design without
adding any real provider dependency.

This is interface and fake-advisor test work only.

## Required Reading

Start with:

```text
git pull origin main
```

Then read:

```text
docs/runbooks/EMPLOYEE_TAKEOVER.md
docs/team/employees/LLM-2026-001_WORKER_ALPHA.md
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
docs/decisions/ADR-002-deterministic-fallback-required.md
docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
PROJECT_STATUS.md
```

## Allowed Write Scope

You may edit:

```text
autonomous_crawler/llm/
autonomous_crawler/agents/planner.py
autonomous_crawler/agents/strategy.py
autonomous_crawler/workflows/crawl_graph.py
autonomous_crawler/tests/test_llm_advisors.py
dev_logs/development/2026-05-07_HH-MM_llm_phase_a_interfaces.md
docs/memory/handoffs/2026-05-07_LLM-2026-001_llm_phase_a_interfaces.md
PROJECT_STATUS.md
docs/reports/2026-05-07_DAILY_REPORT.md
```

Avoid unrelated files.

## Requirements

1. Add provider-neutral advisor protocols.
2. Add closure-based node factories for Planner and Strategy.
3. Add optional advisor parameters to `build_crawl_graph()` and
   `compile_crawl_graph()`.
4. Preserve exact deterministic behavior when no advisor is provided.
5. Add append-only top-level state fields:
   `llm_enabled`, `llm_decisions`, `llm_errors`.
6. Store bounded/redacted `raw_response_preview`, not unbounded raw responses.
7. Add fake-advisor tests only. No API key. No network.
8. Do not add a real OpenAI adapter in this assignment.
9. Do not migrate graph state to Pydantic in this assignment.

## Minimum Tests

Add or update tests proving:

```text
no advisor -> deterministic graph still works
planning advisor success -> accepted fields merge
planning advisor exception -> fallback used and recorded
strategy advisor success -> safe fields merge
strategy advisor unsafe engine/mode -> rejected and recorded
planner + strategy decisions survive in final state
```

Run:

```text
python -m unittest autonomous_crawler.tests.test_llm_advisors -v
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

## Deliverables

- Code changes inside allowed scope.
- Focused tests.
- Developer log.
- Handoff note.
- Short completion report listing changed files, test output, risks, and next
  recommended step.

## Supervisor Notes

The most important acceptance criterion is that existing deterministic tests
continue to pass without advisors. The second most important criterion is that
advisor output is validated before it changes crawl behavior.
