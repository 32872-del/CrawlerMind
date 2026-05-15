# Acceptance: Proxy Retry Orchestration

Date: 2026-05-14

Employee: `LLM-2026-002`

Assignment: `CAP-3.3 / SCRAPLING-ABSORB-1E`

Status: accepted

## Verdict

Accepted. Proxy health is now active runtime behavior, not only passive
diagnostics. `NativeFetchRuntime` can retry retryable proxy failures with
alternative healthy proxies while preserving credential-safe evidence.

## Accepted Evidence

- Runtime proxy retry is opt-in through `RuntimeRequest.proxy_config`.
- Retry attempts emit structured events: `proxy_attempt`,
  `proxy_failure_recorded`, `proxy_retry`, and `proxy_success_recorded`.
- Connection-level failures are retryable; application errors do not trigger
  proxy cycling.
- `ProxyHealthStore` and pool provider hooks receive success/failure updates.
- Plaintext proxy credentials are redacted from events, errors, traces, and
  serialized runtime responses.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_proxy_retry autonomous_crawler.tests.test_proxy_health_lifecycle -v
python -m unittest discover -s autonomous_crawler/tests
```

Latest supervisor verification:

```text
Ran 1670 tests in 81.984s
OK (skipped=5)
```

## Follow-Up

- Carry proxy attempt metrics into `SpiderRunSummary`.
- Add a real provider adapter smoke using a local/fake provider first.
- Add long-run proxy quality scoring by domain.
