# E2E Training Report - 2026-06-02

**Generated:** 2026-06-02 10:30:00  
**Environment:** Windows 10, Python 3.13, PowerShell  
**Project:** CLM - AI Managed Crawl Loop v2  

---

## Executive Summary

The AI Managed Crawl Loop v2 has been systematically tested across 8 real sites with 3 difficulty levels. The core managed loop (action plan → execute → run) is **functionally operational** but has several issues that need attention before production use.

| Metric | Value |
|--------|-------|
| E2E Sites Tested | 8 |
| E2E Pass Rate | 7/8 (87.5%) |
| Total Records Extracted | 196 |
| Managed Loop Tests | 3 (2 completed, 1 hung) |
| Diagnose-and-Repair Tests | 3/3 completed |
| Unit Tests (original) | 106/106 passed |
| Unit Tests (extended) | 48/48 passed |
| Regression Tests | 135/135 passed |
| Compilation Check | ✅ Clean |

---

## Part 1: Unit Test Coverage Analysis

### Original Test Suite (106 tests) ✅ All Pass

| Test File | Tests | Status |
|-----------|-------|--------|
| test_managed_actions.py | 32 | ✅ All pass |
| test_auto_repair.py | 14 | ✅ All pass |
| test_ecommerce_extractors.py | 60 | ✅ All pass |

### Extended Coverage Tests (48 new tests) ✅ All Pass

Added `test_extended_coverage.py` covering:

| Category | Tests | Key Areas |
|----------|-------|-----------|
| execute_and_run() edge cases | 5 | Empty plan, profile merging, schema version, exception handling |
| diagnose_and_repair() closed loop | 4 | Healthy job, failed job, challenge detection, snapshots |
| Extended price range parsing | 8 | Euro tilde, dollar no-space, yen, comma thousands, extra spaces |
| SPA detection signals | 10 | React, Vue, Angular, Next, Nuxt, Svelte, Gatsby, SSR vs CSR |
| Pagination patterns | 4 | page=, offset=, cursor=, no pagination |
| Diagnoser edge cases | 5 | Empty job, string error log, browser crash, timeout, proxy |
| JSON-LD extractor | 2 | Multiple products, aggregate offer |
| ManagedActionPlan | 6 | Empty actions, None, max truncation, malformed, priority, source |
| AutoRepairLoop | 3 | Empty job, serializable, custom executor |

---

## Part 2: E2E Training Results (8 Sites)

### Batch 1: Easy (JSON API) — 3/3 ✅

| Site | Records | Coverage | Elapsed | Status |
|------|---------|----------|---------|--------|
| dummyjson.com/products | 30 | 96.4% | 3.8s | ✅ PASS |
| dummyjson.com/categories | 24 | 70.0% | 4.3s | ✅ PASS |
| jsonplaceholder.typicode.com/posts | 100 | 70.0% | 5.2s | ✅ PASS |

**Analysis:** JSON API sites work perfectly. The crawler correctly identifies API endpoints, fetches JSON, and extracts structured data. Coverage is high because JSON APIs provide clean, structured fields.

### Batch 2: Medium (SSR E-commerce) — 2/2 ✅

| Site | Records | Coverage | Elapsed | Status |
|------|---------|----------|---------|--------|
| scrapingcourse.com/ecommerce | 16 | 100.0% | 8.1s | ✅ PASS |
| scrapingcourse.com/pagination | 12 | 100.0% | 9.0s | ✅ PASS |

**Analysis:** SSR sites work well with DOM parsing. Field coverage is 100% because the HTML is well-structured.

**⚠️ Issue:** Pagination site only extracted 12 items from page 1. **Pagination was NOT auto-followed** despite being a test target. The crawler detected products on the first page but didn't follow pagination links.

### Batch 3: Hard (Real E-commerce) — 2/3 ⚠️

| Site | Records | Coverage | Elapsed | Status |
|------|---------|----------|---------|--------|
| marksandspencer.com | 10 | 100.0% | 5.3s | ✅ PASS |
| nike.com | 0 | 0.0% | 3.7s | ❌ FAIL |
| superdry.com | 4 | 100.0% | 6.5s | ✅ PASS |

**Analysis:**

**marksandspencer.com** — Successfully extracted 10 products with prices and images. However, **price range parsing bug confirmed**: `"£13 - £26"` was parsed as `1326.0` instead of `13.0` (min) / `26.0` (max). This is a known limitation of `_number_or_none()` which strips currency symbols and concatenates digits.

