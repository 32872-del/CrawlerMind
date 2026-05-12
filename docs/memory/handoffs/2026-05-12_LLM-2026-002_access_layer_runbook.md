# Handoff: Access Layer Runbook

Employee: LLM-2026-002
Date: 2026-05-12
Assignment: `2026-05-12_LLM-2026-002_ACCESS_LAYER_RUNBOOK`

## What Was Done

Created a practical runbook explaining how CLM handles advanced access needs
safely. The runbook covers all 8 required topics from the assignment.

## Files Changed

| File | Change |
|---|---|
| `docs/runbooks/ACCESS_LAYER.md` | Created. Full Access Layer runbook. |
| `docs/runbooks/README.md` | Added ACCESS_LAYER.md to list. |

## User-Facing Concepts Documented

1. Access Layer purpose and module overview
2. Safe defaults (proxy off, no CAPTCHA solving, conservative rate limits)
3. Challenge detection (Cloudflare, CAPTCHA, login, 429 classification)
4. Access policy decisions (6 action types with risk levels)
5. Authorized session profiles (headers, cookies, storage state, domain scoping)
6. Proxy configuration (opt-in, per-domain routing, credential redaction)
7. Rate-limit policy (per-domain delay, retry cap, backoff)
8. Manual handoff flow (what triggers it, what to do)
9. Browser rendering escalation (JS shell auto-detection)
10. Future frontend form field designs
11. Future work (browser context, proxy health, OCR, JS RE, distributed rate
    limiting, CAPTCHA plugin interface)

## Safety Boundaries Documented

- Proxy disabled by default
- No CAPTCHA solving as default path
- No Cloudflare challenge bypass
- Session profiles are domain-scoped to prevent credential leakage
- Sensitive headers and cookies are redacted in all logs and reports
- Proxy URLs with credentials are redacted
- Manual handoff is the safe default for unrecognized challenges

## No Code Changed

Documentation only. No implementation or test files modified.

## For Supervisor

### Places That Need Code Examples After Implementation Matures

1. `clm.py` CLI flags for access config (not yet wired)
2. FastAPI request body fields for session/profile/proxy (not yet exposed)
3. Example crawl output showing access_decision in real results

### Remaining Gaps

- Proxy health checks are future work only
- Browser context manager is future work only
- Visual recon / OCR is future work only
- JS reverse-engineering assist is future work only
- Distributed rate limiting is future work only
