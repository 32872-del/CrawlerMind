# Assignment: Access Layer Runbook

## Assignee

Employee ID: `LLM-2026-002`

Project role: `ROLE-ACCESS-DOCS`

Status: assigned

Assigned by: `LLM-2026-000`

Date: 2026-05-12

## Goal

Write a practical runbook explaining how CLM should handle advanced access
needs safely: authorized sessions, optional proxies, rate limits, browser
rendering, challenge detection, and manual handoff.

## Required Reading

Start with:

```text
git pull origin main
```

Then read:

```text
README.md
PROJECT_STATUS.md
docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md
docs/runbooks/QUICK_START_CN.md
docs/runbooks/QUICK_START_WINDOWS.md
docs/runbooks/QUICK_START_LINUX_MAC.md
docs/process/COLLABORATION_GUIDE.md
```

Code to inspect:

```text
autonomous_crawler/tools/access_policy.py
autonomous_crawler/tools/proxy_manager.py
autonomous_crawler/tools/session_profile.py
autonomous_crawler/tools/rate_limit_policy.py
autonomous_crawler/tools/challenge_detector.py
```

## Allowed Write Scope

You may create or edit:

```text
docs/runbooks/ACCESS_LAYER.md
docs/runbooks/README.md
dev_logs/development/2026-05-12_HH-MM_access_layer_runbook.md
docs/memory/handoffs/2026-05-12_LLM-2026-002_access_layer_runbook.md
```

Do not edit code. Do not document any real proxy credentials, cookie values, or
CAPTCHA-solving provider defaults.

## Documentation Requirements

Explain:

1. What the Access Layer is and why it exists.
2. Safe default behavior: no proxy, no CAPTCHA solving, no hidden bypass.
3. Authorized session profile concept: headers, cookies, storage state, domain
   scope, redaction.
4. Proxy configuration concept: disabled by default, per-domain routing, health
   checks as future work.
5. Rate-limit policy concept: per-domain delay, retry cap, backoff.
6. Challenge detection behavior: Cloudflare/CAPTCHA/login/429 diagnosis and
   manual handoff.
7. How this fits the future frontend: form fields the user will configure.
8. What remains future work: browser context manager, OCR/visual recon,
   JS-reverse engineering assist, distributed proxy health scoring.

## Deliverables

Create:

```text
docs/runbooks/ACCESS_LAYER.md
dev_logs/development/2026-05-12_HH-MM_access_layer_runbook.md
docs/memory/handoffs/2026-05-12_LLM-2026-002_access_layer_runbook.md
```

Completion note should include:

- files changed
- user-facing concepts documented
- safety boundaries documented
- any places where docs need code examples after implementation matures
