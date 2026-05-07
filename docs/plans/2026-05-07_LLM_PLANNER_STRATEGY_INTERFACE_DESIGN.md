# 2026-05-07 LLM Planner / Strategy Interface Design

## Goal

Design optional LLM-assisted Planner and Strategy interfaces without breaking
deterministic operation.

This is a design task before implementation.

## Design Principles

1. Deterministic fallback is mandatory.
2. Normal tests must pass without API keys.
3. LLM calls must be injectable and mockable.
4. LLM prompts, responses, and parsed decisions should be stored in final state
   when used.
5. LLM output must be validated before affecting crawl behavior.
6. Side effects stay in typed tools and workflow nodes, not prompts.

## Proposed Interfaces

### Planner

Current deterministic Planner should remain baseline.

Add an optional planning advisor:

```python
class PlanningAdvisor(Protocol):
    def plan(self, user_goal: str, target_url: str) -> dict[str, Any]:
        ...
```

Planner flow:

```text
1. run deterministic planner
2. if advisor is configured:
   - ask advisor for normalized intent
   - validate advisor output
   - merge allowed fields into deterministic plan
   - record advisor decision in state
3. if advisor fails:
   - keep deterministic plan
   - append warning to messages/error_log
```

Allowed advisor fields:

```text
task_type
target_fields
max_items
crawl_preferences
constraints
reasoning_summary
```

### Strategy

Current deterministic Strategy should remain baseline.

Add an optional strategy advisor:

```python
class StrategyAdvisor(Protocol):
    def choose_strategy(self, planner_output: dict[str, Any], recon_report: dict[str, Any]) -> dict[str, Any]:
        ...
```

Strategy flow:

```text
1. generate deterministic strategy
2. if advisor is configured:
   - ask advisor for strategy suggestion
   - validate allowed strategy fields
   - merge only safe fields
   - record advisor decision in state
3. if advisor fails:
   - keep deterministic strategy
```

Allowed advisor fields:

```text
mode
engine
selectors
wait_selector
wait_until
max_items
reasoning_summary
```

Dangerous or unsupported fields must be ignored.

## State Additions

Add optional state keys:

```text
llm_decisions: list[dict]
llm_enabled: bool
llm_errors: list[str]
```

Each decision record:

```text
node
provider
model
input_summary
raw_response
parsed_decision
accepted_fields
rejected_fields
fallback_used
created_at
```

## Configuration

Do not instantiate real OpenAI clients in core nodes by default.

Use dependency injection or config object:

```python
compile_crawl_graph(planning_advisor=None, strategy_advisor=None)
```

If no advisor is passed, current behavior remains unchanged.

## Test Plan

Required tests:

1. no advisor -> current deterministic behavior unchanged
2. planning advisor success -> accepted fields merged
3. planning advisor invalid output -> fallback used
4. planning advisor exception -> fallback used
5. strategy advisor success -> accepted safe fields merged
6. strategy advisor dangerous fields -> rejected
7. strategy advisor exception -> fallback used
8. final state records llm decisions when advisor is used

No test should require an API key.

## Implementation Phases

### Phase A: Interfaces And State

- Add protocol definitions.
- Add state fields.
- Add mock tests.

### Phase B: Planner Advisor

- Add optional advisor path to Planner.
- Validate and merge allowed intent fields.

### Phase C: Strategy Advisor

- Add optional advisor path to Strategy.
- Validate and merge allowed strategy fields.

### Phase D: Provider Adapter

- Add optional provider adapter after interfaces are stable.
- Keep it outside tests by default.

## Open Questions

- Should advisors be passed through `compile_crawl_graph()` or initial state?
- Should provider adapter live under `autonomous_crawler/llm/` or
  `autonomous_crawler/tools/`?
- How much raw LLM response should be persisted for debugging while avoiding
  large final states?
