# Assignment: CLM Frontend Workbench MVP

Date: 2026-05-18

Employee: LLM-2026-004

Project role: Frontend Workbench Worker

## Mission

Build the first CLM product-facing frontend as a browser-based workbench.
The UI should let a user configure CLM, analyze a site, import or edit
catalog/menu data, choose fields, launch test/full runs, watch progress, and
export results.

This is a product workflow task, not a marketing page. The first screen should
be the actual working console.

## Read First

- `docs/plans/2026-05-18_FRONTEND_DEVELOPMENT_SPEC_CN.md`
- `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md`
- `PROJECT_STATUS.md`
- `docs/team/TEAM_BOARD.md`

## Write Scope

You may create or modify:

- a new frontend app at `frontend/` or an equivalent clearly isolated UI workspace
- UI pages, components, request layer, and frontend types
- frontend build/test config for that workspace
- `dev_logs/` and `docs/memory/handoffs/` for your own work notes

Avoid modifying:

- `autonomous_crawler/` backend code unless a tiny contract fix is unavoidable
- backend workflow semantics
- other employees' assignment files

## Requirements

1. Build these screens:
   - dashboard / home
   - new task wizard
   - site analyze result page
   - task detail page
   - task history page
   - settings page
2. Wire the UI to the existing workflow APIs:
   - `POST /catalog/import`
   - `POST /site/analyze`
   - `POST /fields/resolve`
   - `POST /runs/test`
   - `POST /runs/full`
   - `GET /runs/{task_id}/status`
   - `GET /runs/{task_id}/events`
   - `POST /exports`
3. Support these user flows:
   - LLM provider config
   - URL input
   - catalog JSON import
   - field selection and natural-language field request
   - test run vs full run
   - runtime status and event viewing
   - export download / file path display
4. Keep the UI operational and dense, not decorative.
5. Keep the first version simple enough that another employee can continue it.

## Acceptance

- frontend builds successfully
- the main workflow can be completed end-to-end from the UI
- catalog import and field selection work
- task status and events are visible
- export can be triggered from the UI
- the UI looks like a work console, not a landing page

## Handoff

Report:

- files created
- screens completed
- API calls wired
- missing backend gaps noticed
- build/test result

