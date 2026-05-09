"""Tests for rendered DOM selector inference, focused on modern SPA/SSR patterns."""
from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from autonomous_crawler.tools.html_recon import (
    MOCK_HN_ALGOLIA_HTML,
    MOCK_HN_ALGOLIA_VARIANT_HTML,
    build_recon_report,
    fetch_html,
    infer_dom_structure,
)


class TestHNAlgoliaFixture(unittest.TestCase):
    """Test that HN Algolia-style DOM produces valid item selectors."""

    def setUp(self):
        self.soup = BeautifulSoup(MOCK_HN_ALGOLIA_HTML, "lxml")

    def test_fetch_mock_hn_algolia(self):
        result = fetch_html("mock://hn-algolia")
        self.assertEqual(result.status_code, 200)
        self.assertIn("Story_storyContainer", result.html)

    def test_detects_story_items(self):
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia")
        self.assertTrue(report["is_product_list"])
        self.assertGreaterEqual(report["item_count"], 3)

    def test_product_selector_matches_articles(self):
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia")
        selector = report["product_selector"]
        self.assertTrue(selector, "product_selector should not be empty")
        # The selector should match all 3 story articles.
        matched = self.soup.select(selector)
        self.assertGreaterEqual(len(matched), 3)

    def test_title_field_selector(self):
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia")
        title_sel = report["field_selectors"].get("title", "")
        self.assertTrue(title_sel, "title selector should not be empty")
        # Verify the selector matches actual title text in the first article.
        articles = self.soup.select(report["product_selector"])
        first_title = articles[0].select_one(title_sel)
        self.assertIsNotNone(first_title)
        self.assertIn("New Search Engine", first_title.get_text())

    def test_link_field_selector(self):
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia")
        link_sel = report["field_selectors"].get("link", "")
        self.assertTrue(link_sel, "link selector should not be empty")
        articles = self.soup.select(report["product_selector"])
        # link selector is "selector@href" format.
        base_sel = link_sel.replace("@href", "")
        first_link = articles[0].select_one(base_sel)
        self.assertIsNotNone(first_link)
        href = first_link.get("href", "")
        self.assertIn("example.com", href)

    def test_hot_score_field_from_bare_text(self):
        """Bare text nodes like '123 points by user1' should be detected."""
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia")
        score_sel = report["field_selectors"].get("hot_score", "")
        self.assertTrue(score_sel, "hot_score selector should not be empty")

    def test_build_recon_report_end_to_end(self):
        report = build_recon_report("mock://hn-algolia", MOCK_HN_ALGOLIA_HTML)
        dom = report["dom_structure"]
        self.assertTrue(dom["is_product_list"])
        self.assertGreaterEqual(dom["item_count"], 3)
        self.assertIn("title", dom["field_selectors"])
        self.assertIn("link", dom["field_selectors"])


class TestHNAlgoliaVariantFixture(unittest.TestCase):
    """Test HN Algolia variant with <time> and explicit score spans."""

    def setUp(self):
        self.soup = BeautifulSoup(MOCK_HN_ALGOLIA_VARIANT_HTML, "lxml")

    def test_fetch_mock_hn_algolia_variant(self):
        result = fetch_html("mock://hn-algolia-variant")
        self.assertEqual(result.status_code, 200)
        self.assertIn("Story_score", result.html)

    def test_detects_story_items(self):
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia-variant")
        self.assertTrue(report["is_product_list"])
        self.assertGreaterEqual(report["item_count"], 3)

    def test_score_field_from_data_testid(self):
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia-variant")
        score_sel = report["field_selectors"].get("hot_score", "")
        self.assertTrue(score_sel, "hot_score selector should not be empty")

    def test_date_field_from_time_element(self):
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia-variant")
        date_sel = report["field_selectors"].get("date", "")
        self.assertTrue(date_sel, "date selector should not be empty")
        self.assertIn("@datetime", date_sel)

    def test_date_field_in_variant(self):
        """Verify the <time> element is found and contains datetime attr."""
        report = infer_dom_structure(self.soup, base_url="mock://hn-algolia-variant")
        date_sel = report["field_selectors"]["date"]
        articles = self.soup.select(report["product_selector"])
        base_sel = date_sel.replace("@datetime", "")
        time_el = articles[0].select_one(base_sel)
        self.assertIsNotNone(time_el)
        self.assertIn("2026", time_el.get("datetime", ""))


class TestExistingFixturesUnchanged(unittest.TestCase):
    """Verify existing mock fixtures still produce correct selectors."""

    def test_catalog_fixture_still_works(self):
        result = fetch_html("mock://catalog")
        soup = BeautifulSoup(result.html, "lxml")
        report = infer_dom_structure(soup, base_url="mock://catalog")
        self.assertTrue(report["is_product_list"])
        self.assertIn("title", report["field_selectors"])

    def test_ranking_fixture_still_works(self):
        result = fetch_html("mock://ranking")
        soup = BeautifulSoup(result.html, "lxml")
        report = infer_dom_structure(soup, base_url="mock://ranking")
        self.assertTrue(report["is_product_list"])
        self.assertEqual(report["product_selector"], ".category-wrap_iQLoo")
        self.assertIn("title", report["field_selectors"])
        self.assertIn("hot_score", report["field_selectors"])


class TestScoreRegex(unittest.TestCase):
    """Test the POINTS_RE pattern matches common score formats."""

    def test_points_pattern(self):
        from autonomous_crawler.tools.html_recon import POINTS_RE

        self.assertTrue(POINTS_RE.search("123 points"))
        self.assertTrue(POINTS_RE.search("89 points"))
        self.assertTrue(POINTS_RE.search("1 point"))
        self.assertTrue(POINTS_RE.search("456 points by user3"))
        self.assertTrue(POINTS_RE.search("72 votes"))
        self.assertTrue(POINTS_RE.search("210 upvotes"))
        self.assertFalse(POINTS_RE.search("no score here"))
        self.assertFalse(POINTS_RE.search("$123.00"))


if __name__ == "__main__":
    unittest.main()
