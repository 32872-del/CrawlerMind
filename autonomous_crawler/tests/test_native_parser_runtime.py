"""Tests for NativeParserRuntime (SCRAPLING-ABSORB-1).

Verifies CLM-native parser using lxml/cssselect/re matches
ScraplingParserRuntime behaviour on the same fixtures.
No network required — all tests use local HTML strings.
"""
from __future__ import annotations

import unittest

from autonomous_crawler.runtime.models import RuntimeSelectorRequest, RuntimeSelectorResult
from autonomous_crawler.runtime.native_parser import NativeParserRuntime


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


# ======================================================================
# CSS extraction
# ======================================================================

class NativeParserCssTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

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


# ======================================================================
# XPath extraction
# ======================================================================

class NativeParserXpathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

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

    def test_xpath_attribute_direct(self) -> None:
        """XPath returning attribute strings directly (not elements)."""
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="ids", selector="//div[@class='card']/@data-id", selector_type="xpath",
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 3)
        self.assertIn("1", result.values)
        self.assertIn("2", result.values)

    def test_xpath_many_false(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="first", selector="//div[@class='card']//h2", selector_type="xpath", many=False,
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 1)

    def test_xpath_miss_returns_empty(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="nope", selector="//div[@class='none']", selector_type="xpath"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 0)


# ======================================================================
# Text extraction
# ======================================================================

class NativeParserTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

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

    def test_text_case_insensitive(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="ci", selector="widget a", selector_type="text"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertGreaterEqual(result.matched, 1)

    def test_text_empty_selector_returns_empty(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="empty", selector="", selector_type="text"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 0)

    def test_text_many_false(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="one", selector="Widget", selector_type="text", many=False),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 1)


# ======================================================================
# Regex extraction
# ======================================================================

class NativeParserRegexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

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

    def test_regex_many_false(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(
                name="one_price", selector=r"\$[\d.]+", selector_type="regex", many=False,
            ),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 1)


# ======================================================================
# Error handling
# ======================================================================

class NativeParserErrorHandlingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

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
        # Empty HTML returns 0 matches with no error
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

    def test_url_passed_through(self) -> None:
        results = self.parser.parse(
            _FIXTURE_HTML,
            [RuntimeSelectorRequest(name="title", selector=".card .title", selector_type="css")],
            url="https://shop.example.com/catalog",
        )
        self.assertTrue(results[0].ok)

    def test_invalid_xpath_does_not_crash(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="bad", selector="//[@@@", selector_type="xpath"),
        ])
        result = results[0]
        self.assertFalse(result.ok)
        self.assertIn("error", result.error.lower())


# ======================================================================
# Protocol satisfaction
# ======================================================================

class NativeParserProtocolTests(unittest.TestCase):
    def test_satisfies_parser_runtime_protocol(self) -> None:
        from autonomous_crawler.runtime.protocols import ParserRuntime
        runtime = NativeParserRuntime()
        self.assertIsInstance(runtime, ParserRuntime)

    def test_name_is_native_parser(self) -> None:
        runtime = NativeParserRuntime()
        self.assertEqual(runtime.name, "native_parser")


# ======================================================================
# No credential leakage
# ======================================================================

class NativeParserNoCredentialLeakageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

    def test_no_credentials_in_error_messages(self) -> None:
        results = self.parser.parse(_FIXTURE_HTML, [
            RuntimeSelectorRequest(name="bad", selector=">>>invalid<<<", selector_type="css"),
        ])
        result = results[0]
        self.assertNotIn("secret", result.error.lower())
        self.assertNotIn("password", result.error.lower())
        self.assertNotIn("token", result.error.lower())


# ======================================================================
# Native-specific: deep text extraction
# ======================================================================

