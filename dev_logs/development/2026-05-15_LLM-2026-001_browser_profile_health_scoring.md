# SCRAPLING-HARDEN-2: Browser Profile Health Scoring

Date: 2026-05-15
Worker: LLM-2026-001

## Objective

Upgrade BrowserProfile/BrowserProfileRotator/NativeBrowserRuntime from pure round-robin
rotation to health-aware profile selection with structured scoring.

## What Was Done

### Modified Files

1. **`autonomous_crawler/runtime/browser_pool.py`**
   - Added `BrowserProfileHealth` dataclass — mutable health tracker per profile
   - Tracks: total_requests, success_count, failure_count, timeout_count, challenge_count, http_blocked_count
   - Computes: success_rate, avg_elapsed_seconds, health_score (0.0–1.0)
   - Health score formula: `success_rate - timeout_penalty(0.1 each, cap 0.3) - challenge_penalty(0.15 each, cap 0.3) - blocked_penalty(0.05 each, cap 0.15)`
   - Upgraded `BrowserProfileRotator`:
     - `next_profile(strategy="round_robin"|"healthiest")` — default round_robin, healthiest picks best score
     - `update_health(profile_id, ok, elapsed_seconds, failure_category)` — feed back outcomes
     - `get_health(profile_id)` — read health (creates on demand)
     - `to_safe_dict()` now includes `health` dict

2. **`autonomous_crawler/runtime/native_browser.py`**
   - Added `import time`
   - Added `start_time = time.time()` at top of `render()`
   - On success path: calls `rotator.update_health()` and includes `profile_health_update` in engine_result
   - On error path: calls `rotator.update_health()` with failure_category and includes in engine_result
   - Emits `profile_health_update` RuntimeEvent on both paths
   - `_browser_failure_response()` accepts optional `profile_health_update`

3. **`autonomous_crawler/runtime/__init__.py`**
   - Added export: `BrowserProfileHealth`

### Created Files

1. **`autonomous_crawler/tests/test_browser_pool.py`** — 37 new tests
   - `BrowserProfileHealthTests` (10 tests): defaults, record success/failure/timeout/challenge, penalty caps, avg_elapsed, to_dict, mixed outcomes
   - `BrowserProfileRotatorHealthTests` (7 tests): update_health tracking, healthiest strategy, all-healthy picks first, recovery, to_safe_dict includes health, on-demand creation, default strategy
   - `NativeBrowserRuntimeProfileHealthTests` (6 tests): health on success, health on failure, accumulation across requests, no rotator → no health, runtime event emission, rotator to_safe_dict

2. **`run_browser_profile_health_smoke_2026_05_15.py`** — 6 smoke tests (all mocked)
   - Profile health scoring
   - Healthiest rotator strategy
   - Recovery after improvement
   - Runtime health update on success
   - Runtime health on failure
   - No rotator → no health update

## Key Design Decisions

1. **Health score is [0.0, 1.0]**: 1.0 = perfectly healthy, 0.0 = completely broken. Unknown profiles start at 1.0 (optimistic).

2. **Penalties are capped**: Timeout penalty max 0.3, challenge penalty max 0.3, blocked penalty max 0.15. This prevents a profile from being permanently blacklisted.

3. **Strategy is a parameter**: `next_profile(strategy=...)` keeps backward compatibility. Default is "round_robin" (same behavior as before).

4. **Health is mutable**: BrowserProfileHealth is a regular dataclass (not frozen) because it tracks live metrics.

5. **Health update in engine_result**: Every render response now includes `profile_health_update` (or None if no rotator), making it easy for callers to observe health changes.

## Test Results

```
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime -v
# 112 tests OK

python -m compileall autonomous_crawler run_browser_profile_health_smoke_2026_05_15.py -q
# Clean

python run_browser_profile_health_smoke_2026_05_15.py
# 6 passed, 0 failed
```

## Remaining Risks

1. **No persistence**: Health data is in-memory only. Restarting the process resets all health scores. For long-running services, consider persisting to disk or database.

2. **No decay**: Old failures permanently affect the score. A profile that had a timeout 1000 requests ago still has the same penalty as one that had it 2 requests ago. Consider time-decayed or windowed scoring.

3. **No cross-profile dependency**: If all profiles are unhealthy, the rotator still picks the "least bad" one. No circuit-breaker or backoff mechanism.

4. **Penalty values are heuristic**: The 0.1/0.15/0.05 penalty values and 0.3/0.3/0.15 caps are reasonable defaults but not tuned to real-world data.

5. **No profile health in pool events**: Pool events (pool_acquire, pool_reuse, etc.) don't include health scores. Adding them would improve observability.
