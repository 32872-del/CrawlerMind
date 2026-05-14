"""Tests for ScraplingParserRuntime adapter (SCRAPLING-RUNTIME-1).

Tests use local HTML strings — no network required.
"""
from __future__ import annotations

import unittest

from autonomous_crawler.runtime.models import RuntimeSelectorRequest, RuntimeSelectorResult
from autonomous_crawler.runtime.scrapling_parser import ScraplingParserRuntime

_FIXTURE_HTML = """\
<html>
<head><title>Test Page</title></head>
<body>
  <div class="products">
    <div class="card" data-id="1">
      <h2 class="title">Widget A</h2>
      <span class="price">$19.99</span>
      <a href="/products/1">Details</a>
    </div>
    <div class="card" data-id="2">
      <h2 class="title">Widget B</h2>
      <span class="price">$29.99</span>
      <a href="/products/2">Details</a>
    </div>
    <div class="card" data-id="3">
      <h2 class="title">Widget C</h2>
      <span class="price">$39.99</span>
      <a href="/products/3">Details</a>
    </div>
  </div>
  <footer>
    <p>Copyright 2026 Example Corp</p>
    <p>Contact: info@example.com</p>
  </footer>
</body>
</html>
"""


class ScraplingParserCssTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ScraplingParserRuntime()

    def test_css_extracts_multiple_titles(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="title", selector=".card .title", selector_type="css"),
        ])
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 3)
        self.assertIn("Widget A", result.values)
        self.assertIn("Widget B", result.values)
        self.assertIn("Widget C", result.values)

    def test_css_extracts_prices(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="price", selector=".card .price", selector_type="css"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 3)
        self.assertIn("$19.99", result.values)

    def test_css_extracts_attribute(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="link", selector=".card a", selector_type="css", attribute="href",
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 3)
        self.assertIn("/products/1", result.values)
        self.assertIn("/products/2", result.values)

    def test_css_extracts_data_attribute(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="card_id", selector=".card", selector_type="css", attribute="data-id",
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 3)
        self.assertIn("1", result.values)
        self.assertIn("2", result.values)

    def test_css_many_false_returns_first_only(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="first_title", selector=".card .title", selector_type="css", many=False,
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 1)
        self.assertEqual(len(result.values), 1)

    def test_css_selector_miss_returns_empty(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="missing", selector=".nonexistent", selector_type="css"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 0)
        self.assertEqual(result.values, [])


class ScraplingParserXpathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ScraplingParserRuntime()

    def test_xpath_extracts_titles(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="title", selector="//div[@class='card']//h2", selector_type="xpath",
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 3)
        self.assertIn("Widget A", result.values)

    def test_xpath_extracts_attribute(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="link", selector="//a/@href", selector_type="xpath",
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertGreaterEqual(result.matched, 3)

    def test_xpath_with_predicate(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="first_card",
                selector="//div[@class='card'][1]//h2",
                selector_type="xpath",
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 1)
        self.assertEqual(result.values[0], "Widget A")


class ScraplingParserTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ScraplingParserRuntime()

    def test_text_finds_matching_elements(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="found", selector="Widget A", selector_type="text"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertGreaterEqual(result.matched, 1)

    def test_text_partial_match(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="partial", selector="Widget", selector_type="text"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertGreaterEqual(result.matched, 1)

    def test_text_no_match_returns_empty(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="nope", selector="NonexistentText12345", selector_type="text"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 0)


class ScraplingParserRegexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ScraplingParserRuntime()

    def test_regex_extracts_prices(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="prices", selector=r"\$[\d.]+", selector_type="regex"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 3)
        self.assertIn("$19.99", result.values)
        self.assertIn("$29.99", result.values)

    def test_regex_extracts_year(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="year", selector=r"Copyright (\d{4})", selector_type="regex"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertGreaterEqual(result.matched, 1)
        self.assertTrue(any("2026" in v for v in result.values))

    def test_regex_no_match_returns_empty(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="nope", selector=r"ZZZZZ\d+", selector_type="regex"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 0)

    def test_invalid_regex_returns_error(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="bad", selector=r"[invalid", selector_type="regex"),
        ])
        result = results[0]
        self.assertFalse(result.ok)
        self.assertIn("regex", result.error.lower())


class ScraplingParserErrorHandlingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ScraplingParserRuntime()

    def test_invalid_css_does_not_crash(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="bad", selector=">>>invalid<<<", selector_type="css"),
        ])
        result = results[0]
        self.assertFalse(result.ok)
        self.assertIn("error", result.error.lower())

    def test_unsupported_selector_type_returns_error(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="bad", selector="something", selector_type="bogus"),
        ])
        result = results[0]
        self.assertFalse(result.ok)
        self.assertIn("unsupported", result.error.lower())

    def test_empty_html_does_not_crash(self) -> None:
        results = self.parser.parse("", [
            RuntimeSelectorRequest(name="title", selector=".title", selector_type="css"),
        ])
        result = results[0]
        # Empty HTML parses to <html/>, no crash, 0 matches
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 0)

    def test_malformed_html_does_not_crash(self) -> None:
        malformed = "<html><body><div class='unclosed<p>text</p></body>"
        results = self.parser.parse(malformed, [
            RuntimeSelectorRequest(name="text", selector="p", selector_type="css"),
        ])
        result = results[0]
        # lxml recovers from malformed HTML
        self.assertTrue(result.ok, result.error)

    def test_multiple_selectors_in_one_call(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="title", selector=".card .title", selector_type="css"),
            RuntimeSelectorRequest(name="price", selector=".card .price", selector_type="css"),
            RuntimeSelectorRequest(name="link", selector=".card a", selector_type="css", attribute="href"),
        ])
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0].ok)
        self.assertTrue(results[1].ok)
        self.assertTrue(results[2].ok)
        self.assertEqual(results[0].matched, 3)
        self.assertEqual(results[1].matched, 3)
        self.assertEqual(results[2].matched, 3)

    def test_url_passed_to_selector(self) -> None:
        """URL is passed through for potential urljoin operations."""
        results = self.parser.parse(
            _FIXTURE_HTML,
            [RuntimeSelectorRequest(name="title", selector=".card .title", selector_type="css")],
            url="https://shop.example.com/catalog",
        )
        self.assertTrue(results[0].ok)


class ScraplingParserMissingDependencyTests(unittest.TestCase):
    @unittest.skipUnless(True, "always runs")
    def test_missing_scrapling_graceful_skip(self) -> None:
        """When Scrapling is not installed, all selectors return error results."""
        import autonomous_crawler.runtime.scrapling_parser as mod
        original = mod._HAS_SCRAPLING
        try:
            mod._HAS_SCRAPLING = False
            parser = ScraplingParserRuntime()
            results = parser.parse("<html></html>", [
                RuntimeSelectorRequest(name="title", selector=".title", selector_type="css"),
            ])
            self.assertEqual(len(results), 1)
            self.assertFalse(results[0].ok)
            self.assertIn("not installed", results[0].error.lower())
        finally:
            mod._HAS_SCRAPLING = original


class ScraplingParserProtocolTests(unittest.TestCase):
    def test_satisfies_parser_runtime_protocol(self) -> None:
        from autonomous_crawler.runtime.protocols import ParserRuntime
        runtime = ScraplingParserRuntime()
        self.assertIsInstance(runtime, ParserRuntime)


class ScraplingParserNoCredentialLeakageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ScraplingParserRuntime()

    def test_no_credentials_in_error_messages(self) -> None:
        """Error messages must not contain proxy credentials."""
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="bad", selector=">>>invalid<<<", selector_type="css"),
        ])
        result = results[0]
        # Error should contain the selector info but no credentials
        self.assertNotIn("secret", result.error.lower())
        self.assertNotIn("password", result.error.lower())
        self.assertNotIn("token", result.error.lower())


if __name__ == "__main__":
    unittest.main()
