# 2026-05-09 - Ecommerce Workflow Docs

## Goal

Draft a Chinese ecommerce crawl workflow document based on
`docs/plans/2026-05-09_SPIDER_TEXT_ABSORPTION_PLAN.md`, without copying the old
external project into CLM.

## Changes

Created:

```text
docs/process/ECOMMERCE_CRAWL_WORKFLOW.md
```

No code files were edited.

No README, PROJECT_STATUS, TEAM_BOARD, or daily report files were edited.

## Verification

Read:

```text
docs/plans/2026-05-09_SPIDER_TEXT_ABSORPTION_PLAN.md
```

Checked worktree state with:

```text
git status --short
```

No tests were run because this was a documentation-only task.

## Result

The new process document covers:

- ecommerce crawl goals and boundaries
- standard product fields
- category/list/detail/variant task types
- category-aware dedupe rules
- product quality checklist
- image, body, price, color, and size requirements
- anti-bot, Cloudflare, and login safety boundaries
- small-sample workflow
- employee step-by-step task guidance
- prohibited actions around login bypass, CAPTCHA bypass, secrets, proxies, and
  external binaries

## Next Step

Recommended follow-up is an implementation assignment for product schema and
quality helpers, plus deterministic fixtures for detail pages, variants,
category-aware dedupe, noisy body HTML, and image normalization.
