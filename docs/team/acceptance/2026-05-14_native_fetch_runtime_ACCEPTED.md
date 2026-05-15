# Acceptance: NativeFetchRuntime

Date: 2026-05-14

Employee: LLM-2026-000

Track: SCRAPLING-ABSORB-1

## Result

Accepted as supervisor mainline work.

## Accepted Deliverables

- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/runtime/__init__.py`
- `autonomous_crawler/tests/test_native_static_runtime.py`
- `dev_logs/development/2026-05-14_native_fetch_runtime.md`

## Capability Accepted

`NativeFetchRuntime` is a CLM-owned static fetch runtime. It does not import or
call Scrapling. The transition Scrapling adapter can now be used as an oracle,
while this native runtime becomes the target backend.

Accepted behavior:

- default `httpx` transport
- optional `curl_cffi` transport through request metadata
- headers, cookies, params, JSON body, raw data, and HTTP method forwarding
- timeout conversion
- proxy forwarding with credential-safe response/event output
- normalized `RuntimeResponse`
- `RuntimeEvent` start/complete/error events
- `RuntimeProxyTrace`
- structured failure response on network exceptions

## Verification

Focused:

```text
python -m unittest autonomous_crawler.tests.test_native_static_runtime -v
Ran 9 tests
OK
```

Related parity:

```text
python -m unittest autonomous_crawler.tests.test_native_runtime_parity -v
Ran 66 tests
OK (skipped=1)
```

Full:

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 1396 tests in 67.967s
OK (skipped=5)
```

Compile:

```text
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py clm.py
OK
```

## Follow-up

- Add executor routing for `engine="native"` or an equivalent explicit runtime
  flag.
- Run real static-site training through native and transition runtimes.
- Extend curl_cffi transport parity coverage beyond the basic unit path.

