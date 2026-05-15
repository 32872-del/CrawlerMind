# SCRAPLING-ABSORB-2H: Native Browser Profile Pool And Real Dynamic Training

Date: 2026-05-14
Worker: LLM-2026-001

## Objective

Build the next browser-profile layer on top of the accepted NativeBrowserRuntime
and BrowserPoolManager. Add configurable profile rotation and prove it with real
dynamic training evidence.

## What Was Done

### Modified Files

1. **`autonomous_crawler/runtime/browser_pool.py`**
   - Added `BrowserProfile` dataclass — configurable identity: profile_id, user_agent, viewport, locale, timezone, color_scheme, storage_state_mode, block_resource_types, protected_mode, headless, channel, proxy_url
   - Added `BrowserProfile.from_dict()` — create from dict or passthrough
   - Added `BrowserProfile.to_context_options()` — BrowserContextConfig-compatible options
   - Added `BrowserProfile.to_launch_options()` — Playwright launch options
   - Added `BrowserProfile.to_safe_dict()` — credential-safe evidence (redacts proxy, truncates UA)
   - Added `BrowserProfileRotator` — round-robin profile rotation
   - Added `BrowserProfileRotator.next_profile()` / `current_profile()` / `to_safe_dict()`

2. **`autonomous_crawler/runtime/native_browser.py`**
   - Added `rotator: BrowserProfileRotator | None = None` parameter to `__init__`
   - In `render()`, selects profile via rotator and applies to request via `_apply_profile_to_request()`
   - Profile evidence in `engine_result`: `profile`, `profile_id`, `rotator`
   - Profile ID in `browser_render_start` event data
   - Added `_apply_profile_to_request()` helper — merges profile options into request

3. **`autonomous_crawler/runtime/__init__.py`**
   - Added exports: `BrowserProfile`, `BrowserProfileRotator`

4. **`autonomous_crawler/tests/test_browser_pool.py`**
   - Added `BrowserProfileTests` (12 tests): from_dict, defaults, context_options, launch_options, safe_dict, frozen
   - Added `BrowserProfileRotatorTests` (5 tests): round-robin, from_dict_list, empty, current, safe_dict
   - Added `NativeBrowserRuntimeProfileTests` (6 tests): rotator selection, cycling, evidence, no-rotator, protected_mode, user_agent

### Created Files

1. **`run_profile_rotation_smoke_2026_05_14.py`** — real browser smoke
   - 3 profiles: desktop-chrome, mobile-safari, desktop-firefox
   - Verifies rotation cycles and wraps
   - Verifies profile evidence in engine_result
   - Verifies pool integration (3 active leases for 3 different fingerprints)
   - Skips cleanly when Playwright not installed

## Key Design Decisions

1. **Profile as frozen dataclass**: BrowserProfile is immutable, making it safe to share across threads and easy to reason about.

2. **Rotator is optional**: NativeBrowserRuntime works with or without a rotator. Without rotator, no profile evidence is emitted (backward compatible).

3. **Auto pool_id from profile_id**: When a profile is applied, its profile_id becomes the pool_id, so different profiles get different pool contexts automatically.

4. **Protected mode via profile**: Setting `protected_mode=True` on a profile automatically sets mode="protected" on the request, applying anti-detection flags and init scripts.

5. **Credential-safe evidence**: `to_safe_dict()` redacts proxy URLs, truncates long user agents, and never exposes raw credentials.

## Tests Run

```
python -m unittest autonomous_crawler.tests.test_browser_pool -v
# 77 tests OK

python run_profile_rotation_smoke_2026_05_14.py
# [PASS] Profile rotation smoke test passed
```

## Profile Evidence Shape

```json
{
  "profile": {
    "profile_id": "desktop-chrome",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
    "viewport": "1920x1080",
    "locale": "en-US",
    "timezone": "America/New_York",
    "color_scheme": "light",
    "storage_state_mode": "ephemeral",
    "protected_mode": false,
    "headless": true,
    "channel": "",
    "has_proxy": false,
    "block_resource_types": []
  },
  "profile_id": "desktop-chrome",
  "rotator": {
    "profile_count": 3,
    "current_index": 1,
    "profiles": [...]
  }
}
```

## Known Gaps Before Production

1. **No storage state persistence**: Profiles with `storage_state_mode="persistent"` don't yet export/import cookies across sessions. Need to wire `export_storage_state()`.

2. **No proxy rotation**: Proxy URL is per-profile but not yet integrated with proxy pool rotation.

3. **No fingerprint diversity metrics**: No way to measure how diverse the profile pool is (UA overlap, viewport distribution).

4. **No profile health tracking**: If a profile consistently hits challenges, there's no automatic deprioritization.

## What Was NOT Changed

- No site-specific rules added
- No Scrapling import
- No changes to proxy runtime, spider runner, or JS analysis modules
- Backward compatible: runtime without rotator behaves exactly as before
