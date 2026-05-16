# BROWSER-HARDEN-2: Profile Health Persistence / Decay Design Slice

Date: 2026-05-15
Worker: LLM-2026-001

## Summary

Advanced `BrowserProfileHealth` from pure cumulative scoring to a windowed/decay
model where old failures naturally age out. Added `health_summary()` for run
reports and a `BrowserProfileHealthStore` persistence adapter (JSON files).

## Changes

| File | Change |
|---|---|
| `autonomous_crawler/runtime/browser_pool.py` | Added `WindowedHealthRecord`, windowed scoring in `BrowserProfileHealth`, `health_summary()`, `to_persistable_dict()`/`from_persistable_dict()`, `BrowserProfileHealthStore`, `BrowserProfileRotator.health_summaries()` |
| `autonomous_crawler/runtime/__init__.py` | Added `BrowserProfileHealthStore` export |
| `autonomous_crawler/tests/test_browser_pool.py` | 17 new tests (WindowedHealthScoring: 6, HealthSummary: 3, RotatorHealthSummary: 2, HealthStore: 6) |

## Design

### Windowed Scoring

`BrowserProfileHealth` now tracks a `deque[WindowedHealthRecord]` alongside
cumulative counters. Each record has a timestamp. `health_score` computes from
records within `window_seconds` (default 300s):

- Records older than `window_seconds` are excluded from scoring
- Cumulative counters (`total_requests`, `success_count`, etc.) remain unchanged
  for backward compatibility
- If no windowed records exist, falls back to cumulative scoring

This means old failures decay away — a profile that had 10 timeouts 10 minutes
ago but 5 recent successes will score 1.0.

### Health Summary

`health_summary()` returns a compact dict for run reports:
```python
{
    "profile_id": "p1",
    "health_score": 0.85,
    "cumulative": {"total_requests": 20, "success_rate": 0.75, "avg_elapsed_seconds": 3.2},
    "windowed": {"window_seconds": 300, "request_count": 5, "success_count": 4, "failure_breakdown": {"navigation_timeout": 1}},
    "last_failure_category": "navigation_timeout",
}
```

### Persistence

`BrowserProfileHealthStore` saves/loads health data as JSON files:
- `save(health)` / `load(profile_id)` for individual profiles
- `save_all()` / `load_all()` for batch operations
- `to_persistable_dict()` / `from_persistable_dict()` for serialization
- Windowed records are included in persistence

### Rotator Integration

`BrowserProfileRotator.health_summaries()` returns summaries for all tracked
profiles. Added to `to_safe_dict()` output.

## Test Results

```
python -m unittest autonomous_crawler.tests.test_browser_pool -v
# 117 tests OK (17 new)

python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime autonomous_crawler.tests.test_browser_scenario_training -v
# 192 tests OK

python -m compileall autonomous_crawler run_browser_scenario_training_2026_05_15.py -q
# Clean
```

## Remaining Risks

1. **Window sensitivity**: Default 300s window may be too short for long-running
   crawls or too long for rapid rotation. Consider making it configurable per
   use case.
2. **Deque maxlen**: Capped at 500 records per profile. For very high-throughput
   scenarios, this may lose older records within the window.
3. **Persistence is JSON-based**: Fine for small deployments. For production with
   many profiles, SQLite would be more efficient.
4. **No automatic persistence**: Health data is in-memory until explicitly saved.
   Callers must call `store.save()` or `store.save_all()`.
