# Assignment: Access Layer QA

## Assignee

Employee ID: `LLM-2026-001`

Project role: `ROLE-ACCESS-QA`

Status: assigned

Assigned by: `LLM-2026-000`

Date: 2026-05-12

## Goal

Harden the new Access Layer MVP with focused tests and report any behavior
that could make proxy/session/rate-limit/challenge handling unsafe or
unreliable.

## Required Reading

Start with:

```text
git pull origin main
```

Then read:

```text
PROJECT_STATUS.md
docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md
docs/process/COLLABORATION_GUIDE.md
docs/decisions/ADR-002-deterministic-fallback-required.md
docs/decisions/ADR-005-llm-planner-strategy-must-be-optional.md
```

Code to inspect:

```text
autonomous_crawler/tools/access_policy.py
autonomous_crawler/tools/challenge_detector.py
autonomous_crawler/tools/proxy_manager.py
autonomous_crawler/tools/session_profile.py
autonomous_crawler/tools/rate_limit_policy.py
autonomous_crawler/tools/access_diagnostics.py
autonomous_crawler/tools/fetch_policy.py
autonomous_crawler/tests/test_access_layer.py
```

## Allowed Write Scope

You may edit:

```text
autonomous_crawler/tests/test_access_layer.py
autonomous_crawler/tests/test_access_diagnostics.py
autonomous_crawler/tests/test_fetch_policy.py
dev_logs/development/2026-05-12_HH-MM_access_layer_qa.md
docs/memory/handoffs/2026-05-12_LLM-2026-001_access_layer_qa.md
```

Do not edit production code unless a tiny testability fix is unavoidable. If
production code needs a larger change, report it instead of taking ownership.

## Required Checks

Add or verify tests for:

1. Proxy is disabled by default and never appears in safe summaries with
   credentials.
2. Session profile headers/cookies are domain-scoped and redacted in audit
   output.
3. 429 produces a backoff/rate-limit decision.
4. Cloudflare/CAPTCHA markers produce manual handoff, not automatic solving.
5. `fetch_best_page()` records safe access context without leaking secrets.
6. Existing deterministic tests still do not require network, proxy, cookies,
   or API keys.

## Minimum Commands

Run:

```text
python -m unittest autonomous_crawler.tests.test_access_layer -v
python -m unittest autonomous_crawler.tests.test_access_diagnostics -v
python -m unittest autonomous_crawler.tests.test_fetch_policy -v
python -m unittest discover -s autonomous_crawler/tests
```

## Deliverables

Create:

```text
dev_logs/development/2026-05-12_HH-MM_access_layer_qa.md
docs/memory/handoffs/2026-05-12_LLM-2026-001_access_layer_qa.md
```

Completion note should include:

- files changed
- tests added/updated
- tests run
- highest remaining risk
- whether Access Layer MVP is accepted, conditionally accepted, or rejected
