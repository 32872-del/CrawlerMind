# SCRAPLING-HARDEN-2: Browser Profile Health Scoring

Date: 2026-05-15
Worker: LLM-2026-001
Status: COMPLETE

## Deliverables

- `autonomous_crawler/runtime/browser_pool.py` — BrowserProfileHealth, upgraded BrowserProfileRotator
- `autonomous_crawler/runtime/native_browser.py` — profile_health_update in engine_result
- `autonomous_crawler/tests/test_browser_pool.py` — 112 tests (37 new)
- `run_browser_profile_health_smoke_2026_05_15.py` — 6 smoke tests

## Key Classes

| Class | Purpose |
|---|---|
| `BrowserProfileHealth` | Mutable health tracker: success/failure/timeout/challenge/blocked counts, health_score [0.0, 1.0] |
| `BrowserProfileRotator` | Now supports `next_profile(strategy="healthiest")` and `update_health()` |

## Health Score

Formula: `success_rate - timeout_penalty - challenge_penalty - blocked_penalty`

- Timeout: 0.1 each, capped at 0.3
- Challenge: 0.15 each, capped at 0.3
- HTTP blocked: 0.05 each, capped at 0.15
- Unknown profiles (no data) → 1.0 (optimistic)

## Usage

```python
from autonomous_crawler.runtime import BrowserProfile, BrowserProfileRotator

rotator = BrowserProfileRotator([
    BrowserProfile(profile_id="desktop"),
    BrowserProfile(profile_id="mobile"),
])

# Feed back outcomes
rotator.update_health("desktop", ok=True, elapsed_seconds=1.5)
rotator.update_health("mobile", ok=False, elapsed_seconds=30.0, failure_category="navigation_timeout")

# Health-aware selection
best = rotator.next_profile(strategy="healthiest")  # picks desktop

# Read health
health = rotator.get_health("mobile")
print(health.health_score)  # ~0.0
print(health.to_dict())
```

## Verification

```bash
python -m unittest autonomous_crawler.tests.test_browser_pool autonomous_crawler.tests.test_native_browser_runtime -v  # 112 tests OK
python -m compileall autonomous_crawler run_browser_profile_health_smoke_2026_05_15.py -q  # Clean
python run_browser_profile_health_smoke_2026_05_15.py  # 6 passed
```

## Remaining Risks

1. No persistence (in-memory only)
2. No time decay (old failures permanently affect score)
3. No circuit-breaker when all profiles unhealthy
4. Penalty values are heuristic defaults

## Supervisor Acceptance

Pending.
