# Advanced Diagnostics Runbook

This document explains CLM's advanced diagnostics for open-source users,
new team members, and enterprise evaluators.

These capabilities help explain why a crawl is hard. They are not bypass tools.
Most of them are opt-in, evidence-only, or still initial foundations.

## Safety Summary

CLM does not:

- crack login systems
- solve or bypass CAPTCHAs by default
- automatically bypass Cloudflare or managed challenges
- recover private keys, API secrets, session cookies, or signing keys
- run a production proxy platform by default
- perform full JavaScript reverse engineering

Advanced diagnostics should be used on public pages, owned systems, test
fixtures, or targets where you have explicit authorization.

## Maturity Labels

| Label | Meaning |
|---|---|
| `production-ready` | Default path or stable user-facing behavior with broad tests |
| `opt-in` | Must be enabled through constraints or configuration |
| `evidence-only` | Produces diagnostics, reports, hints, or warnings; does not execute bypasses |
| `initial` | Useful foundation exists, but it is not a complete product feature |
| `mocked only` | Mostly validated through mocks/fixtures, not real external targets |
| `advisory` | Can inform Strategy output, but does not own final routing decisions |

## Quick Reference

| Capability | Maturity | Enable With | Main Output |
|---|---|---|---|
| Transport diagnostics | `opt-in`, `evidence-only`, `initial` | `constraints.transport_diagnostics=true` | `recon_report.transport_diagnostics` |
| Browser interception | `opt-in`, `initial` | `constraints.intercept_browser=true` | `recon_report.browser_interception`, refreshed `recon_report.js_evidence` |
| Browser network observation | `opt-in`, `initial` | `constraints.observe_network=true` | `recon_report.network_observation`, API candidates |
| WebSocket observation | `opt-in`, `evidence-only`, `initial` | `constraints.observe_websocket=true` | `recon_report.websocket_observation`, `websocket_summary` |
| Runtime fingerprint probe | `opt-in`, `evidence-only`, `initial` | `constraints.probe_fingerprint=true` | `recon_report.browser_fingerprint_probe` |
| JS / crypto evidence | `evidence-only`, `initial` | automatic for fetched HTML; richer with interception | `recon_report.js_evidence` |
| Proxy pool / health | `opt-in`, `initial` | access config proxy pool | redacted proxy selection and health evidence |
| StrategyEvidenceReport | `advisory`, `evidence-only` | automatic inside Strategy | `crawl_strategy.strategy_evidence` |
| AntiBotReport | `advisory`, `evidence-only` | automatic inside Strategy | `crawl_strategy.anti_bot_report` |

## Example Constraints

Advanced diagnostics are usually enabled by putting constraints into the
workflow state or API request payload.

```json
{
  "constraints": {
    "transport_diagnostics": true,
    "observe_network": true,
    "intercept_browser": true,
    "observe_websocket": true,
    "probe_fingerprint": true,
    "wait_until": "networkidle",
    "render_time_ms": 1000
  }
}
```

Turn on only what you need. Some options launch a browser and are slower than
normal HTTP recon.

## Transport Diagnostics

Capability IDs: `CAP-1.2`, `CAP-6.2`

Maturity: `opt-in`, `evidence-only`, `initial`

Enable with:

```json
{
  "constraints": {
    "transport_diagnostics": true
  }
}
```

What it does:

- compares transport modes such as normal requests, `curl_cffi`, and browser
- records status-code differences
- records HTTP-version differences where available
- records response header clues, server headers, and edge/cache hints
- records challenge differences between modes
- recommends which observed transport looked best

Output:

```text
recon_report.transport_diagnostics
crawl_strategy.strategy_evidence.signals[source=transport]
```

What it does not do:

- no JA3 spoofing or TLS fingerprint control
- no ALPN/SNI tuning
- no hidden bypass
- no automatic retry storm against protected targets

## Browser Interception

Capability IDs: `CAP-4.4`, `CAP-2.1`, `CAP-6.2`

Maturity: `opt-in`, `initial`

Enable with:

```json
{
  "constraints": {
    "intercept_browser": true,
    "browser_interception": {
      "block_resource_types": ["image", "font", "media"]
    }
  }
}
```

What it does:

- launches browser-based recon when explicitly enabled
- can block selected resource types
- captures JS asset metadata and bounded previews
- captures API-like response metadata
- can inject an init script for future hook work
- feeds captured JS into `js_evidence`

