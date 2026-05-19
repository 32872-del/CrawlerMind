# 2026-05-19 LLM-2026-004 AI Managed Workbench Handoff

## Assignment

`2026-05-19_LLM-2026-004_AI_MANAGED_WORKBENCH`

## Changed Files

- `frontend/src/types/workflow.ts`
- `frontend/src/store/workbench.tsx`
- `frontend/src/utils/format.ts`
- `frontend/src/utils/runPayload.ts`
- `frontend/src/api/mockData.ts`
- `frontend/src/components/AiManagedPanel.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`
- `dev_logs/development/2026-05-19_LLM-2026-004_ai_managed_workbench.md`

## Payload Contract

Runs now include:

```json
{
  "managed_ai": {
    "enabled": true,
    "mode": "supervised",
    "analysis_enabled": true,
    "plan_review_enabled": true,
    "runtime_diagnosis_enabled": true,
    "post_run_diagnosis_enabled": true,
    "model": "..."
  },
  "llm": {
    "enabled": true,
    "provider": "...",
    "base_url": "...",
    "model": "..."
  }
}
```

`llm.api_key` is included only when non-empty.

## UI Behavior

- Settings page lets the user enable/disable `AI 托管模式`.
- Supported modes:
  - `analysis_only`: 仅分析增强
  - `supervised`: 监督托管
  - `full_managed`: 全托管
- Analysis page shows `llm_analysis` if present.
- Task detail page shows:
  - `managed_ai`
  - `managed_mode`
  - `ai_decisions`
  - `ai_diagnostics`
  - `ai_repair_suggestions`
- Missing arrays render safely as `暂无模型决策记录`.

## Verification

- `npm run build` passed in `frontend`.
- Browser smoke confirmed AI managed settings and workflow visibility render in Chinese.

## Backend Assumptions

- Backend may return these optional status fields:
  - `managed_mode`
  - `managed_ai`
  - `ai_decisions`
  - `ai_diagnostics`
  - `ai_repair_suggestions`
- Frontend does not require these fields and will not crash when they are absent.
