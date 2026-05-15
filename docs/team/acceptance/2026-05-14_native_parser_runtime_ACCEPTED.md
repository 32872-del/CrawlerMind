# Acceptance: NativeParserRuntime

Date: 2026-05-14

Employee: LLM-2026-001

Assignment:
`docs/team/assignments/2026-05-14_LLM-2026-001_NATIVE_PARSER_RUNTIME.md`

Track: SCRAPLING-ABSORB-1

## Result

Accepted.

## Accepted Deliverables

- `autonomous_crawler/runtime/native_parser.py`
- `autonomous_crawler/runtime/__init__.py`
- `autonomous_crawler/tests/test_native_parser_runtime.py`
- `dev_logs/development/2026-05-14_LLM-2026-001_native_parser_runtime.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-001_native_parser_runtime.md`

## Capability Accepted

`NativeParserRuntime` is a CLM-owned parser runtime that satisfies the
`ParserRuntime` protocol without importing Scrapling.

Accepted behavior:

- CSS extraction through cssselect-to-XPath translation
- XPath extraction, including attribute-string returns
- text selector extraction with direct text matching aligned to current
  Scrapling adapter behavior
- regex extraction on full document text
- attribute extraction
- many/first-only selector behavior
- malformed and empty HTML handling
- selector-error containment through `RuntimeSelectorResult.error`
- protocol conformance and serializable output shape

## Verification

Focused:

```text
python -m unittest autonomous_crawler.tests.test_native_parser_runtime -v
Ran 48 tests
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

- Add executor-level native parser use so parity is tested inside the workflow,
  not only at runtime-unit level.
- Add more edge fixtures for mixed nested text behavior.
- Clean up the lxml HTMLParser deprecation warning when practical.

