# 2026-05-14 - NativeFetchRuntime

Owner: LLM-2026-000

Track: SCRAPLING-ABSORB-1

## Work Completed

- Added CLM-native static fetch runtime:
  `autonomous_crawler/runtime/native_static.py`.
- Exported `NativeFetchRuntime` from `autonomous_crawler/runtime/__init__.py`.
- Added focused tests:
  `autonomous_crawler/tests/test_native_static_runtime.py`.

## Capability

`NativeFetchRuntime` is a CLM-owned `FetchRuntime` implementation. It does not
import or call `scrapling`.

Supported in the initial slice:

- default `httpx` transport
- optional `curl_cffi` transport through `RuntimeRequest.meta["transport"]`
- GET/POST/PUT/etc. via unified request method
- headers, cookies, params, JSON body, raw data
- timeout conversion
- proxy forwarding with credential-safe runtime output
- normalized `RuntimeResponse`
- `RuntimeEvent` start/complete/error events
- `RuntimeProxyTrace`
- structured failure output

## Verification

```text
python -m unittest autonomous_crawler.tests.test_native_static_runtime -v
Ran 9 tests
OK
```

## Next

- Run native-vs-transition parity once `NativeParserRuntime` and parity
  fixtures are ready.
- Add real static-site training.
- Decide when executor should prefer `NativeFetchRuntime` over transition
  adapters for static pages.

