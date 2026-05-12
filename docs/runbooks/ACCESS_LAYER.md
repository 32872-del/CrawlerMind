# Access Layer Runbook

This document explains how CLM handles advanced access needs: authorized
sessions, proxies, rate limits, browser rendering, challenge detection, and
manual handoff. The Access Layer is diagnostic and policy-driven by design. It
does not bypass access controls.

## What the Access Layer Is

The Access Layer is a set of policy modules that turn raw fetch signals into
explicit, auditable decisions. Instead of treating a Cloudflare challenge or a
429 response as a random failure, CLM classifies the situation, chooses a safe
next step, and records what happened.

The modules are:

| Module | File | Purpose |
|---|---|---|
| `ChallengeDetector` | `tools/challenge_detector.py` | Classify Cloudflare, CAPTCHA, login, and 429 pages |
| `AccessPolicy` | `tools/access_policy.py` | Convert diagnostics into an auditable decision |
| `SessionProfile` | `tools/session_profile.py` | Model user-provided headers, cookies, and storage state |
| `ProxyConfig` / `ProxyManager` | `tools/proxy_manager.py` | Opt-in proxy selection with credential redaction |
| `RateLimitPolicy` | `tools/rate_limit_policy.py` | Per-domain delay, retry cap, and backoff rules |
| `AccessDiagnostics` | `tools/access_diagnostics.py` | Page-level signal detection and recommendation engine |

## Safe Defaults

CLM's default behavior is conservative. Nothing happens unless you configure it.

| Setting | Default |
|---|---|
| Proxy | Disabled |
| Session profile | None (plain HTTP headers) |
| Rate limit delay | 1 second per domain |
| Max retries | 3 |
| Backoff factor | 2x |
| CAPTCHA solving | Not implemented |
| Challenge bypass | Not implemented |

If CLM encounters a challenge page and you have not provided an authorized
session, the result is a `manual_handoff` decision. CLM will record what it
found and stop, not attempt to solve or bypass.

## Challenge Detection

The `ChallengeDetector` scans HTML and response headers for known markers. It
classifies challenges into structured types:

| Kind | Examples | Severity |
|---|---|---|
| `managed_challenge` | Cloudflare, Incapsula, DataDome, PerimeterX | High |
| `captcha` | hCaptcha, reCAPTCHA, GeeTest | High |
| `login_required` | 401/403 with login form markers | Medium |
| `rate_limited` | HTTP 429 | Medium |
| `access_denied` | "Access denied" text | High |

The detector returns a `ChallengeSignal` with:
- `detected`: whether a challenge was found
- `kind`: the classified type
- `vendor`: the identified vendor (cloudflare, hcaptcha, recaptcha, etc.)
- `severity`: low, medium, or high
- `primary_marker`: the first matched marker string
- `requires_manual_handoff`: true for managed challenges, CAPTCHAs, and logins

The detector is diagnostic only. It does not solve CAPTCHAs or bypass
Cloudflare.

## Access Policy Decisions

`AccessPolicy.decide_access()` takes diagnostics and produces an `AccessDecision`
with one of these actions:

| Action | Meaning | Allowed by default? |
|---|---|---|
| `standard_http` | No access block detected | Yes |
| `browser_render` | Page likely needs JS rendering | Yes |
| `backoff` | Rate-limited (429), slow down | Yes |
| `authorized_session_required` | 401/403, needs cookies/headers | Only with session |
| `authorized_browser_review` | Challenge detected, has session | Only with session |
| `manual_handoff` | Challenge detected, no session | No |

Every decision includes:
- `risk_level`: low, medium, or high
- `allowed`: whether CLM should proceed
- `reasons`: machine-readable reason codes
- `safeguards`: reminders like "do not solve CAPTCHA by default"

These decisions are stored in the crawl result so you can audit what CLM did
and why.

## Authorized Session Profiles

A session profile describes user-provided authentication state. Use it when you
have legitimate access to a site that requires login.

### What a profile contains

```json
{
  "name": "my-shopify-store",
  "allowed_domains": ["mystore.myshopify.com"],
  "headers": {
    "Authorization": "Bearer <your-token>"
  },
  "cookies": {
    "session_id": "abc123"
  },
  "storage_state_path": ""
}
```

- `name`: a human-readable label
- `allowed_domains`: restrict which domains this profile applies to (empty
  means all domains, which is rarely what you want)
