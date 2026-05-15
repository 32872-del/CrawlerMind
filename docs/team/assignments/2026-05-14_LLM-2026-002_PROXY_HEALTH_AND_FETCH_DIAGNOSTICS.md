# Assignment: Proxy Health and Fetch Diagnostics

Date: 2026-05-14

Employee: LLM-2026-002

Track: CAP-3.3 / SCRAPLING-ABSORB-1C

## Goal

Build CLM-native proxy health scoring, transport diagnostics, and static
fetch reuse evidence so CLM absorbs the useful Scrapling proxy/transport
behavior into its own backend.

Focus on retry/backoff, health scoring, redacted traces, and stress-oriented
verification. Do not move site rules into runtime code.

## Read First

- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/tools/proxy_manager.py`
- `autonomous_crawler/tools/proxy_trace.py`
- `autonomous_crawler/tests/test_transport_diagnostics.py`
- `autonomous_crawler/tests/test_native_static_runtime.py`
- `autonomous_crawler/tests/test_proxy_health_store.py` if it exists, or the
  nearest proxy-health tests
- `autonomous_crawler/tests/test_error_paths.py`

## Write Scope

- `autonomous_crawler/tools/proxy_manager.py`
- `autonomous_crawler/storage/proxy_health_store.py` or an equivalent CLM-owned
  storage/helper module
- `autonomous_crawler/runtime/native_static.py` if proxy/transport evidence
  needs to be surfaced
- `autonomous_crawler/tests/test_native_static_runtime.py`
- `autonomous_crawler/tests/test_transport_diagnostics.py`
- `autonomous_crawler/tests/test_proxy_health_store.py`
- `dev_logs/development/2026-05-14_LLM-2026-002_proxy_health_and_fetch_diagnostics.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-002_proxy_health_and_fetch_diagnostics.md`

## Do Not Modify

- `autonomous_crawler/runtime/native_browser.py`
- browser/session pool files owned by LLM-2026-001
- planner/strategy logic
- real-site selector profiles or site-specific crawl rules

## Acceptance

- Proxy selection can record health, cooldown, and failure evidence in a
  credential-safe way.
- Static runtime surfaces transport/proxy trace evidence cleanly.
- Tests cover good proxy, failed proxy, cooldown, and trace-redaction cases.
- The implementation stays CLM-native and does not depend on Scrapling runtime
  objects as final state.

