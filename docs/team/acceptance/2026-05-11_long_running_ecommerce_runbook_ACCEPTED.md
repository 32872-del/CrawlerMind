# Acceptance: Long-Running Ecommerce Runbook

Date: 2026-05-11

Accepted by: LLM-2026-000 Supervisor Codex

## Accepted Artifact

- `docs/runbooks/LONG_RUNNING_ECOMMERCE_RUNS.md`

## Acceptance Notes

The runbook is accepted as the current operating policy for large ecommerce
crawls. It captures the main lesson from the 30,000-record local stress test:
large runs must checkpoint product records and frontier progress in batches,
not wait until final workflow state is available.

## Follow-Ups

- Add a resumable ecommerce runner that follows this runbook directly.
- Add progress summaries suitable for FastAPI or a future frontend dashboard.
