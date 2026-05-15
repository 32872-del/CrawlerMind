# Assignment: Proxy Retry Orchestration

Date: 2026-05-14

Employee: LLM-2026-002

Track: CAP-3.3 / SCRAPLING-ABSORB-1E

## Goal

Move proxy health from passive diagnostics into active runtime behavior:
`NativeFetchRuntime` should be able to retry with alternative healthy proxies
when a selected proxy fails, while recording credential-safe evidence.

This task absorbs Scrapling-style proxy rotation behavior into CLM-native code.
Do not add provider-specific vendor code unless it is behind a generic adapter
interface.

## Read First

- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `docs/team/acceptance/2026-05-14_proxy_health_fetch_diagnostics_ACCEPTED.md`
- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/tools/proxy_manager.py`
- `autonomous_crawler/tools/proxy_pool.py`
- `autonomous_crawler/tools/proxy_trace.py`
- `autonomous_crawler/storage/proxy_health.py`
- `autonomous_crawler/tests/test_proxy_health.py`
- `autonomous_crawler/tests/test_proxy_health_lifecycle.py`
- `autonomous_crawler/tests/test_native_static_runtime.py`

## Write Scope

- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/tools/proxy_manager.py`
- `autonomous_crawler/tools/proxy_pool.py`
- `autonomous_crawler/tools/proxy_trace.py`
- `autonomous_crawler/storage/proxy_health.py` only if model support is missing
- `autonomous_crawler/tests/test_native_static_runtime.py`
- `autonomous_crawler/tests/test_proxy_health_lifecycle.py`
- optional new test:
  `autonomous_crawler/tests/test_native_proxy_retry.py`
- `dev_logs/development/2026-05-14_LLM-2026-002_proxy_retry_orchestration.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-002_proxy_retry_orchestration.md`

## Required Work

1. Add an opt-in retry policy for native static fetches, configured through
   `request.proxy_config`, such as:
   - `retry_on_proxy_failure`
   - `max_proxy_attempts`
   - `health_store`
   - `pool_provider`
2. On proxy-related connection errors, record failure into health store, skip
   cooldown proxies, select the next available proxy, and retry.
3. On success, record proxy success into health store.
4. Add structured runtime events:
   - `proxy_attempt`
   - `proxy_retry`
   - `proxy_failure_recorded`
   - `proxy_success_recorded`
5. Keep all proxy URLs and errors redacted in `to_dict()` outputs.

## Acceptance

- Tests cover first proxy fail then second proxy success.
- Tests cover all proxies unavailable or cooldown.
- Tests cover max attempts.
- Tests prove credentials never leak.
- Existing native static runtime tests still pass.
- No site-specific rules and no Scrapling final-state objects.
