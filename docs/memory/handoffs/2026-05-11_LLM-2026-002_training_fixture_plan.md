# Handoff: Training Fixture Plan

Employee: LLM-2026-002
Date: 2026-05-11
Assignment: `2026-05-11_LLM-2026-002_TRAINING_FIXTURE_PLAN`

## What Was Done

Abstracted the 5 real ecommerce training sites into 6 generic crawl
scenarios for fixture/test creation. Each scenario is site-agnostic and
uses `example.test` domains.

## Scenarios Defined

| # | Scenario | Source Pattern | Round |
|---|---|---|---|
| 1 | Static list+detail | clausporto, uvex | 1 |
| 2 | Public JSON API | donsje (Shopify) | 1 |
| 3 | Paginated API | generic offset/cursor | 1 |
| 4 | JS rendered list | SPA browser fallback | 2 |
| 5 | Variant detail | donsje, uvex variants | 2 |
| 6 | Challenge diagnosis | shoesme, bosch | 2 |

## Key Design Decisions

- All fixtures use `example.test` — no real URLs.
- No bypass logic — challenge fixtures only test detection.
- Scenarios map to both the training ladder tiers and the ecommerce
  workflow task types (category/list/detail/variant).
- Each scenario has: fixture files, test file, acceptance criteria,
  and failure-to-test mapping.
- Total target: 18+ fixture files, 41+ test cases across 6 scenarios.

## Files Created

- `docs/team/audits/2026-05-11_LLM-2026-002_TRAINING_FIXTURE_PLAN.md`
- `docs/memory/handoffs/2026-05-11_LLM-2026-002_training_fixture_plan.md`

## No Code Changed

This is a planning document only. No implementation or test files created.

## For Supervisor

The plan is ready for review. Recommended next steps:

1. Approve the 6-scenario breakdown.
2. Assign Round 1 (scenarios 1-3) as implementation task.
3. Round 2 (scenarios 4-6) can proceed after Round 1 is accepted.

The plan integrates with the existing `ProductRecord` model and
`validate_product_record()` validator. Clean fixture records should
pass validation; edge-case records should produce expected issue codes.
