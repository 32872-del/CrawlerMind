# Profile Ecommerce Runner Runbook

Date: 2026-05-15

Owner: `LLM-2026-004`

## Purpose

The profile ecommerce runner lets CLM run site-agnostic ecommerce collection
from explicit JSON profile data. Profiles can drive three current paths:

- DOM list/detail crawling with selectors and link discovery.
- Observed API pagination replay with JSON field mapping.
- Mixed SSR + hydration fallback profiles that keep DOM selectors and observed
  API replay hints in one reusable profile.

The runner must not contain site-specific rules. A new site should be described
by a profile file plus safe runtime configuration.

## DOM List/Detail Profile

Use this shape when a category/list page links to product detail pages.

Required fields:

- `selectors.list`: list/category selectors, usually including
  `item_container` and a link selector.
- `selectors.detail`: product field selectors such as `title`,
  `highest_price`, `colors`, `sizes`, `description`, and `image_urls`.
- `pagination_hints.link_discovery`: allow/deny patterns, allowed domains,
  restricted CSS scope, URL classification, priority, and max links.
- `access_config`: declare whether static, dynamic, login, or protected access
  is expected. Do not include cookies or secrets.
- `quality_expectations`: minimum item count, required fields, currency, and
  category.

Example fixture:

- `autonomous_crawler/tests/fixtures/ecommerce_site_profile.json`

## API Pagination Profile

Use this shape when browser/network observation found a stable product API that
can be replayed without private credentials.

Required fields:

- `api_hints.endpoint`: observed API endpoint.
- `api_hints.method`: usually `GET`.
- `api_hints.items_path`: dot path to the product list in the JSON response.
- `api_hints.field_mapping`: generic product fields mapped to JSON paths.
- `api_hints.params`: fixed query parameters such as category filters.
- `pagination_hints.type`: one of `page`, `offset`, or `cursor`.

Supported pagination hints:

- `page`: `page_param`, `start_page`, `page_size_param`, `page_size`,
  `max_pages`.
- `offset`: `offset_param`, `start_offset`, `page_size`, `max_offset`,
  `max_pages`.
- `cursor`: `cursor_param`, `initial_cursor`, `next_cursor_path`.

Example fixture:

- `autonomous_crawler/tests/fixtures/ecommerce_api_pagination_profile.json`

## Mixed SSR + Hydration Profile

Use this shape when a site has useful server-rendered links or detail pages,
but product data may also be available through hydration/XHR APIs.

Profile guidance:

- Keep DOM list/detail selectors under `selectors.list` and `selectors.detail`.
- Keep the observed hydration API under `api_hints`.
- Set `pagination_hints.type` to `cursor`, `page`, or `offset` for the API
  side.
- Use `crawl_preferences.include_seed_urls_with_api: true` when both API seeds
  and DOM seed URLs should be queued for training.
- Do not move brand-specific selectors into runtime code.

Example fixture:

- `autonomous_crawler/tests/fixtures/ecommerce_mixed_hydration_profile.json`

## Quality Summary

Profile training output includes a quality summary with:

- field completeness for `title`, `price`, `category`, `description`, and
  `image_urls`
- duplicate count and duplicate rate
- failed URLs and failed URL count
- pagination stop reason
- final frontier stats
- `quality_gate` checks for item count, required field completeness, duplicate
  rate, and failed URL count

This makes fixture and real-site training evidence easier to compare without
reading raw records first.

## Quality Gate

The profile quality gate is warning-first by default. It adds a structured
`quality_gate` block to the quality summary but does not stop the old runner
flow unless a caller explicitly chooses `mode: fail` or `fail_on_gate=True`.

Gate inputs:

- `min_items`: minimum acceptable product record count.
- `required_fields`: either a list of fields that require 100 percent
  completeness, or a mapping from field name to minimum completeness ratio.
- `field_thresholds`: per-field completeness thresholds. Supported generic
  names include `title`, `price` or `highest_price`, `category`,
  `description`, `image_urls`, `colors`, and `sizes`.
- `max_duplicate_rate`: maximum duplicate product dedupe-key rate.
- `max_failed_url_count`: maximum tolerated failed URL count.
- `mode`: `warn` or `fail`. `warn` preserves report-only behavior. `fail`
  marks failed checks as hard failures and sets `quality_gate.should_fail`.

Example profile policy:

