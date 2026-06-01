# Normalization Completion Note

**Task**: Normalize 30 decision JSONs to clm-action-decision-v1 schema
**Date**: 2026-05-30
**Status**: COMPLETED

---

## Normalization Changes

### 1. `recommended_action_plan` → list
- **Before**: dict with keys `actions`, `rejected_actions`, `total_actions`, `total_rejected`
- **After**: list of action objects (each with `action`, `priority`, `reason`, `params`, `depends_on_evidence`)
- **Files affected**: 30/30

### 2. `rejected_actions` → top-level
- **Before**: nested inside `recommended_action_plan.rejected_actions`
- **After**: top-level `rejected_actions` array
- **Files affected**: 30/30

### 3. `evidence_files` → added
- **Before**: field did not exist
- **After**: top-level `evidence_files` object with:
  - `screenshot.path`, `screenshot.exists`, `screenshot.is_placeholder`
  - `html_summary.path`, `html_summary.exists`
  - `network_summary.path`, `network_summary.exists`
- **Files affected**: 30/30

### 4. `input_artifacts` → fixed filenames
- **Before**: wrong screenshot filenames (e.g. `screenshot_f5e10735.png`)
- **After**: correct filenames (e.g. `screenshot_001.png`)
- **Files affected**: 30/30

### 5. Placeholder screenshots → marked
- **Pages 015, 016**: 2016-byte placeholder PNGs (eBay robots.txt blocked real capture)
- `evidence_files.screenshot.is_placeholder: true`
- `missing_evidence` includes `real_screenshot` and `robots_txt_evidence`
- `blocking_signals` includes `robots_txt` entry
- **Files affected**: 2/30

---

## Summary File Status

| File Type | Count | All Exist | Notes |
|-----------|-------|-----------|-------|
| decision_*.json | 30 | Yes | All normalized to clm-action-decision-v1 |
| screenshot_*.png | 30 | Yes | 28 real, 2 placeholder (015, 016) |
| html_summary_*.txt | 30 | Yes | All real content |
| network_summary_*.txt | 30 | Yes | All marked no_network_captured |

---

## Quality Gates (ALL PASS)

- [x] 30/30 normalized JSONs parse correctly
- [x] top-level `recommended_action_plan` is list (30/30)
- [x] top-level `rejected_actions` not empty (30/30)
- [x] `evidence_files` all point to real files (30/30)
- [x] manifest matches real files
- [x] placeholder screenshots marked in `missing_evidence`

---

## Verification Results

```
Sites: 9 (aliexpress, amazon, bestbuy, bhphotovideo, ebay, etsy, homedepot, newegg, target)
Page types: 6 (bestsellers, empty, home, product_detail, product_listing, search_results)
Action types: 8 (analyze_site, export_results, patch_profile, patch_selector, resolve_fields, run_test, select_catalog, switch_runtime)
Unique confidence values: 24 (range: 0.10 - 0.76)
```

---

**Completed by**: LLM-2026-005
**Schema**: clm-action-decision-v1
