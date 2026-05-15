# Assignment: Native Parser Runtime

Date: 2026-05-14

Employee: LLM-2026-001

Track: SCRAPLING-ABSORB-1

## Goal

Implement CLM-native parser behavior that absorbs the useful Scrapling
`Selector`/`Selectors` behavior without treating `scrapling` as the final
backend.

## Read First

- `docs/plans/2026-05-14_SCRAPLING_ABSORPTION_RECORD.md`
- `autonomous_crawler/runtime/protocols.py`
- `autonomous_crawler/runtime/models.py`
- `autonomous_crawler/runtime/scrapling_parser.py`
- `autonomous_crawler/tests/test_scrapling_parser_runtime.py`

## Write Scope

- `autonomous_crawler/runtime/native_parser.py`
- `autonomous_crawler/runtime/__init__.py`
- `autonomous_crawler/tests/test_native_parser_runtime.py`
- `dev_logs/development/2026-05-14_LLM-2026-001_native_parser_runtime.md`
- `docs/memory/handoffs/2026-05-14_LLM-2026-001_native_parser_runtime.md`

## Do Not Modify

- `autonomous_crawler/runtime/native_static.py`
- `autonomous_crawler/agents/executor.py`
- browser/proxy runtime files

## Acceptance

- `NativeParserRuntime` satisfies `ParserRuntime`.
- It does not import or call `scrapling`.
- It supports CSS, XPath, text, regex, attributes, `many`, invalid selectors,
  empty HTML, malformed HTML, and credential-safe errors.
- Focused tests pass.

