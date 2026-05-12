# CAP-1.4 Real WebSocket Smoke — Dev Log

Date: 2026-05-12
Employee: LLM-2026-001
Assignment: CAP-1.4 Real WebSocket Smoke

## Files Changed

- `autonomous_crawler/tests/test_real_websocket_smoke.py` — new (6 tests)

## Capability IDs Covered

- CAP-1.4 WebSocket observation (real browser)
- CAP-4.1 Playwright automation (real Chromium)
- CAP-6.2 Evidence/audit (frame capture verification)

## Design

### Local Fixture Architecture

Two local servers run in daemon threads:

1. **WebSocket echo server** (websockets.asyncio.server, port 0 → random)
   - Echoes any text message back with `echo:` prefix
   - Runs in its own asyncio event loop inside a thread

2. **HTTP page server** (http.server.TCPServer, port 0 → random)
   - Serves an HTML page with JS that connects to `ws://127.0.0.1:{ws_port}`
   - Sends `hello from browser` on open
   - Sets `document.title` to echo response

### observe_websocket() Integration

The test calls the real `observe_websocket()` function (no mocking):
- Playwright launches a real Chromium browser
- Navigates to the local HTTP page
- Captures WebSocket connection and frame events
- Returns `WebSocketObservationResult` with real data

### Skip Logic

Tests skip cleanly (not fail) when:
- `websockets` package not installed → `@unittest.skipIf`
- Playwright not available → checked at module load via `sync_playwright is None`
- Chromium binary not installed → checked via `_playwright_available()` which tries to launch

## Tests (6 total)

| Test | What it proves |
| --- | --- |
| `test_observe_websocket_real_browser` | Real WS frames captured: status=ok, connection_count>=1, total_frames>=1, sent/received directions, frame content matches echo |
| `test_build_ws_summary_real` | Summary stats correct: connection_count, sent/received/text/binary frames, total_bytes, ws_urls |
| `test_to_dict_serializable` | Result.to_dict() is JSON-serializable from real data |
| `test_frame_preview_truncation_real` | Long WS messages (2000 chars) produce `...[truncated]` marker |
| `test_sensitive_preview_redaction_real` | 64-char hex token in WS frame gets `[redacted_hex]` |
| `test_page_without_websocket` | Plain HTML page yields zero connections, status=ok |

## Tests Run

```
test_real_websocket_smoke:             6 OK (real browser)
test_websocket_observer:              48 OK (mocked)
test_recon_websocket_observation:     14 OK (mocked recon)
full suite:                         1020 OK (1 pre-existing failure in test_proxy_trace, unrelated)
```

## What Changed vs Previous Mocked Tests

| Aspect | Mocked (existing) | Real smoke (new) |
| --- | --- | --- |
| Playwright | Mock object | Real Chromium browser |
| WebSocket | Mock frames | Real WS echo server |
| Page | Mock goto | Real HTTP server + HTML+JS |
| Network | None | localhost loopback |
| Frame capture | Manual callback fire | Real Playwright events |
| Truncation | Mock long string | Real 2000-char WS message |
| Redaction | Mock hex string | Real WS frame with hex token |

## Limitations

- Local fixture only — does not test against external sites
- Single-page, single-connection scenario — no multi-tab or multi-origin
- No TLS (ws:// not wss://) — smoke test scope
- No protocol-level replay or reverse engineering
