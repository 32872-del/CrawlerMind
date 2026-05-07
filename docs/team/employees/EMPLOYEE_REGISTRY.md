# LLM Employee Registry

## Principle

Employee identity is fixed.

Project roles are temporary.

An employee can work on different modules or even different projects over time,
but keeps the same employee badge for continuity and traceability.

## ID Format

```text
LLM-YYYY-XXX
```

Examples:

```text
LLM-2026-001
LLM-2026-002
LLM-2026-003
```

## Current Employees

| Employee ID | Display Name | Default Strength | Current Project Role | Status |
|---|---|---|---|---|
| LLM-2026-000 | Supervisor Codex | project supervision, architecture, review | Project Supervisor | active |
| LLM-2026-001 | Worker Alpha | browser/executor implementation, API boundary work | API Job Worker | assigned |
| LLM-2026-002 | Worker Beta | QA and error-path hardening | Error Path QA Worker | active |
| LLM-2026-003 | Worker Gamma | storage/CLI and strategy support | Unassigned | standby |
| LLM-2026-004 | Worker Delta | onboarding, project reading, risk identification | Documentation Worker | assigned |

## Assignment Rule

Every assignment should identify both:

```text
Employee ID
Project Role
```

Example:

```text
Employee ID: LLM-2026-001
Project Role: Browser Executor Worker
Assignment: Browser Fallback MVP
```

## Updating This Registry

Supervisor updates this file when:

- a new LLM joins
- an LLM changes display name
- an LLM changes project role
- an LLM becomes inactive
- a new stable skill profile is discovered
