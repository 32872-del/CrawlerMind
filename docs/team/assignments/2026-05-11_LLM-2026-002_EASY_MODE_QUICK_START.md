# Assignment: Easy Mode Quick Start Docs

## Assignee

Employee ID: `LLM-2026-002`

Project role: `ROLE-DOCS-QA`

Status: assigned

Assigned by: `LLM-2026-000`

Date: 2026-05-11

## Goal

Rewrite the first-use documentation around CLM Easy Mode so a new user can
install dependencies, configure an API provider, run a local check, perform a
small crawl, and find the output without reading the whole project history.

## Required Reading

Start with:

```text
git pull origin main
```

Then read:

```text
README.md
PROJECT_STATUS.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
docs/runbooks/EMPLOYEE_TAKEOVER.md
dev_logs/README.md
```

## Allowed Write Scope

You may edit:

```text
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
dev_logs/development/2026-05-11_HH-MM_easy_mode_quick_start.md
docs/memory/handoffs/2026-05-11_LLM-2026-002_easy_mode_quick_start.md
```

Do not edit code. Do not remove advanced docs; move advanced details lower if
needed.

## Documentation Requirements

The quick start must explain:

1. Install dependencies.
2. Run `python clm.py init` or the implemented equivalent.
3. Run `python clm.py check`.
4. Run one deterministic crawl without an API key.
5. Run one optional LLM-enabled crawl after API configuration.
6. Where output files go.
7. What is out of scope: login cracking, CAPTCHA solving, hostile Cloudflare
   bypass, private data, unauthorized scraping.
8. Difference between user commands and developer training scripts.

Keep the first-use path short. Put advanced training/stress commands after the
basic workflow.

## Deliverables

Create or update:

```text
README.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/runbooks/QUICK_START_CN.md
dev_logs/development/2026-05-11_HH-MM_easy_mode_quick_start.md
docs/memory/handoffs/2026-05-11_LLM-2026-002_easy_mode_quick_start.md
```

Completion note should include:

- files changed
- exact commands documented
- remaining confusing areas
- whether command docs match current CLI behavior
