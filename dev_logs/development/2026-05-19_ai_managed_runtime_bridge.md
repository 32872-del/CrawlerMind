# 2026-05-19 AI Managed Runtime Bridge

## Blueprint / Capability Gap

The current product workflow could analyze a site with an LLM, then launch a
mostly deterministic profile runner. Compared with the autonomous agent
blueprint, the biggest gap was that the model did not participate in the run
life cycle:

- no pre-run plan/profile review
- no runtime/post-run diagnosis
- no visible model decisions in task status
- no repair suggestions after low-quality or failed runs

This made the system feel like a configurable crawler rather than an agent.

## Backend Work Completed

- Added `ManagedAIConfig` to product run requests.
- Extended OpenAI-compatible advisor with:
  - `review_run_plan()`
  - `diagnose_run_result()`
- Added managed run state:
  - `managed_ai`
  - `ai_decisions`
  - `ai_diagnostics`
  - `ai_repair_suggestions`
- Wired `/runs/test` and `/runs/full` so `managed_ai + llm` can trigger:
  - pre-run LLM plan review
  - post-run LLM quality diagnosis
- Exposed AI state through `GET /runs/{task_id}/status`.
- Added AI decision events through `GET /runs/{task_id}/events`.
- Updated frontend API runbook with managed AI payload and response fields.
- Added tests for deterministic default behavior, managed AI validation, and
  pre/post decision visibility.

## Files Changed

- `autonomous_crawler/api/app.py`
- `autonomous_crawler/llm/openai_compatible.py`
- `autonomous_crawler/runners/product_workflow.py`
- `autonomous_crawler/tests/test_product_workflow_api.py`
- `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md`
- `docs/team/assignments/2026-05-19_LLM-2026-004_AI_MANAGED_WORKBENCH.md`

## Verification

```text
python -m unittest autonomous_crawler.tests.test_product_workflow_api -v
Ran 48 tests
OK

python -m unittest autonomous_crawler.tests.test_frontend_support_api autonomous_crawler.tests.test_product_workflow_api autonomous_crawler.tests.test_job_operations_api -v
Ran 106 tests
OK

python -m compileall autonomous_crawler -q
OK
```

## Remaining Gaps

- The LLM still does not yet actively pause/resume or mutate a running job
  mid-batch.
- `profile_patch` and `next_run_overrides` are recorded but not yet applied
  automatically.
- Frontend still needs to expose AI managed mode controls and render AI
  decisions/diagnostics.
- The next backend phase should add a controlled repair loop that can generate
  a revised run payload from failed/low-quality output.
## Runtime Supervision Extension

Added after the managed runtime bridge checkpoint.

- Added batch-level runtime supervision in `BatchRunner`.
- Added `BatchSupervisorSnapshot`, `BatchSupervisorDecision`, and
  `RuleBasedBatchSupervisor`.
- Supervision detects:
  - consecutive batches with no records and no discovered URLs
  - high batch failure rate
  - low batch success rate
  - low record yield
- `ProfileLongRunConfig.supervision_mode` now supports:
  - `off`
  - `observe`
  - `managed`
- Product API maps managed AI modes to supervision modes:
  - `supervised` -> `observe`
  - `full_managed` -> `managed`
- `/runs/{task_id}/status` now exposes `diagnostics` and `supervision`.
- `/runs/{task_id}/events` now includes `supervision_*` events.
- Full-managed runs can now pause/abort from runtime supervision and recommend
  `ai_rerun`.
- `POST /runs/{task_id}/ai-rerun` now also consumes runtime `supervision`.
  When no LLM `next_run_overrides` exist, consecutive empty batches still
  produce deterministic repair overrides: dynamic mode, networkidle wait, API
  capture, cookie acceptance, longer waits, DOM pagination, and conservative
  title selector fallback.
- Added managed crawl action space:
  - `reanalyze_site`
  - `discover_catalog`
  - `probe_fields`
  - `inspect_access`
  - `repair_selectors`
  - `adjust_runtime`
  - `evaluate_quality`
  - `prepare_export`
  - `prepare_rerun`
- Added `POST /runs/{task_id}/managed-actions`.
  - LLM can choose actions from the supported list.
  - Deterministic fallback builds actions from progress, diagnostics, and
    supervision evidence.
  - Executed actions return `profile_patch`, `run_overrides`, and
    `rerun_ready`.
  - Latest action overrides are consumed by `ai-rerun`.
- Extended managed actions into a broader crawler tool space:
  - catalog discovery repairs missing menu/category seeds
  - field probing prepares target fields and selector fallbacks
  - quality evaluation creates required-field and coverage gates
  - export preparation preserves requested format/path/mapping for reruns