class NativeParserDeepTextTests(unittest.TestCase):
    """Verify text_content() correctly concatenates nested text nodes."""

    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

    def test_nested_text_concatenated(self) -> None:
        html_text = "<html><body><div><span>Hello</span> <span>World</span></div></body></html>"
        results = self.parser.parse(html_text, [
            RuntimeSelectorRequest(name="greeting", selector="div", selector_type="css"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.matched, 1)
        self.assertIn("Hello", result.values[0])
        self.assertIn("World", result.values[0])

    def test_deeply_nested_text(self) -> None:
        html_text = "<html><body><div><p><span><b>Deep</b> text</span></p></div></body></html>"
        results = self.parser.parse(html_text, [
            RuntimeSelectorRequest(name="deep", selector="div", selector_type="css"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertIn("Deep", result.values[0])
        self.assertIn("text", result.values[0])


# ======================================================================
# Native-specific: element ordering
# ======================================================================

class NativeParserOrderingTests(unittest.TestCase):
    """Verify elements are returned in document order."""

    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

    def test_document_order_preserved(self) -> None:
        html_text = """<html><body>
            <ul>
                <li class="item">First</li>
                <li class="item">Second</li>
                <li class="item">Third</li>
            </ul>
        </body></html>"""
        results = self.parser.parse(html_text, [
            RuntimeSelectorRequest(name="items", selector=".item", selector_type="css"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.values, ["First", "Second", "Third"])


# ======================================================================
# Native-specific: special characters
# ======================================================================

class NativeParserSpecialCharsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = NativeParserRuntime()

    def test_unicode_text(self) -> None:
        html_text = "<html><body><p>日本語テスト</p></body></html>"
        results = self.parser.parse(html_text, [
            RuntimeSelectorRequest(name="jp", selector="p", selector_type="css"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.values[0], "日本語テスト")

    def test_html_entities_decoded(self) -> None:
        html_text = "<html><body><p>Price: &amp;100 &lt;200&gt;</p></body></html>"
        results = self.parser.parse(html_text, [
            RuntimeSelectorRequest(name="entity", selector="p", selector_type="css"),
        ])
        result = results[0]
        self.assertTrue(result.ok, result.error)
        self.assertIn("&100", result.values[0])
        self.assertIn("<200>", result.values[0])


# ======================================================================
# Parity with ScraplingParserRuntime
# ======================================================================

class NativeParserParityTests(unittest.TestCase):
    """Verify NativeParserRuntime matches ScraplingParserRuntime on same inputs."""

    def setUp(self) -> None:
        self.native = NativeParserRuntime()
        from autonomous_crawler.runtime.scrapling_parser import ScraplingParserRuntime
        self.scrapling = ScraplingParserRuntime()

    def _assert_parity(self, sel_req: RuntimeSelectorRequest) -> None:
        native_results = self.native.parse(_FIXTURE_HTML, [sel_req])
        scrapling_results = self.scrapling.parse(_FIXTURE_HTML, [sel_req])
        n = native_results[0]
        s = scrapling_results[0]
        self.assertEqual(n.ok, s.ok, f"ok mismatch: native={n.error} scrapling={s.error}")
        self.assertEqual(n.matched, s.matched, f"matched mismatch: {n.matched} vs {s.matched}")
        if n.ok:
            # Values should be equivalent (order may differ for some edge cases)
            self.assertEqual(set(n.values), set(s.values),
                             f"values mismatch: {n.values} vs {s.values}")

    def test_parity_css_titles(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="title", selector=".card .title", selector_type="css",
        ))

    def test_parity_css_attribute(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="link", selector=".card a", selector_type="css", attribute="href",
        ))

    def test_parity_xpath_titles(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="title", selector="//div[@class='card']//h2", selector_type="xpath",
        ))

    def test_parity_xpath_predicate(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="first", selector="//div[@class='card'][1]//h2", selector_type="xpath",
        ))

    def test_parity_text_partial(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="partial", selector="Widget", selector_type="text",
        ))

    def test_parity_text_no_match(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="nope", selector="NonexistentText12345", selector_type="text",
        ))

    def test_parity_regex_prices(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="prices", selector=r"\$[\d.]+", selector_type="regex",
        ))

    def test_parity_regex_year(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="year", selector=r"Copyright (\d{4})", selector_type="regex",
        ))

    def test_parity_regex_no_match(self) -> None:
        self._assert_parity(RuntimeSelectorRequest(
            name="nope", selector=r"ZZZZZ\d+", selector_type="regex",
        ))

    def test_parity_empty_html(self) -> None:
        native_results = self.native.parse("", [
            RuntimeSelectorRequest(name="title", selector=".title", selector_type="css"),
        ])
        scrapling_results = self.scrapling.parse("", [
            RuntimeSelectorRequest(name="title", selector=".title", selector_type="css"),
        ])
        self.assertEqual(native_results[0].ok, scrapling_results[0].ok)
        self.assertEqual(native_results[0].matched, scrapling_results[0].matched)


if __name__ == "__main__":
    unittest.main()
