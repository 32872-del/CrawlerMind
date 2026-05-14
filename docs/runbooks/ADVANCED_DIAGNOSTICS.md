# Advanced Diagnostics Runbook

This document explains CLM's advanced diagnostics for open-source users,
new team members, and enterprise evaluators.

These capabilities explain why a crawl is hard and provide the evidence needed
to choose a stronger runtime, profile, proxy/session configuration, API replay
path, browser path, or future reverse-engineering workflow.

Usage policy, customer authorization language, and commercial deployment rules
belong in `docs/governance/CRAWLING_GOVERNANCE.md`. This runbook focuses on
capability shape, inputs, outputs, and maturity.

## Maturity Labels

| Label | Meaning |
|---|---|
| `production-ready` | Default path or stable user-facing behavior with broad tests |
| `opt-in` | Must be enabled through constraints or configuration |
| `evidence-only` | Produces diagnostics, reports, hints, or warnings; does not execute runtime actions by itself |
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

Growth areas:

- JA3 evidence and TLS fingerprint control
- ALPN/SNI tuning
- impersonation-profile selection
- adaptive retry/backoff based on transport outcome

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

Growth areas:

- request rewriting as a production feature
- full JS bundle archival policy
- stronger browser runtime profiles
- integration with the Scrapling protected browser runtime

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

Growth areas:

- richer API authorization profile support
- safer blocked-candidate classification
- stronger replay validation before Strategy uses a candidate
- pagination and cursor inference across more real sites

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

Growth areas:

- frame replay in controlled training fixtures
- protocol reverse-engineering reports
- binary protocol decoding
- WebSocket message mutation for authorized test harnesses

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

Growth areas:

- browser fingerprint pool rotation
- runtime/config fingerprint consistency scoring
- stronger browser identity profiles
- real-site calibration against accepted and rejected profiles

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

Growth areas:

- full AST parser
- deobfuscation workflow
- source-map discovery and download
- sandboxed JS execution
- signature-function localization
- hook-assisted runtime tracing
- optional CAPTCHA/OCR provider integrations

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

Growth areas:

- bundled provider adapter examples
- production proxy quality scoring
- cross-process proxy health sharing
- BatchRunner proxy metrics
- real provider smoke tests

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

Growth areas:

- allow scorecard to influence final mode in well-tested cases
- execute JS hooks through a sandboxed reverse-engineering path
- connect signature evidence to request-building profiles
- promote blocked API candidates only after replay validation
- calibrate success prediction against training data

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

Growth areas:

- plug AntiBotReport into CLI/API summaries
- calibrate risk scores on real training cases
- connect report categories to stronger runtime profiles
- integrate optional OCR/CAPTCHA/provider tracks when those modules land

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
6. When evidence points to a harder target, decide whether to use a stronger
   runtime profile, a site profile, a reverse-engineering task, or a governance
   review.

## Related Docs

- Access Layer: [ACCESS_LAYER.md](ACCESS_LAYER.md)
- Project status: [../../PROJECT_STATUS.md](../../PROJECT_STATUS.md)
- Capability matrix: [../plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md](../plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md)
- Team board: [../team/TEAM_BOARD.md](../team/TEAM_BOARD.md)
