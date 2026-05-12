# Acceptance: CAP-2.1 JS Static Analysis

Date: 2026-05-12

Assignee: `LLM-2026-002`

Supervisor: `LLM-2026-000`

Status: accepted as static-analysis foundation

## Capability IDs

- `CAP-2.1` Frontend JS reverse engineering / AST foundation
- `CAP-2.2` Hook technique preparation
- `CAP-5.1` NLP-assisted API/selector reasoning support

## Accepted Outputs

- Added `autonomous_crawler/tools/js_static_analysis.py`.
- Added `autonomous_crawler/tests/test_js_static_analysis.py`.
- Extracts quoted and template string literals without executing JS.
- Identifies endpoint-like strings and URLs.
- Extracts function declarations, function assignments, arrow-function names,
  and method-like clues.
- Identifies suspicious call clues for signature, token, encryption,
  verification, challenge, fingerprint, and anti-bot categories.
- Produces a ranked serializable report.

## Supervisor Note

This is not parser-backed AST yet. It is accepted as the `CAP-2.1`
static-analysis/string-table foundation. Future AST work should be assigned
explicitly as a deeper phase.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_js_static_analysis -v
python -m unittest discover -s autonomous_crawler/tests
```

Final result:

```text
Ran 758 tests in 53.272s
OK (skipped=4)
```

## Remaining Gaps

- No AST parser.
- No deobfuscation.
- No source-map download.
- No JS execution.