- `ManagedActionsRequest.extra_context` can now carry workbench context such as
  field goal, selected fields, imported catalog JSON, and export preferences.
- The OpenAI-compatible managed-actions prompt now explains the full action
  tool space, so compatible models can choose crawler operations rather than
  only diagnose textually.
- Added `POST /runs/{task_id}/managed-repair-run` as a one-click frontend
  endpoint. It executes managed actions, stores the action record, then starts a
  repaired child run through the existing AI rerun path.
- Expanded the profile patch allowlist so managed actions can safely carry
  nested selector groups such as `selectors.detail.colors`, `target_fields`,
  `quality_expectations.min_records`, and
  `quality_expectations.min_field_coverage`.
- The frontend task detail page now has an "AI 托管修复并重跑" button. It sends
  current field goal, selected fields, imported catalog, export settings, LLM
  config, and managed AI config to the backend, then switches to the child run.
- The frontend task detail page now displays managed action records from
  `status.managed_actions`.
- Added `managed_ai.auto_repair`.
  - `full_managed` implicitly wants auto repair.
  - After a paused/failed/rejected/empty/unknown-quality run, the backend can
    execute managed actions and start one repaired child run automatically.
  - The child run is forced to `supervised` mode with `auto_repair=false` to
    avoid infinite repair loops.
  - Parent status now exposes `managed_auto_repair`, including child task/run
    ids and the action record used for the repair.
  - `/runs/{task_id}/events` now emits `managed_auto_repair_started` or
    `managed_auto_repair_skipped`.

Verification:

```text
python -m unittest autonomous_crawler.tests.test_batch_runner autonomous_crawler.tests.test_profile_longrun autonomous_crawler.tests.test_product_workflow_api.StatusEndpointTests -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests autonomous_crawler.tests.test_product_workflow_api.StatusEndpointTests autonomous_crawler.tests.test_batch_runner autonomous_crawler.tests.test_profile_longrun -v
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_openai_compatible_llm autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests -v
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests autonomous_crawler.tests.test_openai_compatible_llm.OpenAICompatibleAdvisorTests.test_choose_managed_actions_returns_json_object autonomous_crawler.tests.test_openai_compatible_llm.OpenAICompatibleAdvisorTests.test_choose_managed_actions_prompt_lists_expanded_tool_space -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests autonomous_crawler.tests.test_managed_actions -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_full_managed_auto_repair_starts_child_after_failed_quality autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_repair_run_executes_actions_and_starts_child_run -v
python -m compileall autonomous_crawler -q
npm --prefix frontend run build
```

## 2026-05-19 Follow-up: LLM Trace Visibility and Challenge Repair Hardening

User testing showed that the basic frontend/backend flow can run, but the agent
still felt weak in two important ways:

- The model's participation was not visible enough during the run.
- A real ecommerce test could discover URLs but still save zero products.

Evidence from the latest failed run:

```text
runtime: dev_logs/runtime/frontend-run/nl-myprotein-com-20260519140211
frontier URLs: 419
products saved: 0
failure bucket: challenge_like
browser classification: recaptcha/captcha, requires_manual_handoff=true
session mode: ephemeral
captured XHR: 0
```

Conclusion: this was not primarily a "no catalog" failure. The system found
many candidate URLs, then detail access failed under challenge-like pages. The
generic backend gap was access escalation and visible AI supervision, not a
site-specific selector patch.

Backend changes:

- Added `LLMConfig.reasoning_effort` and `LLMConfig.stream`.
- Passed `reasoning_effort` and `stream` through the OpenAI-compatible adapter.
- Added `llm_traces` to job state and `/runs/{task_id}/status`.
- Added `llm_trace_*` events to `/runs/{task_id}/events`.
- Recorded trace entries for:
  - pre-run plan review
  - post-run diagnosis
  - managed action planning
- Trace records include stage, status, provider, model, duration, input summary,
  output summary, error, and timestamp.
- Added SSE stream-response aggregation for OpenAI-compatible chat completions.
- Added automatic retry without unsupported optional parameters such as
  `response_format`, `reasoning_effort`, or `stream`.
- Enhanced managed action fallback for challenge-like failures:
  - protected runtime mode
  - persistent browser context
  - browser pool enabled
  - API capture enabled
  - lower item concurrency
  - proxy policy marked `rotate_on_challenge`

Frontend changes:

