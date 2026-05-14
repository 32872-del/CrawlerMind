# Handoff: Scrapling Browser + Session + Proxy Runtime Design

**Date**: 2026-05-14
**Worker**: LLM-2026-002
**Status**: COMPLETE

## What Was Done

Designed and implemented the Scrapling browser runtime adapter and proxy mapping layer, connecting Scrapling's DynamicFetcher/StealthyFetcher/Session/ProxyRotator to CLM's runtime protocol. This is Phase 2 infrastructure — pure conversion functions and models, no executor wiring.

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `autonomous_crawler/runtime/scrapling_browser.py` | **NEW** | Browser runtime adapter + proxy conversion |
| `autonomous_crawler/runtime/__init__.py` | **MODIFIED** | Added ScraplingBrowserRuntime export |
| `autonomous_crawler/tests/test_scrapling_browser_runtime_contract.py` | **NEW** | 57 browser runtime tests |
| `autonomous_crawler/tests/test_scrapling_proxy_runtime_contract.py` | **NEW** | 47 proxy runtime tests |
| `docs/memory/handoffs/2026-05-14_LLM-2026-002_scrapling_browser_session_proxy_runtime.md` | **NEW** | This handoff |

## Proposed Runtime Contract

### BrowserRuntime Protocol Implementation

`ScraplingBrowserRuntime` implements the existing `BrowserRuntime` protocol:

```python
class ScraplingBrowserRuntime:
    name: str = "scrapling_browser"
    def render(self, request: RuntimeRequest) -> RuntimeResponse: ...
```

Dispatch logic:
- `mode == "dynamic"` → `DynamicFetcher.fetch()`
- `mode == "protected"` → `StealthyFetcher.fetch()`
- `user_data_dir` or `max_pages` set → `DynamicSession` / `StealthySession` context manager

### ScraplingBrowserConfig

Frozen dataclass resolving all CLM RuntimeRequest fields into Scrapling fetcher kwargs:

```python
@dataclass(frozen=True)
class ScraplingBrowserConfig:
    mode: str = "dynamic"           # "dynamic" | "protected"
    headless: bool = True
    real_chrome: bool = False
    cdp_url: str = ""
    wait_selector: str = ""
    wait_selector_state: str = "attached"
    network_idle: bool = False
    timeout_ms: int = 30000
    capture_xhr: str = ""
    blocked_domains: frozenset[str]
    block_ads: bool = False
    # Protected-mode only (StealthyFetcher)
    solve_cloudflare: bool = True
    block_webrtc: bool = True
    hide_canvas: bool = True
    allow_webgl: bool = True
    # Session continuity
    user_data_dir: str = ""
    max_pages: int = 0
```

Two output methods:
- `to_fetch_kwargs()` → kwargs for `DynamicFetcher.fetch()` / `StealthyFetcher.fetch()`
- `to_session_kwargs()` → kwargs for `DynamicSession()` / `StealthySession()` constructor

## Fields Mapping Table

| CLM RuntimeRequest field | Scrapling parameter | Notes |
|---|---|---|
| `mode` == "dynamic" | `DynamicFetcher` | Default |
| `mode` == "protected" | `StealthyFetcher` | Anti-bot mode |
| `browser_config.headless` | `headless` | Default True |
| `browser_config.real_chrome` | `real_chrome` | Uses installed Chrome |
| `browser_config.cdp_url` | `cdp_url` | CDP connection string |
| `wait_selector` | `wait_selector` | CSS selector to wait for |
| `wait_until` == "networkidle" | `network_idle=True` | Mapped from wait_until |
| `browser_config.wait_selector_state` | `wait_selector_state` | attached/detached/visible/hidden |
| `capture_xhr` | `capture_xhr` | Regex pattern for XHR capture |
| `browser_config.blocked_domains` | `blocked_domains` | Set of domains to block |
| `browser_config.block_ads` | `block_ads` | Block ~3500 ad domains |
| `browser_config.disable_resources` | `disable_resources` | Drop fonts/images/media |
| `browser_config.locale` | `locale` | Browser locale |
| `browser_config.timezone_id` | `timezone_id` | Browser timezone |
| `browser_config.useragent` | `useragent` | Custom UA string |
| `browser_config.extra_headers` | `extra_headers` | Additional headers |
| `browser_config.dns_over_https` | `dns_over_https` | DNS leak prevention |
| `browser_config.retries` | `retries` | Retry count (default 3) |
| `browser_config.solve_cloudflare` | `solve_cloudflare` | Protected mode only |
| `browser_config.block_webrtc` | `block_webrtc` | Protected mode only |
| `browser_config.hide_canvas` | `hide_canvas` | Protected mode only |
| `browser_config.allow_webgl` | `allow_webgl` | Protected mode only |
| `browser_config.user_data_dir` | `user_data_dir` | Session persistence |
| `browser_config.max_pages` | `max_pages` | Rotating tab pool |
| `proxy_config.proxy` | `proxy` | String or dict format |
| `proxy_config.proxy_rotator` | `proxy_rotator` | ProxyRotator instance |
| `session_profile.cookies` | `cookies` | Per-request cookies |
| `session_profile.headers` | `extra_headers` | Merged with browser_config |

