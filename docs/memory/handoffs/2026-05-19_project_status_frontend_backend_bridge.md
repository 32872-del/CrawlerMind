# 2026-05-19 CLM Handoff: Frontend / Backend Bridge

## State

Backend crawl execution is functional. The main issue investigated today was the frontend workbench workflow, not the crawling engine itself.

## Findings

- `POST /site/analyze` works and returns real catalog/field/profile data for Romet.
- `POST /runs/test` works when given the analyzed payload and can complete with real records.
- Frontend analysis view had stale-state and workflow visibility problems.
- Auto mode mock fallback could hide real backend errors.

## Repairs

- Rewrote the analysis page to show:
  - target URL
  - workflow logs
  - catalog tree
  - field selector
  - actual run payload preview
  - reset current analysis
- Removed silent mock fallback in non-mock API calls.

## Verification

- Frontend build passed.
- Backend frontend-support and product-workflow tests passed.
- Direct Romet probe completed successfully and exported CSV output.

## Files

- `frontend/src/api/client.ts`
- `frontend/src/pages/AnalysisPage.tsx`

## Carry Forward

- Ask the user to hard refresh the browser and retry from a reset analysis state.
- If the issue persists, check localStorage and whether the browser is still loading an old bundle.
