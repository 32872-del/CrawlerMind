# LLM Team Workspace

## Purpose

This workspace turns the project into a supervised team workflow:

- Human owner provides project direction.
- Project Supervisor Codex assigns tasks, reviews results, accepts work, and
  updates project direction.
- Worker LLMs have permanent employee IDs and may hold temporary project roles.

The goal is traceability: every task should have an assignee, scope, output,
verification, and supervisor acceptance record.

## Daily Operating Flow

1. Supervisor reads:
   - `PROJECT_STATUS.md`
   - latest `docs/reports/*_DAILY_REPORT.md`
   - `docs/plans/2026-05-05_SHORT_TERM_PLAN.md`
   - open assignments in `docs/team/assignments/`
2. Supervisor assigns work using an assignment document.
3. Worker reads:
   - this workspace
   - its employee badge
   - current project role
   - assignment document
   - relevant project docs and source files
4. Worker implements in its assigned scope.
5. Worker writes dev log and updates required docs.
6. Supervisor validates:
   - scope discipline
   - code behavior
   - tests
   - docs
   - integration risk
7. Supervisor writes acceptance record in `docs/team/acceptance/`.
8. Supervisor updates daily report and project status.

## Supervisor Responsibilities

The supervisor owns:

- Task breakdown.
- Module ownership boundaries.
- Assignment documents.
- Acceptance decisions.
- Daily progress summary.
- Risk analysis.
- Project direction and priority updates.
- New worker onboarding/training.

The supervisor does not need to write every line of code, but must decide what
is accepted as project progress.

## Worker Responsibilities

Each worker must:

- Read its badge and assignment.
- Stay within assigned files unless necessary.
- Avoid reverting others' changes.
- Run required verification commands.
- Write a developer log.
- Report blockers clearly.
- Stop at assignment boundaries.

## Acceptance Rule

A worker task is not considered complete until the supervisor creates an
acceptance record.

Worker dev logs are implementation evidence.

Supervisor acceptance records are project truth.

## Core Files

```text
docs/team/TEAM_WORKSPACE.md
docs/team/TEAM_BOARD.md
docs/team/employees/
docs/team/roles/
docs/team/assignments/
docs/team/acceptance/
docs/team/training/
```

## Identity Model

Permanent identity:

```text
docs/team/employees/
```

Temporary project role:

```text
docs/team/roles/
```

Assignments must include both employee ID and project role.

Legacy note:

```text
docs/team/badges/
```

contains earlier role-oriented badge files kept for traceability. New work
should use permanent employee files under `docs/team/employees/` plus temporary
roles under `docs/team/roles/`.

## Status Labels

- `planned`: task exists but is not assigned.
- `assigned`: worker has been given scope.
- `in_progress`: worker is actively implementing.
- `submitted`: worker says work is ready for review.
- `accepted`: supervisor accepted the work.
- `rework`: supervisor found issues and requested changes.
- `blocked`: worker cannot proceed without decision/input.

## Default Verification Ladder

Workers should run the smallest relevant tests first, then broader tests.

Supervisor acceptance normally requires:

```text
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

For high-risk changes, supervisor may require a real smoke test:

```text
python run_baidu_hot_test.py
```

## Conflict Rules

1. If two workers need the same file, supervisor decides sequencing.
2. Shared files must be edited narrowly.
3. Any shared-file edit must be mentioned in the worker dev log.
4. Supervisor may pause an assignment if integration risk is too high.
5. Do not start browser/executor changes without checking active assignments.
