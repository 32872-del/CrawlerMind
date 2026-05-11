# Crawler-Mind Project Showcase

Date: 2026-05-09

Project name: Crawler-Mind, abbreviated as CLM.

## One-Sentence Summary

Crawler-Mind is an early autonomous crawling agent framework that turns a
natural-language crawl request into a structured workflow:

```text
Planner -> Recon -> Strategy -> Executor -> Extractor -> Validator
```

It is not a finished universal crawler yet. It is a working local research and
engineering framework with real crawl capability, LLM advisor support,
browser/API training, ecommerce training evidence, and a multi-agent development
process.

## Why This Project Exists

Traditional crawlers usually depend on hand-written site scripts. CLM is trying
to move toward a more adaptive model:

- inspect a target page before choosing a crawl mode
- prefer public/static/API paths before browser rendering
- use LLMs for planning and strategy advice without giving them direct side
  effects
- keep deterministic fallback available when LLMs fail
- preserve logs, decisions, handoffs, and training evidence for future agents
- gradually learn from real-site failures through fixtures and tests

The current principle is conservative: CLM should help with public or authorized
collection, and should diagnose access-control issues rather than bypass them.

## Current Architecture

Main workflow:

```text
Planner
  Parses user goal and creates an initial task plan.

Recon
  Fetches or inspects the target, detects static HTML, JS shells, anti-bot
  signals, API hints, selectors, and browser-network candidates.

Strategy
  Chooses mode: http, browser, api_intercept, or diagnosis-only behavior.

Executor
  Runs the selected strategy through HTTP, Playwright browser rendering,
  observed public API replay, GraphQL/JSON API fetch, fnspider, or mock
  fixtures.

Extractor
  Normalizes extracted records into items.

Validator
  Checks completeness, anomalies, retry needs, and final status.
```

Important supporting modules:

- `autonomous_crawler/storage/`: SQLite result store, frontier, domain memory.
- `autonomous_crawler/llm/`: OpenAI-compatible advisor interfaces and adapter.
- `autonomous_crawler/tools/`: recon, browser, API, fetch policy, product
  helpers.
- `autonomous_crawler/api/`: FastAPI background-job service.
- `docs/team/`: team board, assignments, audits, acceptance records, employee
  memory.

## Working Capabilities

| Capability | Current state |
|---|---|
| Static HTML crawling | Usable MVP |
| Selector inference | Usable MVP |
| Browser rendering fallback | Usable MVP |
| Public JSON API extraction | Usable MVP |
| Public GraphQL extraction | Usable MVP |
| Browser network observation | Early MVP |
| Observed JSON POST API replay | Early MVP |
| Page/offset/cursor API pagination | MVP with deterministic tests |
| LLM Planner/Strategy advisor | Optional, OpenAI-compatible |
| Deterministic fallback | Implemented |
| FastAPI background jobs | Implemented, in-memory registry |
| SQLite result persistence | Implemented |
| SQLite frontier | Implemented |
| Bundled fnspider engine | Integrated |
| Ecommerce small-sample workflow | Training-stage MVP |
| Local 30,000-row stress test | Passed synthetic test |

## Real Training Evidence

### Baidu Hot Search

Target:

```text
https://top.baidu.com/board?tab=realtime
```

Result:

```text
30 items extracted
validation passed
end-to-end workflow completed
```

### Public JSON / GraphQL Training

Validated examples include:

- JSONPlaceholder direct JSON
- Reddit `.json`
- Countries GraphQL
- AniList GraphQL
- DummyJSON products
- GitHub issues API
- HN Algolia API

### Browser Network Observation

HN Algolia SPA was used as the first real browser-network training case.

Result:

```text
Recon observed public XHR/API candidates.
Strategy selected api_intercept.
Executor replayed public JSON POST search API.
10 items extracted.
```

### Ecommerce Training

Output:

```text
dev_logs/training/2026-05-09_ecommerce_training_sample.xlsx
dev_logs/training/2026-05-09_ecommerce_training_sample.json
dev_logs/training/2026-05-09_ecommerce_training_summary.md
```

Sites:

| Site | Result |
|---|---|
| Shoesme | Cloudflare challenge detected; diagnosis-only row recorded |
| Donsje | Shopify public JSON; 5 products with price, color, size, description, images |
| Clausporto | Magento-style static list/detail pages; 5 candle products |
| uvex.com.pl | Magento-style pages; 5 helmet products; sizes extracted from `jsonConfig` |
| Bosch.de | Corporate product/service page; partial records without fake prices |

This batch is intentionally small. It proves mode selection and field extraction
patterns, not full-site scale.

### Local Stress Test

Output:

```text
run_stress_test_2026_05_09.py
dev_logs/stress/2026-05-09_local_stress_test_summary.json
dev_logs/stress/2026-05-09_local_stress_test_report.md
dev_logs/stress/2026-05-09_stress_export_30000.xlsx
```

Result:

```text
30,000 synthetic ecommerce URLs inserted into SQLite frontier.
30,000 URLs claimed and marked done.
30,000 product records saved and loaded through result storage.
30,000-row Excel export completed.
Peak memory: about 196 MB.
Total elapsed time: about 39 seconds.
```

Interpretation:

The local components can handle a 30,000-row synthetic batch. This does not yet
prove real-site multi-hour stability, because real long runs add network errors,
rate limits, retries, rendering failures, checkpoint recovery, and per-domain
politeness constraints.

## Current Engineering Limits

CLM should not yet be advertised as a universal production crawler.

Known limits:

- Large ecommerce runs need checkpointed product storage.
- `CrawlResultStore` currently stores both full `final_state_json` and per-item
  rows, which is useful for small tasks but not ideal for very large crawls.
- FastAPI running job state is in memory and is lost on process restart.
- API pagination needs more real-site hardening.
- Infinite scroll and virtualized lists need more training.
- Cloudflare, CAPTCHA, and login-required pages remain diagnosis-only unless a
  separate authorized access plan exists.
- There is no frontend UI yet.

## Safety Boundary

CLM's default policy:

- public or authorized pages only
- no login bypass
- no CAPTCHA bypass
- no Cloudflare challenge bypass
- no committed cookies, tokens, API keys, proxy accounts, or browser profiles
- small-sample validation before any expansion
- challenge/login cases are recorded as diagnosis rather than bypassed

## Development Workflow

This project also tests a supervisor-plus-worker AI development model.

The repository includes:

- employee registry
- task board
- assignments
- audits
- acceptance records
- handoffs
- daily reports
- long-term blueprints

This makes it possible for multiple Codex/LLM workers to collaborate on
separate modules while preserving traceability.

## Near-Term Roadmap

Next practical development target:

1. Add `ProductRecord` schema.
2. Add product quality validation.
3. Add product-specific SQLite storage with checkpointed upserts.
4. Add resumable run progress and run-level metrics.
5. Convert the ecommerce training samples into fixtures/tests.
6. Continue real-site training on pagination, dynamic pages, infinite scroll,
   and virtualized lists.
7. Later, add a simple frontend for API configuration, task submission, example
   upload, and result review.

## Current Evaluation

As of 2026-05-09, CLM is past the pure skeleton stage. It has a real end-to-end
pipeline, LLM advisor integration, browser/API capability, storage, tests,
training evidence, and project process.

It is best described as:

```text
Working research MVP with credible crawl-agent foundations.
Ready for controlled training and internal demos.
Not yet ready for unsupervised large production crawls.
```
