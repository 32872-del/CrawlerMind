# Handoff - LLM-2026-000 - CAP-1.2 Transport Diagnostics

Date: 2026-05-12

## Summary

Implemented the first CAP-1.2 diagnostic capability: compare allowed transport
modes and report whether access behavior depends on transport choice.

## Key Files

```text
autonomous_crawler/tools/transport_diagnostics.py
autonomous_crawler/tests/test_transport_diagnostics.py
autonomous_crawler/tools/fetch_policy.py
autonomous_crawler/agents/recon.py
```

## Behavior

- Compares requests/curl_cffi/browser attempts.
- Detects status, challenge, quality-score, HTTP-version, and error
  differences.
- Redacts sensitive response headers.
- Recon can opt in with `constraints.transport_diagnostics=true`.

## Current Limit

No direct JA3/ALPN/SNI capture yet. This is transport evidence and strategy
diagnosis, not low-level fingerprint control.

## Tests

Focused tests passed. Full suite still needs to be run after this handoff.