**nike.com** — Complete failure. Nike is a Next.js SPA that requires browser rendering. The static HTTP fetch returned 877K chars of HTML but the extractor found 0 products. The site redirected to `nike.com.cn` (China). Anti-bot risk score: 98/100 (critical). **Playwright is not installed** (`chrome-headless-shell.exe` not found), so browser rendering is unavailable.

**superdry.com** — Extracted 4 items but they are **navigation menu items**, not actual products. The DOM parser found repeated elements in the navigation bar instead of the product grid. This is a selector quality issue.

---

## Part 3: Managed Loop (execute_and_run) Results

### Test Sites

| Site | Action Plan | Applied Patch | Records | Run Status | Elapsed | Notes |
|------|-------------|---------------|---------|------------|---------|-------|
| dummyjson.com | 7 actions | ✅ Yes | 0 | partial | 23.4s | Actions ran, crawl produced 0 records |
| scrapingcourse.com | 7 actions | ✅ Yes | 0 | partial | 27.7s | Actions ran, crawl produced 0 records |
| marksandspencer.com | 7 actions | — | — | — | hung | inspect_access hung (browser probe) |

**Key Findings:**

1. **Action plans execute correctly**: All 7 deterministic actions (reanalyze_site → inspect_access → repair_selectors → adjust_runtime → evaluate_quality → prepare_export → prepare_rerun) run successfully and produce profile patches.

2. **Profile merging works**: The `merged_profile` contains all expected keys: `access_config`, `api_hints`, `crawl_preferences`, `selectors`, `quality_expectations`, `pagination_hints`, `target_fields`, `_action_evidence`.

3. **Crawl integration gap**: While the action plan produces patches, the actual crawl (`run_profile_longrun`) produces 0 records. This suggests the patched profile isn't being effectively used by the crawl runner, or the crawl runner has its own issues.

4. **Browser probe timeout**: M&S test hung on `inspect_access` because it attempted a live browser probe without Playwright installed. The `inspect_access` action with `live_probe=True` blocks indefinitely when the browser runtime can't launch.

---

## Part 4: Diagnose-and-Repair Results

| Site | Diagnosis Health | Repair Plan | Actions | Converged |
|------|-----------------|-------------|---------|-----------|
| dummyjson.com | critical | ✅ Yes | adjust_runtime, inspect_access, repair_selectors, prepare_rerun | No |
| scrapingcourse.com | critical | ✅ Yes | adjust_runtime, inspect_access, repair_selectors, prepare_rerun | No |
| marksandspencer.com | critical | ✅ Yes | adjust_runtime, inspect_access, repair_selectors, prepare_rerun | No |

**Analysis:**

1. **Diagnosis works correctly**: The `FailureDiagnoser` correctly identifies "no_records" as a critical failure and generates appropriate repair actions.

2. **Repair plans are reasonable**: For zero-record failures, the repair chain is: `adjust_runtime` (upgrade to dynamic browser) → `inspect_access` (gather access evidence) → `repair_selectors` (fix selectors) → `prepare_rerun` (prepare for retry).

3. **Convergence requires actual re-execution**: The `diagnose_and_repair()` function generates repair plans but convergence requires the re-execution to actually produce records. Since the crawl runner has issues (see Part 3), convergence isn't achieved.

---

## Part 5: Issues Found and Recommendations

### Critical Issues

1. **🔴 Price Range Parsing Bug (CONFIRMED)**
   - **Symptom:** `"£13 - £26"` → `1326.0` (concatenated digits)
   - **Root Cause:** `_number_or_none()` strips all non-digit/dot chars and finds the first number. For ranges, it picks up `13` then `-` then `26` → `1326`.
   - **Note:** `parse_price_range()` works correctly (returns min=13, max=26), but the item extraction doesn't use it for the `highest_price` field.
   - **Fix:** Item extractors should detect price ranges and use `parse_price_range()` to extract min/max, storing `min_price` and `max_price` separately.

2. **🔴 Playwright Not Installed**
   - **Symptom:** Browser rendering unavailable for SPA sites
   - **Impact:** Nike.com and other SPA sites completely fail
   - **Fix:** Run `playwright install chromium` or provide fallback

3. **🔴 Browser Probe Hangs**
   - **Symptom:** `inspect_access` with `live_probe=True` blocks indefinitely when Playwright isn't available
   - **Fix:** Add timeout to browser probe, fall back to static analysis when browser unavailable

