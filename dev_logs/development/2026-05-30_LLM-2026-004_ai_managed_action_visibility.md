# 2026-05-30 LLM-2026-004 AI Managed Action Visibility

## Scope

- Frontend-only update for the task detail workbench.
- Main goal: make AI managed action execution visible, with focused support for `extract_from_contract`.

## Changes

- Updated `frontend/src/components/AiManagedPanel.tsx`
  - Added full AI action plan table with action name, reason, params summary, execution status, and execution result.
  - Added Chinese labels for `extract_from_contract`.
  - Added dedicated contract extraction panel:
    - parser strategy
    - site
    - extracted item count
    - field coverage
    - first five sample products
  - Added Chinese error mapping for missing contract/evidence and unsupported parser strategy.

- Updated `frontend/src/pages/TaskDetailPage.tsx`
  - Expanded managed action record table into a full execution record.
  - Added contract extraction summary and first five sample products in the lower action history area.
  - Kept state in existing workbench store/localStorage path, so page switching does not lose task data.

- Updated `frontend/src/api/mockData.ts`
  - Added mock `extract_from_contract` managed action result using Superdry-style contract output.
  - Added a failing `extract_from_contract` sample to verify Chinese error display.

- Updated `frontend/src/components/EventTimeline.tsx`
  - Added Chinese labels for managed step/control loop/access probe events.

## Verification

- `npm --prefix frontend run build`: passed.
- Local mock UI verification via Python Playwright + system Chrome:
  - URL: `http://127.0.0.1:5173`
  - Screenshot: `output/playwright/ai-managed-contract-detail.png`
  - Checks passed:
    - contract panel visible
    - action label visible
    - sample product visible
    - Chinese error reason visible

## Notes

- No backend Python files were modified.
- No API keys are rendered; raw evidence display remains sanitized by existing sensitive-key masking.
- The screenshot helper is under `output/playwright/` and is only a local verification artifact.
