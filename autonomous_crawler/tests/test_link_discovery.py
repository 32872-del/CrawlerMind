from __future__ import annotations

import unittest

from autonomous_crawler.runners import CrawlRequestEnvelope
from autonomous_crawler.tools.link_discovery import (
    LinkDiscoveryHelper,
    LinkDiscoveryRule,
    SitemapDiscoveryHelper,
    SitemapDiscoveryRule,
    canonicalize_discovered_url,
)


HTML = """
<html>
  <body>
    <nav><a href="/ignored">Ignored Nav</a></nav>
    <main class="products">
      <a href="/products/alpha?b=2">Alpha</a>
      <a href="https://example.com/products/beta#frag">Beta</a>
      <a href="https://cdn.example.com/image.jpg">Image</a>
      <a href="https://other.test/products/offsite">Offsite</a>
      <a href="/api/products.json">API</a>
      <a href="/products/alpha?b=2">Duplicate</a>
    </main>
  </body>
</html>
"""


class LinkDiscoveryHelperTests(unittest.TestCase):
    def test_canonicalize_discovered_url(self) -> None:
        url = canonicalize_discovered_url(
            "../products/a#details",
            base_url="https://example.com/catalog/page/",
        )

        self.assertEqual(url, "https://example.com/catalog/products/a")

    def test_extract_filters_classifies_and_emits_drop_events(self) -> None:
        parent = CrawlRequestEnvelope(run_id="run", url="https://example.com/catalog")
        rules = LinkDiscoveryRule(
            allow_domains=("example.com",),
            restrict_css=("main.products",),
            classify={"detail": r"/products/", "api": r"/api/"},
            default_kind="page",
            priority=7,
        )

        result = LinkDiscoveryHelper().extract(
            HTML,
            base_url="https://example.com/catalog",
            run_id="run",
            rules=rules,
            parent_request=parent,
        )

        urls = [request.url for request in result.requests]

        self.assertEqual(urls, [
            "https://example.com/products/alpha?b=2",
            "https://example.com/products/beta",
            "https://example.com/api/products.json",
        ])
        self.assertEqual([request.kind for request in result.requests], ["detail", "detail", "api"])
        self.assertEqual(result.requests[0].priority, 7)
        self.assertEqual(result.requests[0].depth, 1)
        self.assertEqual(result.dropped["ignored_extension"], 1)
        self.assertEqual(result.dropped["offsite"], 1)
        self.assertEqual(result.dropped["duplicate"], 1)
        self.assertTrue(any(event.type == "spider.link_dropped" for event in result.events))

    def test_allow_and_deny_patterns(self) -> None:
        rules = LinkDiscoveryRule(
            allow=(r"/products/",),
            deny=(r"beta",),
            allow_domains=("example.com",),
        )

        result = LinkDiscoveryHelper().extract(
            HTML,
            base_url="https://example.com/catalog",
            run_id="run",
            rules=rules,
        )

        self.assertEqual([request.url for request in result.requests], [
            "https://example.com/products/alpha?b=2",
        ])
        self.assertEqual(result.dropped["denied_pattern"], 1)
        self.assertGreaterEqual(result.dropped["not_allowed_pattern"], 1)

    def test_max_links_caps_results(self) -> None:
        rules = LinkDiscoveryRule(allow_domains=("example.com",), max_links=1)

        result = LinkDiscoveryHelper().extract(
            HTML,
            base_url="https://example.com/catalog",
            run_id="run",
            rules=rules,
        )

        self.assertEqual(len(result.requests), 1)
        self.assertEqual(result.events[-1].message, "link discovery capped")

    def test_matches_reports_filtered_urls(self) -> None:
        helper = LinkDiscoveryHelper()
        rules = LinkDiscoveryRule(allow_domains=("example.com",))

        self.assertTrue(helper.matches("https://example.com/products/a", rules))
        self.assertFalse(helper.matches("https://other.test/products/a", rules))


class SitemapDiscoveryHelperTests(unittest.TestCase):
    def test_parse_urlset_filters_same_domain(self) -> None:
        xml = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/products/a</loc></url>
          <url><loc>https://example.com/products/b</loc></url>
          <url><loc>https://other.test/products/offsite</loc></url>
        </urlset>
        """

        result = SitemapDiscoveryHelper().parse(
            xml,
            sitemap_url="https://example.com/sitemap.xml",
            run_id="run",
            rules=SitemapDiscoveryRule(default_kind="detail", priority=5),
        )

        self.assertEqual([request.url for request in result.requests], [
            "https://example.com/products/a",
            "https://example.com/products/b",
        ])
        self.assertEqual([request.kind for request in result.requests], ["detail", "detail"])
        self.assertEqual(result.requests[0].priority, 5)
        self.assertEqual(result.dropped["offsite"], 1)
        self.assertEqual(result.events[-1].type, "spider.sitemap_discovered")

    def test_parse_sitemap_index_returns_nested_sitemaps(self) -> None:
        xml = """<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <sitemap><loc>https://example.com/sitemap-products.xml</loc></sitemap>
          <sitemap><loc>https://cdn.example.com/sitemap-cdn.xml</loc></sitemap>
        </sitemapindex>
        """

        result = SitemapDiscoveryHelper().parse(
            xml,
            sitemap_url="https://example.com/sitemap.xml",
            run_id="run",
            rules=SitemapDiscoveryRule(allow_domains=("example.com",)),
        )

        self.assertEqual(result.sitemap_urls, ["https://example.com/sitemap-products.xml"])
        self.assertEqual(result.requests, [])
        self.assertEqual(result.dropped["offsite"], 1)

    def test_malformed_xml_returns_event_not_exception(self) -> None:
        result = SitemapDiscoveryHelper().parse(
            "<urlset><url>",
            sitemap_url="https://example.com/sitemap.xml",
            run_id="run",
        )

        self.assertEqual(result.requests, [])
        self.assertIn("ParseError", result.error)
        self.assertEqual(result.events[0].type, "spider.sitemap_parse_failed")


if __name__ == "__main__":
    unittest.main()
