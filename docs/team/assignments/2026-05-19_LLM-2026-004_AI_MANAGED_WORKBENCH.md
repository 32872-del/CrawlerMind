# Assignment: AI Managed Workbench UI

Date: 2026-05-19

Employee: LLM-2026-004

Supervisor: LLM-2026-000

## Background

The current CLM frontend can configure LLM credentials and call site analysis,
but the user experience still feels like a deterministic crawler UI. The model
appears during analysis and then disappears during task launch, monitoring, and
diagnosis.

This assignment makes AI participation visible and controllable from the
frontend. Backend support is being developed in parallel by the supervisor.

## Goal

Add an "AI 托管模式" frontend path that lets the user decide whether the LLM
should participate in:

- site analysis
- run-plan/profile review before launch
- runtime monitoring/diagnosis
- post-run quality diagnosis and repair suggestions

## Owned Files

Prefer frontend-only changes:

- `frontend/src/types/workflow.ts`
- `frontend/src/store/workbench.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/NewTaskWizardPage.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`
- `frontend/src/components/*` if a reusable panel helps

Do not edit backend Python files unless explicitly needed for type alignment.

## Requirements

1. Add AI managed settings to frontend state.
   - enabled / disabled
   - mode: `analysis_only`, `supervised`, `full_managed`
   - booleans for plan review and post-run diagnosis if useful

2. Send LLM config and managed settings in `/runs/test` and `/runs/full` payloads.
   - Preserve current deterministic behavior when disabled.
   - Do not send empty API keys in screenshots/log panels.

3. Make AI decisions visible.
   - In analysis page: show `llm_analysis`.
   - In task detail: show new backend fields when present:
     - `ai_decisions`
     - `ai_diagnostics`
     - `ai_repair_suggestions`
     - `managed_mode`

4. Add clear Chinese UI labels.
   - "AI 托管模式"
   - "运行前计划审阅"
   - "运行后质量诊断"
   - "模型决策记录"
   - "修复建议"

5. Improve workflow visibility.
   - Task detail should make it obvious whether a run used deterministic mode,
     analysis-only LLM, or managed AI mode.
   - Display actual seed URL count, selected fields, export path, and model name.

## Acceptance Checks

Run:

```text
cd frontend
npm run build
```

Manual/browser smoke:

- Configure a model in settings.
- Enable AI 托管模式.
- Analyze a site.
- Launch a test run.
- Open task detail and verify the AI panels render even if backend returns empty arrays.

## Notes

The supervisor backend branch will add real payload fields and status fields.
Keep rendering defensive: missing AI fields should show "暂无模型决策记录", not crash.
