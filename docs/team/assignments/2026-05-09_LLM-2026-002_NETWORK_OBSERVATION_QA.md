# Assignment: Browser Network Observation QA

Employee ID: `LLM-2026-002`

Project role: `ROLE-QA`

Status: assigned

Assigned by: `LLM-2026-000`

Date: 2026-05-09

## Goal

Prepare QA coverage for the new browser network observation capability.

The supervisor will implement the first tool skeleton. Your job is to review
the behavior, add focused tests where useful, and identify failure paths.

## Scope

Own these files:

```text
autonomous_crawler/tests/test_browser_network_observer.py
docs/team/audits/
dev_logs/
docs/memory/handoffs/
```

You may read:

```text
autonomous_crawler/tools/browser_network_observer.py
autonomous_crawler/tools/browser_fetch.py
autonomous_crawler/tools/fetch_policy.py
```

Avoid editing implementation files unless the supervisor explicitly asks.

## Expected QA Areas

Cover or audit:

- Playwright missing
- navigation failure
- response capture limit
- JSON response capture
- GraphQL request detection
- non-JSON response handling
- redaction of sensitive headers or tokens
- deterministic output shape

## Constraints

- Do not run hostile anti-bot bypass tests.
- Do not use real credentials.
- Do not require network access for unit tests.
- Prefer mocked Playwright.

## Verification

Run:

```text
python -m unittest autonomous_crawler.tests.test_browser_network_observer -v
python -m unittest discover -s autonomous_crawler/tests
```

If the implementation lands after you start, base tests on the final public
interface.

## Completion Report

Report:

- number of tests added or audit findings
- highest severity issue
- files changed
- tests run
- recommended supervisor action
