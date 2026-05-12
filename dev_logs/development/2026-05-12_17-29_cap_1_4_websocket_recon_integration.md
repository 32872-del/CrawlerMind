# CAP-1.4 WebSocket Recon Opt-in Integration — Dev Log

Date: 2026-05-12
Employee: LLM-2026-001
Assignment: CAP-1.4 WebSocket Recon Opt-in Integration

## Files Changed

- `autonomous_crawler/agents/recon.py` — added import, `_should_observe_websocket()`, observation block
- `autonomous_crawler/tests/test_recon_websocket_observation.py` — new test file (14 tests)

## Capability IDs Covered

- CAP-1.4 WebSocket observation
- CAP-4.1 Playwright automation (observation entry point)
- CAP-2.1 JS/API endpoint discovery support (WS URLs as evidence)
- CAP-5.1 Strategy evidence input (websocket_summary in recon_report)

## Changes to recon.py

### New import
```python
from ..tools.websocket_observer import build_ws_summary, observe_websocket
```

### New function: `_should_observe_websocket()`
Follows the exact pattern of `_should_observe_network`, `_should_intercept_browser`, etc.:
- Returns False if `constraints.observe_websocket` is falsy
- Returns False if target_url is not http/https
- Returns True only when both conditions met

### New observation block in `recon_node()`
Added after the fingerprint probe block:
1. Calls `observe_websocket(target_url)` (no extra kwargs — uses defaults)
2. Stores `ws_result.to_dict()` in `recon_report["websocket_observation"]`
3. Stores `build_ws_summary(ws_result)` in `recon_report["websocket_summary"]`
4. Appends message: `[Recon] WebSocket observation status={status}, connections={N}, frames={N}`

### Default path behavior
The default path (no constraints or empty constraints) does NOT call `observe_websocket`.
Verified by test: `test_websocket_not_observed_by_default`.

## Tests (14 total)

| Class | Count | Coverage |
| --- | --- | --- |
| ShouldObserveWebsocketTests | 7 | default false, constraint false, true+https, true+http, non-http, None constraints, missing key |
| ReconWebsocketIntegrationTests | 7 | enabled, default off, constraint false, non-http, failed result, multiple connections, other constraints preserved |

## Tests Run

```
test_websocket_observer:              48 OK
test_recon_websocket_observation:     14 OK
full suite:                          929 OK (4 skipped)
```

## How Results Flow to Strategy

1. `recon_report["websocket_summary"]` contains: page_url, status, connection_count, ws_urls, total_frames, sent_frames, received_frames, text_frames, binary_frames, total_bytes, error_count
2. Strategy can read `recon_report.get("websocket_summary")` to incorporate WS evidence
3. WS URLs from `ws_urls` list could be added as API candidates or evidence hints
4. Frame patterns (text vs binary ratio, sent vs received) could inform Strategy mode selection
5. Currently Strategy does not consume websocket_summary — this is the next integration point
