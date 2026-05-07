# 2026-05-07 Daily Report

## Summary

Started the day by turning Crawler-Mind into a Git-backed project with a remote
truth source. Added the first employee memory model, supervisor handoff, ADR
records, runbooks, and next worker assignments.

## Completed

### Git / Repository

- Initialized local Git repository.
- Pushed `main` to:
  `https://github.com/32872-del/CrawlerMind.git`
- Added `.gitattributes` for stable text/binary handling.
- Added Git workflow runbook.

### Employee Memory

- Added `docs/memory/EMPLOYEE_MEMORY_MODEL.md`.
- Added `docs/memory/HANDOFF_TEMPLATE.md`.
- Added supervisor handoff snapshot:
  `docs/memory/handoffs/2026-05-07_LLM-2026-000_supervisor_handoff.md`.
- Updated employee records with persistent-memory sections.
- Updated onboarding to clarify that future AI sessions take over persistent
  state rather than role-playing an employee.

### ADR / Runbook Foundation

- Added `docs/decisions/ADR_TEMPLATE.md`.
- Added initial accepted ADRs:
  - ADR-001 employee memory is persistent state
  - ADR-002 deterministic fallback required
  - ADR-003 local background jobs are in-memory for MVP
  - ADR-004 fnspider routing is explicit
- Added runbooks:
  - `docs/runbooks/GIT_WORKFLOW.md`
  - `docs/runbooks/EMPLOYEE_TAKEOVER.md`
  - `docs/runbooks/README.md`

### Assignments

- Assigned `LLM-2026-001`:
  `Job Registry Concurrency Limits`
- Assigned `LLM-2026-004`:
  `ADR And Runbook Audit`

### Job Registry Concurrency Limits (LLM-2026-001)

- Added `_max_active_jobs()` reading `CLM_MAX_ACTIVE_JOBS` env var (default 4).
- Added `_count_active_jobs()` counting only `"running"` jobs under lock.
- `POST /crawl` now returns HTTP 429 when active jobs reach the limit.
- Completed and failed jobs do not count as active; slots free on finish.
- 10 new concurrency limit tests added. Total: 20 API tests, 94 suite tests.
- Handoff note and dev log created.
- Supervisor tightened the implementation with `_try_register_job()` so active
  job count and registration happen under the same lock.

### ADR And Runbook Audit (LLM-2026-004)

- Completed docs-only audit:
  `docs/team/audits/2026-05-07_LLM-2026-004_ADR_RUNBOOK_AUDIT.md`.
- Found 9 issues, highest severity high.
- Supervisor accepted the audit and updated stale handoff/runbook guidance.

### LLM Planner / Strategy Interface Design

- Added design plan:
  `docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md`.
- Added proposed ADR-005:
  `docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md`.
- Design keeps deterministic fallback mandatory and LLM advisors injectable.
- Assigned Worker Delta to audit the design before implementation.

### New Assignments

- Assigned `LLM-2026-001` to Job Registry TTL Cleanup.
- Assigned `LLM-2026-004` to LLM Interface Design Audit.

### Job Registry TTL Cleanup (LLM-2026-001)

- Added `_job_retention_seconds()` reading `CLM_JOB_RETENTION_SECONDS` env var
  (default 3600).
- Added `_cleanup_stale_jobs()` removing completed/failed jobs older than TTL.
- Added `_parse_iso()` for robust ISO timestamp parsing.
- Jobs now track `updated_at` alongside `created_at`; `_update_job()` stamps it
  automatically.
- Cleanup runs opportunistically on POST /crawl and GET /crawl/{id}.
- Running jobs are never removed by TTL cleanup.
- 7 new TTL tests added. Total: 27 API tests, 101 suite tests.
- Supervisor accepted the work after API, full-suite, and compile verification.

### LLM Interface Design Audit (LLM-2026-004)

- Completed docs-only audit:
  `docs/team/audits/2026-05-07_LLM-2026-004_LLM_INTERFACE_DOC_AUDIT.md`.
- Found 10 issues, highest severity high.
- Key findings covered advisor injection, raw response persistence,
  validation/merge rules, exact state placement, and timeout/test policy.
- Supervisor accepted the audit and revised the design plan.

### LLM Planner / Strategy Design Revision

