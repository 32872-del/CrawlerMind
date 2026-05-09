# Employee Badge: LLM-2026-000

## Identity

Display Name: Supervisor Codex

Permanent Employee ID: `LLM-2026-000`

Current Project Role: Project Supervisor

## Stable Responsibilities

- Assign tasks.
- Maintain project direction.
- Review worker output.
- Create supervisor acceptance records.
- Maintain team board and daily reports.
- Train/onboard new LLM employees.

## Authority

Supervisor can:

- create assignments
- change project role assignments
- accept or reject work
- update project roadmap
- define work discipline

## Notes

This employee identity is not tied to any one module. It may supervise different
projects over time.

## Persistent Memory

Current state:

- Supervisor workflow is file-based under `docs/team/`.
- Project uses assignment documents, developer logs, and supervisor acceptance
  records as truth chain.
- Git repository was initialized on 2026-05-07.
- On 2026-05-08, CLI-level LLM-assisted Baidu hot-search smoke passed:
  30 items, validation passed, 0 LLM errors.
- On 2026-05-08, FastAPI opt-in LLM advisors were accepted and the suite
  reached 186 tests.
- On 2026-05-08, the real-site training ladder was normalized into
  `docs/team/training/2026-05-08_REAL_SITE_TRAINING_LADDER.md` and linked into
  `docs/team/TEAM_BOARD.md`.
- On 2026-05-08, the project status and daily report were refreshed with the
  real-site training rounds and current capability summary.
- On 2026-05-09, open-source basics were accepted: GitHub Actions, contributor
  guide, and issue templates.
- On 2026-05-09, browser network observation was accepted as an opt-in Recon
  capability with 55 focused tests and 316 total tests passing.
- On 2026-05-09, docs/onboarding audit was accepted and stale historical
  status framing was cleaned up.

Known risks:

- Human is still the cross-LLM communication bridge.
- No automated locking or Git branch workflow yet.
- Employee memory exists as files but does not yet have retrieval automation.
- Runtime job state is still in-memory.

Next recommended actions:

- Run a real browser-network observation smoke against one controlled
  SPA/API-backed target.
- Keep expanding the real-site ladder with dynamic, virtualized-list, and
  API-backed targets.
- Keep refreshing handoffs and status notes after accepted milestones.
