"""Tests for profile_draft module — browser evidence to SiteProfile draft.

Mocked tests — no network required.
Covers: selector inference, api_hints, pagination_hints, quality_expectations,
target_fields, training_notes, and full draft round-trip.
"""
from __future__ import annotations

import unittest
from typing import Any

from autonomous_crawler.runners.profile_draft import (
    _domain_as_name,
    _draft_api_hints,
    _draft_crawl_preferences,
    _draft_pagination_hints,
    _draft_quality_expectations,
    _draft_selectors,
    _draft_target_fields,
    _draft_training_notes,
    draft_profile_from_evidence,
)


def _minimal_evidence(**overrides: Any) -> dict[str, Any]:
    """Build minimal evidence dict for testing."""
    base: dict[str, Any] = {
        "url": "https://example.com/products",
        "selector_matches": {},
        "network_candidates": {"resource_counts": {}, "xhr_count": 0, "captured_xhr": []},
        "html_chars": 10000,
        "rendered_item_count": 20,
        "scroll_events": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Selector inference
# ---------------------------------------------------------------------------


class SelectorInferenceTests(unittest.TestCase):

    def test_selector_matches_populated(self) -> None:
        evidence = _minimal_evidence(selector_matches={"item": 10, "title": 10, "price": 5})
        selectors = _draft_selectors(evidence)
        self.assertIn("item", selectors)
        self.assertIn("title", selectors)
        self.assertIn("price", selectors)

    def test_selector_matches_zero_count_excluded(self) -> None:
        evidence = _minimal_evidence(selector_matches={"item": 10, "missing": 0})
        selectors = _draft_selectors(evidence)
        self.assertIn("item", selectors)
        self.assertNotIn("missing", selectors)

    def test_field_candidates_override_matches(self) -> None:
        evidence = _minimal_evidence(
            selector_matches={"title": 5},
            field_candidates={
                "title": [{"selector": "h1.product-title", "score": 15.0, "count": 1}],
                "price": [{"selector": ".price-value", "score": 12.0, "count": 1}],
            },
        )
        selectors = _draft_selectors(evidence)
        self.assertEqual(selectors["title"], "h1.product-title")
        self.assertEqual(selectors["price"], ".price-value")

    def test_explicit_selectors_used(self) -> None:
        evidence = _minimal_evidence(selectors={"item": ".product-card", "name": "h3"})
        selectors = _draft_selectors(evidence)
        self.assertEqual(selectors["item"], ".product-card")
        self.assertEqual(selectors["name"], "h3")

    def test_empty_evidence_no_selectors(self) -> None:
        selectors = _draft_selectors({})
        self.assertEqual(selectors, {})


# ---------------------------------------------------------------------------
# API hints inference
# ---------------------------------------------------------------------------


class ApiHintsTests(unittest.TestCase):

    def test_no_xhr_empty_hints(self) -> None:
        evidence = _minimal_evidence()
        hints = _draft_api_hints(evidence)
        self.assertNotIn("endpoint", hints)

    def test_captured_xhr_json_endpoint(self) -> None:
        evidence = _minimal_evidence(
            network_candidates={
                "resource_counts": {},
                "xhr_count": 3,
                "captured_xhr": [
                    {"url": "https://api.example.com/products?page=1", "method": "GET", "content_type": "application/json"},
                    {"url": "https://api.example.com/products?page=2", "method": "GET", "content_type": "application/json"},
                ],
            },
        )
        hints = _draft_api_hints(evidence)
        self.assertEqual(hints["endpoint"], "https://api.example.com/products?page=1")
        self.assertEqual(hints["format"], "json")
        self.assertEqual(hints["xhr_count"], 3)

    def test_scout_api_hints_json_like(self) -> None:
        evidence = _minimal_evidence(
            api_hints=[
                {"url": "https://cdn.example.com/data.json", "json_like": True},
                {"url": "https://fonts.googleapis.com/css", "json_like": False},
            ],
        )
        hints = _draft_api_hints(evidence)
        self.assertEqual(hints["endpoint"], "https://cdn.example.com/data.json")

    def test_non_json_xhr_recorded(self) -> None:
        evidence = _minimal_evidence(
            network_candidates={
                "resource_counts": {},
                "xhr_count": 1,
                "captured_xhr": [
                    {"url": "https://example.com/api/data", "method": "GET", "content_type": "text/html"},
                ],
            },
        )
        hints = _draft_api_hints(evidence)
        self.assertEqual(hints["endpoint"], "https://example.com/api/data")
        self.assertNotIn("format", hints)


# ---------------------------------------------------------------------------
# Pagination hints inference
# ---------------------------------------------------------------------------


class PaginationHintsTests(unittest.TestCase):

    def test_scroll_events_infinite_scroll(self) -> None:
        evidence = _minimal_evidence(scroll_events=[{"type": "scroll"}, {"type": "scroll"}])
        pagination = _draft_pagination_hints(evidence)
        self.assertEqual(pagination["type"], "infinite_scroll")
        self.assertEqual(pagination["scroll_event_count"], 2)

    def test_xhr_page_param(self) -> None:
        evidence = _minimal_evidence(
            network_candidates={
                "resource_counts": {},
                "xhr_count": 2,
                "captured_xhr": [
                    {"url": "https://api.example.com/items?page=1&limit=20", "method": "GET", "content_type": "application/json"},
                    {"url": "https://api.example.com/items?page=2&limit=20", "method": "GET", "content_type": "application/json"},
                ],
            },
        )
        pagination = _draft_pagination_hints(evidence)
        self.assertIn("params", pagination)
        self.assertIn("page", pagination["params"])

    def test_xhr_offset_param(self) -> None:
        evidence = _minimal_evidence(
            network_candidates={
                "resource_counts": {},
                "xhr_count": 2,
                "captured_xhr": [
                    {"url": "https://api.example.com/items?offset=0&limit=20", "method": "GET"},
                    {"url": "https://api.example.com/items?offset=20&limit=20", "method": "GET"},
                ],
            },
        )
        pagination = _draft_pagination_hints(evidence)
        self.assertIn("offset", pagination.get("params", {}))

    def test_no_pagination_evidence(self) -> None:
        evidence = _minimal_evidence()
        pagination = _draft_pagination_hints(evidence)
        self.assertEqual(pagination, {})

    def test_explicit_pagination_hints(self) -> None:
        evidence = _minimal_evidence(
            pagination_hints={"type": "cursor", "cursor_param": "after"},
        )
        pagination = _draft_pagination_hints(evidence)
        self.assertEqual(pagination["type"], "cursor")
        self.assertEqual(pagination["cursor_param"], "after")


# ---------------------------------------------------------------------------
# Quality expectations
# ---------------------------------------------------------------------------


class QualityExpectationsTests(unittest.TestCase):

    def test_rendered_items_recorded(self) -> None:
        evidence = _minimal_evidence(rendered_item_count=50)
        quality = _draft_quality_expectations(evidence)
        self.assertEqual(quality["min_items_expected"], 50)
        self.assertEqual(quality["item_count_observed"], 50)

    def test_html_size_recorded(self) -> None:
        evidence = _minimal_evidence(html_chars=100000)
        quality = _draft_quality_expectations(evidence)
        self.assertEqual(quality["html_size_observed"], 100000)

    def test_category_from_url(self) -> None:
        evidence = _minimal_evidence(url="https://shop.example.com/products/shoes")
        quality = _draft_quality_expectations(evidence)
        self.assertEqual(quality["category"], "product")

    def test_category_docs(self) -> None:
        evidence = _minimal_evidence(url="https://docs.example.com/api/reference")
        quality = _draft_quality_expectations(evidence)
        self.assertEqual(quality["category"], "documentation")

    def test_empty_evidence(self) -> None:
        quality = _draft_quality_expectations({})
        self.assertEqual(quality, {})


# ---------------------------------------------------------------------------
# Crawl preferences
# ---------------------------------------------------------------------------


class CrawlPreferencesTests(unittest.TestCase):

    def test_source_url_becomes_seed_url(self) -> None:
        preferences = _draft_crawl_preferences(_minimal_evidence(url="https://example.com/products"), {})
        self.assertEqual(preferences["seed_urls"], ["https://example.com/products"])
        self.assertEqual(preferences["seed_kind"], "list")

    def test_final_url_used_when_url_missing(self) -> None:
        preferences = _draft_crawl_preferences(
            _minimal_evidence(url="", final_url="https://example.com/rendered"),
            {},
        )
        self.assertEqual(preferences["seed_urls"], ["https://example.com/rendered"])

    def test_non_http_url_not_seeded(self) -> None:
        preferences = _draft_crawl_preferences(_minimal_evidence(url="mock://catalog"), {})
        self.assertEqual(preferences, {})

    def test_api_endpoint_marks_seed_as_optional(self) -> None:
        preferences = _draft_crawl_preferences(
            _minimal_evidence(url="https://example.com/products"),
            {"endpoint": "https://api.example.com/products"},
        )
        self.assertFalse(preferences["include_seed_urls_with_api"])


# ---------------------------------------------------------------------------
# Target fields
# ---------------------------------------------------------------------------


class TargetFieldsTests(unittest.TestCase):

    def test_known_field_names_extracted(self) -> None:
        selectors = {"title": ".title", "price": ".price", "image": "img@src"}
        fields = _draft_target_fields({}, selectors)
        self.assertIn("title", fields)
        self.assertIn("price", fields)
        self.assertIn("image", fields)

    def test_field_candidates_added(self) -> None:
        selectors = {"title": ".title"}
        evidence = {"field_candidates": {"body": [], "rating": []}}
        fields = _draft_target_fields(evidence, selectors)
        self.assertIn("body", fields)
        self.assertIn("rating", fields)

    def test_no_duplicates(self) -> None:
        selectors = {"title": ".title"}
        evidence = {"field_candidates": {"title": []}}
        fields = _draft_target_fields(evidence, selectors)
        self.assertEqual(fields.count("title"), 1)


# ---------------------------------------------------------------------------
# Training notes
# ---------------------------------------------------------------------------


class TrainingNotesTests(unittest.TestCase):

    def test_completed_no_failure_no_notes(self) -> None:
        evidence = _minimal_evidence(rendered_item_count=20)
        notes = _draft_training_notes(evidence)
        self.assertEqual(notes, [])

    def test_stop_reason_recorded(self) -> None:
        evidence = _minimal_evidence(stop_reason="navigation_timeout")
        notes = _draft_training_notes(evidence)
        self.assertTrue(any("navigation_timeout" in n for n in notes))

    def test_failure_category_recorded(self) -> None:
        evidence = _minimal_evidence(failure_classification={"category": "challenge"})
        notes = _draft_training_notes(evidence)
        self.assertTrue(any("challenge" in n for n in notes))

    def test_no_items_noted(self) -> None:
        evidence = _minimal_evidence(rendered_item_count=0)
        notes = _draft_training_notes(evidence)
        self.assertTrue(any("No items" in n for n in notes))

    def test_few_items_noted(self) -> None:
        evidence = _minimal_evidence(rendered_item_count=3)
        notes = _draft_training_notes(evidence)
        self.assertTrue(any("3 items" in n for n in notes))

    def test_xhr_noted(self) -> None:
        evidence = _minimal_evidence(
            network_candidates={"resource_counts": {}, "xhr_count": 5, "captured_xhr": []},
        )
        notes = _draft_training_notes(evidence)
        self.assertTrue(any("XHR" in n for n in notes))

    def test_scroll_noted(self) -> None:
        evidence = _minimal_evidence(scroll_events=[{"type": "scroll"}] * 3)
        notes = _draft_training_notes(evidence)
        self.assertTrue(any("3 events" in n for n in notes))


# ---------------------------------------------------------------------------
# Full draft round-trip
# ---------------------------------------------------------------------------


class DraftProfileRoundTripTests(unittest.TestCase):

    def test_full_evidence_produces_valid_profile(self) -> None:
        evidence = _minimal_evidence(
            selector_matches={"item": 10, "title": 10, "price": 5},
            rendered_item_count=20,
            html_chars=50000,
        )
        profile = draft_profile_from_evidence(evidence, site_name="test-shop")
        self.assertEqual(profile["name"], "test-shop")
        self.assertIn("item", profile["selectors"])
        self.assertIn("title", profile["selectors"])
        self.assertIn("title", profile["target_fields"])
        self.assertEqual(profile["quality_expectations"]["min_items_expected"], 20)

    def test_api_evidence_produces_api_hints(self) -> None:
        evidence = _minimal_evidence(
            network_candidates={
                "resource_counts": {},
                "xhr_count": 3,
                "captured_xhr": [
                    {"url": "https://api.test.com/v1/products?page=1", "method": "GET", "content_type": "application/json"},
                ],
            },
        )
        profile = draft_profile_from_evidence(evidence)
        self.assertIn("endpoint", profile["api_hints"])
        self.assertEqual(profile["api_hints"]["format"], "json")

    def test_scroll_evidence_produces_pagination(self) -> None:
        evidence = _minimal_evidence(
            scroll_events=[{"type": "scroll"}] * 5,
        )
        profile = draft_profile_from_evidence(evidence)
        self.assertEqual(profile["pagination_hints"]["type"], "infinite_scroll")

    def test_minimal_evidence_produces_draft(self) -> None:
        profile = draft_profile_from_evidence({})
        self.assertEqual(profile["name"], "draft-profile")
        self.assertIsInstance(profile["selectors"], dict)
        self.assertIsInstance(profile["target_fields"], list)
        self.assertIsInstance(profile["training_notes"], list)

    def test_domain_name_from_url(self) -> None:
        evidence = _minimal_evidence(url="https://www.shop-example.com/products")
        profile = draft_profile_from_evidence(evidence)
        self.assertEqual(profile["name"], "shop-example-com")

    def test_profile_can_be_loaded_as_site_profile(self) -> None:
        from autonomous_crawler.runners import SiteProfile, initial_requests_from_profile
        evidence = _minimal_evidence(
            selector_matches={"item": 5, "title": 5},
            rendered_item_count=10,
        )
        draft = draft_profile_from_evidence(evidence, site_name="roundtrip-test")
        profile = SiteProfile.from_dict(draft)
        self.assertEqual(profile.name, "roundtrip-test")
        self.assertIn("item", profile.selectors)
        self.assertEqual(profile.quality_expectations.get("min_items_expected"), 10)
        initial = initial_requests_from_profile(profile, run_id="draft-roundtrip")
        self.assertEqual(len(initial), 1)
        self.assertEqual(initial[0].url, "https://example.com/products")


# ---------------------------------------------------------------------------
# Domain utility
# ---------------------------------------------------------------------------


class DomainNameTests(unittest.TestCase):

    def test_simple_domain(self) -> None:
        self.assertEqual(_domain_as_name("https://example.com/path"), "example-com")

    def test_www_stripped(self) -> None:
        self.assertEqual(_domain_as_name("https://www.example.com/"), "example-com")

    def test_empty_url(self) -> None:
        self.assertEqual(_domain_as_name(""), "draft-profile")

    def test_subdomain_kept(self) -> None:
        self.assertEqual(_domain_as_name("https://api.shop.example.com/"), "api-shop-example-com")


if __name__ == "__main__":
    unittest.main()
