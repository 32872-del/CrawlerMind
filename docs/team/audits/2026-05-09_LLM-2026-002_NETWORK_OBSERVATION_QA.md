# Audit: Browser Network Observation QA

Employee: LLM-2026-002
Date: 2026-05-09
Assignment: `2026-05-09_LLM-2026-002_NETWORK_OBSERVATION_QA`

## Scope

Reviewed `autonomous_crawler/tools/browser_network_observer.py` and
`autonomous_crawler/agents/recon.py` integration for correctness, edge cases,
and safety.

## Findings

### F-001: `_should_keep_entry` threshold is permissive (severity: low)

The keep threshold is `score >= 10` OR `resource_type in {xhr, fetch}`. A 200
OK HTML document page (score ~10 from status_ok alone) would be kept. This is
not harmful but may add noise to `entries`. The `api_candidates` threshold
(score < 20 filtered) mitigates downstream impact.

**Recommendation:** No action needed now. Consider raising threshold to 15 if
entry noise becomes a problem during real-site use.

### F-002: `_truncate_json` returns `{"preview": "..."}` wrapper for large JSON (severity: low)

When JSON exceeds the character limit, `_truncate_json` returns
`{"preview": "truncated_string"}` instead of a truncated dict. Downstream
consumers checking `isinstance(json_preview, dict)` and expecting original keys
will get unexpected structure. Current consumers (scoring, candidates) only
check `is not None`, so no breakage today.

**Recommendation:** Document this shape in the module docstring or add a
`_TRUNCATED_MARKER` sentinel. No urgency.

### F-003: `observe_browser_network` captures responses before `goto` (severity: info)

Responses registered on the page before `page.goto()` is called (e.g., from
service workers or prefetch) would be captured by the `on_response` callback.
This is correct browser observation behavior but worth noting: the callback is
registered before navigation, so early-arriving responses are not lost.

**Recommendation:** No change needed. This is desirable behavior.

### F-004: Sensitive header set is static (severity: low)

`SENSITIVE_HEADER_NAMES` is a module-level set. Adding new sensitive headers
requires code change. The current set covers the most common auth/token headers.

**Recommendation:** Adequate for MVP. Consider config-driven extension if
custom header redaction is needed later.

### F-005: No Playwright missing in Recon integration (severity: info)

When `sync_playwright is None`, `observe_browser_network` returns a failed
result. The recon integration stores this as `network_observation.status=failed`
and continues. No crash or silent skip.

**Recommendation:** No change needed. Behavior is correct.

### F-006: `recon_node` swallows observation exceptions silently (severity: low)

If `observe_browser_network` raises an unexpected exception (not caught by its
internal try/except), it would propagate to `recon_node` and crash the recon
phase. The internal try/except in `observe_browser_network` catches `Exception`,
so this is very unlikely but not impossible (e.g., `KeyboardInterrupt`).

**Recommendation:** No change needed for MVP. The broad `except Exception`
inside `observe_browser_network` is sufficient.

## Summary

| Finding | Severity | Action Needed |
|---------|----------|---------------|
| F-001 Permissive keep threshold | low | none now |
| F-002 JSON truncation wrapper shape | low | document or sentinel |
| F-003 Pre-goto response capture | info | none |
| F-004 Static sensitive header set | low | none now |
| F-005 Playwright missing graceful fail | info | none |
| F-006 Exception propagation risk | low | none now |

Highest severity: **low**. No blocking issues. Implementation is solid for MVP.

## Tests Run

```text
python -m unittest autonomous_crawler.tests.test_browser_network_observer -v
Ran 55 tests in 0.037s
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 316 tests in 29.706s
OK (skipped=3)
```
