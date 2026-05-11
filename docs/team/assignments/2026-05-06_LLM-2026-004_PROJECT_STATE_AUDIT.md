# Assignment: Project State Consistency Audit

Assignment ID: `2026-05-06_LLM-2026-004_PROJECT_STATE_AUDIT`

Employee ID: `LLM-2026-004`

Project Role: `ROLE-DOCS`

Status: `accepted`

Supervisor: `LLM-2026-000`

## Objective

Perform a narrow documentation consistency audit after today's rapid multi-LLM
development.

Your goal is to find stale or conflicting project-state claims across status,
reports, plans, team board, assignments, and acceptance records.

This is your first scoped assignment. It is intentionally documentation-only.

## Required Reading

Read:

```text
PROJECT_STATUS.md
README.md
docs/reports/2026-05-06_DAILY_REPORT.md
docs/plans/2026-05-05_SHORT_TERM_PLAN.md
docs/team/TEAM_BOARD.md
docs/team/TEAM_WORKSPACE.md
docs/team/employees/EMPLOYEE_REGISTRY.md
docs/team/roles/PROJECT_ROLES.md
docs/team/assignments/
docs/team/acceptance/
dev_logs/
```

Skim:

```text
docs/reviews/2026-05-05_ENGINEERING_REVIEW.md
docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md
```

## Owned Files

You may create exactly one audit report:

```text
docs/team/audits/2026-05-06_LLM-2026-004_PROJECT_STATE_AUDIT.md
```

If the `docs/team/audits/` directory does not exist, create it.

You may also write one developer log:

```text
dev_logs/audits/2026-05-06_HH-MM_project_state_audit.md
```

## Avoid Files

Do not edit:

```text
autonomous_crawler/
run_*.py
README.md
PROJECT_STATUS.md
docs/reports/
docs/plans/
docs/team/TEAM_BOARD.md
docs/team/employees/
docs/team/roles/
docs/team/assignments/
docs/team/acceptance/
```

For this assignment, do not directly fix inconsistencies. Report them for
supervisor review.

## Required Audit Report Format

Use this exact structure:

```text
# 2026-05-06 Project State Consistency Audit

## Assignee

## Scope

## Findings

## Recommended Supervisor Actions

## No-Conflict Confirmation

## Verification
```

For each finding, include:

```text
Severity: high/medium/low
Files:
Issue:
Suggested action:
```

## What To Look For

Check for:

- completed work still shown as assigned or pending
- accepted work missing acceptance record
- status documents claiming capabilities not represented in tests
- stale upcoming task order
- employee role mismatch between registry, badge, and team board
- old role-oriented badge docs that could confuse new workers
- missing daily report mention for accepted work
- project limitations that no longer match implementation

## Required Verification

This is a docs-only audit. Do not run full tests unless you need to confirm a
specific status claim.

At minimum, verify file presence with shell commands such as:

```text
Get-ChildItem docs\team\acceptance
Get-ChildItem dev_logs
```

## Required Worker Deliverables

1. Audit report.
2. Developer log.
3. Short completion note listing:

```text
files created
number of findings
highest severity
recommended next supervisor action
```

## Supervisor Acceptance Checklist

Supervisor will verify:

- report exists
- dev log exists
- no code files changed
- no protected docs were edited
- findings are specific and actionable
- worker stayed within scope

Acceptance record target:

```text
docs/team/acceptance/2026-05-06_project_state_audit_ACCEPTED.md
```
