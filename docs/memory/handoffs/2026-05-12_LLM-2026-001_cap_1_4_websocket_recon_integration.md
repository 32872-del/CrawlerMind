# Handoff: CAP-1.4 WebSocket Recon Opt-in Integration

Employee: LLM-2026-001
Date: 2026-05-12
Status: complete

## Summary

Integrated `websocket_observer.py` into Recon as an opt-in evidence channel.
Default OFF — only runs when `constraints.observe_websocket=true` AND URL is
http/https. Results stored in `recon_report.websocket_observation` and
`recon_report.websocket_summary`. 14 new tests, all deterministic.

## Deliverables

- `autonomous_crawler/agents/recon.py` — added `_should_observe_websocket()` + observation block
- `autonomous_crawler/tests/test_recon_websocket_observation.py` — 14 tests
- `dev_logs/development/2026-05-12_17-29_cap_1_4_websocket_recon_integration.md`

## Key Design Decisions

- Follows exact pattern of `_should_observe_network`, `_should_intercept_browser`, etc.
- `observe_websocket()` called with defaults (no extra kwargs) — uses Playwright defaults
- `build_ws_summary()` produces compact summary for Strategy consumption
- Failed observations still stored (status="failed") so downstream can handle gracefully
- No frame replay, no protocol parsing, no bypass — observation only

## Opt-in Verification

- `_should_observe_websocket({}, url)` → False (default)
- `_should_observe_websocket({"constraints": {"observe_websocket": True}}, "https://...")` → True
- `_should_observe_websocket({"constraints": {"observe_websocket": True}}, "ftp://...")` → False
- Full recon_node with empty constraints → `observe_websocket` never called

## recon_report Keys Added

| Key | Content |
| --- | --- |
| `websocket_observation` | Full `WebSocketObservationResult.to_dict()` |
| `websocket_summary` | Compact dict: connection_count, ws_urls, total_frames, sent/received/text/binary counts, total_bytes |

## Next Steps: Strategy Integration

Strategy can now consume `recon_report.get("websocket_summary")`:
- `ws_urls` → potential API candidate URLs
- `connection_count > 0` → site uses WebSocket (may need browser mode)
- Frame patterns → inform api_intercept feasibility
- Currently Strategy does not read websocket_summary — next integration point is `_attach_ws_evidence_hints()` in strategy.py
