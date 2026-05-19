# 2026-05-19 LLM-2026-004 AI Managed Workbench

## Summary

- Added frontend AI managed mode state and UI controls.
- Extended run payloads so `/runs/test` and `/runs/full` include `managed_ai` and `llm`.
- Added defensive AI managed panels for analysis and task detail pages.
- Kept all new visible text in Chinese.

## Files Changed

- `frontend/src/types/workflow.ts`
- `frontend/src/store/workbench.tsx`
- `frontend/src/utils/format.ts`
- `frontend/src/utils/runPayload.ts`
- `frontend/src/api/mockData.ts`
- `frontend/src/components/AiManagedPanel.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`

## AI Managed Settings

- Added `settings.managed_ai`:
  - `enabled`
  - `mode`: `analysis_only`, `supervised`, `full_managed`
  - `analysis_enabled`
  - `plan_review_enabled`
  - `runtime_diagnosis_enabled`
  - `post_run_diagnosis_enabled`

## Run Payload

- `buildRunPayload()` now includes:
  - `managed_ai`
  - `llm`
- Empty API keys are omitted from `llm`.
- Disabled managed mode still sends a deterministic-style `managed_ai` block with all participation switches off.
- `profile.managed_mode` is also set for backend/runtime visibility.

## UI

- Settings page now has an `AI 托管模式` section.
- Analysis page always renders `AI 托管与模型分析`.
- Task detail page renders `AI 托管与模型决策`.
- Missing AI records display:
  - `暂无模型分析记录`
  - `暂无模型决策记录`
- Task detail now also shows:
  - AI mode
  - model name
  - actual seed URL count
  - selected fields
  - export path

## Verification

- `cd frontend && npm run build` passed.
- Browser smoke at `http://127.0.0.1:5174/` verified:
  - settings page shows `AI 托管模式`
  - settings page shows `运行前计划审阅`
  - settings page shows `运行后质量诊断`
  - wizard/workflow shows AI/workflow visibility

## Notes

- No backend Python files were modified.
- Backend support for real `managed_ai`, `managed_mode`, `ai_decisions`, `ai_diagnostics`, and `ai_repair_suggestions` is expected to land in parallel.
