# Real-Site Training Ladder

## Purpose

This document preserves the user-provided real-site training list as a
permanent backlog item in the team workflow.

It is the long-term reference for future crawl training, acceptance, and
fixture creation.

## Source

- `E:\爬虫Agent实战训练网站清单.md`

## Working Rules

1. Keep safe/public targets in the active training loop.
2. Treat login, CAPTCHA, Cloudflare challenge, and signature-heavy targets as
   diagnosis-only until an explicit authorized test plan exists.
3. Convert each completed training round into:
   - a `dev_logs/` record
   - a `docs/reports/` summary
   - a board update if capability changed
4. Promote repeated failures into fixtures, tests, or strategy rules.

## Training Ladder

### Tier 1: Safe Public Targets

- public JSON APIs
- public GraphQL APIs
- static ranking pages
- SSR and framework recon pages

Completed examples:

- JSONPlaceholder posts
- Reddit `r/python.json`
- Countries GraphQL
- AniList GraphQL
- Bilibili public ranking API
- Douban Top250
- React docs SSR recon
- Vue examples recon

### Tier 2: Browser-Rendered Targets

- local SPA fixtures
- public SPA demos
- pages that require browser fallback but not hostile bypass

### Tier 3: Scroll / Virtualization / Mixed Rendering

- infinite scroll demos
- virtualized list demos
- mixed SSR plus hydration pages

### Tier 4: Diagnosis-Only Targets

- login-required targets
- CAPTCHA-protected targets
- Cloudflare challenge targets
- signature-heavy or device-fingerprint-heavy targets

These remain on the map for planning, but not as active implementation
targets unless the project has a documented safety boundary.

## Supervisor Usage

When assigning training work:

1. Pick one ladder rung.
2. Write a short assignment with a concrete success condition.
3. Require a dev log and a report.
4. Accept only after tests and board updates are complete.

## Next Suggested Training

- one controlled SPA target
- one virtualized-list target
- one browser-network-observation sample
- one failure case that becomes a reusable fixture
