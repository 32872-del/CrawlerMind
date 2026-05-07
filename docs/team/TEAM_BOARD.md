# Team Board

Last updated: 2026-05-07

## Active Employees

| Employee ID | Display Name | Current Project Role | Status | Current Assignment |
|---|---|---|---|---|
| LLM-2026-000 | Supervisor Codex | Project Supervisor | active | project direction, assignments, acceptance |
| LLM-2026-001 | Worker Alpha | LLM Interface Worker | assigned | LLM Advisor Phase A Interfaces |
| LLM-2026-002 | Worker Beta | Error Path QA Worker | accepted | Error-path hardening |
| LLM-2026-003 | Worker Gamma | Unassigned | standby | none |
| LLM-2026-004 | Worker Delta | Documentation Worker | assigned | LLM Phase A Docs / Readiness Audit |

## Current Project Roles

| Role ID | Role Name | Current Employee | Status |
|---|---|---|---|
| ROLE-SUPERVISOR | Project Supervisor | LLM-2026-000 | active |
| ROLE-BROWSER | Browser Executor Worker | LLM-2026-001 | accepted |
| ROLE-QA | Error Path QA Worker | LLM-2026-002 | accepted |
| ROLE-STORAGE | Storage / CLI Worker | LLM-2026-003 | accepted work completed |
| ROLE-STRATEGY | Strategy / Engine Routing Worker | LLM-2026-003 | accepted work completed |
| ROLE-API | API Job Worker | LLM-2026-001 | assigned |
| ROLE-DOCS | Documentation Worker | LLM-2026-004 | assigned |
| ROLE-LLM-INTERFACE | LLM Interface Worker | LLM-2026-001 | assigned |

## Assignment Records

| Assignment | Employee ID | Project Role | Status | Acceptance |
|---|---|---|---|---|
| Browser Fallback MVP | LLM-2026-001 | ROLE-BROWSER | accepted | `docs/team/acceptance/2026-05-06_browser_fallback_ACCEPTED.md` |
| FastAPI background job execution | LLM-2026-001 | ROLE-API | accepted | `docs/team/acceptance/2026-05-06_fastapi_background_jobs_ACCEPTED.md` |
| New worker onboarding and project orientation | LLM-2026-004 | Onboarding | accepted | `docs/team/acceptance/2026-05-06_worker_delta_onboarding_ACCEPTED.md` |
| Project State Consistency Audit | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-06_project_state_audit_ACCEPTED.md` |
| Real Browser SPA Smoke | LLM-2026-001 | ROLE-BROWSER | accepted | `docs/team/acceptance/2026-05-06_real_browser_spa_smoke_ACCEPTED.md` |
| Job Registry Concurrency Limits | LLM-2026-001 | ROLE-API | accepted | `docs/team/acceptance/2026-05-07_job_registry_limits_ACCEPTED.md` |
| ADR And Runbook Audit | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-07_adr_runbook_audit_ACCEPTED.md` |
| Job Registry TTL Cleanup | LLM-2026-001 | ROLE-API | accepted | `docs/team/acceptance/2026-05-07_job_registry_ttl_cleanup_ACCEPTED.md` |
| LLM Interface Design Audit | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-07_llm_interface_doc_audit_ACCEPTED.md` |
| LLM Advisor Phase A Interfaces | LLM-2026-001 | ROLE-LLM-INTERFACE | assigned | pending |
| LLM Phase A Docs / Readiness Audit | LLM-2026-004 | ROLE-DOCS | assigned | pending |

## Accepted Work Today

| Module | Employee ID | Acceptance Record | Summary |
|---|---|---|---|
| Storage / CLI | LLM-2026-003 | `docs/team/acceptance/2026-05-06_result_cli_ACCEPTED.md` | `run_results.py`, exports, CLI tests |
| Error Paths | LLM-2026-002 | `docs/team/acceptance/2026-05-06_error_paths_ACCEPTED.md` | 30 error-path tests, extractor hardening, recon fail-fast |
| Fnspider Routing | LLM-2026-003 | `docs/team/acceptance/2026-05-06_fnspider_routing_ACCEPTED.md` | explicit product-list fnspider routing |
| Browser Fallback | LLM-2026-001 | `docs/team/acceptance/2026-05-06_browser_fallback_ACCEPTED.md` | Playwright rendered HTML executor path |
| FastAPI Background Jobs | LLM-2026-001 | `docs/team/acceptance/2026-05-06_fastapi_background_jobs_ACCEPTED.md` | non-blocking `/crawl`, in-memory job registry |
| Worker Delta Onboarding | LLM-2026-004 | `docs/team/acceptance/2026-05-06_worker_delta_onboarding_ACCEPTED.md` | onboarding accepted, identified stale board state |
| Real Browser SPA Smoke | LLM-2026-001 | `docs/team/acceptance/2026-05-06_real_browser_spa_smoke_ACCEPTED.md` | local JS-rendered SPA smoke accepted |
| Project State Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-06_project_state_audit_ACCEPTED.md` | 9 consistency findings, cleanup applied |
| Job Registry Limits | LLM-2026-001 | `docs/team/acceptance/2026-05-07_job_registry_limits_ACCEPTED.md` | active job cap with atomic registry gate |
| ADR / Runbook Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-07_adr_runbook_audit_ACCEPTED.md` | 9 findings, handoff/runbook cleanup applied |
| Job Registry TTL Cleanup | LLM-2026-001 | `docs/team/acceptance/2026-05-07_job_registry_ttl_cleanup_ACCEPTED.md` | stale completed/failed in-memory jobs expire after configurable TTL |
| LLM Interface Design Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-07_llm_interface_doc_audit_ACCEPTED.md` | 10 findings drove advisor injection, validation, and audit-state design revision |

## Upcoming Candidate Tasks

1. LLM Advisor Phase A implementation with fake-advisor tests.
2. Docs/readiness audit for the revised LLM Phase A contract.
3. Site sample collection for automatic engine selection.
4. Durable job registry design after the in-memory MVP stabilizes.

## Supervisor Notes

- Employee identity is permanent; project role is temporary.
- Browser fallback touches `executor.py`, a shared boundary. Future executor work
  needs clear assignment.
- Automatic fnspider selection is deferred until more real site samples exist.
- Visual understanding remains blueprint-level and should not be started before
  browser artifacts exist.
- LLM provider adapters are not approved yet; Phase A is interface-only.
