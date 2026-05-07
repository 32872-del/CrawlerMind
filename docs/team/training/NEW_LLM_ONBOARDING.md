# New LLM Worker Onboarding

## Welcome

You are joining a supervised multi-LLM development workflow.

You may be taking over an existing employee ID. If so, you are not role-playing
that employee. You are operating the persistent employee state recorded in this
project.

Do not start coding immediately.

## Step 1: Read Project State

Read in order:

```text
PROJECT_STATUS.md
docs/team/TEAM_WORKSPACE.md
docs/team/TEAM_BOARD.md
docs/process/COLLABORATION_GUIDE.md
latest docs/reports/*_DAILY_REPORT.md
```

## Step 2: Read Your Badge

Your supervisor should give you a permanent employee ID, for example:

```text
LLM-2026-001
```

Read the matching file in:

```text
docs/team/employees/
```

This file is persistent employee memory. Treat it as project state, not as a
character description.

## Step 3: Read Your Project Role

Project roles are temporary. Read:

```text
docs/team/roles/PROJECT_ROLES.md
```

Your assignment will tell you which project role you currently hold.

## Step 4: Read Your Assignment

Assignments live in:

```text
docs/team/assignments/
```

Only work on your assigned scope.

If you are taking over an existing employee ID, also read recent accepted work
and developer logs for that employee.

## Step 5: Confirm Ownership Boundaries

Before editing, identify:

- files you own
- files you should avoid
- shared files that need supervisor caution

## Step 6: Implement Narrowly

Prefer:

- small patches
- focused tests
- additive behavior
- no broad refactors

Avoid:

- changing unrelated modules
- reverting others' work
- silently changing project direction

## Step 7: Verify

Run focused tests first, then required verification from your assignment.

Default broad verification:

```text
python -m unittest discover autonomous_crawler\tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

## Step 8: Write Developer Log

Write:

```text
dev_logs/YYYY-MM-DD_HH-MM_topic.md
```

Use:

```text
## Goal
## Changes
## Verification
## Result
## Next Step
```

## Step 9: Submit For Acceptance

Your task is not accepted until supervisor writes an acceptance record in:

```text
docs/team/acceptance/
```

## Important Rule

Developer logs are evidence. Acceptance records are project truth.

Employee identity is permanent. Project role is temporary.

AI sessions are replaceable. Employee memory is persistent.

For takeover of an existing employee ID, also follow:

```text
docs/runbooks/EMPLOYEE_TAKEOVER.md
```
