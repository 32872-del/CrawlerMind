# 2026-05-18 LLM-2026-004 Chinese UI Model Export Polish Handoff

## Assignment

`2026-05-18_ROUND2_LLM-2026-004_CHINESE_UI_MODEL_EXPORT_POLISH`

## UI Files Changed

- `frontend/src/App.tsx`
- `frontend/src/pages/*`
- `frontend/src/components/*`
- `frontend/src/api/client.ts`
- `frontend/src/api/mockData.ts`
- `frontend/src/store/workbench.tsx`
- `frontend/src/types/workflow.ts`
- `frontend/src/utils/format.ts`
- `frontend/src/styles.css`
- `frontend/index.html`

## Model Picker Behavior

- Settings page now has provider presets and a `获取模型列表` button.
- Frontend calls `POST /llm/models` with `provider`, `base_url`, and `api_key`.
- If the endpoint is unavailable, the UI shows a Chinese error and keeps manual model input enabled.
- Mock mode returns sample models for demo continuity.

## Provider Presets

- OpenAI 兼容: `https://api.openai.com/v1`
- DeepSeek 兼容: `https://api.deepseek.com/v1`
- SiliconFlow 兼容: `https://api.siliconflow.cn/v1`
- 本地 Ollama 类: `http://127.0.0.1:11434/v1`
- 自定义中转: editable relay placeholder

## Export Folder Behavior

- Settings page validates or creates default export directory through `POST /exports/validate-path`.
- Wizard export step previews the final file path before run.
- Wizard attempts `POST /exports/validate-path` and `POST /exports/resolve-path`.
- Browser directory picker is offered when available, but copy explains that backend path remains authoritative.

## localStorage Keys

- Main key: `clm-workbench-state-v2`
- Stores API base URL, API mode, LLM config, runtime/export defaults, UI mode, wizard draft, tasks, active task, and current page.

## Polling Behavior

- Task detail auto-refreshes every 5 seconds while task status is `running` or `queued`.
- User can pause/resume polling.
- Detail page shows last refresh time, current stage, progress summary, quality table, event stream, and last error.

## Visual Description

- Dashboard now reads as a dense operations console: run metrics, current configuration, first-run checklist, capability boundaries, and recent task table.
- Cards and tables have tighter spacing, clearer hierarchy, Chinese labels, and practical status tags.

## Build Result

- `npm run build` passed.
- Known remaining warning: Ant Design bundle chunk is larger than 500 kB.

## Backend Endpoint Assumptions

- Expected but not guaranteed yet:
  - `POST /llm/models`
  - `POST /exports/validate-path`
  - `POST /exports/resolve-path`
- Frontend has mock/manual fallback for these endpoints.
