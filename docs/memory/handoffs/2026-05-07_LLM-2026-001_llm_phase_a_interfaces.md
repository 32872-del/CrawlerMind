# Handoff: LLM Advisor Phase A Interfaces

Employee: LLM-2026-001
Date: 2026-05-07
Assignment: `2026-05-07_LLM-2026-001_LLM_PHASE_A_INTERFACES`

## What Was Done

Implemented Phase A of the optional LLM Planner/Strategy interfaces:

- `autonomous_crawler/llm/protocols.py`: `PlanningAdvisor` and
  `StrategyAdvisor` runtime-checkable Protocol definitions.
- `autonomous_crawler/llm/audit.py`: bounded/redacted decision records
  with `MAX_PREVIEW_LENGTH=2000`, secret redaction for api_key,
  authorization, cookie, token, password, secret.
- `autonomous_crawler/agents/planner.py`: `make_planner_node(advisor)`
  factory with field validation, max_items normalization, fallback on error.
- `autonomous_crawler/agents/strategy.py`: `make_strategy_node(advisor)`
  factory with mode/engine/selector validation, fnspider routing guard,
  fallback on error.
- `autonomous_crawler/workflows/crawl_graph.py`: optional
  `planning_advisor`/`strategy_advisor` params on `build_crawl_graph()`
  and `compile_crawl_graph()`.
- `autonomous_crawler/tests/test_llm_advisors.py`: 32 tests, all fake
  advisors, no API key, no network.

## Files Changed

- `autonomous_crawler/llm/__init__.py` (new)
- `autonomous_crawler/llm/protocols.py` (new)
- `autonomous_crawler/llm/audit.py` (new)
- `autonomous_crawler/agents/planner.py` - added factory
- `autonomous_crawler/agents/strategy.py` - added factory + validation
- `autonomous_crawler/workflows/crawl_graph.py` - advisor params
- `autonomous_crawler/agents/__init__.py` - updated exports
- `autonomous_crawler/tests/test_llm_advisors.py` (new)

## Test Status

32 new LLM advisor tests pass. Full suite: 133 tests (3 skipped).
Compile check: OK.

## What Is NOT Changed

- No real provider adapter (deferred to Phase D).
- No Pydantic graph state migration (deferred per assignment).
- No changes to agents/executor, agents/extractor, agents/validator,
  agents/recon, tools/, storage/, docs/team/, docs/decisions/.

## Known Open Issues

- Phase B (Planner advisor merge logic) and Phase C (Strategy advisor
  merge logic) need implementation with more detailed merge tests.
- Strategy validation may need tuning if real providers return unexpected
  but safe fields.

## Environment

- No new environment variables added.
- No new dependencies added.
