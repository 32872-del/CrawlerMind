# 2026-05-12 12:00 - Access Layer Runbook

## Goal

Write a practical user runbook explaining how CLM handles advanced access needs
safely: authorized sessions, proxies, rate limits, browser rendering, challenge
detection, and manual handoff.

## Changes

| File | Change |
|---|---|
| `docs/runbooks/ACCESS_LAYER.md` | Created. Full runbook covering all Access Layer modules. |
| `docs/runbooks/README.md` | Added `ACCESS_LAYER.md` to the runbook list. |

## What Was Documented

1. **What the Access Layer is**: policy modules that turn fetch signals into
   auditable decisions.
2. **Safe defaults**: proxy disabled, no CAPTCHA solving, 1s/domain rate limit,
   3 retries, 2x backoff.
3. **Challenge detection**: Cloudflare/CAPTCHA/login/429 classification with
   structured `ChallengeSignal` output.
4. **Access policy decisions**: 6 actions (standard_http, browser_render,
   backoff, authorized_session_required, authorized_browser_review,
   manual_handoff) with risk levels and safeguards.
5. **Authorized session profiles**: headers/cookies/storage_state with domain
   scoping and credential redaction.
6. **Proxy configuration**: opt-in, per-domain routing, credential redaction,
   health checks as future work.
7. **Rate-limit policy**: per-domain delay/retry/backoff with wildcard support.
8. **Manual handoff**: what triggers it, what the output looks like, what to do.
9. **Browser rendering escalation**: auto-detect JS shells, switch to Playwright.
10. **Future frontend config**: form field designs for session profiles, proxy,
    rate limit, and challenge policy.
11. **Future work**: browser context manager, proxy health scoring, OCR/visual
    recon, JS reverse-engineering assist, distributed rate limiting, CAPTCHA
    provider plugin interface.

## Verification

- Read all 5 source modules (`access_policy.py`, `proxy_manager.py`,
  `session_profile.py`, `rate_limit_policy.py`, `challenge_detector.py`) plus
  `access_diagnostics.py`.
- Read `PROJECT_STATUS.md`, `TOP_CRAWLER_CAPABILITY_ROADMAP.md`, and
  `COLLABORATION_GUIDE.md`.
- Runbook accuracy verified against code: dataclass fields, decision logic,
  default values, redaction behavior all match implementation.

## Result

Runbook created. Covers all 8 documentation requirements from the assignment.

## Gaps

- Code examples are conceptual (JSON config), not runnable CLI commands. This
  is intentional: the Access Layer modules are not yet wired into `clm.py`
  CLI flags. When they are, the runbook should be updated with `clm.py`
  command examples.
- Proxy health checks, browser context manager, and visual recon are documented
  as future work only.
