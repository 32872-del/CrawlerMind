# Team Board

Last updated: 2026-05-15

## Active Employees

| Employee ID | Display Name | Current Project Role | Status | Current Assignment |
|---|---|---|---|---|
| LLM-2026-000 | Supervisor Codex | Project Supervisor | active | Backend execution automation hardening accepted; planning real runtime execution |
| LLM-2026-001 | Worker Alpha | Browser Runtime Worker | standby | Profile draft generation and profile draft smoke accepted |
| LLM-2026-002 | Worker Beta | Proxy / Transport Runtime Worker | standby | Replay executor and 30k resumable checkpoint restart accepted |
| LLM-2026-003 | Worker Gamma | Unassigned | standby | none |
| LLM-2026-004 | Worker Delta | Spider Runtime Worker | standby | Profile report export and real profile batch accepted |

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
| Real-Site Scenario Matrix | `docs/team/training/2026-05-15_REAL_SITE_SCENARIO_MATRIX.md` | active | Clean scenario matrix derived from the owner training list; current hardening round source |
| Top Crawler Capability Roadmap | `docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md` | active | Converts expert crawler skill checklist into CLM product capability roadmap |
| Capability Implementation Matrix | `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md` | active | Maps CLM work directly to the top crawler capability checklist; future tasks must cite CAP IDs |
| Scrapling Capability Absorption Plan | `docs/plans/2026-05-14_SCRAPLING_FIRST_RUNTIME_PLAN.md` | active | Near-term mainline to absorb Scrapling 0.4.8 capabilities into CLM-native crawler backend modules |

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
| Rendered DOM Selector Training | LLM-2026-001 | Browser / DOM Recon Worker | accepted | `docs/team/acceptance/2026-05-09_rendered_dom_selector_training_ACCEPTED.md` |
| Browser Network Observation Timing QA | LLM-2026-002 | QA / Browser Network Auditor | accepted | `docs/team/acceptance/2026-05-09_network_timing_qa_ACCEPTED.md` |
| Observed API Pagination/Cursor MVP | LLM-2026-001 | API / Crawl Capability Worker | conditionally accepted | `docs/team/acceptance/2026-05-09_observed_api_pagination_ACCEPTED.md` |
| API Pagination QA | LLM-2026-002 | QA / Browser Network Auditor | accepted | `docs/team/acceptance/2026-05-09_api_pagination_qa_ACCEPTED.md` |
| Docs State Audit After API Replay | LLM-2026-004 | Documentation Worker | accepted | `docs/team/acceptance/2026-05-09_docs_state_audit_after_api_replay_ACCEPTED.md` |
| Ecommerce Product Store Foundation | LLM-2026-001 | Storage / Ecommerce Worker | accepted | `docs/team/acceptance/2026-05-11_product_store_ACCEPTED.md` |
| Ecommerce Product Quality Foundation | LLM-2026-002 | QA / Ecommerce Worker | accepted | `docs/team/acceptance/2026-05-11_product_quality_ACCEPTED.md` |
| Long-Running Ecommerce Runbook | LLM-2026-000 | Supervisor | accepted | `docs/team/acceptance/2026-05-11_long_running_ecommerce_runbook_ACCEPTED.md` |
| Generic Resumable Batch Runner MVP | LLM-2026-000 | Supervisor | accepted | `docs/team/acceptance/2026-05-11_resumable_batch_runner_ACCEPTED.md` |
| Resumable Runner QA Audit | LLM-2026-001 | QA / Runner Auditor | accepted | `docs/team/acceptance/2026-05-11_resumable_runner_qa_ACCEPTED.md` |
| Training Fixture Plan | LLM-2026-002 | Training / Fixture Planner | accepted | `docs/team/acceptance/2026-05-11_training_fixture_plan_ACCEPTED.md` |
| Runner Docs Consistency Audit | LLM-2026-004 | Documentation Worker | accepted | `docs/team/acceptance/2026-05-11_runner_docs_audit_ACCEPTED.md` |
| Easy Mode CLI Tests | LLM-2026-001 | ROLE-CLI-QA | conditionally accepted | `docs/team/acceptance/2026-05-11_easy_mode_cli_tests_CONDITIONAL.md` |
| Easy Mode Quick Start Docs | LLM-2026-002 | ROLE-DOCS-QA | accepted | `docs/team/acceptance/2026-05-11_easy_mode_quick_start_ACCEPTED.md` |
| Easy Mode Docs And Command Consistency Audit | LLM-2026-004 | ROLE-DOCS-AUDIT | accepted | `docs/team/acceptance/2026-05-11_easy_mode_docs_audit_ACCEPTED.md` |
| Access Layer QA | LLM-2026-001 | ROLE-ACCESS-QA | accepted | `docs/team/acceptance/2026-05-12_access_layer_qa_ACCEPTED.md` |
| Access Layer Runbook | LLM-2026-002 | ROLE-ACCESS-DOCS | accepted | `docs/team/acceptance/2026-05-12_access_layer_runbook_ACCEPTED.md` |
| Access Layer Safety Audit | LLM-2026-004 | ROLE-ACCESS-AUDIT | accepted | `docs/team/acceptance/2026-05-12_access_layer_safety_audit_ACCEPTED.md` |
| CAP-4.4 Browser Interception And JS Capture | LLM-2026-001 | ROLE-BROWSER-CAPABILITY | accepted | `docs/team/acceptance/2026-05-12_cap_4_4_browser_interception_ACCEPTED.md` |
| CAP-2.1 JS Asset Inventory | LLM-2026-002 | ROLE-JS-RECON | accepted | `docs/team/acceptance/2026-05-12_cap_2_1_js_asset_inventory_ACCEPTED.md` |
| CAP-4.4 / CAP-2.1 Capability Alignment Audit | LLM-2026-004 | ROLE-CAPABILITY-AUDIT | accepted | `docs/team/acceptance/2026-05-12_capability_alignment_audit_ACCEPTED.md` |
| CAP-4.2 Browser Fingerprint Profile Report | LLM-2026-001 | ROLE-BROWSER-FINGERPRINT | accepted | `docs/team/acceptance/2026-05-12_cap_4_2_browser_fingerprint_ACCEPTED.md` |
| CAP-2.1 JS Static Analysis Foundation | LLM-2026-002 | ROLE-JS-AST | accepted | `docs/team/acceptance/2026-05-12_cap_2_1_js_static_analysis_ACCEPTED.md` |
| Capability Round 2 Audit | LLM-2026-004 | ROLE-CAPABILITY-AUDIT | accepted | `docs/team/acceptance/2026-05-12_capability_round2_audit_ACCEPTED.md` |
| CAP-5.1 Strategy JS Evidence QA | LLM-2026-001 | ROLE-STRATEGY-QA | accepted | `docs/team/acceptance/2026-05-12_cap_5_1_strategy_js_evidence_qa_ACCEPTED.md` |
| CAP-1.4 WebSocket Observation MVP | LLM-2026-002 | ROLE-WEBSOCKET | accepted | `docs/team/acceptance/2026-05-12_cap_1_4_websocket_observation_ACCEPTED.md` |
| Capability Matrix Refresh Audit | LLM-2026-004 | ROLE-CAPABILITY-DOC-AUDIT | accepted | `docs/team/acceptance/2026-05-12_capability_matrix_refresh_audit_ACCEPTED.md` |
| CAP-4.2 Runtime Fingerprint Probe | LLM-2026-000 | ROLE-SUPERVISOR / ROLE-BROWSER-FINGERPRINT | accepted | `docs/team/acceptance/2026-05-12_cap_4_2_runtime_fingerprint_probe_ACCEPTED.md` |
| CAP-5.1 Strategy and AntiBot Calibration | LLM-2026-001 | ROLE-STRATEGY-QA | accepted | `docs/team/acceptance/2026-05-14_cap_5_1_strategy_antibot_calibration_ACCEPTED.md` |
| CAP-3.3 Proxy Trace Reporting Integration | LLM-2026-002 | ROLE-QA | accepted | `docs/team/acceptance/2026-05-14_cap_3_3_proxy_trace_reporting_ACCEPTED.md` |
| CAP-6.2 / Docs Refresh | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-14_capability_docs_refresh_ACCEPTED.md` |
| Scrapling Static + Parser Adapter | LLM-2026-001 | Runtime Adapter Worker | accepted | `docs/team/acceptance/2026-05-14_scrapling_static_parser_adapter_ACCEPTED.md` |
| Scrapling Browser + Session + Proxy Runtime Design | LLM-2026-002 | Browser Runtime Infrastructure Worker | accepted | `docs/team/acceptance/2026-05-14_scrapling_browser_session_proxy_runtime_ACCEPTED.md` |
| Scrapling Runtime Docs + Source Tracking Audit | LLM-2026-004 | Runtime Documentation Auditor | accepted | `docs/team/acceptance/2026-05-14_scrapling_runtime_docs_source_tracking_ACCEPTED.md` |
| Scrapling Executor Routing | LLM-2026-000 | Supervisor mainline | accepted | `docs/team/acceptance/2026-05-14_scrapling_executor_routing_ACCEPTED.md` |
| NativeFetchRuntime | LLM-2026-000 | Supervisor mainline / Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_fetch_runtime_ACCEPTED.md` |
| NativeParserRuntime | LLM-2026-001 | Runtime Parser Worker | accepted | `docs/team/acceptance/2026-05-14_native_parser_runtime_ACCEPTED.md` |
| Native Runtime Parity QA | LLM-2026-002 | Runtime QA Worker | accepted | `docs/team/acceptance/2026-05-14_native_runtime_parity_ACCEPTED.md` |
| Spider / Checkpoint Native Design Prep | LLM-2026-004 | Runtime Design / Docs Worker | accepted | `docs/team/acceptance/2026-05-14_spider_checkpoint_design_ACCEPTED.md` |
| Native Executor Routing And Runtime Comparison | LLM-2026-000 | Supervisor mainline / Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_executor_routing_ACCEPTED.md` |
| Native Browser Runtime Shell | LLM-2026-000 | Supervisor mainline / Browser Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_browser_runtime_ACCEPTED.md` |
| Native Dynamic Runtime Comparison Harness | LLM-2026-000 | Supervisor mainline / Runtime QA | accepted | `docs/team/acceptance/2026-05-14_native_dynamic_comparison_ACCEPTED.md` |
| Native Browser Session Lifecycle Slice | LLM-2026-000 | Supervisor mainline / Browser Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_browser_session_lifecycle_ACCEPTED.md` |
| Native Browser Protected Evidence And Failure Classification | LLM-2026-000 | Supervisor mainline / Browser Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_browser_protected_failure_evidence_ACCEPTED.md` |
| Native Spider Request Result Event Models | LLM-2026-000 | Supervisor mainline / Spider Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_spider_models_ACCEPTED.md` |
| Native Spider CheckpointStore | LLM-2026-000 | Supervisor mainline / Storage Worker | accepted | `docs/team/acceptance/2026-05-14_native_checkpoint_store_ACCEPTED.md` |
| Native SpiderRuntimeProcessor | LLM-2026-000 | Supervisor mainline / Spider Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_spider_runtime_processor_ACCEPTED.md` |
| Native LinkDiscovery And RobotsPolicy Helpers | LLM-2026-000 | Supervisor mainline / Spider Tooling Worker | accepted | `docs/team/acceptance/2026-05-14_native_link_robots_helpers_ACCEPTED.md` |
| Native Spider Pause/Resume Smoke | LLM-2026-000 | Supervisor mainline / Spider Runtime QA | accepted | `docs/team/acceptance/2026-05-14_native_spider_pause_resume_smoke_ACCEPTED.md` |
| Native Browser Session and Profile Pool | LLM-2026-001 | ROLE-BROWSER | accepted | `docs/team/acceptance/2026-05-14_native_browser_session_pool_ACCEPTED.md` |
| Proxy Health and Fetch Diagnostics | LLM-2026-002 | ROLE-QA | accepted | `docs/team/acceptance/2026-05-14_proxy_health_fetch_diagnostics_ACCEPTED.md` |
| Native Adaptive Parser | LLM-2026-000 | Supervisor mainline / Parser Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_adaptive_parser_ACCEPTED.md` |
| Native Selector Memory | LLM-2026-000 | Supervisor mainline / Parser Runtime Worker | accepted | `docs/team/acceptance/2026-05-14_native_selector_memory_ACCEPTED.md` |
| Browser Pool Real Smoke And Batch Wiring | LLM-2026-001 | ROLE-BROWSER | accepted | `docs/team/acceptance/2026-05-14_browser_pool_real_smoke_batch_wiring_ACCEPTED.md` |
| Proxy Retry Orchestration | LLM-2026-002 | ROLE-QA | accepted | `docs/team/acceptance/2026-05-14_proxy_retry_orchestration_ACCEPTED.md` |
| Sitemap Robots Long-Run Integration | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-14_sitemap_robots_longrun_ACCEPTED.md` |
| Native Browser Profile Rotation And Real Dynamic Training | LLM-2026-001 | ROLE-BROWSER | accepted | `docs/team/acceptance/2026-05-14_native_browser_profile_rotation_real_dynamic_ACCEPTED.md` |
| Native Async Fetch Pool And Long-Run Stress Metrics | LLM-2026-002 | ROLE-QA | accepted | `docs/team/acceptance/2026-05-14_native_async_fetch_pool_stress_ACCEPTED.md` |
| Site Profile And Profile-Driven Ecommerce Runner | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-14_profile_driven_ecommerce_runner_ACCEPTED.md` |
| VisualRecon Strategy And AntiBot Integration | LLM-2026-000 | ROLE-SUPERVISOR | accepted | `docs/team/acceptance/2026-05-14_visual_recon_strategy_antibot_ACCEPTED.md` |
| Scrapling Absorption Baseline Closeout | LLM-2026-000 | ROLE-SUPERVISOR | accepted | `docs/team/acceptance/2026-05-14_scrapling_absorption_baseline_ACCEPTED.md` |
| Browser Profile Health And Scenario Training | LLM-2026-001 | ROLE-BROWSER | accepted | `docs/team/acceptance/2026-05-15_browser_profile_health_and_scenario_training_ACCEPTED.md` |
| API GraphQL Training And Native Long-Run Metrics | LLM-2026-002 | ROLE-QA | accepted | `docs/team/acceptance/2026-05-15_api_graphql_longrun_metrics_ACCEPTED.md` |
| Profile Library And Ecommerce Training | LLM-2026-004 | ROLE-DOCS | accepted | `docs/team/acceptance/2026-05-15_profile_library_ecommerce_training_ACCEPTED.md` |
| Scrapling Harden Round 1 And 2 | LLM-2026-000 | ROLE-SUPERVISOR | accepted | `docs/team/acceptance/2026-05-15_scrapling_harden_round1_round2_ACCEPTED.md` |
| Real Scale Reverse Profile Hardening | LLM-2026-000 | ROLE-SUPERVISOR | accepted | `docs/team/acceptance/2026-05-15_real_scale_reverse_profile_hardening_ACCEPTED.md` |
| Backend Execution Automation Hardening | LLM-2026-000 | ROLE-SUPERVISOR | accepted | `docs/team/acceptance/2026-05-15_backend_execution_automation_hardening_ACCEPTED.md` |

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
| Browser Network Timing And API Replay | LLM-2026-000 | supervisor direct work | `networkidle` observation, JSON POST replay, Algolia-style POST classification, HN SPA completed with 10 items |
| Open Source CI | LLM-2026-001 | `docs/team/acceptance/2026-05-09_open_source_ci_ACCEPTED.md` | GitHub Actions, CONTRIBUTING, issue templates |
| Browser Network Observation QA | LLM-2026-002 | `docs/team/acceptance/2026-05-09_browser_network_observation_qa_ACCEPTED.md` | 55 focused tests and QA audit |
| Open Source Docs Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-09_open_source_docs_audit_ACCEPTED.md` | onboarding audit and doc consistency findings |
| Real-Site Training Round 4 | LLM-2026-000 | supervisor direct work | 5/5 scenarios completed; public JSON/API plus HN Algolia SPA observed API replay |
| Controlled XHR SPA Network Smoke | LLM-2026-000 | supervisor direct work | optional real-browser test proves `observe_browser_network()` captures a real local XHR API candidate |
| Rendered DOM Selector Training | LLM-2026-001 | `docs/team/acceptance/2026-05-09_rendered_dom_selector_training_ACCEPTED.md` | HN Algolia-style DOM fixtures and selector inference tests |
| Browser Network Timing QA | LLM-2026-002 | `docs/team/acceptance/2026-05-09_network_timing_qa_ACCEPTED.md` | diagnosed observer timing gap and recommended `networkidle` plus optional render delay |
| Observed API Pagination/Cursor MVP | LLM-2026-001 | `docs/team/acceptance/2026-05-09_observed_api_pagination_ACCEPTED.md` | page/limit, offset/limit, and cursor JSON pagination MVP; accepted with hardening follow-up |
| API Pagination QA | LLM-2026-002 | `docs/team/acceptance/2026-05-09_api_pagination_qa_ACCEPTED.md` | identified pagination loop, dedupe, cursor-stuck, and analytics replay risks |
| Docs State Audit After API Replay | LLM-2026-004 | `docs/team/acceptance/2026-05-09_docs_state_audit_after_api_replay_ACCEPTED.md` | README/status docs stale after HN Algolia API replay; supervisor cleanup applied |
| Ecommerce Product Quality QA | LLM-2026-002 | `docs/team/acceptance/2026-05-09_ecommerce_product_quality_qa_ACCEPTED.md` | product schema, price/body/image/variant, category-aware dedupe, and anti-starvation QA design accepted |
| Ecommerce Crawl Workflow Docs | LLM-2026-004 | `docs/team/acceptance/2026-05-09_ecommerce_workflow_docs_ACCEPTED.md` | safe ecommerce workflow, category/list/detail/variant decomposition, and challenge diagnosis boundary accepted |
| Ecommerce Real-Site Training Batch | LLM-2026-000 | supervisor direct work | Shoesme diagnosis-only, Donsje Shopify JSON, Clausporto/uvex Magento list/detail, Bosch corporate product page; Excel/JSON exported |
| Local Ecommerce Stress Test | LLM-2026-000 | supervisor direct work | 30,000 synthetic products passed frontier, result storage, and Excel export; long-run checkpoint storage still required |
| Ecommerce Product Store Foundation | LLM-2026-001 | `docs/team/acceptance/2026-05-11_product_store_ACCEPTED.md` | generic `ProductRecord`, category-aware dedupe, SQLite `ProductStore`, 30,000-row batch tests |
| Ecommerce Product Quality Foundation | LLM-2026-002 | `docs/team/acceptance/2026-05-11_product_quality_ACCEPTED.md` | generic quality validator for price/image/body/status/dedupe checks; supervisor cleaned encoding-sensitive tests |
| Long-Running Ecommerce Runbook | LLM-2026-000 | `docs/team/acceptance/2026-05-11_long_running_ecommerce_runbook_ACCEPTED.md` | operational policy for checkpointed large ecommerce runs |
| Generic Resumable Batch Runner MVP | LLM-2026-000 | `docs/team/acceptance/2026-05-11_resumable_batch_runner_ACCEPTED.md` | frontier-backed claim/process/checkpoint loop with pause/resume smoke |
| Resumable Runner QA Audit | LLM-2026-001 | `docs/team/acceptance/2026-05-11_resumable_runner_qa_ACCEPTED.md` | retry-limit, progress-event, lease, atomicity, and politeness risks accepted as follow-ups |
| Training Fixture Plan | LLM-2026-002 | `docs/team/acceptance/2026-05-11_training_fixture_plan_ACCEPTED.md` | six generic training scenarios accepted for fixture/test implementation |
| Runner Docs Consistency Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-11_runner_docs_audit_ACCEPTED.md` | generic runner framing risk accepted and supervisor docs updated |
| Two-Round Real-Site Training | LLM-2026-000 | supervisor direct work | 850 rows exported; round 1: 5 public targets x 50; round 2: 3 ecommerce sites x 200 |
| Easy Mode CLI Mainline | LLM-2026-000 | supervisor direct work | `clm.py` added with init/check/crawl/smoke/train |
| Easy Mode Quick Start Alignment | LLM-2026-000 | supervisor direct work | README and platform quick starts now center `clm.py` |
| Access Layer QA | LLM-2026-001 | `docs/team/acceptance/2026-05-12_access_layer_qa_ACCEPTED.md` | 62 Access Layer tests covering proxy/session/rate-limit/challenge/trace safety |
| Access Layer Runbook | LLM-2026-002 | `docs/team/acceptance/2026-05-12_access_layer_runbook_ACCEPTED.md` | user/developer runbook for authorized sessions, proxies, rate limits, challenges, and future UI |
| Access Layer Safety Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-12_access_layer_safety_audit_ACCEPTED.md` | 6 findings; supervisor fixed global session warning and storage-state path redaction |
| Access Config Resolver And Artifact Manifest | LLM-2026-000 | supervisor direct work | unified access config resolver plus recon/browser artifact manifests |
| CAP-4.4 Browser Interception And JS Capture | LLM-2026-001 | `docs/team/acceptance/2026-05-12_cap_4_4_browser_interception_ACCEPTED.md` | Playwright route interception, resource blocking, JS/API metadata capture, init-script injection |
| CAP-2.1 JS Asset Inventory | LLM-2026-002 | `docs/team/acceptance/2026-05-12_cap_2_1_js_asset_inventory_ACCEPTED.md` | script inventory, signature/token/challenge clues, API/GraphQL/WebSocket/sourcemap extraction |
| CAP-1.2 Transport Diagnostics Increment | LLM-2026-000 | supervisor direct work | transport profile, server header, and edge/cache header difference detection |
| CAP-4.2 Browser Fingerprint Profile | LLM-2026-001 | `docs/team/acceptance/2026-05-12_cap_4_2_browser_fingerprint_ACCEPTED.md` | config-side browser fingerprint consistency report with risk/recommendations |
| CAP-2.1 JS Static Analysis | LLM-2026-002 | `docs/team/acceptance/2026-05-12_cap_2_1_js_static_analysis_ACCEPTED.md` | JS string table, endpoint strings, suspicious function/call clues |
| Capability Round 2 Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-12_capability_round2_audit_ACCEPTED.md` | identified integration gap; supervisor added JS evidence path |
| JS Evidence Integration | LLM-2026-000 | `docs/team/acceptance/2026-05-12_js_evidence_integration_ACCEPTED.md` | browser/HTML JS evidence combines inventory and static analysis into `recon_report.js_evidence` |
| Browser Interception Recon Path | LLM-2026-000 | `docs/team/acceptance/2026-05-12_browser_interception_recon_path_ACCEPTED.md` | opt-in `constraints.intercept_browser=true` feeds captured JS assets into `recon_report.js_evidence` |
| Strategy JS Evidence Advisory | LLM-2026-000 | `docs/team/acceptance/2026-05-12_strategy_js_evidence_advisory_ACCEPTED.md` | Strategy consumes `js_evidence` as advisory endpoint/hook/challenge hints without overriding stronger evidence |
| Runtime Fingerprint Probe | LLM-2026-000 | `docs/team/acceptance/2026-05-12_cap_4_2_runtime_fingerprint_probe_ACCEPTED.md` | opt-in `constraints.probe_fingerprint=true` samples navigator/screen/Intl/WebGL/canvas/font runtime evidence |
| Strategy JS Evidence QA | LLM-2026-001 | `docs/team/acceptance/2026-05-12_cap_5_1_strategy_js_evidence_qa_ACCEPTED.md` | 58 tests prove JS evidence remains advisory and bounded |
| WebSocket Observation MVP | LLM-2026-002 | `docs/team/acceptance/2026-05-12_cap_1_4_websocket_observation_ACCEPTED.md` | connection/frame models, preview truncation, redaction, mocked Playwright WS event path |
| Capability Matrix Refresh | LLM-2026-004 | `docs/team/acceptance/2026-05-12_capability_matrix_refresh_audit_ACCEPTED.md` | readable matrix aligned to CAP-2.1, CAP-4.2, CAP-4.4, CAP-5.1 current status |
| Proxy Pool And Crypto Evidence | LLM-2026-000 | `docs/team/acceptance/2026-05-12_proxy_pool_and_crypto_evidence_ACCEPTED.md` | pluggable proxy pool foundation plus built-in JS crypto/signature evidence |
| Strategy Evidence Report | LLM-2026-000 | `docs/team/acceptance/2026-05-12_strategy_evidence_report_ACCEPTED.md` | unified DOM/API/JS/crypto/transport/fingerprint/challenge/WebSocket evidence report plus replay-risk action hints |
| WebSocket Recon Opt-in Integration | LLM-2026-001 | `docs/team/acceptance/2026-05-12_cap_1_4_websocket_recon_integration_ACCEPTED.md` | Recon stores `websocket_observation` and `websocket_summary` only when `constraints.observe_websocket=true` |
| Proxy Health Store | LLM-2026-002 | `docs/team/acceptance/2026-05-12_cap_3_3_proxy_health_store_ACCEPTED.md` | SQLite proxy health store, cooldown, credential-safe IDs, and provider adapter template |
| Aggressive Capability Sprint Audit | LLM-2026-004 | `docs/team/acceptance/2026-05-12_aggressive_capability_sprint_audit_ACCEPTED.md` | capability matrix refreshed with maturity labels and overclaiming guardrails |
| Strategy Scoring Policy | LLM-2026-000 | `docs/team/acceptance/2026-05-12_strategy_scoring_policy_ACCEPTED.md` | conservative scorecard for http/api/browser/deeper_recon/manual_handoff attached to Strategy output |
| Unified AntiBotReport | LLM-2026-000 | `docs/team/acceptance/2026-05-12_anti_bot_report_ACCEPTED.md` | CAP-6.2 report unifies access, transport, fingerprint, JS/crypto, proxy, API-block, and WebSocket evidence |
| Real WebSocket Smoke | LLM-2026-001 | `docs/team/acceptance/2026-05-12_real_websocket_smoke_ACCEPTED.md` | local real-browser WebSocket smoke proves Playwright WS events, frame capture, truncation, and redaction |
| Proxy Health Trace | LLM-2026-002 | `docs/team/acceptance/2026-05-12_proxy_health_trace_ACCEPTED.md` | redacted proxy trace and aggregate health evidence accepted |
| Advanced Diagnostics Runbook | LLM-2026-004 | `docs/team/acceptance/2026-05-12_advanced_diagnostics_docs_ACCEPTED.md` | public-facing advanced diagnostics guide accepted without overclaiming |
| Strategy and AntiBot Calibration | LLM-2026-001 | `docs/team/acceptance/2026-05-14_cap_5_1_strategy_antibot_calibration_ACCEPTED.md` | 82 targeted tests confirm conservative score/report boundaries |
| Proxy Trace Reporting | LLM-2026-002 | `docs/team/acceptance/2026-05-14_cap_3_3_proxy_trace_reporting_ACCEPTED.md` | executor return paths now include credential-safe proxy trace |
| Capability Docs Refresh | LLM-2026-004 | `docs/team/acceptance/2026-05-14_capability_docs_refresh_ACCEPTED.md` | README and advanced diagnostics docs updated for AntiBotReport |
| Scrapling Runtime Static/Parser | LLM-2026-001 | `docs/team/acceptance/2026-05-14_scrapling_static_parser_adapter_ACCEPTED.md` | Scrapling static fetch and parser adapters behind CLM runtime protocols |
| Scrapling Browser/Proxy Runtime | LLM-2026-002 | `docs/team/acceptance/2026-05-14_scrapling_browser_session_proxy_runtime_ACCEPTED.md` | Scrapling dynamic/protected browser adapter, session config, and proxy mapping |
| Scrapling Runtime Docs | LLM-2026-004 | `docs/team/acceptance/2026-05-14_scrapling_runtime_docs_source_tracking_ACCEPTED.md` | Scrapling capability absorption runbook and source tracking plan |
| Scrapling Executor Routing | LLM-2026-000 | `docs/team/acceptance/2026-05-14_scrapling_executor_routing_ACCEPTED.md` | `engine="scrapling"` routes through CLM runtime adapters; full suite green |
| NativeFetchRuntime | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_fetch_runtime_ACCEPTED.md` | CLM-native static fetch runtime with httpx/curl_cffi, proxy trace, runtime events, and structured failures |
| NativeParserRuntime | LLM-2026-001 | `docs/team/acceptance/2026-05-14_native_parser_runtime_ACCEPTED.md` | CLM-native parser runtime with CSS/XPath/text/regex extraction and Scrapling-adapter parity |
| Native Runtime Parity QA | LLM-2026-002 | `docs/team/acceptance/2026-05-14_native_runtime_parity_ACCEPTED.md` | 66-test parity suite comparing CLM-native runtimes against Scrapling transition adapters |
| Spider / Checkpoint Native Design | LLM-2026-004 | `docs/team/acceptance/2026-05-14_spider_checkpoint_design_ACCEPTED.md` | Design path for CLM-native spider request/result/checkpoint/link/robots absorption |
| Native Executor Routing | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_executor_routing_ACCEPTED.md` | `engine="native"` routes static execution through NativeFetchRuntime and NativeParserRuntime; comparison smoke passed |
| Native Browser Runtime | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_browser_runtime_ACCEPTED.md` | `engine="native"` browser execution now routes through NativeBrowserRuntime with Playwright context/session/proxy/XHR evidence |
| Native Dynamic Comparison | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_dynamic_comparison_ACCEPTED.md` | Local SPA/API comparison harness proves native_browser and scrapling_browser parity on rendered selectors and captured XHR |
| Native Browser Session Lifecycle | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_browser_session_lifecycle_ACCEPTED.md` | NativeBrowserRuntime supports persistent user-data contexts and storage-state export artifacts |
| Native Browser Protected Evidence | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_browser_protected_failure_evidence_ACCEPTED.md` | NativeBrowserRuntime attaches fingerprint reports, protected-mode profile hints, and browser failure classification evidence |
| Native Spider Models | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_spider_models_ACCEPTED.md` | CLM-native `CrawlRequestEnvelope`, `CrawlItemResult`, and `SpiderRunSummary` contracts for long-running crawls |
| Native CheckpointStore | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_checkpoint_store_ACCEPTED.md` | SQLite checkpoint store persists spider runs, batch checkpoints, item records, events, and failure buckets |
| Native Spider Processor | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_spider_runtime_processor_ACCEPTED.md` | `SpiderRuntimeProcessor` connects runtime backends, parser callbacks, discovered requests, BatchRunner results, and CheckpointStore |
| Native Link / Robots Helpers | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_link_robots_helpers_ACCEPTED.md` | `LinkDiscoveryHelper` and `RobotsPolicyHelper` add profile-driven link extraction, URL classification, robots directives, and evidence events |
| Native Spider Pause/Resume Smoke | LLM-2026-000 | `docs/team/acceptance/2026-05-14_native_spider_pause_resume_smoke_ACCEPTED.md` | Local smoke proves URLFrontier + BatchRunner + SpiderRuntimeProcessor + CheckpointStore + LinkDiscoveryHelper pause/resume without public network |

## Upcoming Candidate Tasks

1. REPLAY-RUNTIME-1: Add a real JS/WebCrypto sandbox execution path behind the accepted replay result contract.
2. PROFILE-AUTO-2: Add advisor-assisted profile refinement, selector repair, and missing-field explanation on top of generated drafts.
3. SCALE-RUNTIME-1: Connect resumable checkpoint logic to real `URLFrontier`, `SpiderRuntimeProcessor`, and `ProductStore` long-running jobs.
4. REAL-ECOM-2: Run 600+ records through profile runner on public ecommerce/API targets with profile-run reports.
5. RUNTIME-HARDEN-1: Add persistent async client pooling, DNS reuse tuning, and adaptive concurrency using the accepted scale metrics.
6. REAL-HARDEN-5: Expand real dynamic training to harder virtualized/protected-profile targets from the scenario matrix.
7. VISUAL-HARDEN-1: Add real OCR provider adapter and screenshot-to-DOM alignment.
8. UX-P1: Simplify user onboarding around `clm.py`, FastAPI, and future UI config without weakening the native backend.

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
- Scrapling work has reached a CLM-native baseline for the major backend
  patterns. Transition adapters remain useful as comparison oracles, but the
  product direction is now hardening, large-run proof, and easier operation on
  top of CLM-owned modules.
- The 2026-05-15 hardening closeout accepted real dynamic evidence, real
  product-like API profile training, 10k native stress, 30k smoke artifact,
  quality gates, and hook/sandbox planning. Next work should move from
  diagnosis/planning into executable reverse replay and automatic profile
  drafting.
- The later 2026-05-15 execution automation closeout accepted deterministic
  replay execution fixtures, generated runnable profile drafts, profile run
  reports, and 30k pause/resume checkpoint restart evidence. Next work should
  connect these pieces to real JS sandbox execution and real long-running
  ecommerce runs.
