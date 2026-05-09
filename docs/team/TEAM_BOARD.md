# Team Board

Last updated: 2026-05-09

## Active Employees

| Employee ID | Display Name | Current Project Role | Status | Current Assignment |
|---|---|---|---|---|
| LLM-2026-000 | Supervisor Codex | Project Supervisor | active | project direction, assignments, acceptance |
| LLM-2026-001 | Worker Alpha | Open Source CI Worker | accepted | Open Source CI And Contributor Basics |
| LLM-2026-002 | Worker Beta | Browser Network Observation QA | accepted | Browser Network Observation QA |
| LLM-2026-003 | Worker Gamma | Unassigned | standby | none |
| LLM-2026-004 | Worker Delta | Open Source Docs Auditor | accepted | Open Source Docs And Onboarding Audit |

## Current Project Roles

| Role ID | Role Name | Current Employee | Status |
|---|---|---|---|
| ROLE-SUPERVISOR | Project Supervisor | LLM-2026-000 | active |
| ROLE-BROWSER | Browser Executor Worker | LLM-2026-001 | accepted |
| ROLE-QA | Error Path QA Worker | LLM-2026-002 | accepted |
| ROLE-STORAGE | Storage / CLI Worker | LLM-2026-003 | accepted work completed |
| ROLE-STRATEGY | Strategy / Engine Routing Worker | LLM-2026-003 | accepted work completed |
| ROLE-API | API Job Worker | LLM-2026-001 | accepted work completed |
| ROLE-DOCS | Documentation Worker | LLM-2026-004 | accepted work completed |
| ROLE-LLM-INTERFACE | LLM Interface Worker | LLM-2026-001 | accepted work completed |

## Persistent Training Backlog

| Backlog Item | Source | Status | Notes |
|---|---|---|---|
| Real-Site Training Ladder | `docs/team/training/2026-05-08_REAL_SITE_TRAINING_LADDER.md` | active | Long-term training map for future assignments and acceptance records |

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
| LLM Advisor Phase A Interfaces | LLM-2026-001 | ROLE-LLM-INTERFACE | accepted | `docs/team/acceptance/2026-05-07_llm_phase_a_interfaces_ACCEPTED.md` |
| LLM Phase A Docs / Readiness Audit | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-07_llm_phase_a_docs_audit_ACCEPTED.md` |
| Real LLM Baidu Hot Smoke | LLM-2026-000 | ROLE-SUPERVISOR | accepted | `docs/team/acceptance/2026-05-08_real_llm_baidu_hot_smoke_ACCEPTED.md` |
| FastAPI Opt-In LLM Advisors | LLM-2026-001 | ROLE-API / ROLE-LLM-INTERFACE | accepted | `docs/team/acceptance/2026-05-08_fastapi_opt_in_llm_advisors_ACCEPTED.md` |
| Status Docs Audit After Real LLM Smoke | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-08_status_docs_audit_after_real_llm_smoke_ACCEPTED.md` |
| Structured Error Codes | LLM-2026-001 | ROLE-API / ROLE-LLM-INTERFACE | accepted | `docs/team/acceptance/2026-05-08_structured_error_codes_ACCEPTED.md` |
| v5.2 MVP Release Note | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-08_v5.2_mvp_release_note_ACCEPTED.md` |
| Open Source CI And Contributor Basics | LLM-2026-001 | Open Source CI Worker | accepted | `docs/team/acceptance/2026-05-09_open_source_ci_ACCEPTED.md` |
| Browser Network Observation QA | LLM-2026-002 | ROLE-QA | accepted | `docs/team/acceptance/2026-05-09_browser_network_observation_qa_ACCEPTED.md` |
| Open Source Docs And Onboarding Audit | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-09_open_source_docs_audit_ACCEPTED.md` |

