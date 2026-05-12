"""QA tests for Strategy consumption of js_evidence.

These tests prove that JS evidence is advisory and does NOT override stronger
deterministic evidence (good DOM candidates, observed public APIs, challenge
warnings).  No production code is edited; this file is purely additive.
"""
from __future__ import annotations

import unittest

from autonomous_crawler.agents.strategy import (
    _attach_js_evidence_hints,
    _build_js_evidence_hints,
    _dedupe_strings,
    strategy_node,
)


# ── helpers ─────────────────────────────────────────────────────────────────

def _base_state(**overrides: object) -> dict:
    """Return a minimal valid strategy state with sensible defaults."""
    recon: dict = {
        "target_url": "https://shop.example",
        "task_type": "product_list",
        "rendering": "static",
        "anti_bot": {"detected": False},
        "dom_structure": {"item_count": 0, "field_selectors": {}},
    }
    recon.update(overrides)
    return {
        "user_goal": "collect products",
        "target_url": recon.get("target_url", "https://shop.example"),
        "recon_report": recon,
        "messages": [],
    }


def _js_evidence(
    endpoints: list[str] | None = None,
    calls: list[str] | None = None,
    items: list[dict] | None = None,
) -> dict:
    """Build a js_evidence dict quickly."""
    return {
        "top_endpoints": endpoints or [],
        "top_suspicious_calls": calls or [],
        "items": items or [],
    }


# ────────────────────────────────────────────────────────────────────────────
# 1. DOM selectors remain http/dom_parse when JS endpoint strings exist
# ────────────────────────────────────────────────────────────────────────────

class DomDominanceTests(unittest.TestCase):
    """Good DOM selectors must NOT be overridden by JS evidence endpoints."""

    def test_good_dom_stays_dom_parse_with_js_endpoints(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 5,
                "product_selector": ".card",
                "field_selectors": {"title": ".title", "price": ".price"},
            },
            js_evidence=_js_evidence(
                endpoints=["/api/v2/products", "/api/search"],
                items=[{"source": "inline", "total_score": 70, "keyword_categories": ["token"]}],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "http")
        self.assertEqual(strategy["extraction_method"], "dom_parse")
        # JS hints are attached but advisory only
        self.assertIn("js_evidence_hints", strategy)
        self.assertEqual(strategy["js_evidence_hints"]["api_endpoints"], ["/api/v2/products", "/api/search"])

    def test_dom_with_many_js_endpoints_stays_dom(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 10,
                "product_selector": ".item",
                "field_selectors": {"title": ".name"},
            },
            js_evidence=_js_evidence(
                endpoints=[f"/api/endpoint{i}" for i in range(20)],
            ),
        ))
        self.assertEqual(state["crawl_strategy"]["mode"], "http")

    def test_dom_ranking_list_stays_dom_with_js_evidence(self) -> None:
        state = strategy_node(_base_state(
            task_type="ranking_list",
            dom_structure={
                "item_count": 8,
                "product_selector": ".rank-item",
                "field_selectors": {"title": ".rank-title", "rank": ".rank-num"},
            },
            js_evidence=_js_evidence(endpoints=["/api/rankings"]),
        ))
        self.assertEqual(state["crawl_strategy"]["mode"], "http")
        self.assertEqual(state["crawl_strategy"]["extraction_method"], "dom_parse")


# ────────────────────────────────────────────────────────────────────────────
# 2. High-confidence observed API candidates remain stronger than JS hints
# ────────────────────────────────────────────────────────────────────────────

