# Dev Log - 2026-05-04 17:33 - Recon Selector MVP

## Goal

Replace hardcoded product selectors with deterministic HTML recon so Strategy can
use selectors inferred from the target page.

## What changed

### 1. Added local HTML recon helpers

- Added `autonomous_crawler/tools/html_recon.py`.
- Supports deterministic `mock://catalog` fixture.
- Detects basic frontend framework markers:
  - Next.js
  - Nuxt
  - React
  - Vue
  - Angular
- Detects simple anti-bot/challenge indicators.
- Discovers obvious API endpoint strings.
- Infers repeated product/card containers and field selectors.

### 2. Recon node now performs actual HTML analysis

- Updated `autonomous_crawler/agents/recon.py`.
- Recon fetches HTML and writes:
  - `frontend_framework`
  - `rendering`
  - `anti_bot`
  - `api_endpoints`
  - `dom_structure.product_selector`
  - `dom_structure.field_selectors`

### 3. Strategy uses inferred selectors

- Updated `autonomous_crawler/agents/strategy.py`.
- Strategy now prefers selectors from `recon_report.dom_structure`.
- Hardcoded `.product-item` selectors remain only as fallback.

### 4. Mock fixture now proves inference is being used

- Updated `autonomous_crawler/agents/executor.py`.
- The fixture now uses:
  - `.catalog-card`
  - `.product-name`
  - `.product-price`
  - `.product-photo`
  - `.product-link`
- This prevents tests from passing via old `.product-item` defaults.

### 5. Tests expanded

- Rewrote `autonomous_crawler/tests/test_workflow_mvp.py` as ASCII-safe source.
- Added coverage for:
  - Recon selector inference
  - Strategy consuming recon selectors
  - Full graph completion via inferred selectors

## Verification

```text
python -m unittest discover autonomous_crawler\tests
Ran 6 tests
OK

python run_skeleton.py "<Chinese product title and price goal>" mock://catalog
Final Status: completed
Extracted 2 items
Strategy rationale: using inferred DOM selectors
```

## Notes

This is still heuristic. It is not a replacement for MCP crawler's richer
`infer_site_selectors` / `infer_site_spec_from_samples`, but it gives the Agent
a stable local fallback and a clear state contract for MCP integration.

## Next recommended step

Add a `site_spec` adapter so inferred selectors can be exported into a
spider_Uvex-compatible configuration.
