# Assignment: Open Source Docs And Onboarding Audit

Employee ID: `LLM-2026-004`

Project role: `ROLE-DOCS`

Status: assigned

Assigned by: `LLM-2026-000`

Date: 2026-05-09

## Goal

Audit the repository as if you are a new outside contributor arriving from
GitHub.

The project was just prepared for open-source sync. Your job is to find docs
gaps, stale status, confusing onboarding, and mismatches between README,
runbooks, team board, and project status.

## Scope

Read and audit:

```text
README.md
LICENSE
PROJECT_STATUS.md
docs/runbooks/
docs/team/TEAM_BOARD.md
docs/team/training/
docs/reports/2026-05-08_STAGE_AND_BLUEPRINT_ANALYSIS.txt
```

If `LLM-2026-001` completes CI/contributor files before you finish, also audit:

```text
CONTRIBUTING.md
.github/
```

## Deliverables

Create:

```text
docs/team/audits/2026-05-09_LLM-2026-004_OPEN_SOURCE_DOCS_AUDIT.md
dev_logs/2026-05-09_HH-MM_open_source_docs_audit.md
docs/memory/handoffs/2026-05-09_LLM-2026-004_open_source_docs_audit.md
```

## Audit Questions

Answer:

- Can a new user install on Windows, Linux, and macOS?
- Is it clear how to run without an API key?
- Is it clear how to configure an OpenAI-compatible API?
- Is it clear that hostile anti-bot bypass is out of scope?
- Are project status and team board consistent?
- Are open-source release gaps visible?
- Are there stale or misleading docs?

## Constraints

- Prefer audit findings over large edits.
- Do not rewrite README unless specifically assigned.
- Do not edit code.
- Do not revert other workers' changes.

## Completion Report

Report:

- number of findings
- highest severity
- files created
- recommended supervisor action
