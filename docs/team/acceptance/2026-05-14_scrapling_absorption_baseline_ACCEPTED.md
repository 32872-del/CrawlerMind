# Acceptance: Scrapling Absorption Baseline Closeout

Date: 2026-05-14

Employee: `LLM-2026-000`

Assignment: `SCRAPLING-ABSORB baseline`

Status: accepted

## Verdict

Accepted as a native capability baseline. CLM no longer depends on Scrapling as
the final product backend for the major crawler patterns we wanted to absorb:
static fetch, parser, adaptive selectors, browser/session/profile, proxy retry,
async fetch, spider/checkpoint/link/robots/site profile, and visual/evidence
reporting now all have CLM-owned modules or accepted first-class integration
points.

This does not mean the product is finished. It means the Scrapling-inspired
backend foundation is now inside CLM, and the next work should be hardening,
large-run training, and user-facing simplification rather than further
wrapping.

## Accepted Evidence

- Static/runtime: `NativeFetchRuntime`, `NativeParserRuntime`, executor routing,
  parity tests, adaptive parser, and selector memory.
- Browser/runtime: `NativeBrowserRuntime`, session lifecycle, storage-state
  export, profile rotation, pool leasing, failure classification, and dynamic
  comparison smokes.
- Proxy/transport: proxy health, redacted trace, retry orchestration, transport
  diagnostics, and async fetch metrics.
- Spider/long-run: request/result models, `CheckpointStore`,
  `SpiderRuntimeProcessor`, link discovery, robots/sitemap integration,
  pause/resume smoke, site profile, and profile ecommerce runner.
- Evidence layer: Strategy evidence and AntiBotReport consume DOM/API/JS/
  crypto/transport/fingerprint/proxy/WebSocket/visual signals.

## Follow-Up

- Prove the baseline with 10k/30k native long-run tests.
- Run a real dynamic/ecommerce training batch on profile-driven spiders.
- Add async client pooling and browser profile health scoring.
- Move the user experience toward a simpler CLI/API/UI without changing the
  native backend direction.

