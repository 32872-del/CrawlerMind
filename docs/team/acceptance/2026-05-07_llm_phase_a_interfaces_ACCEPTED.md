# 2026-05-07 LLM Advisor Phase A Interfaces - ACCEPTED

## Assignment

`docs/team/assignments/2026-05-07_LLM-2026-001_LLM_PHASE_A_INTERFACES.md`

## Assignee

Employee ID: `LLM-2026-001`

Project Role: `ROLE-LLM-INTERFACE`

## Scope Reviewed

Reviewed:

```text
autonomous_crawler/llm/__init__.py
autonomous_crawler/llm/protocols.py
autonomous_crawler/llm/audit.py
autonomous_crawler/agents/planner.py
autonomous_crawler/agents/strategy.py
autonomous_crawler/workflows/crawl_graph.py
autonomous_crawler/agents/__init__.py
autonomous_crawler/tests/test_llm_advisors.py
dev_logs/development/2026-05-07_14-00_llm_phase_a_interfaces.md
docs/memory/handoffs/2026-05-07_LLM-2026-001_llm_phase_a_interfaces.md
```

## Verification

```text
python -m unittest autonomous_crawler.tests.test_llm_advisors -v
Ran 34 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 135 tests
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Accepted Changes

- Added provider-neutral `PlanningAdvisor` and `StrategyAdvisor` protocols.
- Added LLM audit helpers with bounded/redacted `raw_response_preview`.
- Added `make_planner_node()` and `make_strategy_node()` factories.
- Added graph-level advisor injection through `build_crawl_graph()` and
  `compile_crawl_graph()`.
- Preserved zero-argument deterministic graph construction.
- Added top-level append-only `llm_enabled`, `llm_decisions`, and `llm_errors`
  behavior.
- Added planner advisor validation and max item conflict handling.
- Added strategy advisor value validation for mode, engine, selectors,
  `wait_until`, and `max_items`.
- Preserved ADR-004: ranking-list tasks cannot be routed to `fnspider` because
  of advisor output.
- Added fake-advisor tests only. No API key or network dependency.

## Supervisor Hardening

Supervisor added two acceptance-hardening tests:

- full compiled graph preserves both Planner and Strategy `llm_decisions`
  through Validator
- JSON-shaped secret values are redacted in `raw_response_preview`

## Risks / Follow-Up

- Real provider adapters are still deferred.
- Strategy validation may need tuning once real provider output is observed.
- Graph state remains dict-based by design for this phase.
- Phase B/C should deepen merge behavior and integration tests before any real
  provider adapter is added.

## Supervisor Decision

Accepted.
