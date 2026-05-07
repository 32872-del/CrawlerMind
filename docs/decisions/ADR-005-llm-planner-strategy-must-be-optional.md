# ADR-005: LLM Planner And Strategy Must Be Optional

## Status

Proposed

## Date

2026-05-07

## Decision Owner

`LLM-2026-000`

## Context

The project needs to move from deterministic pipeline behavior toward a more
autonomous agent. Planner and Strategy are the best first places to add LLM
assistance.

However, the project must remain portable, testable, and usable without API
keys.

## Options

| Option | Pros | Cons |
|---|---|---|
| Directly call an LLM inside Planner/Strategy | Fast to prototype | Hard to test, requires API keys, couples graph to provider |
| Add optional advisor interfaces | Testable, provider-neutral, deterministic fallback remains | More design work before visible behavior |
| Keep deterministic only | Stable | Does not advance agent capability |

## Decision

Proposed decision:

Planner and Strategy may use optional advisor interfaces, but deterministic
fallback remains the default and required behavior.

No API key should be required for normal tests.

## Consequences

- Advisor implementations must be injectable and mockable.
- LLM output must be validated before it can affect crawling.
- LLM decisions should be recorded in final state for audit.
- Provider-specific adapters should be separate from core graph logic.

## Follow-Up

Review design in:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Accept or revise this ADR before implementation.
