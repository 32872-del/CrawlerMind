# Collaboration Guide

## Purpose

This project will be developed by humans and multiple Codex agents. The goal of
this guide is to keep work parallel, traceable, and easy to resume.

## Required Reading Order

Before starting a development session, read:

1. `PROJECT_STATUS.md`
2. `docs/team/TEAM_WORKSPACE.md`
3. `docs/team/TEAM_BOARD.md`
4. Latest file in `docs/reports/`
5. Latest relevant file in `dev_logs/`
6. `docs/plans/2026-05-05_SHORT_TERM_PLAN.md`
7. The files in the module you will edit

For architectural work, also read:

1. `docs/blueprints/AUTONOMOUS_CRAWL_AGENT_BLUEPRINT.md`
2. Relevant engineering review in `docs/reviews/`

## File Organization

Root directory:

- Keep only project entry docs, runnable scripts, requirements, and status.

`docs/blueprints/`:

- Long-term architecture and capability designs.
- These are not daily logs.

`docs/reviews/`:

- External/internal engineering reviews.
- Preserve original review content for historical comparison.

`docs/plans/`:

- Short-term implementation plans.
- Update when priorities change.

`docs/reports/`:

- Daily human-readable reports.
- One file per day.
- Summarize progress, verification, risks, and next actions.

`docs/process/`:

- Development rules, collaboration rules, packaging rules.

`docs/team/`:

- Supervisor/worker workspace.
- Worker badges.
- Assignment documents.
- Supervisor acceptance records.
- New worker training.

`dev_logs/`:

- Developer evidence only.
- Put implementation notes in `development/`.
- Put QA/audit notes in `audits/`.
- Put training exports in `training/`, smoke outputs in `smoke/`, and stress
  outputs in `stress/`.
- Put scratch command state in `runtime/`; it is not tracked.
- Do not put broad blueprint documents or engineering reviews here.

## Naming Rules

Developer logs:

```text
dev_logs/development/YYYY-MM-DD_HH-MM_short_topic.md
```

Daily reports:

```text
docs/reports/YYYY-MM-DD_DAILY_REPORT.md
```

Plans:

```text
docs/plans/YYYY-MM-DD_SHORT_TERM_PLAN.md
```

Reviews:

```text
docs/reviews/YYYY-MM-DD_REVIEW_TOPIC.md
```

Blueprints:

```text
docs/blueprints/TOPIC_BLUEPRINT.md
```

## Developer Log Format

Each developer log should include:

```text
# YYYY-MM-DD HH:MM - Topic

## Goal
## Changes
## Verification
## Result
## Next Step
```

Keep it factual and developer-oriented. Avoid broad essays.

## Daily Report Format

Each daily report should include:

```text
# YYYY-MM-DD Daily Report

## Summary
## Completed
## Verification
## Risks
## Next Day Plan
```

Daily reports are for project continuity, not implementation details.

## Multi-Codex Work Rules

1. Each Codex should own a clear module or file set.
2. Do not edit files outside your assigned scope unless necessary.
3. If you must touch shared files, record it in your dev log.
4. Do not revert another agent's changes.
5. Before editing, inspect the latest file contents.
6. After editing, run the smallest relevant tests first, then broader tests.
7. Update docs only when behavior, architecture, or workflow changes.
8. Prefer additive changes over broad refactors during parallel work.

## Suggested Ownership Slices

API Codex:

- `autonomous_crawler/api/`
- API tests

Storage Codex:

- `autonomous_crawler/storage/`
- storage tests

Browser Codex:

- browser executor tools
- browser-mode tests

Planner/Strategy Codex:

- `autonomous_crawler/agents/planner.py`
- `autonomous_crawler/agents/strategy.py`
- prompts

Recon Codex:

- `autonomous_crawler/tools/html_recon.py`
- `autonomous_crawler/tools/recon_tools.py`
- recon tests

Docs Codex:

- `docs/`
- `PROJECT_STATUS.md`
- `README.md`

## Definition of Done

A task is done only when:

1. Code is implemented.
2. Relevant tests pass.
3. Any changed behavior is documented.
4. A developer log is written.
5. `PROJECT_STATUS.md` is updated if project status changed.
6. The supervisor writes an acceptance record under `docs/team/acceptance/`.
