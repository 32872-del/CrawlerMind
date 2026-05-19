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

Verification:

```text
python -m unittest autonomous_crawler.tests.test_batch_runner autonomous_crawler.tests.test_profile_longrun autonomous_crawler.tests.test_product_workflow_api.StatusEndpointTests -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests autonomous_crawler.tests.test_product_workflow_api.StatusEndpointTests autonomous_crawler.tests.test_batch_runner autonomous_crawler.tests.test_profile_longrun -v
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_openai_compatible_llm autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests -v
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests autonomous_crawler.tests.test_openai_compatible_llm.OpenAICompatibleAdvisorTests.test_choose_managed_actions_returns_json_object autonomous_crawler.tests.test_openai_compatible_llm.OpenAICompatibleAdvisorTests.test_choose_managed_actions_prompt_lists_expanded_tool_space -v
python -m unittest autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests autonomous_crawler.tests.test_managed_actions -v
python -m compileall autonomous_crawler -q
npm --prefix frontend run build
```
