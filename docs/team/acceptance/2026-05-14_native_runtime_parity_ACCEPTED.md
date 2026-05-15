# Acceptance: Native Runtime Parity QA

Date: 2026-05-14

Employee: LLM-2026-002

Assignment:
`docs/team/assignments/2026-05-14_LLM-2026-002_NATIVE_RUNTIME_PARITY.md`

Track: SCRAPLING-ABSORB-1

## Result

Accepted.

## Accepted Deliverables

- `autonomous_crawler/tests/fixtures/__init__.py`
- `autonomous_crawler/tests/fixtures/native_runtime_parity.py`
- `autonomous_crawler/tests/test_native_runtime_parity.py`
- `dev_logs/development/2026-05-14_LLM-2026-002_native_runtime_parity.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-002_native_runtime_parity.md`

## Capability Accepted

The parity suite compares CLM-native runtimes against Scrapling transition
adapters on identical local fixtures. This gives CLM a controlled way to absorb
Scrapling behavior while keeping the final backend native.

Accepted coverage:

- parser parity for CSS, XPath, regex, text, attributes, first-only selectors,
  missing selectors, mixed selector batches, malformed HTML, and error output
- static fetch contract parity for 200/403 responses, connection failures,
  POST JSON, proxy forwarding, credential redaction, runtime events, and proxy
  trace population
- output-shape and protocol-conformance checks for native runtime objects

## Verification

Focused:

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

- Extend parity to native browser runtime once implemented.
- Add curl_cffi-specific transport parity tests.
- Add performance and memory comparison fixtures for parser/fetch paths.