```json
{
  "quality_expectations": {
    "mode": "warn",
    "min_items": 50,
    "required_fields": {
      "title": 0.95,
      "highest_price": 0.95,
      "category": 0.95,
      "description": 0.8,
      "image_urls": 0.8
    },
    "max_duplicate_rate": 0.05,
    "max_failed_url_count": 0
  }
}
```

Example report shape:

```json
{
  "quality_gate": {
    "mode": "warn",
    "passed": true,
    "should_fail": false,
    "severity": "pass",
    "checks": [
      {"name": "min_items", "passed": true, "expected": 50, "actual": 55},
      {"name": "duplicate_rate", "passed": true, "expected": 0.0, "actual": 0.0},
      {"name": "failed_url_count", "passed": true, "expected": 0, "actual": 0},
      {"name": "field:title", "passed": true, "expected": 0.95, "actual": 1.0}
    ]
  }
}
```

For profile training, policy is read from `quality_expectations`. Duplicate and
failed URL thresholds default to strict zero unless the profile provides
`max_duplicate_rate` or `max_failed_url_count`.

Duplicate rate uses `ProductRecord.dedupe_key`, currently generated from:

```text
sha256(source_site | category | canonical_url_or_source_url_or_title)[:32]
```

This is category-aware, but it still depends on profile URL mapping quality.

## Profile Run Report

Training scripts can now export stable `profile-run-report/v1` JSON through
`build_profile_run_report`.

The report includes:

- record count and runner summary
- field completeness
- `quality_gate` and `quality_policy`
- duplicate count/rate and duplicate-key strategy
- failed URLs and stored failures
- pagination/stop reason
- runtime and parser backend
- sample records
- suggested `next_actions`

The offline profile library training and real profile training scripts include
this report under each profile case as `report`.

## Run Smoke

Offline smoke:

```text
python run_profile_ecommerce_runner_smoke_2026_05_14.py
```

The smoke writes:

```text
dev_logs/smoke/2026-05-14_profile_ecommerce_runner_smoke.json
```

Focused test:

```text
python -m unittest autonomous_crawler.tests.test_profile_ecommerce_runner -v
```

Profile library training:

```text
python run_profile_training_2026_05_15.py
```

The training script writes:

```text
dev_logs/training/2026-05-15_profile_ecommerce_training.json
```

Real public ecommerce-like profile training:

```text
python run_real_ecommerce_profile_training_2026_05_15.py
```

The current real training profile is:

```text
autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json
```

It targets the public DummyJSON products API with offset pagination and writes:

```text
dev_logs/training/2026-05-15_real_ecommerce_profile_dummyjson.json
```

If the real target is unavailable, the script preserves real failure evidence
and runs a deterministic fixture regression with the same profile shape:

```text
python run_real_ecommerce_profile_training_2026_05_15.py --fixture-only
```

Real public batch profile training:

```text
python run_profile_real_batch_2026_05_15.py
```

The batch currently uses these profile files:

```text
autonomous_crawler/tests/fixtures/ecommerce_real_dummyjson_profile.json
autonomous_crawler/tests/fixtures/ecommerce_real_platzi_profile.json
autonomous_crawler/tests/fixtures/ecommerce_real_fakestore_profile.json
```

It writes:

```text
dev_logs/training/2026-05-15_profile_real_batch_report.json
```

Current expected behavior:

- DummyJSON: 50+ records, quality gate pass.
- Platzi Fake Store API: 50+ records, quality gate pass.
- FakeStoreAPI: public catalog is smaller than 50 records; report should show
  a `min_items` warning while preserving useful field completeness evidence.

## Safety Boundaries

- Do not put cookies, API keys, bearer tokens, proxy credentials, or storage
  state paths into a profile.
- Do not use profiles to bypass login, CAPTCHA, Cloudflare, or access controls.
- Only replay APIs that are observable and safe to access in the current
  environment.
- Keep site-specific selectors and URL patterns in profile files, not runner
  code.

## Current Limits

- DOM/API/mixed profile fixtures are deterministic and offline; real ecommerce
  APIs need observed response validation.
- DummyJSON is a public product-like catalog API, not a protected retail site.
  It proves profile-driven pagination and product mapping, but not anti-bot,
  browser rendering, checkout, login, or inventory-specific behavior.
- Generic product quality gates are currently report-first. Hard stop behavior
  is opt-in through fail mode and is not wired as a global runner default.
- Public API batch training is useful evidence, but protected retail sites,
  browser-rendered catalogs, and long 600+ real-site regressions are still
  pending.
