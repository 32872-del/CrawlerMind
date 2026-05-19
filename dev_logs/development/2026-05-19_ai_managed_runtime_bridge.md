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
