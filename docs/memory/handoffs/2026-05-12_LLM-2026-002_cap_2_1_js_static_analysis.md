# Handoff: CAP-2.1 JS Static Analysis: String Table MVP

Employee: LLM-2026-002
Date: 2026-05-12
Assignment: `2026-05-12_LLM-2026-002_CAP-2.1_JS_AST_STRING_TABLE.md`

## What Was Done

Extended the JS Asset Inventory with a deeper static analysis layer: string
literal extraction (quoted, template, URL), function declaration/assignment/
method detection, suspicious call identification (including object-method
patterns like `hcaptcha.getResponse()`), and a ranked report with scoring.

## Files Changed

| File | Change |
|---|---|
| `autonomous_crawler/tools/js_static_analysis.py` | Created. String table, function/call clues, ranked report. |
| `autonomous_crawler/tests/test_js_static_analysis.py` | Created. 54 tests. |
| `dev_logs/development/2026-05-12_15-00_cap_2_1_js_static_analysis.md` | Dev log. |
| `docs/memory/handoffs/2026-05-12_LLM-2026-002_cap_2_1_js_static_analysis.md` | This handoff. |

## Capability IDs Covered

- CAP-2.1: JS AST 逆向 foundation (string table, function extraction, suspicious call detection)
- CAP-2.2: Hook technique preparation (suspicious keyword catalog for call interception)
- CAP-5.1: NLP-assisted API reasoning (endpoint/URL string ranking)

## Key API

```python
from autonomous_crawler.tools.js_static_analysis import (
    extract_strings,            # JS text → list[StringEntry]
    extract_endpoint_strings,   # JS text → list[str]
    extract_functions,          # JS text → list[FunctionClue]
    extract_suspicious_calls,   # JS text → list[CallClue]
    score_static_analysis,      # entries, functions, calls → (score, reasons)
    analyze_js_static,          # JS text → StaticAnalysisReport
)
```

## How Output Feeds Future Work

- **AST work**: function names and suspicious calls identify signature/token
  logic locations for deeper AST parsing.
- **Hook work**: suspicious call expressions are CDP hook targets.
- **Endpoint discovery**: URL/API strings complement the JS Asset Inventory's
  endpoint candidates.
- **String table**: large string tables hint at obfuscated or config-heavy code
  that may need deobfuscation.
- **Scoring**: ranked reports prioritize which JS files to analyze first.

## Remaining Gaps

- No AST parsing (regex-only, may miss complex patterns)
- No minification/deobfuscation
- No control-flow or data-flow analysis
- No Wasm detection (CAP-2.3)
- External script content not fetched (only inline analyzed)
- No site-specific rules
