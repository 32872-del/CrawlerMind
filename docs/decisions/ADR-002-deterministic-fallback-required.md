# ADR-002: Deterministic Fallback Required

## Status

Accepted

## Date

2026-05-07

## Decision Owner

`LLM-2026-000`

## Context

The project will add optional LLM-assisted Planner and Strategy behavior.
However, normal development and tests must remain usable without API keys,
network model calls, or vendor-specific availability.

## Options

| Option | Pros | Cons |
|---|---|---|
| Make LLM calls mandatory | More agent-like behavior | Breaks offline tests, increases cost and fragility |
| Keep deterministic fallback | Portable, testable, predictable | Requires maintaining rule-based logic alongside LLM path |

## Decision

LLM capabilities may enhance Planner/Strategy, but deterministic fallback is
mandatory.

Normal tests must pass without API keys.

## Consequences

- LLM integration must be optional and injectable.
- Prompts and model decisions should be stored in final state when used.
- Rule-based Planner/Strategy remains the baseline behavior.
- Tests should cover both fallback behavior and mocked LLM behavior.

## Follow-Up

Design the optional LLM Planner/Strategy interface before implementation.
