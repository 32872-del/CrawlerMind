# Assignment: Product Workflow Export and Status Hardening

# Date: 2026-05-18

Employee: LLM-2026-001

Project role: Backend Product Workflow Worker

## Mission

Strengthen the product workflow backend so the new frontend workbench can use
it for real work, not just demo calls.

Focus on export templating and task status clarity:

- make exported files follow a user template more precisely
- make task status easier to understand from the frontend
- keep the existing data-first export path intact

## Read First

- `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md`
- `docs/plans/2026-05-18_FRONTEND_DEVELOPMENT_SPEC_CN.md`
- `autonomous_crawler/runners/product_workflow.py`
- `autonomous_crawler/api/app.py`
- `autonomous_crawler/storage/product_store.py`
- `PROJECT_STATUS.md`

## Write Scope

Primary ownership:

- `autonomous_crawler/runners/product_workflow.py`
- `autonomous_crawler/api/app.py`
- `autonomous_crawler/storage/product_store.py`
- a small new helper module if needed for template export
- tests for the workflow API and export behavior
- your `dev_logs/` and `docs/memory/handoffs/` notes

Avoid touching:

- frontend files
- durable job registry logic
- browser/runtime executor internals unless export status absolutely requires it

## Requirements

1. Add a richer export template model.
   - sheet name
   - start row / start column
   - field-to-column mapping or explicit cell placement
2. Make `POST /exports` honor the template model for `xlsx`.
3. Keep current export defaults working when no template is supplied.
4. Improve task status payloads for frontend use.
   - current stage
   - last error snippet
   - progress summary
   - any clear completion/quality indicator already available
5. Keep payloads stable and backward compatible.
6. Add focused tests for template export and status behavior.

## Acceptance

- xlsx export can follow a template layout
- default export still works
- status responses are clearer for the UI
- tests pass
- compileall passes

## Handoff

Report:

- template behavior implemented
- status fields added
- tests added
- remaining export gaps
- any frontend-facing contract notes

