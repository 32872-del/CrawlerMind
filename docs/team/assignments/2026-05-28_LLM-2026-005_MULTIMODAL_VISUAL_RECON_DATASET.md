# Assignment: Multimodal Visual Recon Dataset

## Metadata

- Date: 2026-05-28
- Employee ID: `LLM-2026-005`
- Display Name: `Worker Echo`
- Project Role: Multimodal Visual Evidence Worker
- Supervisor: `LLM-2026-000`
- Status: assigned

## Required Reading

Before starting, read:

```text
PLAN.md
docs/plans/2026-05-20_AI_MANAGED_CRAWL_LOOP_V2_SHORT_TERM_PLAN.md
docs/process/DEVELOPMENT_STARTUP_RULE.md
docs/team/TEAM_WORKSPACE.md
docs/team/employees/LLM-2026-005_WORKER_ECHO.md
docs/team/training/XIAOMI_RECON_DATA_QUALITY_GUIDE.md
docs/team/training/XIAOMI_MULTIMODAL_RECON_GUIDE.md
```

## Mission

Build a multimodal visual evidence dataset for CLM. Your work should help CLM understand what a screenshot shows during crawl planning, runtime diagnosis, and repair.

This assignment supports:

```text
AI Managed Crawl Loop v2
```

Current project gap:

```text
CLM has backend crawler tools, but AI still lacks enough structured visual evidence to diagnose page state, product cards, field regions, blocking states, and next actions.
```

## Scope

You are not responsible for code changes.

You are responsible for producing structured files only:

```text
JSON evidence
batch reports
visual failure taxonomy
final summary
```

## Output Directory

Use your own directory so you do not conflict with other workers:

```text
F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28\
```

Do not write into another worker's output directory.

## Input Sources

Use any available public website screenshots, browser screenshots, or provided page captures. Prioritize ecommerce and data-listing pages because they are most relevant to CLM.

Recommended page types:

- ecommerce homepage
- ecommerce category/listing page
- ecommerce product detail page
- search results page
- blocked/challenge page
- cookie banner page
- empty listing page
- infinite-scroll product grid
- GraphQL/API-driven product grid

If you have a URL but no screenshot, create or request screenshot evidence first. Do not produce high-confidence visual claims without visual input.

## Required Per-Page Output

For each page, produce one JSON file following:

```text
docs/team/training/XIAOMI_MULTIMODAL_RECON_GUIDE.md
```

Schema:

```text
clm-visual-recon-v1
```

Required minimum fields:

- `schema_version`
- `site_url`
- `page_url`
- `domain`
- `checked_at`
- `input_artifacts`
- `page_type`
- `visual_state`
- `is_product_listing`
- `is_product_detail`
- `visible_product_cards`
- `field_regions`
- `blocking_signals`
- `pagination_signals`
- `visual_action_hints`
- `recommended_action_plan`
- `confidence`
- `evidence_log`
- `missing_evidence`
- `needs_backend_verification`
- `needs_human_review`

## Quality Rules

1. Evidence first.
   - If something is visible in screenshot, mark `evidence_type=observed`.
   - If inferred from layout or URL, mark `evidence_type=inferred`.
   - If weak guess, mark `evidence_type=guessed`.

2. Do not fake backend proof.
   - Visual recognition is not selector validation.
   - Visual recognition is not API verification.
   - Visual recognition is not successful crawl evidence.

3. Confidence discipline.
   - Screenshot only: `overall` normally must not exceed 0.65.
   - Screenshot + HTML summary: may reach 0.8.
   - Screenshot + HTML + API/runtime evidence: may reach 0.9+.

4. All recommended actions must use CLM canonical action names:
   - `analyze_site`
   - `select_catalog`
   - `resolve_fields`
   - `switch_runtime`
   - `patch_profile`
   - `patch_selector`
   - `promote_xhr_to_api`
   - `apply_replay_runtime`
   - `run_test`
   - `rerun_failed`
   - `export_results`

5. Do not modify source code.

## Target Volume

Minimum useful target:

```text
100 page-level visual recon JSON files
```

Stretch target:

```text
500+ page-level visual recon JSON files
```

Because you have a large token budget, prioritize breadth and consistency.

## Batch Reports

Every 20 pages, write:

```text
batch_001_visual_summary.md
batch_002_visual_summary.md
...
```

Each report must include:

1. Number of pages reviewed.
2. Page type distribution.
3. Visual state distribution.
4. Product listing pages detected.
5. Product detail pages detected.
6. Blocked/challenge/captcha pages.
7. Cookie banner / login wall / geo redirect pages.
8. Common field-region patterns.
9. Common pagination patterns.
10. Most useful CLM action hints.
11. Pages needing human review.

## Failure Taxonomy

Every 100 pages, write:

```text
visual_failure_taxonomy_001.md
```

Classify visual failure patterns:

- `challenge_or_captcha`
- `cookie_banner_blocks_content`
- `login_wall`
- `geo_or_language_redirect`
- `empty_listing`
- `loading_spinner`
- `js_not_rendered`
- `product_cards_unclear`
- `field_regions_unclear`
- `pagination_unclear`
- `mobile_layout_mismatch`
- `unknown`

For each category:

- count
- representative pages
- visual evidence
- recommended CLM backend action
- whether it can become automatic repair logic

## Final Report

At the end, write:

```text
xiaomi_visual_recon_final_report.md
```

Include:

1. Dataset size.
2. Page type distribution.
3. Visual state distribution.
4. Top 20 field-region patterns.
5. Top 20 blocking patterns.
6. Top 20 pagination patterns.
7. Recommended backend improvements for CLM.
8. Recommended frontend display improvements for CLM workbench.
9. Which JSON files are high enough quality to become fixtures.
10. Which pages should be used for real crawl training.

## Acceptance Criteria

Supervisor will accept this assignment only if:

- Output files are in the assigned directory.
- JSON files parse cleanly.
- Evidence type and confidence are present.
- No source code was modified.
- Batch reports exist.
- Final report exists.
- The work clearly supports `AI Managed Crawl Loop v2`.

## Completion Note Format

When finished, report:

```text
Completion Note: Multimodal Visual Recon Dataset

files created:
- ...

number of page JSON files:

batch reports:

failure taxonomy reports:

final report:

highest-confidence examples:

lowest-confidence / needs-review examples:

recommended next supervisor action:
```

