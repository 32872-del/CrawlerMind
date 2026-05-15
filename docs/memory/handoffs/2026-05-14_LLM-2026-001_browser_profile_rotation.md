# SCRAPLING-ABSORB-2H: Native Browser Profile Pool And Real Dynamic Training

Date: 2026-05-14
Worker: LLM-2026-001
Status: COMPLETE

## Deliverables

- Updated `autonomous_crawler/runtime/browser_pool.py` — BrowserProfile, BrowserProfileRotator
- Updated `autonomous_crawler/runtime/native_browser.py` — rotator integration, profile evidence
- Updated `autonomous_crawler/tests/test_browser_pool.py` — 77 tests (23 new)
- `run_profile_rotation_smoke_2026_05_14.py` — real browser profile rotation smoke

## Key Classes

| Class | Purpose |
|---|---|
| `BrowserProfile` | Frozen profile identity: user_agent, viewport, locale, timezone, color_scheme, protected_mode, etc. |
| `BrowserProfileRotator` | Round-robin rotation across profiles, integrates with pool via fingerprint |

## Usage

```python
from autonomous_crawler.runtime import (
    NativeBrowserRuntime, BrowserPoolManager, BrowserPoolConfig,
    BrowserProfile, BrowserProfileRotator,
)

profiles = [
    BrowserProfile(profile_id="desktop", user_agent="Chrome/120", viewport="1920x1080"),
    BrowserProfile(profile_id="mobile", user_agent="Safari/17", viewport="375x812"),
]
pool = BrowserPoolManager(BrowserPoolConfig(keepalive_on_release=True))
rotator = BrowserProfileRotator(profiles)
runtime = NativeBrowserRuntime(pool=pool, rotator=rotator)

request = RuntimeRequest.from_dict({"url": "https://example.com"})
response = runtime.render(request)
# response.engine_result["profile_id"] == "desktop"
# response.engine_result["profile"]["viewport"] == "1920x1080"

response2 = runtime.render(request)
# response2.engine_result["profile_id"] == "mobile"

runtime.close()
```

## Profile Evidence in engine_result

- `engine_result["profile"]` — credential-safe profile dict
- `engine_result["profile_id"]` — selected profile ID
- `engine_result["rotator"]` — rotator state (profile_count, current_index, profiles)

## Verification

```bash
python -m unittest autonomous_crawler.tests.test_browser_pool -v  # 77 tests OK
python run_profile_rotation_smoke_2026_05_14.py                    # [PASS]
```

## Supervisor Acceptance

Pending.