class ApiCandidateDominanceTests(unittest.TestCase):
    """Browser-observed API candidates with high scores must dominate JS hints."""

    def test_high_score_api_candidate_wins_over_js_endpoints(self) -> None:
        state = strategy_node(_base_state(
            api_candidates=[{
                "url": "https://shop.example/api/v1/catalog",
                "method": "GET",
                "kind": "json",
                "score": 80,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_js_evidence(
                endpoints=["/api/v2/products", "/graphql"],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_endpoint"], "https://shop.example/api/v1/catalog")
        # JS evidence endpoint is NOT used; observed API is stronger
        self.assertNotEqual(strategy.get("api_endpoint_source"), "js_evidence")

    def test_graphql_candidate_wins_over_js_endpoints(self) -> None:
        state = strategy_node(_base_state(
            api_candidates=[{
                "url": "https://shop.example/graphql",
                "method": "POST",
                "kind": "graphql",
                "score": 90,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_js_evidence(endpoints=["/api/fallback"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["extraction_method"], "graphql_json")
        self.assertEqual(strategy["api_endpoint"], "https://shop.example/graphql")

    def test_low_score_candidate_uses_fallback_api_path(self) -> None:
        """Low-score candidates (< 50) bypass the high-confidence path but
        still reach api_intercept via the fallback branch.  This is correct:
        the high-confidence path requires score >= 50 AND browser_network_observation
        reason, but the fallback catches any api_candidates list."""
        state = strategy_node(_base_state(
            rendering="static",
            api_candidates=[{
                "url": "https://shop.example/track",
                "method": "GET",
                "kind": "json",
                "score": 30,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_js_evidence(endpoints=["/api/products"]),
        ))
        strategy = state["crawl_strategy"]
        # Low-score candidate still reaches api_intercept via fallback branch
        # (api_candidates is non-empty and no good DOM)
        self.assertEqual(strategy["mode"], "api_intercept")
        # But JS evidence endpoint does NOT override the candidate URL
        self.assertEqual(strategy["api_endpoint"], "https://shop.example/track")


# ────────────────────────────────────────────────────────────────────────────
# 3. Challenge/fingerprint JS categories add warnings but do NOT force routing
# ────────────────────────────────────────────────────────────────────────────

class ChallengeSafetyTests(unittest.TestCase):
    """Challenge/fingerprint JS clues must produce warnings, not force api_intercept."""

    def test_challenge_clues_add_warning_not_api_mode(self) -> None:
        state = strategy_node(_base_state(
            rendering="spa",
            js_evidence=_js_evidence(
                calls=["hcaptcha.getResponse", "turnstile.render"],
                items=[{
                    "source": "captured",
                    "url": "https://shop.example/app.js",
                    "total_score": 80,
                    "keyword_categories": ["challenge", "fingerprint"],
                    "reasons": ["challenge_call"],
                }],
            ),
        ))
        strategy = state["crawl_strategy"]
        # SPA rendering → browser mode, not api_intercept
        self.assertEqual(strategy["mode"], "browser")
        self.assertEqual(strategy.get("js_evidence_warning"), "challenge_or_fingerprint_clues")
        self.assertIn("challenge/fingerprint", strategy["rationale"])

    def test_fingerprint_clues_add_warning_keep_browser(self) -> None:
        state = strategy_node(_base_state(
            rendering="spa",
            js_evidence=_js_evidence(
                items=[{
                    "source": "captured",
                    "total_score": 70,
                    "keyword_categories": ["fingerprint"],
                }],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")
        self.assertEqual(strategy.get("js_evidence_warning"), "challenge_or_fingerprint_clues")

    def test_anti_bot_clues_add_warning(self) -> None:
        state = strategy_node(_base_state(
            rendering="spa",
            js_evidence=_js_evidence(
                items=[{
                    "source": "captured",
                    "total_score": 60,
                    "keyword_categories": ["anti_bot"],
                }],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy.get("js_evidence_warning"), "challenge_or_fingerprint_clues")

    def test_challenge_clues_do_not_force_api_when_dom_good(self) -> None:
        """Even with challenge JS clues, good DOM → stays http mode."""
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 5,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(
                calls=["hcaptcha.getResponse"],
                items=[{
                    "source": "captured",
                    "total_score": 90,
                    "keyword_categories": ["challenge"],
                }],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "http")
        self.assertEqual(strategy["extraction_method"], "dom_parse")
        # Warning still attached
        self.assertEqual(strategy.get("js_evidence_warning"), "challenge_or_fingerprint_clues")

    def test_challenge_clues_do_not_override_existing_api_endpoint(self) -> None:
        """JS challenge clues do NOT replace a real observed API endpoint."""
        state = strategy_node(_base_state(
            api_candidates=[{
                "url": "https://shop.example/api/data",
                "method": "GET",
                "kind": "json",
                "score": 70,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_js_evidence(
                endpoints=["/api/js-hint"],
                items=[{
                    "source": "captured",
                    "total_score": 80,
                    "keyword_categories": ["challenge"],
                }],
            ),
        ))
        strategy = state["crawl_strategy"]
        # No DOM, no challenge in access_diagnostics → API mode with real candidate
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_endpoint"], "https://shop.example/api/data")

    def test_no_warning_for_normal_api_endpoint_hints(self) -> None:
        """Normal API endpoint hints (no challenge/fingerprint) → no warning."""
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 5,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(
                endpoints=["/api/products"],
                items=[{"source": "inline", "total_score": 40, "keyword_categories": ["token"]}],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertNotIn("js_evidence_warning", strategy)
        self.assertIn("js_evidence_hints", strategy)


# ────────────────────────────────────────────────────────────────────────────
# 4. Duplicate endpoint/call hints are deduped
# ────────────────────────────────────────────────────────────────────────────

class DeduplicationTests(unittest.TestCase):
    """Duplicate endpoints and calls must be deduped in strategy output."""

    def test_duplicate_endpoints_deduped(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 3,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(
                endpoints=["/api/products", "/api/products", "/api/search", "/api/products"],
            ),
        ))
        hints = state["crawl_strategy"]["js_evidence_hints"]
        self.assertEqual(hints["api_endpoints"], ["/api/products", "/api/search"])

    def test_duplicate_calls_deduped(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={"item_count": 0, "field_selectors": {}},
            js_evidence=_js_evidence(
                calls=["fetch('/api')", "fetch('/api')", "XMLHttpRequest"],
                items=[{"source": "captured", "total_score": 50, "keyword_categories": ["token"]}],
            ),
        ))
        hints = state["crawl_strategy"]["js_evidence_hints"]
        self.assertEqual(hints["suspicious_calls"], ["fetch('/api')", "XMLHttpRequest"])

    def test_dedup_strings_preserves_order(self) -> None:
        result = _dedupe_strings(["c", "a", "b", "a", "c", "d"], limit=10)
        self.assertEqual(result, ["c", "a", "b", "d"])

    def test_dedup_strings_respects_limit(self) -> None:
        result = _dedupe_strings(["a", "b", "c", "d", "e"], limit=3)
        self.assertEqual(result, ["a", "b", "c"])

    def test_dedup_strings_skips_empty(self) -> None:
        result = _dedupe_strings(["a", "", "  ", "b"], limit=10)
        self.assertEqual(result, ["a", "b"])

    def test_top_endpoints_from_multiple_items_deduped(self) -> None:
        """Endpoints from multiple JS evidence items are globally deduped."""
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 2,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(
                endpoints=["/api/a", "/api/b"],
                items=[
                    {
                        "source": "inline",
                        "total_score": 30,
                        "endpoint_candidates": ["/api/a", "/api/c"],
                        "static_endpoint_strings": ["/api/b"],
                    },
                ],
            ),
        ))
        hints = state["crawl_strategy"]["js_evidence_hints"]
        # /api/a and /api/b from top_endpoints; /api/c from item candidates
        self.assertIn("/api/a", hints["api_endpoints"])
        self.assertIn("/api/b", hints["api_endpoints"])


# ────────────────────────────────────────────────────────────────────────────
# 5. Strategy messages/rationale stay readable and bounded
# ────────────────────────────────────────────────────────────────────────────

class RationaleBoundsTests(unittest.TestCase):
    """Rationale must stay readable and not grow unbounded."""

    def test_rationale_includes_js_evidence_summary(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 3,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(
                endpoints=["/api/products"],
                calls=["fetch('/data')"],
            ),
        ))
        rationale = state["crawl_strategy"]["rationale"]
        self.assertIn("JS evidence found endpoint strings", rationale)
        self.assertIn("JS evidence found suspicious call clues", rationale)

    def test_rationale_bounded_with_many_endpoints(self) -> None:
        """Even with many endpoints, rationale should not list them all."""
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 3,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(
                endpoints=[f"/api/endpoint{i}" for i in range(50)],
            ),
        ))
        rationale = state["crawl_strategy"]["rationale"]
        # Rationale should not contain individual endpoint paths
        self.assertNotIn("/api/endpoint0", rationale)
        self.assertIn("JS evidence", rationale)

    def test_rationale_stays_string(self) -> None:
        state = strategy_node(_base_state(
            js_evidence=_js_evidence(endpoints=["/api/test"]),
        ))
        self.assertIsInstance(state["crawl_strategy"]["rationale"], str)
        self.assertTrue(len(state["crawl_strategy"]["rationale"]) > 0)

    def test_strategy_message_emitted(self) -> None:
        state = strategy_node(_base_state(
            js_evidence=_js_evidence(endpoints=["/api/test"]),
        ))
        messages = state["messages"]
        self.assertTrue(any("[Strategy]" in m for m in messages))

    def test_rationale_no_js_section_when_no_evidence(self) -> None:
        state = strategy_node(_base_state())
        rationale = state["crawl_strategy"]["rationale"]
        self.assertNotIn("JS evidence", rationale)


# ────────────────────────────────────────────────────────────────────────────
# 6. Edge cases — malformed, missing, or empty js_evidence
# ────────────────────────────────────────────────────────────────────────────

class EdgeCaseTests(unittest.TestCase):
    """js_evidence edge cases must not crash or corrupt strategy."""

    def test_no_js_evidence_no_hints(self) -> None:
        state = strategy_node(_base_state())
        strategy = state["crawl_strategy"]
        self.assertNotIn("js_evidence_hints", strategy)
        self.assertNotIn("js_evidence_warning", strategy)

    def test_empty_js_evidence_no_hints(self) -> None:
        state = strategy_node(_base_state(js_evidence={}))
        strategy = state["crawl_strategy"]
        self.assertNotIn("js_evidence_hints", strategy)

    def test_none_js_evidence_no_crash(self) -> None:
        state = strategy_node(_base_state(js_evidence=None))
        strategy = state["crawl_strategy"]
        self.assertNotIn("js_evidence_hints", strategy)

    def test_non_dict_js_evidence_ignored(self) -> None:
        state = strategy_node(_base_state(js_evidence="not a dict"))
        strategy = state["crawl_strategy"]
        self.assertNotIn("js_evidence_hints", strategy)

    def test_js_evidence_with_empty_items(self) -> None:
        state = strategy_node(_base_state(
            js_evidence=_js_evidence(items=[]),
        ))
        strategy = state["crawl_strategy"]
        self.assertNotIn("js_evidence_hints", strategy)

    def test_js_evidence_with_non_dict_items(self) -> None:
        state = strategy_node(_base_state(
            js_evidence={"items": ["not", "dicts", 42]},
        ))
        strategy = state["crawl_strategy"]
        # Non-dict items are filtered out → no high-score items → no hints
        self.assertNotIn("js_evidence_hints", strategy)

    def test_malformed_endpoints_ignored(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 3,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence={"top_endpoints": [123, None, True]},
        ))
        # _dedupe_strings converts to str, so these become "123", "None", "True"
        hints = state["crawl_strategy"].get("js_evidence_hints", {})
        self.assertIn("api_endpoints", hints)

    def test_empty_endpoint_strings_filtered(self) -> None:
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 3,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(endpoints=["", "  ", "/api/real"]),
        ))
        hints = state["crawl_strategy"]["js_evidence_hints"]
        self.assertEqual(hints["api_endpoints"], ["/api/real"])


# ────────────────────────────────────────────────────────────────────────────
# 7. JS evidence fills missing API endpoint ONLY in api_intercept mode
# ────────────────────────────────────────────────────────────────────────────

class EndpointFillTests(unittest.TestCase):
    """JS evidence can fill a missing api_endpoint, but only when strategy
    is already api_intercept mode."""

    def test_fills_missing_endpoint_in_api_mode(self) -> None:
        state = strategy_node(_base_state(
            api_candidates=[{"kind": "json", "score": 30}],
            api_endpoints=[""],
            js_evidence=_js_evidence(endpoints=["/api/products"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_endpoint"], "/api/products")
        self.assertEqual(strategy.get("api_endpoint_source"), "js_evidence")

    def test_does_not_fill_when_endpoint_already_set(self) -> None:
        state = strategy_node(_base_state(
            api_candidates=[{
                "url": "https://shop.example/api/real",
                "method": "GET",
                "kind": "json",
                "score": 70,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_js_evidence(endpoints=["/api/js-hint"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["api_endpoint"], "https://shop.example/api/real")
        self.assertNotEqual(strategy.get("api_endpoint_source"), "js_evidence")

    def test_does_not_switch_to_api_mode_for_endpoint_fill(self) -> None:
        """JS endpoints cannot FORCE strategy into api_intercept mode."""
        state = strategy_node(_base_state(
            rendering="static",
            dom_structure={
                "item_count": 3,
                "product_selector": ".card",
                "field_selectors": {"title": ".title"},
            },
            js_evidence=_js_evidence(endpoints=["/api/products"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "http")
        self.assertNotEqual(strategy.get("api_endpoint_source"), "js_evidence")

    def test_fill_uses_first_endpoint(self) -> None:
        state = strategy_node(_base_state(
            api_candidates=[{"kind": "json", "score": 30}],
            api_endpoints=[""],
            js_evidence=_js_evidence(endpoints=["/api/first", "/api/second"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["api_endpoint"], "/api/first")

    def test_fill_sets_accept_json_header(self) -> None:
        state = strategy_node(_base_state(
            api_candidates=[{"kind": "json", "score": 30}],
            api_endpoints=[""],
            js_evidence=_js_evidence(endpoints=["/api/products"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["headers"]["Accept"], "application/json")


# ────────────────────────────────────────────────────────────────────────────
# 8. _build_js_evidence_hints unit tests
# ────────────────────────────────────────────────────────────────────────────

class BuildHintsTests(unittest.TestCase):
    """Unit tests for _build_js_evidence_hints directly."""

    def test_empty_evidence_returns_empty_hints(self) -> None:
        self.assertEqual(_build_js_evidence_hints({}), {})

    def test_endpoints_extracted(self) -> None:
        hints = _build_js_evidence_hints({"top_endpoints": ["/api/a", "/api/b"]})
        self.assertEqual(hints["api_endpoints"], ["/api/a", "/api/b"])

    def test_calls_extracted(self) -> None:
        hints = _build_js_evidence_hints({"top_suspicious_calls": ["eval(code)"]})
        self.assertEqual(hints["suspicious_calls"], ["eval(code)"])

    def test_categories_collected_from_items(self) -> None:
        hints = _build_js_evidence_hints({"items": [
            {"keyword_categories": ["token", "challenge"]},
            {"keyword_categories": ["fingerprint"]},
        ]})
        self.assertIn("challenge", hints["categories"])
        self.assertIn("fingerprint", hints["categories"])
        self.assertIn("token", hints["categories"])

    def test_categories_sorted_and_deduped(self) -> None:
        hints = _build_js_evidence_hints({"items": [
            {"keyword_categories": ["z", "a", "z"]},
        ]})
        self.assertEqual(hints["categories"], sorted(set(hints["categories"])))

    def test_high_score_sources_extracted(self) -> None:
        hints = _build_js_evidence_hints({"items": [
            {
                "source": "captured",
                "url": "https://example.com/app.js",
                "total_score": 80,
                "reasons": ["r1", "r2"],
            },
        ]})
        self.assertEqual(len(hints["high_score_sources"]), 1)
        self.assertEqual(hints["high_score_sources"][0]["score"], 80)

    def test_low_score_items_not_in_high_score_sources(self) -> None:
        hints = _build_js_evidence_hints({"items": [
            {"source": "inline", "total_score": 30},
        ]})
        self.assertNotIn("high_score_sources", hints)

    def test_high_score_sources_capped_at_5(self) -> None:
        items = [{"source": f"s{i}", "total_score": 60} for i in range(10)]
        hints = _build_js_evidence_hints({"items": items})
        self.assertLessEqual(len(hints["high_score_sources"]), 5)


# ────────────────────────────────────────────────────────────────────────────
# 9. _attach_js_evidence_hints unit tests (isolated)
# ────────────────────────────────────────────────────────────────────────────

class AttachHintsUnitTests(unittest.TestCase):
    """Test _attach_js_evidence_hints in isolation with a plain strategy dict."""

    def test_no_evidence_no_mutation(self) -> None:
        strategy = {"mode": "http", "rationale": "test"}
        _attach_js_evidence_hints(strategy, {})
        self.assertNotIn("js_evidence_hints", strategy)
        self.assertEqual(strategy["rationale"], "test")

    def test_non_dict_evidence_ignored(self) -> None:
        strategy = {"mode": "http", "rationale": "test"}
        _attach_js_evidence_hints(strategy, {"js_evidence": [1, 2, 3]})
        self.assertNotIn("js_evidence_hints", strategy)

    def test_hints_attached_to_strategy(self) -> None:
        strategy = {"mode": "http", "rationale": "test"}
        _attach_js_evidence_hints(strategy, {"js_evidence": {
            "top_endpoints": ["/api/x"],
            "top_suspicious_calls": [],
            "items": [],
        }})
        self.assertIn("js_evidence_hints", strategy)
        self.assertEqual(strategy["js_evidence_hints"]["api_endpoints"], ["/api/x"])

    def test_warning_set_for_challenge_categories(self) -> None:
        strategy = {"mode": "http", "rationale": "test"}
        _attach_js_evidence_hints(strategy, {"js_evidence": {
            "top_endpoints": [],
            "top_suspicious_calls": [],
            "items": [{"keyword_categories": ["challenge"], "total_score": 10}],
        }})
        self.assertEqual(strategy["js_evidence_warning"], "challenge_or_fingerprint_clues")

    def test_warning_not_set_for_normal_categories(self) -> None:
        strategy = {"mode": "http", "rationale": "test"}
        _attach_js_evidence_hints(strategy, {"js_evidence": {
            "top_endpoints": [],
            "top_suspicious_calls": [],
            "items": [{"keyword_categories": ["token"], "total_score": 10}],
        }})
        self.assertNotIn("js_evidence_warning", strategy)

    def test_endpoint_fill_only_in_api_mode(self) -> None:
        strategy = {"mode": "http", "rationale": "test", "api_endpoint": ""}
        _attach_js_evidence_hints(strategy, {"js_evidence": {
            "top_endpoints": ["/api/x"],
            "top_suspicious_calls": [],
            "items": [],
        }})
        # mode is http, not api_intercept → no fill
        self.assertNotEqual(strategy.get("api_endpoint_source"), "js_evidence")

    def test_endpoint_fill_in_api_mode_with_empty_endpoint(self) -> None:
        strategy = {"mode": "api_intercept", "rationale": "test", "api_endpoint": "", "api_method": "GET", "headers": {}}
        _attach_js_evidence_hints(strategy, {"js_evidence": {
            "top_endpoints": ["/api/x"],
            "top_suspicious_calls": [],
            "items": [],
        }})
        self.assertEqual(strategy["api_endpoint"], "/api/x")
        self.assertEqual(strategy["api_endpoint_source"], "js_evidence")

    def test_endpoint_fill_sets_method_if_missing(self) -> None:
        strategy = {"mode": "api_intercept", "rationale": "test", "api_endpoint": "", "headers": {}}
        _attach_js_evidence_hints(strategy, {"js_evidence": {
            "top_endpoints": ["/api/x"],
            "top_suspicious_calls": [],
            "items": [],
        }})
        self.assertEqual(strategy["api_method"], "GET")


# ────────────────────────────────────────────────────────────────────────────
# 10. Browser mode stays browser even with JS evidence
# ────────────────────────────────────────────────────────────────────────────

class BrowserModeTests(unittest.TestCase):
    """Browser mode must not be downgraded by JS evidence."""

    def test_spa_with_challenge_stays_browser(self) -> None:
        state = strategy_node(_base_state(
            rendering="spa",
            js_evidence=_js_evidence(
                endpoints=["/api/products"],
                items=[{"source": "captured", "total_score": 80, "keyword_categories": ["challenge"]}],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")

    def test_challenge_detected_stays_browser(self) -> None:
        state = strategy_node(_base_state(
            access_diagnostics={"signals": {"challenge": True}, "findings": []},
            js_evidence=_js_evidence(endpoints=["/api/products"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")
        self.assertEqual(strategy.get("access_warning"), "challenge_detected")

    def test_browser_mode_with_js_endpoints_stays_browser(self) -> None:
        state = strategy_node(_base_state(
            rendering="spa",
            js_evidence=_js_evidence(
                endpoints=["/api/a", "/api/b", "/api/c"],
                calls=["eval(x)"],
                items=[{"source": "captured", "total_score": 90, "keyword_categories": ["token"]}],
            ),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "browser")


# ────────────────────────────────────────────────────────────────────────────
# 11. Combined scenario — DOM + API candidates + JS evidence
# ────────────────────────────────────────────────────────────────────────────

class CombinedScenarioTests(unittest.TestCase):
    """Complex scenarios with multiple evidence sources."""

    def test_dom_wins_when_all_three_present(self) -> None:
        """DOM > API candidates > JS evidence. Good DOM always wins."""
        state = strategy_node(_base_state(
            dom_structure={
                "item_count": 5,
                "product_selector": ".card",
                "field_selectors": {"title": ".title", "price": ".price"},
            },
            api_candidates=[{
                "url": "https://shop.example/api/catalog",
                "method": "GET",
                "kind": "json",
                "score": 80,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_js_evidence(
                endpoints=["/api/v2/products", "/graphql"],
                calls=["fetch('/api')"],
                items=[{"source": "inline", "total_score": 70, "keyword_categories": ["token"]}],
            ),
        ))
        strategy = state["crawl_strategy"]
        # Good DOM → http/dom_parse
        self.assertEqual(strategy["mode"], "http")
        self.assertEqual(strategy["extraction_method"], "dom_parse")
        # JS hints still attached (advisory)
        self.assertIn("js_evidence_hints", strategy)
        self.assertEqual(strategy["js_evidence_hints"]["api_endpoints"], ["/api/v2/products", "/graphql"])

    def test_api_candidate_wins_when_no_dom(self) -> None:
        """Without good DOM, high-score API candidate beats JS hints."""
        state = strategy_node(_base_state(
            dom_structure={"item_count": 0, "field_selectors": {}},
            api_candidates=[{
                "url": "https://shop.example/api/catalog",
                "method": "GET",
                "kind": "json",
                "score": 80,
                "reason": "browser_network_observation",
                "status_code": 200,
            }],
            js_evidence=_js_evidence(endpoints=["/api/js-hint"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_endpoint"], "https://shop.example/api/catalog")

    def test_js_hint_fills_when_no_dom_no_api(self) -> None:
        """When nothing else available and strategy happens to be api_intercept,
        JS endpoint fills the gap."""
        state = strategy_node(_base_state(
            dom_structure={"item_count": 0, "field_selectors": {}},
            api_candidates=[{"kind": "json", "score": 30}],
            api_endpoints=[""],
            js_evidence=_js_evidence(endpoints=["/api/fallback"]),
        ))
        strategy = state["crawl_strategy"]
        self.assertEqual(strategy["mode"], "api_intercept")
        self.assertEqual(strategy["api_endpoint"], "/api/fallback")
        self.assertEqual(strategy.get("api_endpoint_source"), "js_evidence")


if __name__ == "__main__":
    unittest.main()
