# Employee Takeover Runbook

## Purpose

Use this when a new AI session takes over an existing employee ID.

The AI is not role-playing. It is operating persistent project state.

## Required Reading

Read in order:

```text
PROJECT_STATUS.md
docs/team/TEAM_BOARD.md
docs/team/employees/<employee>.md
docs/memory/EMPLOYEE_MEMORY_MODEL.md
latest docs/reports/*_DAILY_REPORT.md
current assignment, if any
relevant docs/team/acceptance/*
relevant dev_logs/*
relevant docs/decisions/*
latest docs/memory/handoffs/*
```

Before docs-only work, also run:

```text
git pull origin main
git status --short
```

If unrelated files are already modified, do not touch them. Mention the dirty
scope in your completion note.

## Required Confirmation

Before editing, reply:

```text
Employee ID:
Operating session:
Current assignment:
Accepted work I inherit:
Known risks I inherit:
Files I may edit:
Files I must avoid:
Open questions:
Latest handoff checked against team board and daily report: yes/no
I understand I am taking over persisted state, not role-playing: yes/no
```

## Work Rules

- Do not edit without assignment.
- Do not claim accepted work unless an acceptance record exists.
- Do not change employee memory unless assigned or approved.
- Write a developer log for every implementation event.
- Supervisor acceptance is required before work becomes project truth.

## End Of Task

Create or update:

```text
dev_logs/YYYY-MM-DD_HH-MM_topic.md
docs/memory/handoffs/YYYY-MM-DD_<employee>_<topic>.md
```

Supervisor creates acceptance records.