- Settings pass `reasoning_effort` and `stream` to backend requests.
- Task detail passes `llm_traces` into the AI managed panel.
- AI managed panel now shows a "模型调用轨迹" table with visible model call
  evidence.
- Event timeline labels are now more readable in Chinese for AI, LLM trace,
  supervision, job, export, and managed action events.

What this improves:

- Users can now see whether the model was actually called and where it failed.
- Third-party OpenAI-compatible relays are less likely to break because of
  optional parameter differences.
- Runs that hit challenge/captcha-like failures now produce a stronger generic
  repair plan instead of only "empty data" diagnosis.

Remaining hard gaps:

- The trace is polling-based. True token-by-token streaming needs a dedicated
  SSE/WebSocket endpoint.
- Protected runtime escalation is now planned/applied into rerun overrides, but
  real-site success still depends on browser session quality, proxy quality,
  API capture evidence, and profile refinement.
- The next backend sprint should focus on real browser/XHR catalog and product
  detail refinement, plus quality-driven rerun loops that can compare parent and
  child runs.

Verification:

```text
python -m unittest autonomous_crawler.tests.test_openai_compatible_llm autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_ai_pre_and_post_decisions_are_queryable autonomous_crawler.tests.test_product_workflow_api.StatusEndpointTests.test_status_includes_new_fields -v
Ran 39 tests
OK

python -m compileall autonomous_crawler -q
OK

npm --prefix frontend run build
OK
```

## 2026-05-19 Follow-up 3: Backend Evidence Pack for AI Decisions

User clarified the backend has two separate responsibilities:

1. Improve backend crawler capability itself.
2. Let AI actually use those capabilities instead of only producing text.

Implemented a bridge for both:

- Added `build_run_evidence_pack(job)`.
- `/runs/{task_id}/status` now exposes `evidence_pack`.
- `managed-step` stores the evidence pack used for that step.
- Managed action planning now sends compact evidence to the LLM path:
  - `profile_summary` instead of full profile
  - `run_spec_summary` instead of full run spec
  - `evidence_pack` as diagnostics
- Frontend task detail now has "让 AI 执行下一步".
- Frontend displays "AI 托管步骤与证据包" with recommended focus and failure
  buckets.

Evidence pack includes:

```text
task
progress
run_spec_summary
profile_summary
quality_gaps
failure_evidence
diagnostics
managed_history
recommended_focus
```

Why this matters:

- Backend gains a reusable diagnosis substrate independent of any one website.
- AI gets a smaller and more actionable context, reducing timeout risk and
  improving its chance of choosing useful crawler actions.
- The workbench now has a practical "AI next step" control tied to the same
  backend action system used by auto repair.

Verification:

```text
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_status_and_managed_step_include_evidence_pack autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_step_executes_actions_and_can_start_child_run -v
OK

python -m compileall autonomous_crawler -q
OK

npm --prefix frontend run build
OK
```

## 2026-05-19 Follow-up 2: Managed Step and Practical LLM Timeout Controls

The workbench screenshot showed the model was now visible, but both visible
model calls timed out after about 31 seconds:

```text
运行后诊断 error gpt-5.5 31157ms LLM request failed: The read operation timed out
运行前计划审阅 error gpt-5.5 31124ms LLM request failed: The read operation timed out
```

Interpretation: the AI path was wired, but the provider call did not return in
time. After timeout the system fell back to deterministic suggestions, which is
why the agent still felt passive.

Progress made in this follow-up:

- Added `POST /runs/{task_id}/managed-step`.
- A managed step performs one explicit observe-decide-act cycle:
  - summarize current job progress
  - classify stage as runtime supervision, repair after failure, quality review,
    or planning
  - plan managed actions with LLM or deterministic fallback
  - execute bounded actions
  - optionally start a repaired child run
  - persist the step in `status.managed_steps`
  - emit `managed_step_executed`
- Added frontend LLM settings for:
  - `timeout_seconds`
  - `max_tokens`
- Run payloads, analysis requests, and managed repair requests now pass those
  settings through to the backend.

Why this is a real step forward:

- The product now has a single backend primitive for "let AI take the next
  action" instead of only "show AI diagnostics".
- The frontend can expose this as a user-facing button and later the scheduler
  can call the same primitive automatically.
- Provider timeouts are now adjustable from the workbench, which matters for
  third-party relays and higher-reasoning models.

Verification:

```text
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_step_executes_actions_and_can_start_child_run -v
OK

python -m unittest autonomous_crawler.tests.test_openai_compatible_llm -v
OK

python -m compileall autonomous_crawler -q
OK

npm --prefix frontend run build
OK
```
