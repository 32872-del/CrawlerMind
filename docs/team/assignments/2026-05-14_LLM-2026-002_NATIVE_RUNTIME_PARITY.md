# Assignment: Native Runtime Parity QA

Date: 2026-05-14

Employee: LLM-2026-002

Track: SCRAPLING-ABSORB-1

## Goal

Build parity tests and fixtures that compare CLM-native runtime behavior with
the current Scrapling transition adapters. Transition adapters are benchmarks,
not the final backend.

## Read First

- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `autonomous_crawler/runtime/scrapling_static.py`
- `autonomous_crawler/runtime/scrapling_parser.py`
- `autonomous_crawler/tests/test_scrapling_static_runtime.py`
- `autonomous_crawler/tests/test_scrapling_parser_runtime.py`

## Write Scope

- `autonomous_crawler/tests/test_native_runtime_parity.py`
- `autonomous_crawler/tests/fixtures/native_runtime_parity.py`
- `dev_logs/development/2026-05-14_LLM-2026-002_native_runtime_parity.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-002_native_runtime_parity.md`

## Do Not Modify

- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/runtime/native_parser.py`
- `autonomous_crawler/agents/executor.py`

## Acceptance

- Tests skip cleanly if native modules are not yet present.
- Fixtures cover static HTML, product cards, attributes, regex, XPath, invalid
  selectors, empty HTML, and redaction.
- No real external network.