- `headers`: HTTP headers to inject (Authorization, custom tokens, etc.)
- `cookies`: cookie key-value pairs (merged into a Cookie header automatically)
- `storage_state_path`: path to a Playwright storage state JSON file (for
  browser-mode sessions with localStorage/IndexedDB)

### Domain scoping

A profile only applies to URLs whose hostname matches `allowed_domains`. If you
set `allowed_domains: ["example.com"]`, the profile will not be sent to
`other.com`. This prevents accidental credential leakage.

### Redaction

When CLM logs or serializes a profile, sensitive headers (`Authorization`,
`Cookie`, `X-API-Key`, `X-Auth-Token`) and all cookie values are replaced with
`[redacted]`. Proxy URLs with credentials are also redacted. This means you can
safely include profile summaries in reports and logs.

### Validation

Profiles are validated before use. If `storage_state_path` points to a file
that does not exist, CLM reports the error. If `allowed_domains` is empty, the
profile applies globally (a warning is recommended).

### Using a session profile in a crawl

Session profiles are passed through the access config to the fetch and recon
layers. When CLM detects a 401/403 or challenge page and a matching session
profile exists, the access decision changes from `manual_handoff` to
`authorized_browser_review`. CLM will then attempt the crawl with the provided
session.

## Proxy Configuration

Proxy support is opt-in and disabled by default.

### Configuration

```json
{
  "enabled": true,
  "default_proxy": "http://proxy.example.com:8080",
  "per_domain": {
    "example.com": "http://proxy-a.example.com:8080",
    "*.protected.com": "socks5://proxy-b.example.com:1080"
  },
  "provider": "manual"
}
```

- `enabled`: must be `true` for any proxy to be used
- `default_proxy`: fallback proxy for all domains
- `per_domain`: domain-specific proxy routing (supports `*.domain.com` wildcard)
- `provider`: label for your proxy source (manual, your-pool-name, etc.)

### Supported schemes

`http`, `https`, `socks5`

### Credential redaction

Proxy URLs like `http://user:pass@host:port` are logged as
`http://***:***@host:port`. Credentials are never exposed in reports, logs, or
crawl results.

### Validation

CLM checks that proxy URLs have a supported scheme and a valid network location.
If `enabled` is true but no proxy URL is configured, CLM reports the error.

### Health checks

Proxy health checking is not yet implemented. The `provider` field exists so a
future health-check module can track proxy availability, latency, and failure
rates per domain.

## Rate Limit Policy

Rate limiting is always active. The default policy is 1 request per second per
domain with 3 retries and 2x exponential backoff.

### Configuration

```json
{
  "default": {
    "delay_seconds": 1.0,
    "max_retries": 3,
    "backoff_factor": 2.0
  },
  "per_domain": {
    "api.github.com": {
      "delay_seconds": 2.0,
      "max_retries": 5,
      "backoff_factor": 3.0
    },
    "*.example.com": {
      "delay_seconds": 0.5,
      "max_retries": 2,
      "backoff_factor": 2.0
    }
  }
}
```

### How it works

1. Before each request, CLM looks up the domain rule (exact match, then
   wildcard, then default).
2. It waits `delay_seconds` since the last request to that domain.
3. If the request fails with a retryable status (408, 425, 429, 500, 502, 503,
   504) or a transport error, CLM checks `attempt < max_retries`.
4. On retry, the delay increases: `delay * (backoff_factor ^ attempt)`.
5. The decision is recorded as a `RateLimitDecision` with the computed delay,
   retry count, and reason.

### 429 handling

When CLM receives a 429 response:
- The `ChallengeDetector` classifies it as `rate_limited`
- The `AccessPolicy` produces a `backoff` decision
- The `RateLimitPolicy` increases the delay before the next attempt
- The crawl result records the rate-limit event

## Challenge Identification and Manual Handoff

When CLM encounters a challenge it cannot handle, it stops and records a
`manual_handoff`. This is the safe default.

### What triggers manual handoff

- Cloudflare managed challenge (cf-challenge, "just a moment", etc.)
- CAPTCHA pages (hCaptcha, reCAPTCHA, GeeTest)
- Login-required pages (401/403 with login form markers)
- Any challenge when no authorized session is configured

### What manual handoff looks like in output

The crawl result will contain:

```json
{
  "access_decision": {
    "action": "manual_handoff",
    "risk_level": "high",
    "allowed": false,
    "reasons": ["managed_challenge:cf-challenge"],
    "safeguards": [
      "do not solve CAPTCHA by default",
      "use only user-provided authorized sessions",
      "respect configured rate limits",
      "record access decision"
    ],
    "requires_authorized_session": true,
    "requires_manual_review": true
  }
}
```