## Proxy Mapping

### CLM ProxyConfig → Scrapling proxy format

| CLM format | Scrapling format | Notes |
|---|---|---|
| `"http://user:pass@host:port"` (string) | `{"server": "http://host:port", "username": "user", "password": "pass"}` (dict) | Credentials isolated in dict |
| `ProxyPoolProvider` with round_robin | `ProxyRotator(proxies, strategy=cyclic_rotation)` | CLM round_robin ≈ Scrapling cyclic |
| `ProxyPoolProvider` with random | `ProxyRotator(proxies, strategy=random_strategy)` | Custom strategy function |
| Per-domain sticky | `ProxyRotator` with custom strategy or direct proxy kwarg | Domain matching stays in CLM |

### Credential Safety

- `clm_proxy_to_scrapling()` splits URL into `{"server": ..., "username": ..., "password": ...}` — server field never contains credentials
- `clm_proxy_dict_for_browser()` always returns dict form for Playwright browser context
- `RuntimeProxyTrace` applies `redact_proxy_url()` → `***:***@host`
- Browser proxy constraint: Scrapling creates separate context per proxy when using ProxyRotator

### Key Functions

```python
clm_proxy_to_scrapling(proxy_url: str) -> str | dict[str, str]
clm_proxy_dict_for_browser(proxy_url: str) -> dict[str, str]
build_proxy_rotator(proxy_urls: list[str], strategy: str = "cyclic") -> ProxyRotator | None
select_scrapling_proxy(proxy_url, *, proxy_rotator=None) -> (proxy_arg, trace_info)
resolve_browser_config(request: RuntimeRequest) -> ScraplingBrowserConfig
```

## Test Results

```
Ran 104 tests in 0.004s — OK
compileall — OK
```

### Browser Runtime Tests (57)

- ResolveBrowserConfigDefaultsTests (7): default mode, headless, real_chrome, network_idle, timeout, wait_state, retries
- ResolveBrowserConfigDynamicTests (20): all dynamic mode field mappings
- ResolveBrowserConfigProtectedTests (8): stealth fields, kwargs inclusion/exclusion
- SessionConfigTests (5): user_data_dir, max_pages, session kwargs
- FetchKwargsMappingTests (7): kwargs structure, optional key omission
- BrowserRuntimeProtocolTests (3): protocol conformance
- BrowserRuntimeRenderWithoutScraplingTests (1): graceful degradation
- BrowserRuntimeResponseShapeTests (3): response structure, XHR, failure
- SelectScraplingProxyTests (3): disabled/direct/rotator
- BuildProxyRotatorTests (3): empty/cyclic/random
- InvalidModeFallbackTests (1): unknown mode → dynamic

### Proxy Runtime Tests (47)

- ClmProxyToScraplingTests (9): empty, simple, credentials, https, socks5, no-port, username-only, special chars
- ProxyFormatForBrowserTests (3): server key, credential separation, no plaintext in server
- ProxyRotatorConstructionTests (6): empty, single, multiple, cyclic, random, dict conversion
- SelectScraplingProxyLogicTests (6): disabled, direct, rotator override, auth, trace fields
- RuntimeProxyTraceIntegrationTests (4): disabled/direct/rotator trace, credential safety
- BlockStatusCodesTests (5): known block codes verification
- ProxyStrategyMappingTests (2): cyclic→cyclic, random→random
- CredentialSafetyTests (4): no plaintext in any output path
- ProxyRotatorIsProxyErrorTests (1): Scrapling error pattern detection

## Risks and Integration Blockers

1. **Scrapling dependency not installed in CI**: Tests gracefully skip when Scrapling is absent (`_HAS_SCRAPLING = False`). Real integration requires `pip install scrapling`.

2. **Playwright browser binary**: DynamicFetcher/StealthyFetcher require Playwright + browser binaries. Protected mode needs Camoufox. These are deployment-time dependencies, not code blockers.

3. **Session context manager lifecycle**: `DynamicSession` / `StealthySession` use context managers (`with` blocks). The adapter wraps fetch in a `with` block, which means the browser closes after each `render()` call unless `max_pages` or `user_data_dir` triggers session mode. For true multi-request session reuse, the caller (executor) would need to hold the session open.

4. **ProxyRotator + browser context isolation**: Scrapling creates separate browser contexts per proxy in ProxyRotator mode. This means cookies/state don't share across proxies. This is correct behavior but differs from HTTP-mode proxy rotation.

5. **page_action / page_setup not exposed**: Scrapling supports `page_action` (post-navigation automation) and `page_setup` (pre-navigation setup) as callable parameters. The current RuntimeRequest model doesn't carry callables — these would need to be injected via `browser_config` or a new field if automation is needed.

6. **Executor not wired**: This design is pure protocol + conversion. Integration into `executor_node()` is the next step — replacing the current `fetch_rendered_html()` call with `ScraplingBrowserRuntime.render()`.
