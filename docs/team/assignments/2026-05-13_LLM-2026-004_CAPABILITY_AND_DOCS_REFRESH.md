# Assignment: CAP-6.2 / Docs Refresh

## Assignee

Employee ID: `LLM-2026-004`

Project role: `ROLE-DOCS`

Status: assigned

Assigned by: `LLM-2026-000`

Date: 2026-05-13

## Capability IDs

```text
CAP-6.2 evidence/audit reporting
CAP-7.3 documentation / onboarding
CAP-5.1 strategy evidence explanation
```

## Goal

Refresh the public and internal documentation so it reflects the new
AntiBotReport, the current advanced diagnostics surface, and the next-step
workflow without overclaiming maturity.

## Required Reading

Start with:

```text
git pull origin main
```

Then read:

```text
PROJECT_STATUS.md
docs/runbooks/ADVANCED_DIAGNOSTICS.md
docs/team/TEAM_BOARD.md
docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md
README.md
docs/team/TEAM_WORKSPACE.md
```

## Allowed Write Scope

You own:

```text
README.md
docs/runbooks/ADVANCED_DIAGNOSTICS.md
docs/team/TEAM_BOARD.md
docs/team/acceptance/*
docs/memory/handoffs/2026-05-13_LLM-2026-004_capability_and_docs_refresh.md
dev_logs/audits/2026-05-13_HH-MM_capability_and_docs_refresh.md
```

Do not edit production code.

## Requirements

1. Add a short AntiBotReport section to the public diagnostics docs.
2. Make sure README points users to the right next docs, not internal clutter.
3. Update the team board with the new assignments and the already accepted
   worker outputs.
4. Audit for stale wording or overclaiming.

## Acceptance

Run:

```text
python -m unittest discover -s autonomous_crawler/tests
```

Docs-only task. Acceptance should focus on clarity, correctness, and absence of
overclaiming.
