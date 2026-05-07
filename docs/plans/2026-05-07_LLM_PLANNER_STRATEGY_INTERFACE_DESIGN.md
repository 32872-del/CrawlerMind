# 2026-05-07 LLM Planner / Strategy Interface Design

## Goal

Design optional LLM-assisted Planner and Strategy interfaces without breaking
deterministic operation.

This design has been revised after Worker Delta's docs audit on 2026-05-07.

## Design Principles

1. Deterministic fallback is mandatory.
2. Normal tests must pass without API keys or network calls.
3. LLM calls must be injectable and mockable.
4. Provider construction must stay outside core graph nodes.
5. LLM output must be validated before affecting crawl behavior.
6. Side effects stay in typed tools and workflow nodes, not prompts.
7. LLM audit data must be bounded, redacted, and append-only.

## Injection Mechanism

Use graph-level dependency injection through closure-based node factories.

The graph compiler owns advisor lifecycle:

```python
compile_crawl_graph(
    planning_advisor: PlanningAdvisor | None = None,
    strategy_advisor: StrategyAdvisor | None = None,
)
```

`build_crawl_graph()` should accept the same optional advisors and register
wrapped nodes:

```python
graph.add_node("planner", make_planner_node(planning_advisor))
graph.add_node("strategy", make_strategy_node(strategy_advisor))
```

Core node modules may expose factories, but they must not:

- instantiate provider clients directly
- read API keys directly
- store advisor objects inside graph state
- use module-level mutable advisor globals

If no advisor is passed, the compiled graph must behave exactly like today's
deterministic graph.

## Proposed Interfaces

### Planner

Current deterministic Planner remains the baseline.

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
   - normalize max item constraints
   - merge allowed fields into deterministic plan
   - append advisor decision to state
3. if advisor fails or times out:
   - keep deterministic plan
   - append fallback decision and error to state
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

Normalization rule:

- `max_items` is normalized into `recon_report["constraints"]["max_items"]`.
- If both `max_items` and `constraints.max_items` are present and conflict,
  keep the deterministic value when present; otherwise keep `max_items`.
- Record conflicting or ignored values in `rejected_fields`.

### Strategy

Current deterministic Strategy remains the baseline.

```python
class StrategyAdvisor(Protocol):
    def choose_strategy(
        self,
        planner_output: dict[str, Any],
        recon_report: dict[str, Any],
    ) -> dict[str, Any]:
        ...
```

Strategy flow:

```text
1. generate deterministic strategy
2. if advisor is configured:
   - ask advisor for strategy suggestion
   - validate allowed strategy fields and values
   - merge only safe fields
   - append advisor decision to state
3. if advisor fails or times out:
   - keep deterministic strategy
   - append fallback decision and error to state
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

Value-level validation:

- `mode`: allow only `http`, `browser`, `api_intercept`.
- `engine`: allow only empty/default or `fnspider`.
- `engine="fnspider"` may be accepted only for `product_list` tasks.
- Ranking-list tasks must not route to `fnspider` because of advisor output.
- `wait_until`: allow only `domcontentloaded`, `load`, `networkidle`.
- `max_items`: must be a positive integer.

Selector validation:

- Advisor selectors may fill missing selector keys or replace selectors only
  when the replacement is non-empty and syntactically plausible.
- Allowed selector keys:
  `item_container`, `title`, `price`, `image`, `link`, `rank`, `hot_score`,
  `summary`, `description`, `url`, `stock`, `size`, `color`.
- Selector values must be strings no longer than 300 characters.
- Empty selectors, control characters, and unsupported selector keys are
  rejected.
- Malformed selector behavior must remain covered by deterministic extractor
  tests; advisor selector validation should fail closed.

## State Additions

Use top-level graph state keys with append-only semantics:

```text
llm_enabled: bool
llm_decisions: list[dict]
llm_errors: list[str]
```

Planner and Strategy nodes must preserve previous entries. A later node must
append to `llm_decisions` and `llm_errors`, not replace them.

Each decision record:

```text
node
provider
model
input_summary
raw_response_preview
parsed_decision
accepted_fields
rejected_fields
fallback_used
created_at
```

State placement:

- Do not nest `llm_decisions` inside `recon_report` or `crawl_strategy`.
- Persist top-level LLM audit fields with the final workflow state.
- Do not store advisor instances or provider clients in state.

## Raw Response Persistence Policy

Raw provider responses are not stored unbounded.

Store only `raw_response_preview`:

- maximum 2,000 characters by default
- redact common secret patterns before storing:
  `api_key`, `authorization`, `cookie`, `token`, `password`, `secret`
- preserve parsed structured decisions separately after validation
- real provider adapters may offer a debug mode later, but normal workflow
  state must stay bounded

If redaction changes the response, record that fact in the decision record.

## Timeout And Retry Policy

Core nodes should call advisors once. No retry loop belongs inside Planner or
Strategy nodes.

Provider adapters may enforce a short configurable timeout. On timeout:

- keep deterministic output
- append an `llm_errors` entry
- append a decision record with `fallback_used=true`

Normal tests must use fake advisors or fake provider clients only. Any real LLM
smoke test must be opt-in through an environment variable and skipped by
default.

## Configuration

No advisor:

```python
compile_crawl_graph()
```

Fake advisor in tests:

```python
compile_crawl_graph(planning_advisor=FakePlanningAdvisor())
```

Future provider adapter:

```python
from autonomous_crawler.llm.openai_adapter import OpenAIPlanningAdvisor

compile_crawl_graph(planning_advisor=OpenAIPlanningAdvisor(...))
```

Provider adapter code should live outside existing agent nodes, preferably under
`autonomous_crawler/llm/`.

## Test Plan

Required tests:

1. no advisor -> current deterministic behavior unchanged
2. planning advisor success -> accepted fields merged
3. planning advisor invalid output -> fallback used
4. planning advisor exception -> fallback used
5. planning advisor conflict -> deterministic/normalized constraint preserved
6. strategy advisor success -> accepted safe fields merged
7. strategy advisor dangerous fields -> rejected
8. strategy advisor invalid mode/engine -> rejected
9. strategy advisor exception -> fallback used
10. multiple LLM decisions survive Planner -> Strategy -> Validator

No test should require an API key.

## Implementation Phases

### Phase A: Interfaces And State

- Add protocol definitions.
- Add node factories and graph injection parameters.
- Add append-only LLM audit helpers.
- Add fake-advisor tests.
- Do not migrate graph state to Pydantic in this phase.

### Phase B: Planner Advisor

- Add optional advisor path to Planner.
- Validate and merge allowed intent fields.
- Normalize item limits into `recon_report["constraints"]["max_items"]`.

### Phase C: Strategy Advisor

- Add optional advisor path to Strategy.
- Validate and merge allowed strategy fields.
- Preserve ADR-004 fnspider routing constraints.

### Phase D: Provider Adapter

- Add optional provider adapter after interfaces are stable.
- Keep real-provider tests opt-in and skipped by default.

## Supervisor Decision

Design revised after audit and approved for Phase A implementation.
