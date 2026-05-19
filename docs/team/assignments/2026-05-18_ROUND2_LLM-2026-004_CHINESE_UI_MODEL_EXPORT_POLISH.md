# Assignment: Chinese Product Workbench Round 2

Date: 2026-05-18

Employee: LLM-2026-004

Project role: Frontend Workbench Worker

Priority: P0

## Mission

Upgrade the frontend MVP into a product-facing Chinese workbench that can be
used for a real demo and continued product development.

The current frontend is accepted as a technical MVP, but the next version must
feel like a real CLM control panel for Chinese users.

## Read First

- `docs/team/acceptance/2026-05-18_frontend_workbench_mvp_ACCEPTED.md`
- `docs/plans/2026-05-18_FRONTEND_DEVELOPMENT_SPEC_CN.md`
- `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md`
- `frontend/src/`

## Write Scope

Primary ownership:

- `frontend/src/`
- `frontend/package.json` only if needed
- frontend notes under `dev_logs/development/`
- handoff under `docs/memory/handoffs/`

Avoid modifying backend files. If an endpoint is missing, mock the frontend
contract and document it clearly for the backend worker.

## Requirements

1. Convert all visible page text to Chinese.
   - menus
   - buttons
   - form labels
   - table headers
   - messages
   - empty states
   - status labels
   - validation errors
   - mock/demo text
   - status and quality labels
2. Add LLM model picker flow.
   - user enters `base_url`
   - user enters `api_key`
   - user clicks "获取模型列表"
   - frontend calls backend model-list endpoint when available
   - user selects a model from a dropdown
   - if backend endpoint is unavailable, show a clear Chinese error and allow
     manual model input
3. Add provider presets.
   - OpenAI-compatible
   - DeepSeek-compatible
   - SiliconFlow-compatible
   - local/Ollama-like custom base URL
   - custom relay
   - presets should only fill defaults; user can always edit manually
4. Add export folder selection UX.
   - preferred: browser directory picker if available
   - fallback: text input for local backend path
   - show final export file path before run
   - call backend path validation endpoint when available
   - show whether directory exists, was created, and is writable
5. Polish the UI.
   - make the dashboard look like a mature operations console
   - improve spacing, hierarchy, color use, and task cards
   - keep information dense and practical
   - avoid marketing hero sections
   - add clear visual distinction for setup, analysis, running, completed,
     warning, and failed states
   - refine tables and cards so they are readable with many tasks
6. Persist settings in `localStorage`.
   - API base URL
   - LLM config except consider not displaying the key after reload if you
     choose to mask it
   - runtime/export defaults
   - selected model
   - UI mode and last selected task
7. Add task polling improvements.
   - auto refresh task detail while running
   - allow user to pause polling
   - show last refresh time
   - show current stage, quality indicator, progress summary, and last error
8. Add first-run guidance inside the workbench.
   - compact Chinese setup checklist
   - no marketing copy
   - no separate landing page
9. Improve API error display.
   - distinguish backend offline, LLM config invalid, export path invalid,
     and run failed
   - display backend error message in Chinese context
10. Keep `npm run build` passing.

## Acceptance

- no obvious English UI text remains on visible pages
- model list request and dropdown exist
- export folder/path UX exists
- settings survive page reload
- visual design is noticeably more polished
- dashboard, wizard, task detail, history, and settings all work in Chinese
- task detail auto polling works and can be paused
- backend API failures are understandable to a Chinese user
- `npm run build` passes

## Handoff

Report:

- UI files changed
- model picker behavior
- provider presets
- export folder behavior
- localStorage keys
- polling behavior
- screenshots or a concise visual description of the polished UI
- build result
- backend endpoint assumptions