- Revised:
  `docs/plans/2026-05-07_LLM_PLANNER_STRATEGY_INTERFACE_DESIGN.md`.
- Accepted:
  `docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md`.
- Locked the Phase A implementation contract:
  closure-based advisor injection, no provider construction in core nodes,
  append-only top-level LLM audit state, bounded/redacted raw response previews,
  value-level strategy validation, and fake-advisor tests only.

### New Assignments After Acceptance

- Assigned `LLM-2026-001`:
  `LLM Advisor Phase A Interfaces`
- Assigned `LLM-2026-004`:
  `LLM Phase A Docs / Readiness Audit`

### LLM Advisor Phase A Interfaces (LLM-2026-001)

- Added `autonomous_crawler/llm/` package:
  - `protocols.py`: `PlanningAdvisor` and `StrategyAdvisor` runtime-checkable
    Protocol definitions.
  - `audit.py`: `build_decision_record()` with bounded/redacted
    `raw_response_preview` (max 2000 chars), `redact_preview()` with secret
    pattern matching for api_key, authorization, cookie, token, password,
    secret.
- Added `make_planner_node(advisor=None)` factory in `planner.py`:
  - No advisor: deterministic output with `llm_enabled=False`, empty
    decisions/errors.
  - With advisor: validates allowed fields (`task_type`, `target_fields`,
    `max_items`, `crawl_preferences`, `constraints`, `reasoning_summary`),
    merges accepted fields into `recon_report`, normalizes `max_items` into
    `constraints.max_items`, records decision/fallback in `llm_decisions`/
    `llm_errors`.
- Added `make_strategy_node(advisor=None)` factory in `strategy.py`:
  - No advisor: deterministic output, preserves existing LLM state.
  - With advisor: validates mode (`http`/`browser`/`api_intercept`), engine
    (empty/`fnspider`, `fnspider` only for product_list), selectors (allowed
    keys, max 300 chars, no control chars), `wait_until`, `max_items`.
  - Appends to existing `llm_decisions`/`llm_errors` from planner.
- Updated `build_crawl_graph()` and `compile_crawl_graph()` with optional
  `planning_advisor`/`strategy_advisor` parameters.
- Updated `agents/__init__.py` exports.
- 34 new fake-advisor tests in `test_llm_advisors.py`. Total: 135 suite tests
  (3 skipped).
- Supervisor added two acceptance-hardening tests:
  - full compiled graph preserves Planner and Strategy `llm_decisions` through
    Validator
  - JSON-shaped raw response secrets are redacted in `raw_response_preview`

### LLM Advisor Phase B/C Merge Hardening (Supervisor)

- Planner advisor output now has value-level validation before merge:
  `task_type`, `target_fields`, `max_items`, `constraints`,
  `crawl_preferences`, and `reasoning_summary`.
- Invalid task types, invalid target fields, invalid max_items, non-scalar
  constraints, and unsupported crawl preference keys are rejected and recorded
  in `llm_decisions`.
- Planner now promotes safe `crawl_preferences` to top-level state, so Strategy
  can actually consume advisor engine preferences.
- Strategy advisor fields now use conservative merge rules:
  - strong deterministic recon selectors are preserved
  - missing selectors can be filled by advisor output
  - known fallback selectors can be replaced by advisor output
  - deterministic `max_items` is preserved on conflict
  - browser mode cannot be downgraded to HTTP by advisor output
  - accepted/rejected fields record final merge results, not just schema
    validity
- Added 7 focused tests for Planner validation and Strategy merge priority.
  Total: 142 suite tests (3 skipped).

## Verification

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 142 tests (skipped=3)
OK

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
OK
```

## Risks

- Remote Git exists, but no branch policy or lock automation exists yet.
- Employee memory is file-based and manual; no retrieval automation yet.
- Job registry still uses in-memory state; concurrency limits added but
  persistence is deferred.
- Completed/failed job registry entries now have TTL cleanup; persistence is
  still deferred.
- LLM Advisor Phase A interfaces implemented and accepted; Phase B/C merge
  hardening implemented. Real provider adapter is still pending.

## Next Day Plan

1. Add OpenAI-compatible provider adapter and CLI opt-in path.
2. Run one real LLM-assisted smoke test with a configured provider.
3. Collect more real site samples before automatic engine selection.
