# Assignment: Async Fetch Pool And Transport Backpressure

Date: 2026-05-14

Employee: `LLM-2026-002`

Priority: P0

Track: `SCRAPLING-ABSORB-1F / CAP-1.3 / CAP-3.3`

## Mission

Absorb Scrapling-style async/static fetch capability into CLM-native transport.
The goal is a first async fetch pool that can support long-running crawls with
per-domain concurrency, retry/backoff evidence, and proxy-health integration.

## Ownership

Primary files:

- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/runtime/models.py`
- `autonomous_crawler/tools/rate_limit_policy.py`
- `autonomous_crawler/tests/test_native_static_runtime.py`
- `autonomous_crawler/tests/test_native_proxy_retry.py`
- new `autonomous_crawler/runtime/native_async.py` if a separate module is
  cleaner

Avoid touching browser runtime or parser internals.

## Requirements

1. Add an async-capable native fetch path or a clearly separated
   `NativeAsyncFetchRuntime` behind the existing runtime models/protocol style.
2. Support bounded per-domain concurrency and structured backpressure evidence.
3. Preserve current proxy retry and proxy-health behavior.
4. Return normalized `RuntimeResponse` objects and safe serialized evidence.
5. Unit tests must be deterministic and should not depend on public network.
6. Update dev log and handoff.

## Acceptance Checks

Run:

```text
python -m unittest autonomous_crawler.tests.test_native_static_runtime autonomous_crawler.tests.test_native_proxy_retry -v
python -m unittest discover -s autonomous_crawler/tests
python -m compileall autonomous_crawler
```

Report:

- whether async runtime is separate or integrated
- concurrency/backpressure event schema
- proxy retry compatibility evidence
- known remaining long-run performance limits
