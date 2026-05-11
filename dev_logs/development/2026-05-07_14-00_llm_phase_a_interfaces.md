# 2026-05-07 14:00 - LLM Advisor Phase A Interfaces

## Goal

Implement Phase A of the optional LLM Planner/Strategy interface design.
Assignment: `2026-05-07_LLM-2026-001_LLM_PHASE_A_INTERFACES`.

Employee: LLM-2026-001 / Worker Alpha
Project Role: ROLE-LLM-INTERFACE

## Changes

### New files

- `autonomous_crawler/llm/__init__.py` - package exports
- `autonomous_crawler/llm/protocols.py` - `PlanningAdvisor` and
  `StrategyAdvisor` runtime-checkable Protocol definitions
- `autonomous_crawler/llm/audit.py` - `build_decision_record()` with
  bounded/redacted `raw_response_preview`, `redact_preview()`,
  `MAX_PREVIEW_LENGTH=2000`
- `autonomous_crawler/tests/test_llm_advisors.py` - 32 fake-advisor tests

### Modified files

- `autonomous_crawler/agents/planner.py`:
  - Added `make_planner_node(advisor=None)` factory
  - Advisor path validates allowed fields, merges accepted fields into
    `recon_report`, normalizes `max_items` into `constraints.max_items`,
    records decision and fallback in `llm_decisions`/`llm_errors`
  - No-advisor path emits `llm_enabled=False`, empty decisions/errors
  - Preserved original `planner_node` unchanged

- `autonomous_crawler/agents/strategy.py`:
  - Added `make_strategy_node(advisor=None)` factory
  - Advisor path validates mode/engine/selectors/wait_until/max_items,
    rejects `fnspider` for ranking_list tasks, rejects unknown selector
    keys and control characters, caps selector length at 300
  - Appends to existing `llm_decisions`/`llm_errors` from planner
  - Preserved original `strategy_node` unchanged

- `autonomous_crawler/workflows/crawl_graph.py`:
  - `build_crawl_graph(planning_advisor=None, strategy_advisor=None)`
  - `compile_crawl_graph(planning_advisor=None, strategy_advisor=None)`
  - Uses `make_planner_node`/`make_strategy_node` factories

- `autonomous_crawler/agents/__init__.py`:
  - Added `make_planner_node`, `make_strategy_node` to exports

### Not modified

- agents/(other than planner/strategy), tools/, workflows/(other than
  crawl_graph), storage/, docs/team/, docs/decisions/

## Tests

```text
python -m unittest autonomous_crawler.tests.test_llm_advisors -v
Ran 32 tests in 0.031s
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 133 tests in 15.557s
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Test Coverage

32 new tests across 9 test classes:

- `TestDeterministicNoAdvisor` (5): no-advisor deterministic output,
  graph compilation, LLM fields present
- `TestPlanningAdvisorSuccess` (5): fields merge, decision record,
  unknown fields rejected, max_items accepted, max_items conflict
- `TestPlanningAdvisorException` (2): fallback used, fallback message
- `TestStrategyAdvisorSuccess` (2): safe fields merge, decision record
- `TestStrategyAdvisorUnsafe` (6): fnspider rejected for ranking_list,
  fnspider accepted for product_list, invalid mode, invalid wait_until,
  negative max_items, unknown selector key
- `TestStrategyAdvisorException` (1): fallback used
- `TestDecisionsSurviveFullPipeline` (2): both decisions present,
  decisions survive through subsequent nodes
- `TestAuditHelpers` (5): redact api_key, redact authorization, no
  change when clean, truncate preview, required fields
- `TestProtocolCompliance` (4): fake/failing advisors satisfy protocols

## Result

Phase A interfaces are complete. Provider-neutral advisor protocols exist
with closure-based injection through graph construction. Deterministic
fallback is preserved when no advisor is provided. LLM audit records are
bounded, redacted, and append-only. All existing tests pass unchanged.

## Known Risks

- `raw_response_preview` truncation may cut JSON mid-structure; acceptable
  for audit purposes.
- Strategy advisor validation is strict; overly cautious rejection is
  safer than permissive acceptance per ADR-005.
- No real provider adapter yet (Phase D).
- Graph state is still dict-based, not Pydantic (deferred per assignment).

## Next Step

Submit for supervisor acceptance. Await Phase B/C assignment.