### What to do when you see manual handoff

1. **Check the challenge kind and vendor.** This tells you what protection the
   site uses.
2. **If you have authorized access**, create a session profile with your
   credentials and re-run with the profile configured.
3. **If the site has a public API**, use that instead of scraping the HTML page.
4. **If you need browser rendering** (JS shell pages), CLM will auto-escalate
   to browser mode. This is separate from challenges.
5. **Do not use CAPTCHA-solving services** as a default CLM path. If you have
   an authorized integration, it should be a clearly labeled plugin with its
   own configuration.

## Browser Rendering Escalation

Separate from challenges, CLM auto-detects pages that need JavaScript rendering.

When `access_diagnostics` detects a JS shell (little visible text, many script
tags, React/Angular/Vue app roots), the access decision is `browser_render`.
CLM automatically switches to Playwright browser mode with these defaults:

- `wait_until`: networkidle
- `render_time`: 5 seconds
- `scroll_count`: 2

This escalation is safe and does not require special configuration. It only
affects the fetch mode, not the access policy.

## How This Fits the Future Frontend

The Access Layer modules are designed as configuration objects. A future
frontend form will let users fill in these fields without touching JSON:

### Session Profile Form

| Field | Type | Description |
|---|---|---|
| Profile Name | Text | Human-readable label |
| Allowed Domains | Text list | Which domains this profile applies to |
| Headers | Key-value pairs | HTTP headers (Authorization, etc.) |
| Cookies | Key-value pairs | Cookie values |
| Storage State | File upload | Playwright storage state JSON |

### Proxy Configuration Form

| Field | Type | Description |
|---|---|---|
| Enable Proxy | Toggle | Master on/off |
| Default Proxy | Text | Fallback proxy URL |
| Per-Domain Routing | Table | Domain-to-proxy mapping |
| Provider | Text | Label for your proxy source |

### Rate Limit Configuration Form

| Field | Type | Description |
|---|---|---|
| Default Delay (seconds) | Number | Base delay between requests |
| Default Max Retries | Number | Retry cap |
| Default Backoff Factor | Number | Exponential multiplier |
| Per-Domain Overrides | Table | Domain-specific rules |

### Challenge Policy Form (future)

| Field | Type | Description |
|---|---|---|
| On CAPTCHA | Select | manual_handoff / authorized_plugin |
| On Cloudflare | Select | manual_handoff / authorized_browser |
| On 401/403 | Select | manual_handoff / use_session_profile |
| On 429 | Select | backoff / manual_handoff |

These forms will write to the same JSON structures the policy modules already
consume. No code changes are needed on the policy side; the frontend is a
configuration UI.

## Future Work

The Access Layer MVP provides structured detection and policy decisions. These
areas are planned but not yet implemented:

### Browser Context Manager

Currently, browser rendering uses default Playwright settings. A future
`BrowserContextManager` will support:
- Custom user-agent and viewport
- Locale and timezone configuration
- Per-domain storage state loading
- Screenshot artifact capture on failure or challenge
- Network observation artifact storage with redacted headers

### Proxy Health Scoring

A future health-check module will track:
- Proxy availability per domain
- Latency percentiles
- Failure rates
- Automatic failover to backup proxies

### OCR and Visual Recon

A future `VisualRecon` module will:
- Extract text from screenshots (OCR)
- Detect repeated card layouts visually
- Map visual fields to DOM elements
- Generate selector candidates from visual analysis

### JS Reverse-Engineering Assist

A future expert module will:
- Inventory JS assets on a page
- Detect API signature parameters
- Generate request-diff reports
- Optionally integrate AST parsers

### Distributed Rate Limiting

The current rate limiter is per-process. A future version will use Redis or a
similar store for cross-process coordination.

### CAPTCHA Provider Plugin Interface

If authorized CAPTCHA solving is needed, it will be implemented as an optional
plugin with explicit configuration, not as a default behavior. The plugin will
require the user to provide their own provider credentials and will log every
solve attempt.

## Related Docs

- Quick start: [QUICK_START_WINDOWS.md](QUICK_START_WINDOWS.md),
  [QUICK_START_LINUX_MAC.md](QUICK_START_LINUX_MAC.md),
  [QUICK_START_CN.md](QUICK_START_CN.md)
- Roadmap: `docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md`
- Project status: `PROJECT_STATUS.md`
