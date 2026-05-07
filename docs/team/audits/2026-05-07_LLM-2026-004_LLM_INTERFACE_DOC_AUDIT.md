# 2026-05-07 LLM Interface Design Audit

## Assignee

Employee ID: `LLM-2026-004`

Display Name: Worker Delta

Project Role: `ROLE-DOCS`

Assignment: `2026-05-07_LLM-2026-004_LLM_INTERFACE_DOC_AUDIT`

## Scope

Docs-only audit of the proposed optional LLM Planner/Strategy interface design.

Reviewed:

```text
docs/team/assignments/2026-05-07_LLM-2026-004_LLM_INTERFACE_DOC_AUDIT.md
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
docs/decisions/ADR-002-deterministic-fallback-required.md
docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
PROJECT_STATUS.md
docs/team/TEAM_BOARD.md
docs/runbooks/EMPLOYEE_TAKEOVER.md
docs/team/employees/LLM-2026-004_WORKER_DELTA.md
```

No audited documents were edited.

## Findings

### Finding 1

Severity: high

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

The design proposes `compile_crawl_graph(planning_advisor=None,
strategy_advisor=None)` for dependency injection, but it does not specify how
those advisors are passed into existing LangGraph node functions. Current nodes
are plain functions that receive state; without a concrete injection path, an
implementer might use globals, instantiate providers inside nodes, or place
advisors directly in runtime state. Those approaches could weaken the
deterministic fallback and testability requirements.

Suggested action:

Before implementation, add a concrete injection design: closure-based node
factory, graph builder config object, or explicit state-safe advisor registry.
State which files own the advisor lifecycle and forbid provider construction in
core nodes by default.

### Finding 2

Severity: high

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
```

Issue:

The design says raw LLM responses should be stored in final state, but does not
define redaction, truncation, size limits, or sensitive-data handling. Crawl
goals, target URLs, prompts, and model responses may include proprietary
content, credentials accidentally entered by a user, or large HTML-derived
summaries. Persisting raw responses unbounded could bloat SQLite final states
and leak sensitive data.

Suggested action:

Add an audit-record policy before implementation: maximum raw response length,
redaction rules for secrets/cookies/tokens, and whether raw responses are
stored by default or only in debug mode.

### Finding 3

Severity: medium

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

Allowed planner field `constraints` overlaps with top-level allowed field
`max_items`. Existing planner state stores max item constraints under
`recon_report["constraints"]["max_items"]`, while the design lists both
`max_items` and `constraints`. Without precedence rules, advisor output could
produce conflicting values such as `max_items=30` and `constraints.max_items=50`.

Suggested action:

Define merge precedence and normalization. For example, normalize all item
limits into `constraints.max_items`, reject conflicts, and record rejected
fields in `llm_decisions`.

### Finding 4

Severity: medium

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

Allowed strategy field `selectors` is broad and could let an advisor replace
all inferred selectors at once. This may be safe in tests but risky in real
crawls, especially because malformed selectors and empty extraction behavior
have required hardening. The plan says dangerous fields must be ignored, but
does not define selector validation beyond "allowed strategy fields".

Suggested action:

Define selector validation rules: allowed selector keys, CSS parse validation,
minimum required fields, max selector length, and whether advisor selectors can
replace deterministic selectors or only fill missing fields.

### Finding 5

Severity: medium

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

Allowed strategy fields include `mode` and `engine`, but there is no explicit
safe-list for values. The project has important routing constraints: ranking
lists should stay on lightweight DOM, and fnspider routing is explicit by ADR.
An advisor could suggest `engine="fnspider"` for ranking-list tasks unless
value-level validation is documented.

Suggested action:

Add value-level validation: allowed modes, allowed engines, and task-type
constraints. Explicitly preserve ADR-004 behavior that ranking-list tasks do
not route to fnspider because of advisor suggestions.

### Finding 6

Severity: medium

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

The failure path says advisor exceptions should keep deterministic strategy,
but does not specify how advisor timeouts are controlled. Without timeout
guidance, a real provider adapter might block workflow execution or background
jobs longer than expected.

Suggested action:

Add timeout and retry guidance for advisors. For MVP, prefer no retries inside
core nodes, a short configurable timeout in provider adapters, and clear
fallback recording when the timeout is reached.

### Finding 7

Severity: medium

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

State additions list `llm_decisions`, `llm_enabled`, and `llm_errors`, but the
design does not specify whether these are top-level graph state keys, nested
under `recon_report`/`crawl_strategy`, or persisted by the storage layer
unchanged. Since the graph uses dict state and preservation/merge behavior is
sensitive, unclear state placement can cause lost or overwritten audit records.

Suggested action:

Define exact state locations and merge behavior. Prefer top-level keys with
append-only semantics for `llm_decisions` and `llm_errors`, and include tests
that multiple LLM decisions survive Planner -> Strategy -> Validator.

### Finding 8

Severity: low

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
```

Issue:

ADR-005 is still `Proposed`, while the plan is concrete enough to guide
implementation phases. That is acceptable for design review, but implementation
should not proceed as accepted architecture until ADR-005 is accepted or revised.

Suggested action:

Supervisor should accept or revise ADR-005 after reviewing this audit and
before assigning implementation.

### Finding 9

Severity: low

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

The plan says no tests should require an API key, which is aligned with ADR-002.
However, it does not explicitly say provider adapter tests must use fake clients
or be skipped unless credentials are intentionally configured. A future
provider-adapter task could accidentally introduce network-dependent tests.

Suggested action:

Add test policy: unit tests use fake advisors/fake provider clients only; any
real provider smoke must be opt-in via environment variable and skipped by
default.

### Finding 10

Severity: low

Files:

```text
docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
```

Issue:

The implementation phases are narrow, but Phase A "Add state fields" could be
ambiguous because no code state schema is currently enforced by Pydantic in the
graph. A worker may over-refactor graph state to add LLM fields, increasing risk
for a design that should be additive.

Suggested action:

Clarify that Phase A should be additive and should not migrate graph state
typing or remove deterministic state behavior unless separately assigned.

## Recommended Supervisor Actions

1. Require one short revision to the design before implementation, focused on:
   advisor injection mechanism, validation/merge rules, state placement, and
   raw-response persistence policy.
2. Accept or revise ADR-005 only after those clarifications.
3. Keep implementation phased: interfaces and fake-advisor tests first, no real
   provider adapter until core fallback behavior is proven.
4. Explicitly preserve ADR-004 fnspider routing constraints in LLM Strategy
   validation.

## No-Conflict Confirmation

- No code files were edited.
- No files under `docs/plans/` or `docs/decisions/` were edited.
- No team board, employee, assignment, acceptance, project status, or README
  files were edited.
- Created only assignment-allowed files:
  - audit report
  - developer log
  - handoff note
- Existing dirty file observed before this audit:
  `autonomous_crawler/api/app.py`. It appears related to active API work and was
  not touched.

## Verification

Commands/read checks performed:

```text
git pull origin main
Get-Content docs/runbooks/EMPLOYEE_TAKEOVER.md
Get-Content docs/team/employees/LLM-2026-004_WORKER_DELTA.md
Get-Content docs/team/assignments/2026-05-07_LLM-2026-004_LLM_INTERFACE_DOC_AUDIT.md
Get-Content docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md
Get-Content docs/decisions/ADR-002-deterministic-fallback-required.md
Get-Content docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
Get-Content PROJECT_STATUS.md
Get-Content docs/team/TEAM_BOARD.md
git status --short
```

No test suite was run because this is a docs-only audit.