Output:

```text
recon_report.browser_interception
recon_report.js_evidence
crawl_strategy.strategy_evidence.signals[source=js]
```

What it does not do:

- not enabled by default
- no request rewriting as a production feature yet
- no full JS bundle archival policy yet
- no stealth mode
- no CAPTCHA or challenge bypass

## Browser Network Observation

Capability IDs: `CAP-4.1`, `CAP-5.1`, `CAP-6.2`

Maturity: `opt-in`, `initial`

Enable with:

```json
{
  "constraints": {
    "observe_network": true,
    "wait_until": "networkidle",
    "render_time_ms": 1000
  }
}
```

What it does:

- observes browser XHR/fetch responses during page load
- redacts sensitive headers
- captures bounded JSON and POST previews
- ranks JSON/API/GraphQL candidates
- can provide safe observed API candidates for Strategy

Output:

```text
recon_report.network_observation
recon_report.api_candidates
crawl_strategy.strategy_evidence.signals[source=api]
```

What it does not do:

- no credential theft
- no login bypass
- no private API authorization bypass
- no automatic replay of unsafe or blocked API candidates

## WebSocket Observation

Capability IDs: `CAP-1.4`, `CAP-4.1`, `CAP-6.2`

Maturity: `opt-in`, `evidence-only`, `initial`

Enable with:

```json
{
  "constraints": {
    "observe_websocket": true
  }
}
```

What it does:

- listens for Playwright `page.on("websocket")` events
- records WebSocket URLs
- records sent/received frame counts
- records text/binary frame type
- stores bounded, redacted previews
- builds a compact WebSocket summary

Output:

```text
recon_report.websocket_observation
recon_report.websocket_summary
crawl_strategy.strategy_evidence.signals[source=websocket]
```

What it does not do:

- no frame replay
- no protocol reverse engineering
- no binary protocol decoding
- no WebSocket message mutation
- no login or challenge bypass

## Runtime Fingerprint Probe

Capability IDs: `CAP-4.2`, `CAP-6.2`

Maturity: `opt-in`, `evidence-only`, `initial`

Enable with:

```json
{
  "constraints": {
    "probe_fingerprint": true
  }
}
```

What it does:

- launches a browser context
- samples runtime evidence such as navigator, screen, timezone, WebGL, canvas
  metadata, and a bounded font probe
- compares some runtime evidence with configured browser context expectations
- reports risk and findings

Output:

```text
recon_report.browser_fingerprint_probe
crawl_strategy.strategy_evidence.signals[source=fingerprint]
```

What it does not do:

- no stealth or anti-fingerprint spoofing
- no fingerprint pool rotation
- no promise that a target will accept the browser profile
- no CAPTCHA or Cloudflare bypass

## JS Evidence And Crypto Evidence

Capability IDs: `CAP-2.1`, `CAP-2.2`, `CAP-5.1`, `CAP-6.2`

Maturity: `evidence-only`, `initial`

How it is enabled:

- basic JS evidence is built automatically from fetched HTML
- richer evidence is available when `intercept_browser=true` captures JS assets

What it does:

- inventories inline and captured JS assets
- extracts endpoint-looking strings
- finds GraphQL, WebSocket, sourcemap, and bundler clues
- extracts string/function/call clues with static heuristics
- detects crypto/signature clues such as hash, HMAC, WebCrypto, AES/RSA,
  timestamp, nonce, parameter sorting, and custom token names
- produces replay-risk hints for Strategy

Output:

```text
recon_report.js_evidence
crawl_strategy.js_evidence_hints
crawl_strategy.reverse_engineering_hints
crawl_strategy.api_replay_warning
crawl_strategy.strategy_evidence.signals[source=js]
crawl_strategy.strategy_evidence.signals[source=crypto]
```

What it does not do:

- no full AST parser yet
- no deobfuscation
- no source-map download by default
- no JS execution
- no key recovery
- no signature bypass
- no CAPTCHA solving

## Proxy Pool And Proxy Health

Capability IDs: `CAP-3.3`, `CAP-6.2`

Maturity: `opt-in`, `initial`

How it is enabled:

Proxy support is configured through the Access Layer. It remains disabled unless
explicitly enabled.

Conceptual config:

```json
{
  "proxy_pool": {
    "enabled": true,
    "provider": "static",
    "strategy": "round_robin",
    "endpoints": [
      {"url": "http://user:pass@proxy.example:8080", "label": "example"}
    ]
  }
}
```

