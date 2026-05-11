# Ecommerce Crawl Workflow

This document defines the generic ecommerce crawl workflow for Crawler-Mind.
It is a process guide, not a place for site-specific rules.

## Goal

Crawler-Mind should extract structured product data from public or authorized
pages while keeping site-specific knowledge outside the core engine.

Core code may provide:

- generic product records
- price, image, body, and variant quality checks
- category-aware deduplication
- frontier/checkpoint storage
- runtime profiles and strategy hints

Core code must not hard-code:

- selectors for one named site
- one-off API endpoints
- Cloudflare or CAPTCHA bypass logic
- real cookies, tokens, API keys, proxy accounts, or sessions

Site-specific selectors, pagination hints, API templates, and fallback notes
belong in a runtime site profile, crawl profile, fixture, or training record.

## Standard Product Fields

Minimum useful ecommerce output:

| Field | Meaning | Requirement |
|---|---|---|
| `url` / `canonical_url` | product detail URL | required |
| `title` | product title | required |
| `highest_price` | normalized numeric highest visible price | recommended |
| `currency` | visible or inferred currency | recommended |
| `colors` | product colors when available | optional |
| `sizes` | product sizes when available | optional |
| `description` | product body or cleaned detail text | recommended |
| `image_urls` | product image URL list | recommended |
| `category` | category/list context | recommended |
| `status` | `ok`, `partial`, `blocked`, or `failed` | required |
| `mode` | crawl mode used, such as `http`, `browser`, `api_intercept` | recommended |
| `notes` | diagnosis notes, especially for blocked/partial records | recommended |
| `raw_json` | bounded raw evidence for replay/debugging | optional |
| `dedupe_key` | stable category-aware key | required by storage |

The normalized schema can be extended later, but product storage and quality
checks should remain site-agnostic.

## Task Types

### Category

Discover category entry points from a homepage, sitemap, navigation tree, or
known category URL.

Output category name, level, URL, and context payload. Do not run a large detail
crawl from this step.

### List

Extract product links or card-level records from one category/search/list page.

Output detail URLs, card title/price/image when available, pagination metadata,
and category context. Prefer sending discovered detail URLs into the frontier
quickly instead of crawling every category first.

### Detail

Extract one product page into a `ProductRecord`.

Check title, price, image, description, colors, sizes, variant hints, and
category context. Detail pages are the main quality gate.

### Variant

Extract color/size/stock/price combinations from page JSON, visible controls,
or public variant APIs.

Keep missing/out-of-stock variants when they are visible; do not silently drop
them.

## Category-Aware Dedupe

Ecommerce dedupe must preserve category context. The same product URL may appear
in several categories, and that relationship can be valuable.

Default key:

```text
source_site + category + canonical_url
```

Fallback key:

```text
source_site + category + source_url_or_title
```

Future variant-aware key:

```text
source_site + category + canonical_url + color + size
```

## Quality Checklist

Each ecommerce sample should answer:

- Does the record have a usable URL and title?
- Can the price be parsed, or is the raw value preserved for review?
- Are product images present and not only logos/icons/placeholders?
- Is the description/body present when the site exposes it?
- Are colors and sizes captured when visible?
- Is the category context still attached at detail time?
- Is the dedupe key stable and category-aware?
- Are blocked/challenge/login cases marked as diagnosis-only with notes?
- Can a human review the sample in JSON/CSV/Excel?

Failed samples should become fixtures or tests before expanding crawl volume.

## Safety Boundary

Allowed:

- public or authorized pages
- low-rate small samples
- static HTML extraction
- browser rendering without bypassing access controls
- public JSON/GraphQL/XHR API observation and replay
- challenge/login/CAPTCHA diagnosis

Not allowed in core:

- login cracking
- CAPTCHA solving
- Cloudflare challenge bypass
- forged authorization
- committed real cookies, tokens, sessions, or API keys
- proxy-account configuration
- site-specific bypass scripts
- full-scale scraping before sample quality is accepted

## Small-Sample Workflow

1. Confirm the site is public or authorized.
2. Pick one category/list page and one to five product details.
3. Run recon: static HTML, JS shell, structured data, API hints, challenge signs.
4. Choose mode: `http`, `browser`, `api_intercept`, or `diagnosis_only`.
5. Save sample evidence and extracted records.
6. Run product quality validation.
7. Convert generic failures into fixtures/tests.
8. Only then expand pagination, categories, and run duration.

## Long-Running Rule

Large ecommerce jobs must use checkpointed product storage and frontier progress.
Do not rely only on an in-memory final state for tens of thousands of products.

See `docs/runbooks/LONG_RUNNING_ECOMMERCE_RUNS.md`.