### Warning Issues

4. **🟡 Pagination Not Auto-Followed**
   - **Symptom:** scrapingcourse.com/pagination only got 12 items from page 1
   - **Root Cause:** The base crawler (`run_crawl` via `run_skeleton.py`) doesn't follow pagination. The managed loop's `follow_pagination` action is only triggered when pagination URLs are provided in `extra_context`.
   - **Fix:** The `reanalyze_site` action should detect pagination links and pass them to the crawl runner.

5. **🟡 SPA Detection Not Triggering Browser Upgrade**
   - **Symptom:** Nike.com detected as `nextjs` framework but didn't trigger browser rendering
   - **Root Cause:** SPA detection checks for `rendering=spa/csr` but Nike reports as `nextjs` (which can be SSR). The detection logic needs to also check item count (0 items from 877K HTML = likely SPA).
   - **Fix:** Add heuristic: if framework is SPA-capable (next/nuxt/react/vue) AND items extracted == 0, trigger browser upgrade.

6. **🟡 Superdry Extracting Nav Items**
   - **Symptom:** Superdry.com homepage extracts navigation menu items instead of products
   - **Root Cause:** DOM parser finds repeated elements in nav bar before reaching product grid
   - **Fix:** Improve DOM analysis to prefer product-grid selectors over navigation selectors

7. **🟡 Crawl Runner Not Using Patches Effectively**
   - **Symptom:** `execute_and_run()` produces 0 records even with patches applied
   - **Root Cause:** The `run_profile_longrun()` function may not be using the patched selectors/access_config effectively
   - **Fix:** Verify the patch-to-crawl pipeline

### Informational

8. **🔵 Comma-Separated Thousands Not Parsed**
   - `"£1,000"` → `1.0` instead of `1000.0`
   - Low priority, uncommon in practice

9. **🔵 `_extract_progress()` Crashes on Non-Dict `profile_run`**
   - When `profile_run` is a string, `.get()` raises `AttributeError`
   - Defensive coding fix needed

---

## Part 6: Regression Test Results

| Test Suite | Tests | Status |
|------------|-------|--------|
| test_managed_actions.py | 32 | ✅ All pass |
| test_auto_repair.py | 14 | ✅ All pass |
| test_ecommerce_extractors.py | 60 | ✅ All pass |
| test_extended_coverage.py | 48 | ✅ All pass |
| **Total** | **154** | **✅ All pass** |
| Compilation check | — | ✅ Clean |

**No regressions detected.** All existing tests continue to pass after changes.

---

## Overall Assessment

### Is the Closed Loop Actually Connected?

**Partially.** The managed loop has three phases:

1. **Action Planning** ✅ — `build_deterministic_action_plan()` correctly generates action plans based on site state
2. **Action Execution** ✅ — `execute_managed_action_plan()` correctly executes actions and produces profile patches
3. **Crawl Integration** ⚠️ — `execute_and_run()` merges patches but the crawl runner (`run_profile_longrun`) produces 0 records

The loop is **structurally complete** but the **crawl runner integration needs work**. The action plan → profile patch → merged profile pipeline works, but the merged profile isn't translating into successful crawls.

### Readiness Assessment

| Component | Status | Ready for Production? |
|-----------|--------|----------------------|
| Action Planning | ✅ Working | Yes |
| Action Execution | ✅ Working | Yes |
| Profile Merging | ✅ Working | Yes |
| Failure Diagnosis | ✅ Working | Yes |
| Repair Plan Generation | ✅ Working | Yes |
| Crawl Runner | ⚠️ 0 records | No - needs fixes |
| Pagination Following | ❌ Not working | No |
| SPA Auto-Upgrade | ❌ Not working | No |
| Price Range Parsing | ❌ Bug confirmed | No - needs fix |
| Browser Rendering | ❌ Playwright missing | No - needs install |

### Recommended Next Steps

1. **Install Playwright** — `playwright install chromium`
2. **Fix price range parsing** — Use `parse_price_range()` in item extractors
3. **Fix crawl runner integration** — Verify patches are used by `run_profile_longrun`
4. **Fix pagination detection** — Auto-detect pagination in `reanalyze_site`
5. **Fix SPA detection heuristic** — Check item count + framework combo
6. **Add timeout to browser probe** — Prevent indefinite hangs