## Recent Accepted Work Log

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
| LLM Advisor Phase A Interfaces | LLM-2026-001 | `docs/team/acceptance/2026-05-07_llm_phase_a_interfaces_ACCEPTED.md` | optional advisor protocols, graph injection, audit records, validation, fake-advisor tests |
| LLM Phase A Docs / Readiness Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-07_llm_phase_a_docs_audit_ACCEPTED.md` | 7 findings, highest medium; acceptance checks applied |
| LLM Advisor Phase B/C Merge Hardening | LLM-2026-000 | supervisor direct work | Planner validation and Strategy conservative merge rules |
| OpenAI-Compatible LLM Adapter | LLM-2026-000 | supervisor direct work | opt-in provider adapter and CLI path |
| Real LLM Baidu Hot Smoke | LLM-2026-000 | `docs/team/acceptance/2026-05-08_real_llm_baidu_hot_smoke_ACCEPTED.md` | LLM-enabled Baidu hot-search run extracted 30 validated items |
| FastAPI Opt-In LLM Advisors | LLM-2026-001 | `docs/team/acceptance/2026-05-08_fastapi_opt_in_llm_advisors_ACCEPTED.md` | request-level LLM config added to FastAPI crawl path |
| Status Docs Audit After Real LLM Smoke | LLM-2026-004 | `docs/team/acceptance/2026-05-08_status_docs_audit_after_real_llm_smoke_ACCEPTED.md` | status docs refreshed after LLM smoke milestone |
| Structured Error Codes | LLM-2026-001 | `docs/team/acceptance/2026-05-08_structured_error_codes_ACCEPTED.md` | machine-readable error codes across agents and API |
| v5.2 MVP Release Note | LLM-2026-004 | `docs/team/acceptance/2026-05-08_v5.2_mvp_release_note_ACCEPTED.md` | current MVP abilities, limitations, and startup path summarized |
| P1 Access Diagnostics | LLM-2026-000 | supervisor direct work | JS shell, challenge, structured data, API hints, and access recommendations added to recon |
| P1 Fetch Best Page | LLM-2026-000 | supervisor direct work | requests/curl_cffi/browser scoring, escalation trace, and browser-mode carry-forward added to recon |
| P1 Crawl Foundation | LLM-2026-000 | supervisor direct work | site-zoo, API intercept, SQLite frontier, domain memory, and product task helpers completed |
| Browser Network Observation Skeleton | LLM-2026-000 | supervisor direct work | opt-in Playwright network observation, API candidate scoring, header redaction; duplicate candidate merge now keeps higher-score version |
| Open Source CI | LLM-2026-001 | `docs/team/acceptance/2026-05-09_open_source_ci_ACCEPTED.md` | GitHub Actions, CONTRIBUTING, issue templates |
| Browser Network Observation QA | LLM-2026-002 | `docs/team/acceptance/2026-05-09_browser_network_observation_qa_ACCEPTED.md` | 55 focused tests and QA audit |
| Open Source Docs Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-09_open_source_docs_audit_ACCEPTED.md` | onboarding audit and doc consistency findings |

## Upcoming Candidate Tasks

1. Real-site training suite: continue from the training ladder and convert failures into fixtures/tests.
2. Real browser network observation smoke on one controlled SPA/API-backed target.
3. Durable job registry design after the in-memory FastAPI MVP stabilizes.
4. One controlled SPA target for browser fallback validation.
5. One virtualized-list target for scroll strategy validation.

## Supervisor Notes

- Employee identity is permanent; project role is temporary.
- Browser fallback touches `executor.py`, a shared boundary. Future executor work
  needs clear assignment.
- Automatic fnspider selection is deferred until more real site samples exist.
- Visual understanding remains blueprint-level and should not be started before
  browser artifacts exist.
- LLM provider adapter exists for CLI. Real provider smoke passed on
  2026-05-08 with Baidu realtime hot-search extraction.
- FastAPI LLM integration is accepted.
- P1 should focus on crawl capability breadth before frontend work: access
  diagnostics, mode escalation, network observation, and product list/detail/
  variant task modeling.