What it does:

- models proxy endpoints and safe selections
- supports static pool strategies: `round_robin`, `domain_sticky`,
  `first_healthy`
- redacts proxy credentials in summaries
- can write success/failure/cooldown state to `proxy_health.sqlite3`
- can skip proxies that are in persisted cooldown
- provides a provider adapter template for future vendor integrations

Output:

```text
access_config.proxy
fetch_trace.attempts[].access_context
autonomous_crawler/storage/runtime/proxy_health.sqlite3
```

What it does not do:

- no proxy is used by default
- no bundled paid proxy provider
- no automatic anti-bot bypass
- no guarantee that a proxy will work on a target
- no cross-process production proxy platform yet

## StrategyEvidenceReport

Capability IDs: `CAP-5.1`, `CAP-6.2`

Maturity: `advisory`, `evidence-only`, `initial`

How it is enabled:

Strategy builds it automatically from `recon_report`.

What it does:

- normalizes signals from DOM, API candidates, JS evidence, crypto evidence,
  transport diagnostics, fingerprint probe, access/challenge diagnostics, and
  WebSocket summary
- ranks evidence signals
- records dominant sources
- records warnings such as challenge, transport sensitivity, runtime
  fingerprint risk, and crypto replay risk
- creates reverse-engineering hints when crypto/signature evidence is present
- can attach an advisory scorecard in current Strategy output

Output:

```text
crawl_strategy.strategy_evidence
crawl_strategy.strategy_scorecard
crawl_strategy.strategy_guardrails
crawl_strategy.strategy_scorecard_warning
crawl_strategy.reverse_engineering_hints
crawl_strategy.api_replay_warning
```

What it does not do:

- does not replace deterministic final mode selection yet
- does not execute JS or hooks
- does not bypass signatures or challenges
- does not make blocked API replay safe
- does not guarantee crawl success

## AntiBotReport

Capability IDs: `CAP-6.2`, `CAP-5.1`

Maturity: `advisory`, `evidence-only`, `initial`

How it is enabled:

Strategy builds it automatically from `recon_report`, `StrategyEvidenceReport`,
and the current strategy scorecard.

What it does:

- consolidates access diagnostics, HTTP 429, blocked API candidates, transport
  diagnostics, runtime fingerprint evidence, JS anti-bot clues, crypto/signature
  replay risk, WebSocket activity, proxy trace/health evidence, and Strategy
  warnings
- returns risk level, risk score, normalized categories, findings, recommended
  action, next steps, guardrails, and evidence sources
- redacts proxy credentials, token-like values, cookies, API keys, and sensitive
  error fragments

Output:

```text
crawl_strategy.anti_bot_report
```

What it does not do:

- no CAPTCHA solving
- no login bypass
- no automatic Cloudflare or managed-challenge bypass
- no signed API replay
- no automatic proxy enablement

## How To Read The Evidence

Use this rough interpretation:

| Evidence | Meaning |
|---|---|
| `dom_repeated_items` | DOM parsing may be enough |
| `observed_api_candidate` | A public JSON/GraphQL API may be available |
| `blocked_api_candidate` | API exists but may require authorization or backoff |
| `js_endpoint_strings` | JS contains endpoint-looking strings |
| `crypto_signature_flow` | API replay may need request signing inputs |
| `crypto_encryption_flow` | Payloads may need browser/runtime crypto context |
| `transport_sensitive` | Response changes by transport mode |
| `fingerprint_runtime_risk` | Browser runtime surface may look inconsistent |
| `challenge_detected` | Manual review or authorized session may be required |
| `websocket_activity` | Site uses WebSocket traffic worth inspecting |

## Recommended Workflow

1. Start with normal Easy Mode or deterministic crawl.
2. If output is empty or suspicious, enable one diagnostic at a time.
3. Read `recon_report` first, then `crawl_strategy`.
4. Prefer public APIs or stable DOM when evidence supports them.
5. Treat challenge, crypto, fingerprint, and proxy evidence as risk signals.
6. Escalate to manual review when the page requires login, CAPTCHA, or managed
   challenge handling.

## Related Docs

- Access Layer: [ACCESS_LAYER.md](ACCESS_LAYER.md)
- Project status: [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md)
- Capability matrix: [../plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md](../plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md)
- Team board: [../team/TEAM_BOARD.md](../team/TEAM_BOARD.md)
