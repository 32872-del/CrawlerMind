# 2026-05-18 LLM-2026-004 Frontend Workbench MVP Handoff

## Assignment

`2026-05-18_LLM-2026-004_FRONTEND_WORKBENCH_MVP`

## Screens Completed

- Dashboard / home
- New task wizard
- Site analyze result page
- Task detail page
- Task history page
- Settings page

## API Calls Wired

- `POST /catalog/import`
- `POST /site/analyze`
- `POST /fields/resolve`
- `POST /runs/test`
- `POST /runs/full`
- `GET /runs/{task_id}/status`
- `GET /runs/{task_id}/events`
- `POST /exports`

The API layer supports `auto`, `live`, and `mock` modes. `auto` attempts the
configured backend first and falls back to deterministic mock data if the
backend is unavailable.

## Main Files

- `frontend/src/App.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/mockData.ts`
- `frontend/src/store/workbench.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/NewTaskWizardPage.tsx`
- `frontend/src/pages/AnalysisPage.tsx`
- `frontend/src/pages/TaskDetailPage.tsx`
- `frontend/src/pages/HistoryPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/types/workflow.ts`
- `frontend/src/styles.css`

## Verification

Passed:

- `npm install`
- `npm run build`
- browser smoke at `http://127.0.0.1:5174/`

Smoke coverage:

- dashboard renders
- new task navigation works
- analyze action reaches field selection in auto/mock mode
- wizard reaches run/export steps
- test run launches into task detail
- refresh loads status and event data
- export action displays an output path

Local dev server:

- `http://127.0.0.1:5174/`

## Backend Gaps / Product Notes

- Events are still polling JSON, not SSE/WebSocket.
- Settings are currently frontend session state, not persisted.
- Export can be triggered, but actual files require the backend runtime/product
  store to contain records for that `run_id`.
- Backend site analysis is deterministic HTML/menu recon, not full browser/XHR
  catalog discovery yet.
- Template export is accepted by the API but not advanced cell-coordinate
  template writing.

## Suggested Next Steps

- Add persisted frontend settings, probably localStorage first.
- Add a status polling hook with interval controls and pause/resume behavior.
- Add better API error display per step.
- Split Ant Design chunks if bundle size becomes a release concern.
