# ADR-001: Employee Memory Is Persistent State

## Status

Accepted

## Date

2026-05-07

## Decision Owner

`LLM-2026-000`

## Context

The project uses multiple AI sessions as workers. A new AI session may need to
continue work previously done under an employee ID.

If continuity depends on chat history or role-play instructions, the project
will lose memory when the environment changes.

## Options

| Option | Pros | Cons |
|---|---|---|
| Treat employees as prompts/personas | Easy to start | Fragile, encourages role-play, loses factual continuity |
| Treat employees as persistent project state | Auditable, transferable, model-independent | Requires maintaining memory files |

## Decision

Employee identity is persistent project state.

An AI session temporarily operates an employee ID, but the employee is defined
by repository files:

```text
docs/team/employees/
docs/team/assignments/
docs/team/acceptance/
docs/memory/
dev_logs/
```

## Consequences

- New AI sessions must read memory files before acting.
- Employee files should record accepted work, strengths, risks, and handoff
  context.
- Supervisor acceptance records remain project truth.
- This is not role-play; it is state takeover.

## Follow-Up

Add lightweight memory checks to future onboarding and assignment workflows.
