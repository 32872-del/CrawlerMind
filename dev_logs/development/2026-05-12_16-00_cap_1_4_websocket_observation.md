# 2026-05-12 16:00 - CAP-1.4 WebSocket Observation MVP

## Goal

Add a deterministic WebSocket observation foundation. No external network;
pure data model and mocked Playwright event handling so later real-browser
training can capture WS URLs and frame metadata safely.

## Capability IDs

- CAP-1.4: WebSocket observation (connection/frame capture, preview truncation, redaction)
- CAP-4.1: Playwright automation (page.on("websocket", ...) event handling)
- CAP-2.1: JS/API endpoint discovery support (WS URL extraction for inventory)

## Changes

| File | Change |
|---|---|
| `autonomous_crawler/tools/websocket_observer.py` | Created. WebSocket observation data models and Playwright integration. |
| `autonomous_crawler/tests/test_websocket_observer.py` | Created. 48 tests. |

## Implementation

### Data Models

- `WebSocketFrame`: direction (sent/received), data_type (text/binary), preview
  (truncated), byte_length, timestamp_ms
- `WebSocketConnection`: url, is_alive, frame_count, frames, error
- `WebSocketObservationResult`: page_url, status, error, connections, total_frames,
  errors

### Frame Payload Helpers

- `normalize_frame_payload(payload, max_preview)`: converts str/bytes to
  (preview, data_type, byte_length). Handles UTF-8 decode of bytes, truncation.
- `truncate_preview(text, max_chars)`: truncates with "...[truncated]" marker.
- `redact_sensitive_preview(preview)`: redacts hex tokens (32+ chars), Bearer
  tokens, and api_key/token/secret/password/session_id values.

### WebSocket Collector

- `_WebSocketCollector`: mutable state class that accumulates frames across
  multiple WebSocket connections. Has `on_websocket(ws)` callback that registers
  frame/close event handlers. Supports max_frames, max_connections, max_frame_preview,
  and redaction.

### Main Entry Point

- `observe_websocket(page_url, ...)`: navigates to page, listens for WebSocket
  events via `_WebSocketCollector`, returns `WebSocketObservationResult`. Uses
  `browser.new_page()` (not `context.new_page()`).

### Summary Helper

- `build_ws_summary(result)`: compact summary dict with connection_count, ws_urls,
  total_frames, sent/received/text/binary counts, total_bytes, error_count.

## Key Design Decisions

1. **No external network**: all tests use mocked Playwright events.
2. **Bounded previews**: frame payloads truncated to DEFAULT_MAX_FRAME_PREVIEW (500)
   chars. Never leaks full payloads.
3. **Sensitive redaction**: hex tokens, Bearer tokens, and key=value patterns
   with long values are redacted.
4. **Shared-state collector**: `_WebSocketCollector` accumulates frames across
   connections during page load, avoiding closure capture issues.
5. **browser.new_page()**: Playwright uses `browser.new_page()` directly, not
   through a context. Mock setup must match this.

## Tests

48 tests covering:
- normalize_frame_payload (text, bytes, UTF-8, truncation, empty, fallback, JSON)
- truncate_preview (short, exact, long, empty, zero max)
- redact_sensitive_preview (hex, Bearer, api_key, session_id, normal, empty)
- WebSocketFrame (text, binary, frozen)
- WebSocketConnection (basic, error)
- WebSocketObservationResult (to_dict, empty)
- _WebSocketCollector (text frames, binary, multiple connections, close event,
  max frames, max connections, redaction on/off, truncation, empty, bind error)
- observe_websocket (no ws, with frames, not installed, navigation error,
  multiple connections, to_dict serialization)
- build_ws_summary (basic, empty, multiple connections, error count)

## Verification

```text
python -m unittest autonomous_crawler.tests.test_websocket_observer -v
Ran 48 tests
OK

python -m unittest discover -s autonomous_crawler/tests
Ran 888 tests (skipped=4)
OK
```

## How Output Feeds Recon Integration

1. **WS URLs**: `WebSocketObservationResult.connections[].url` identifies live
   WebSocket endpoints. These can be added to the JS Asset Inventory's
   websocket_urls for cross-referencing.
2. **Frame previews**: text frames may contain JSON subscription confirmations,
   data payloads, or protocol messages that reveal data formats.
3. **Direction tracking**: sent frames show client→server messages (subscribe,
   auth), received frames show server→client data (ticks, updates).
4. **Redaction**: sensitive tokens are automatically redacted before persistence.
5. **Scoring integration**: a future `score_ws_connection()` could rank
   connections by frame count, data type, and keyword hits in previews.

## Remaining Gaps

- No real browser integration (mocked only)
- No frame replay or protocol parsing
- No binary frame decoding (protobuf, msgpack, etc.)
- No connection lifecycle tracking (open/close timing)
- No integration into Recon pipeline yet
- No WebSocket URL correlation with JS Asset Inventory
