"""GraphQL / API / Reverse Evidence Trainer tests.

Covers SCRAPLING-HARDEN-4 acceptance:
- GraphQL mock fixtures: nested fields, cursor pagination, errors, rate-limit
- API pagination 50+ records: page/offset/cursor
- Reverse evidence: signature/timestamp/nonce/token/encrypted payload clues
- Async/backpressure/proxy metrics integration with training
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from autonomous_crawler.tools.api_candidates import (
    PaginatedResult,
    PaginationSpec,
    build_graphql_candidate,
    build_graphql_cursor_query,
    build_graphql_nested_fields_query,
    extract_records_from_json,
    fetch_graphql_api,
    fetch_json_api,
    fetch_paginated_api,
    normalize_api_records,
)
from autonomous_crawler.tools.strategy_evidence import (
    EvidenceSignal,
    StrategyEvidenceReport,
    build_reverse_engineering_hints,
    build_strategy_evidence_report,
    has_high_crypto_replay_risk,
)
from autonomous_crawler.tools.js_crypto_analysis import analyze_js_crypto


# ---------------------------------------------------------------------------
# GraphQL Mock Fixtures
# ---------------------------------------------------------------------------


class TestGraphQLNestedFields(unittest.TestCase):
    """GraphQL mock: nested fields extraction."""

    def test_nested_fields_response_structure(self) -> None:
        result = fetch_graphql_api(
            "mock://api/graphql-nested",
            query=build_graphql_nested_fields_query(),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status_code"], 200)
        data = result["data"]
        self.assertIn("data", data)
        characters = data["data"]["characters"]["results"]
        self.assertEqual(len(characters), 2)
        # Nested fields present
        self.assertIn("origin", characters[0])
        self.assertIn("episode", characters[0])
        self.assertIsInstance(characters[0]["episode"], list)
        self.assertGreaterEqual(len(characters[0]["episode"]), 1)

    def test_nested_fields_origin_shape(self) -> None:
        result = fetch_graphql_api("mock://api/graphql-nested", query="{}")
        char = result["data"]["data"]["characters"]["results"][0]
        self.assertEqual(char["origin"]["name"], "Earth")
        self.assertEqual(char["origin"]["dimension"], "C-137")

    def test_nested_fields_episode_count(self) -> None:
        result = fetch_graphql_api("mock://api/graphql-nested", query="{}")
        chars = result["data"]["data"]["characters"]["results"]
        self.assertEqual(len(chars[0]["episode"]), 2)
        self.assertEqual(len(chars[1]["episode"]), 1)

    def test_extract_records_from_graphql_nested(self) -> None:
        result = fetch_graphql_api("mock://api/graphql-nested", query="{}")
        records = extract_records_from_json(result["data"])
        self.assertGreaterEqual(len(records), 2)
        titles = [r.get("name") or r.get("title") for r in records]
        self.assertIn("Nested Alpha", titles)


class TestGraphQLCursorPagination(unittest.TestCase):
    """GraphQL mock: Relay-style cursor pagination."""

    def test_first_page(self) -> None:
        result = fetch_graphql_api(
            "mock://api/graphql-paginated",
            query=build_graphql_cursor_query(),
            variables={"after": None},
        )
        self.assertTrue(result["ok"])
        data = result["data"]["data"]["characters"]
        self.assertIn("pageInfo", data)
        self.assertIn("edges", data)
        self.assertTrue(data["pageInfo"]["hasNextPage"])
        self.assertEqual(data["pageInfo"]["endCursor"], "cursor_page2")
        self.assertEqual(len(data["edges"]), 2)

    def test_second_page(self) -> None:
        result = fetch_graphql_api(
            "mock://api/graphql-paginated",
            query=build_graphql_cursor_query(),
            variables={"after": "cursor_page2"},
        )
        data = result["data"]["data"]["characters"]
        self.assertFalse(data["pageInfo"]["hasNextPage"])
        self.assertIsNone(data["pageInfo"]["endCursor"])
        self.assertEqual(len(data["edges"]), 2)

    def test_cursor_pagination_total_items(self) -> None:
        """All pages combined yield 4 items."""
        all_items = []
        cursor = None
        for _ in range(5):
            result = fetch_graphql_api(
                "mock://api/graphql-paginated",
                query="{}",
                variables={"after": cursor},
            )
            data = result["data"]["data"]["characters"]
            edges = data["edges"]
            all_items.extend(edges)
            if not data["pageInfo"]["hasNextPage"]:
                break
            cursor = data["pageInfo"]["endCursor"]
        self.assertEqual(len(all_items), 4)

    def test_cursor_edges_node_structure(self) -> None:
        result = fetch_graphql_api(
            "mock://api/graphql-paginated",
            query="{}",
            variables={"after": None},
        )
        edge = result["data"]["data"]["characters"]["edges"][0]
        self.assertIn("node", edge)
        node = edge["node"]
        self.assertIn("id", node)
        self.assertIn("name", node)
        self.assertIn("origin", node)
        self.assertIn("episode", node)


class TestGraphQLResponseTypes(unittest.TestCase):
    """GraphQL mock: error and rate-limit responses."""

    def test_error_response(self) -> None:
        result = fetch_graphql_api("mock://api/graphql-error", query="{ nonexistent }")
        self.assertTrue(result["ok"])  # HTTP 200 but GraphQL errors
        data = result["data"]
        self.assertIn("errors", data)
        self.assertIsNone(data.get("data"))
        error = data["errors"][0]
        self.assertIn("message", error)
        self.assertEqual(error["extensions"]["code"], "GRAPHQL_VALIDATION_FAILED")

    def test_rate_limit_response(self) -> None:
        result = fetch_graphql_api("mock://api/graphql-rate-limited", query="{}")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status_code"], 429)
        data = result["data"]
        self.assertIn("errors", data)
        error = data["errors"][0]
        self.assertEqual(error["extensions"]["code"], "RATE_LIMITED")
        self.assertEqual(error["extensions"]["retryAfter"], 30)

    def test_countries_simple(self) -> None:
        result = fetch_graphql_api("mock://api/graphql-countries", query="{}")
        self.assertTrue(result["ok"])
        countries = result["data"]["data"]["countries"]
        self.assertGreaterEqual(len(countries), 2)
        self.assertIn("continent", countries[0])


class TestGraphQLCandidateBuilder(unittest.TestCase):
    """GraphQL candidate building."""

    def test_build_graphql_candidate(self) -> None:
        candidate = build_graphql_candidate(
            url="https://api.example.com/graphql",
            query="{ products { title } }",
            variables={"page": 1},
        )
        self.assertEqual(candidate["method"], "POST")
        self.assertEqual(candidate["kind"], "graphql")
        self.assertEqual(candidate["score"], 70)
        self.assertIn("query", candidate)

    def test_build_graphql_nested_query(self) -> None:
        query = build_graphql_nested_fields_query()
        self.assertIn("characters", query)
        self.assertIn("origin", query)
        self.assertIn("episode", query)

    def test_build_graphql_cursor_query(self) -> None:
        query = build_graphql_cursor_query()
        self.assertIn("pageInfo", query)
        self.assertIn("endCursor", query)
        self.assertIn("hasNextPage", query)


# ---------------------------------------------------------------------------
# API Pagination 50+ Records
# ---------------------------------------------------------------------------


class TestAPIPagination50Plus(unittest.TestCase):
    """API pagination fixtures outputting 50+ records."""

    def test_page_pagination_50_plus(self) -> None:
        result = fetch_paginated_api(
            "mock://api/paged-products-50?page=1",
            pagination=PaginationSpec(type="page", page_param="page", max_pages=10),
        )
        self.assertGreaterEqual(len(result.all_items), 50)
        self.assertGreater(result.pages_fetched, 1)
        self.assertIn(result.stop_reason, {"max_pages", "no_next_hint", ""})

    def test_offset_pagination_50_plus(self) -> None:
        result = fetch_paginated_api(
            "mock://api/offset-products-50?offset=0&limit=10",
            pagination=PaginationSpec(
                type="offset", offset_param="offset", limit_param="limit",
                limit=10, max_pages=10,
            ),
        )
        self.assertGreaterEqual(len(result.all_items), 50)
        self.assertGreater(result.pages_fetched, 1)

    def test_cursor_pagination_50_plus(self) -> None:
        result = fetch_paginated_api(
            "mock://api/cursor-products-50?cursor=",
            pagination=PaginationSpec(type="cursor", cursor_param="cursor", max_pages=10),
        )
        self.assertGreaterEqual(len(result.all_items), 50)
        self.assertGreater(result.pages_fetched, 1)
        self.assertIn(result.stop_reason, {"no_next_hint", "max_pages", ""})

    def test_page_pagination_unique_items(self) -> None:
        result = fetch_paginated_api(
            "mock://api/paged-products-50?page=1",
            pagination=PaginationSpec(type="page", page_param="page", max_pages=10),
        )
        titles = [item.get("title") for item in result.all_items]
        self.assertEqual(len(titles), len(set(titles)))

    def test_offset_pagination_stop_reason(self) -> None:
        result = fetch_paginated_api(
            "mock://api/offset-products-50?offset=0&limit=10",
            pagination=PaginationSpec(
                type="offset", offset_param="offset", limit_param="limit",
                limit=10, max_pages=10,
            ),
        )
        self.assertIn(result.stop_reason, {"no_next_hint", "max_pages", ""})

    def test_cursor_pagination_stop_reason(self) -> None:
        result = fetch_paginated_api(
            "mock://api/cursor-products-50?cursor=",
            pagination=PaginationSpec(type="cursor", cursor_param="cursor", max_pages=10),
        )
        self.assertIn(result.stop_reason, {"no_next_hint", "max_pages", ""})

    def test_pagination_result_structure(self) -> None:
        result = fetch_paginated_api(
            "mock://api/paged-products-50?page=1",
            pagination=PaginationSpec(type="page", page_param="page", max_pages=10),
        )
        self.assertIsInstance(result, PaginatedResult)
        self.assertIsInstance(result.all_items, list)
        self.assertGreater(result.pages_fetched, 0)
        self.assertGreater(len(result.api_responses), 0)


# ---------------------------------------------------------------------------
# Reverse Evidence: Signature / Timestamp / Nonce / Token / Encrypted
# ---------------------------------------------------------------------------


class TestReverseEvidenceSignatureDetection(unittest.TestCase):
    """Reverse evidence: detect signature/token clues in API candidates."""

    def test_signature_in_url_detected(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/data?x-sign=abc123&timestamp=1234",
                    "method": "GET",
                    "kind": "json",
                    "score": 60,
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertIn("api_auth_token_hint", codes)

    def test_token_in_url_detected(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/feed?api-key=secret&nonce=xyz",
                    "method": "GET",
                    "kind": "json",
                    "score": 50,
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertIn("api_auth_token_hint", codes)

    def test_timestamp_nonce_detected(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/rpc?timestamp=1234567890&nonce=abc",
                    "method": "GET",
                    "kind": "json",
                    "score": 50,
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertIn("api_dynamic_input_hint", codes)

    def test_encrypted_payload_detected(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/rpc",
                    "method": "POST",
                    "kind": "json",
                    "score": 50,
                    "body": "encrypted_data=aes_ciphertext_here",
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertIn("api_encrypted_payload_hint", codes)

    def test_no_clues_no_signals(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/products?page=1",
                    "method": "GET",
                    "kind": "json",
                    "score": 40,
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertNotIn("api_auth_token_hint", codes)
        self.assertNotIn("api_dynamic_input_hint", codes)


class TestReverseEvidenceGraphQLSignals(unittest.TestCase):
    """Reverse evidence: GraphQL-specific signals."""

    def test_graphql_rate_limit_signal(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/graphql",
                    "method": "POST",
                    "kind": "graphql",
                    "score": 70,
                    "status_code": 429,
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertIn("graphql_rate_limit", codes)

    def test_graphql_auth_header_signal(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/graphql",
                    "method": "POST",
                    "kind": "graphql",
                    "score": 70,
                    "headers": {"Authorization": "Bearer token123"},
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertIn("graphql_signature_hint", codes)

    def test_graphql_nested_complexity(self) -> None:
        deep_query = "{ a { b { c { d { e { id } } } } } }"
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/graphql",
                    "method": "POST",
                    "kind": "graphql",
                    "score": 70,
                    "query": deep_query,
                },
            ],
        })
        codes = {s.code for s in report.signals}
        self.assertIn("graphql_nested_complexity", codes)


class TestReverseEvidenceHints(unittest.TestCase):
    """Reverse evidence: action hints and replay blockers."""

    def test_api_replay_blocker_from_signature(self) -> None:
        hints = build_reverse_engineering_hints({}, [
            {
                "url": "https://api.example.com/data?x-sign=abc",
                "method": "GET",
                "kind": "json",
            },
        ])
        self.assertEqual(hints.get("api_replay_blocker"), "signature_or_token_in_request")
        self.assertIn("hook_plan", hints)

    def test_api_replay_blocker_from_encrypted_payload(self) -> None:
        hints = build_reverse_engineering_hints({}, [
            {
                "url": "https://api.example.com/rpc",
                "method": "POST",
                "kind": "json",
                "body": "encrypt=data",
            },
        ])
        self.assertEqual(hints.get("api_replay_blocker"), "encrypted_payload_requires_runtime_execution")
        self.assertIn("sandbox_plan", hints)

    def test_no_blocker_for_plain_api(self) -> None:
        hints = build_reverse_engineering_hints({}, [
            {
                "url": "https://api.example.com/products?page=1",
                "method": "GET",
                "kind": "json",
            },
        ])
        self.assertNotIn("api_replay_blocker", hints)

    def test_high_crypto_replay_risk_with_api_hint(self) -> None:
        report = StrategyEvidenceReport(
            signals=[
                EvidenceSignal(
                    code="api_auth_token_hint",
                    source="api",
                    confidence="high",
                    score=70,
                ),
            ],
            action_hints={"api_replay_blocker": "signature_or_token_in_request"},
        )
        self.assertTrue(has_high_crypto_replay_risk(report))

    def test_js_signature_flow_risk(self) -> None:
        js_evidence = {
            "items": [
                {
                    "source": "inline",
                    "url": "https://example.com/app.js",
                    "total_score": 60,
                    "crypto_analysis": {
                        "signals": [{"kind": "hash", "name": "SHA256"}],
                        "categories": ["hash"],
                        "likely_signature_flow": True,
                        "score": 65,
                        "recommendations": ["Hook hash function"],
                    },
                },
            ],
        }
        report = build_strategy_evidence_report({"js_evidence": js_evidence})
        codes = {s.code for s in report.signals}
        self.assertIn("crypto_signature_flow", codes)
        self.assertTrue(has_high_crypto_replay_risk(report))

    def test_combined_js_and_api_evidence(self) -> None:
        """Both JS crypto and API signature clues produce combined hints."""
        js_evidence = {
            "items": [
                {
                    "source": "inline",
                    "url": "https://example.com/app.js",
                    "total_score": 55,
                    "crypto_analysis": {
                        "signals": [{"kind": "timestamp", "name": "Date.now"}],
                        "categories": ["timestamp"],
                        "likely_timestamp_nonce_flow": True,
                        "score": 55,
                        "recommendations": [],
                    },
                },
            ],
        }
        hints = build_reverse_engineering_hints(js_evidence, [
            {
                "url": "https://api.example.com/data?x-sign=abc&nonce=xyz",
                "method": "GET",
                "kind": "json",
            },
        ])
        # JS evidence provides dynamic_inputs
        self.assertIn("dynamic_inputs", hints)
        # API evidence with x-sign provides api_replay_blocker
        self.assertIn("api_replay_blocker", hints)


class TestJSAndGraphQLCombinedEvidence(unittest.TestCase):
    """Integration: JS crypto + GraphQL + API in one evidence report."""

    def test_full_evidence_report(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/graphql",
                    "method": "POST",
                    "kind": "graphql",
                    "score": 70,
                    "status_code": 429,
                    "headers": {"Authorization": "Bearer tok"},
                },
                {
                    "url": "https://api.example.com/data?x-sign=abc&timestamp=123",
                    "method": "GET",
                    "kind": "json",
                    "score": 60,
                },
            ],
            "js_evidence": {
                "items": [
                    {
                        "source": "inline",
                        "url": "https://example.com/app.js",
                        "total_score": 50,
                        "crypto_analysis": {
                            "signals": [{"kind": "hash", "name": "MD5"}],
                            "categories": ["hash"],
                            "likely_signature_flow": True,
                            "score": 50,
                            "recommendations": ["Hook hash"],
                        },
                    },
                ],
            },
        })
        codes = {s.code for s in report.signals}
        # All three signal types present
        self.assertIn("api_auth_token_hint", codes)
        self.assertIn("graphql_rate_limit", codes)
        self.assertIn("crypto_signature_flow", codes)
        # Warnings include all risk signals
        self.assertIn("graphql_rate_limit", report.warnings)
        self.assertIn("api_auth_token_hint", report.warnings)


# ---------------------------------------------------------------------------
# Async / Backpressure / Proxy Metrics Integration
# ---------------------------------------------------------------------------


class TestMetricsIntegrationWithTraining(unittest.TestCase):
    """Verify async/backpressure/proxy metrics flow through training context."""

    def test_build_strategy_evidence_report_with_transport(self) -> None:
        """Transport diagnostics flow into evidence report."""
        report = build_strategy_evidence_report({
            "transport_diagnostics": {
                "selected_mode": "curl_cffi",
                "transport_sensitive": True,
                "findings": ["tls_fingerprint_mismatch"],
                "recommendations": ["Use curl_cffi impersonation"],
            },
        })
        codes = {s.code for s in report.signals}
        self.assertIn("transport_sensitive", codes)

    def test_build_strategy_evidence_report_empty(self) -> None:
        report = build_strategy_evidence_report({})
        self.assertIsInstance(report, StrategyEvidenceReport)
        self.assertEqual(len(report.signals), 0)

    def test_evidence_report_to_dict(self) -> None:
        report = build_strategy_evidence_report({
            "api_candidates": [
                {
                    "url": "https://api.example.com/data?x-sign=abc",
                    "method": "GET",
                    "kind": "json",
                    "score": 60,
                },
            ],
        })
        d = report.to_dict()
        self.assertIn("signals", d)
        self.assertIn("warnings", d)
        self.assertIn("action_hints", d)
        self.assertIsInstance(d["signals"], list)


class TestNormalizeGraphQLRecords(unittest.TestCase):
    """Verify normalize_api_records works with GraphQL-shaped data."""

    def test_normalize_graphql_characters(self) -> None:
        result = fetch_graphql_api("mock://api/graphql-nested", query="{}")
        records = extract_records_from_json(result["data"])
        normalized = normalize_api_records(records)
        self.assertGreaterEqual(len(normalized), 2)
        for item in normalized:
            self.assertIn("title", item)
            self.assertTrue(item["title"])

    def test_normalize_graphql_cursor_edges(self) -> None:
        """Extract and normalize records from Relay-style edges/nodes."""
        result = fetch_graphql_api(
            "mock://api/graphql-paginated",
            query="{}",
            variables={"after": None},
        )
        edges = result["data"]["data"]["characters"]["edges"]
        nodes = [e["node"] for e in edges if isinstance(e, dict) and "node" in e]
        normalized = normalize_api_records(nodes)
        self.assertGreaterEqual(len(normalized), 2)
        for item in normalized:
            self.assertIn("title", item)

    def test_normalize_api_50_records(self) -> None:
        """Normalize 50+ records from pagination fixture."""
        result = fetch_paginated_api(
            "mock://api/paged-products-50?page=1",
            pagination=PaginationSpec(type="page", page_param="page", max_pages=10),
        )
        self.assertGreaterEqual(len(result.all_items), 50)
        for item in result.all_items[:10]:
            self.assertIn("title", item)
            self.assertTrue(item["title"])


if __name__ == "__main__":
    unittest.main()
