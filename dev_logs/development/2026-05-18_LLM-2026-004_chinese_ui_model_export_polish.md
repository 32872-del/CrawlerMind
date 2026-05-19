# 2026-05-18 LLM-2026-004 Chinese UI Model Export Polish

## Summary

- Upgraded the frontend workbench from technical MVP to a Chinese product-facing control panel.
- Converted visible page text across shell, dashboard, wizard, analysis, task detail, history, settings, empty states, messages, status labels, and mock text.
- Added LLM provider presets and model picker flow.
- Added export directory/path UX, including browser directory picker fallback copy, backend path validation calls, and final output path preview.
- Added localStorage persistence under `clm-workbench-state-v2`.
- Added task detail auto polling while running, pause/resume polling, and last refresh time.
- Polished dashboard spacing, cards, tables, first-run checklist, and status hierarchy.

## Files Changed

- `frontend/index.html`
- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/mockData.ts`
- `frontend/src/components/CatalogTreeView.tsx`
- `frontend/src/components/EventTimeline.tsx`
- `frontend/src/components/FieldSelector.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/HistoryPage.tsx`
- `frontend/src/pages/NewTaskWizardPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`
- `frontend/src/store/workbench.tsx`
- `frontend/src/styles.css`
- `frontend/src/types/workflow.ts`
- `frontend/src/utils/format.ts`

## Model Picker

- Presets: OpenAI-compatible, DeepSeek-compatible, SiliconFlow-compatible, local/Ollama-like, custom relay.
- `获取模型列表` calls `POST /llm/models`.
- In `mock` mode it returns deterministic sample models.
- In `auto/live`, backend failure is shown in Chinese and manual model input remains available.

## Export Path UX

- Settings page can check or create the default export directory through `POST /exports/validate-path`.
- Wizard export step shows final output file path before run.
- Wizard calls `POST /exports/validate-path` and `POST /exports/resolve-path` when available.
- Browser directory picker is offered when supported, with clear copy that backend export still uses server/local backend paths.

## Verification

- `npm run build` passed.
- Browser smoke at `http://127.0.0.1:5174/` verified:
  - Chinese dashboard title and first-run checklist
  - no old `New task` menu text on home snapshot
  - model picker button and manual fallback visible
  - wizard reaches Chinese field selection
  - export path UX visible
  - test run reaches Chinese task detail
  - polling pause/resume button visible

## Notes

- Build still emits the known Ant Design large chunk warning.
- Backend endpoints `/llm/models`, `/exports/validate-path`, and `/exports/resolve-path` are treated as expected contracts; frontend degrades to mock/manual paths when unavailable.
