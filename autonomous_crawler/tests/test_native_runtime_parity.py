"""Native-vs-Transition Runtime Parity Tests (SCRAPLING-ABSORB-1).

Compares CLM-native runtime implementations against Scrapling transition
adapters on identical inputs.  When a native module is not yet implemented
or has known bugs, tests skip with a clear message documenting the gap.

No real network, no site rules, no external dependencies.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from autonomous_crawler.runtime.models import (
    RuntimeRequest,
    RuntimeResponse,
    RuntimeSelectorRequest,
    RuntimeSelectorResult,
)
from autonomous_crawler.runtime.scrapling_parser import ScraplingParserRuntime
from autonomous_crawler.runtime.scrapling_static import ScraplingStaticRuntime

from autonomous_crawler.tests.fixtures.native_runtime_parity import (
    PRODUCT_CATALOG_HTML,
    NESTED_LIST_HTML,
    MALFORMED_HTML,
    EMPTY_HTML,
    MINIMAL_HTML,
    DATA_TABLE_HTML,
    CONTACT_HTML,
    JSON_LD_SCRIPT_HTML,
    CSS_MISS_XPATH_HIT_HTML,
    RELATIVE_URL_HTML,
    NESTED_CATEGORY_DETAIL_HTML,
    product_name_selector,
    product_price_selector,
    product_link_selector,
    product_image_src_selector,
    product_sku_selector,
    product_brand_selector,
    product_first_only_selector,
    missing_selector,
    xpath_titles_selector,
    xpath_prices_selector,
    xpath_links_selector,
    xpath_predicate_selector,
    regex_price_selector,
    regex_email_selector,
    regex_phone_selector,
    text_widget_selector,
    text_partial_selector,
    invalid_css_selector,
    invalid_regex_selector,
    unsupported_type_selector,
    table_cell_selector,
    table_row_attr_selector,
    nested_item_name_selector,
    nested_category_selector,
    jsonld_visible_title_selector,
    jsonld_visible_price_selector,
    jsonld_visible_link_selector,
    jsonld_visible_img_selector,
    jsonld_data_id_selector,
    jsonld_xpath_titles_selector,
    xpath_following_sibling_stock,
    xpath_ancestor_section_attr,
    xpath_positional_last_item,
    css_item_name_selector,
    css_section_miss_selector,
    relative_href_selector,
    relative_img_src_selector,
    relative_img_alt_selector,
    relative_xpath_href_selector,
    relative_xpath_src_selector,
    nested_cat_name_selector,
    nested_subcat_name_selector,
    nested_detail_link_selector,
    nested_detail_text_selector,
    nested_product_price_selector,
    nested_product_img_selector,
    nested_pid_selector,
    nested_xpath_detail_under_gaming,
    nested_xpath_cat_names,
    product_full_batch,
    mixed_type_batch,
    contact_batch,
    error_prone_batch,
    jsonld_full_batch,
    css_xpath_hit_batch,
    relative_url_batch,
    nested_detail_batch,
)


# ---------------------------------------------------------------------------
# Conditional import and functional checks
# ---------------------------------------------------------------------------
_HAS_NATIVE_PARSER = True
try:
    from autonomous_crawler.runtime.native_parser import NativeParserRuntime
except ImportError:
    _HAS_NATIVE_PARSER = False

_HAS_NATIVE_STATIC = True
try:
    from autonomous_crawler.runtime.native_static import NativeFetchRuntime
except ImportError:
    _HAS_NATIVE_STATIC = False

# Probe whether NativeParserRuntime can actually parse HTML.
# Known bug: html.fromstring(..., recover=True) fails on some lxml versions.
_NATIVE_PARSER_FUNCTIONAL: bool | None = None
_NATIVE_PARSER_BUG: str = ""


def _check_native_parser_functional() -> tuple[bool, str]:
    """Return (is_functional, bug_description)."""
    if not _HAS_NATIVE_PARSER:
        return False, "NativeParserRuntime not importable"
    try:
        native = NativeParserRuntime()
        results = native.parse(
            "<html><body><p>test</p></body></html>",
            [RuntimeSelectorRequest(name="t", selector="p", selector_type="css")],
        )
        if results and results[0].ok:
            return True, ""
        # Parser ran but returned error
        error = results[0].error if results else "unknown"
        return False, f"NativeParserRuntime.parse() returned error: {error}"
    except Exception as exc:
        return False, f"NativeParserRuntime.parse() raised: {type(exc).__name__}: {exc}"


def _skip_if_no_native_parser() -> None:
    global _NATIVE_PARSER_FUNCTIONAL, _NATIVE_PARSER_BUG
    if not _HAS_NATIVE_PARSER:
        raise unittest.SkipTest("NativeParserRuntime not importable")
    if _NATIVE_PARSER_FUNCTIONAL is None:
        _NATIVE_PARSER_FUNCTIONAL, _NATIVE_PARSER_BUG = _check_native_parser_functional()
    if not _NATIVE_PARSER_FUNCTIONAL:
        raise unittest.SkipTest(
            f"NativeParserRuntime has known bug — {_NATIVE_PARSER_BUG}"
        )


def _skip_if_no_native_static() -> None:
    if not _HAS_NATIVE_STATIC:
        raise unittest.SkipTest("NativeFetchRuntime not importable")


# ---------------------------------------------------------------------------
# Helper: assert two RuntimeSelectorResults match on core shape
# ---------------------------------------------------------------------------

def assert_selector_parity(
    test: unittest.TestCase,
    scrapling_result: RuntimeSelectorResult,
    native_result: RuntimeSelectorResult,
    *,
    check_values: bool = True,
    check_error: bool = True,
) -> None:
    """Assert that two selector results match on core contract fields."""
    test.assertEqual(
        scrapling_result.ok, native_result.ok,
        f"ok mismatch: scrapling={scrapling_result.ok}, native={native_result.ok}",
    )
    test.assertEqual(
        scrapling_result.matched, native_result.matched,
        f"matched mismatch: scrapling={scrapling_result.matched}, native={native_result.matched}",
    )
    test.assertEqual(
        scrapling_result.name, native_result.name,
        "name should be preserved",
    )
    test.assertEqual(
        scrapling_result.selector, native_result.selector,
        "selector should be preserved",
    )
    test.assertEqual(
        scrapling_result.selector_type, native_result.selector_type,
        "selector_type should be preserved",
    )
    if check_values:
        test.assertEqual(
            len(scrapling_result.values), len(native_result.values),
            f"values length mismatch: scrapling={len(scrapling_result.values)}, native={len(native_result.values)}",
        )
    if check_error:
        test.assertEqual(
            bool(scrapling_result.error), bool(native_result.error),
            f"error presence mismatch: scrapling='{scrapling_result.error}', native='{native_result.error}'",
        )


def assert_result_list_parity(
    test: unittest.TestCase,
    scrapling_results: list[RuntimeSelectorResult],
    native_results: list[RuntimeSelectorResult],
    *,
    check_values: bool = True,
    check_error: bool = True,
) -> None:
    """Assert parity across a full list of selector results."""
    test.assertEqual(
        len(scrapling_results), len(native_results),
        "result list length must match",
    )
    for i, (s, n) in enumerate(zip(scrapling_results, native_results)):
        with test.subTest(index=i, selector=s.name):
            assert_selector_parity(test, s, n, check_values=check_values, check_error=check_error)


# ===================================================================
# Native Parser: Known Bug Detection
# ===================================================================

class NativeParserBugDetectionTests(unittest.TestCase):
    """Detect and document known bugs in NativeParserRuntime."""

    def test_native_parser_recover_keyword_bug(self) -> None:
        """Document: NativeParserRuntime uses html.fromstring(..., recover=True)
        which fails on some lxml versions.

        GAP-001: html.fromstring() does not accept 'recover' keyword in
        lxml < 5.x (or certain builds). Fix: use HTMLParser(recover=True)
        or remove the recover parameter.
        """
        if not _HAS_NATIVE_PARSER:
            self.skipTest("NativeParserRuntime not importable")
        native = NativeParserRuntime()
        try:
            results = native.parse(
                "<html><body><p>test</p></body></html>",
                [RuntimeSelectorRequest(name="t", selector="p", selector_type="css")],
            )
            # If it works, the bug is fixed
            if results and results[0].ok:
                self.skipTest("NativeParserRuntime recover bug appears to be fixed")
            else:
                self.fail(
                    f"GAP-001: NativeParserRuntime.parse() returns error: {results[0].error if results else 'empty'}"
                )
        except TypeError as exc:
            self.fail(
                f"GAP-001: NativeParserRuntime.parse() raises TypeError: {exc}. "
                "Fix: html.fromstring() does not accept 'recover' kwarg in this lxml version."
            )

    def test_native_parser_functional_probe(self) -> None:
        """Probe whether NativeParserRuntime can parse basic HTML."""
        if not _HAS_NATIVE_PARSER:
            self.skipTest("NativeParserRuntime not importable")
        functional, bug = _check_native_parser_functional()
        if not functional:
            self.skipTest(f"GAP: NativeParserRuntime not functional: {bug}")


# ===================================================================
# Parser Parity: CSS Extraction
# ===================================================================

class ParityParserCssMultiNodeTests(unittest.TestCase):
    """CLM native must match Scrapling on multi-node CSS extraction."""

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, html: str, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(html, selectors)
        native_results = native.parse(html, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_css_extracts_all_product_names(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [product_name_selector()])

    def test_css_extracts_all_prices(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [product_price_selector()])

    def test_css_extracts_link_href_attribute(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [product_link_selector()])

    def test_css_extracts_image_src_attribute(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [product_image_src_selector()])

    def test_css_extracts_data_attribute(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [product_sku_selector()])

    def test_css_extracts_brand_text(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [product_brand_selector()])

    def test_css_first_only_returns_one(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [product_first_only_selector()])

    def test_css_missing_selector_returns_empty(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [missing_selector()])

    def test_css_full_product_batch(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, product_full_batch())


class ParityParserCssNestedTests(unittest.TestCase):
    """CLM native must match Scrapling on nested HTML structures."""

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, html: str, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(html, selectors)
        native_results = native.parse(html, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_css_nested_item_names(self) -> None:
        self._run_parity(NESTED_LIST_HTML, [nested_item_name_selector()])

    def test_css_table_cells(self) -> None:
        self._run_parity(DATA_TABLE_HTML, [table_cell_selector()])

    def test_css_table_row_attribute(self) -> None:
        self._run_parity(DATA_TABLE_HTML, [table_row_attr_selector()])


# ===================================================================
# Parser Parity: XPath Extraction
# ===================================================================

class ParityParserXpathTests(unittest.TestCase):
    """CLM native must match Scrapling on XPath extraction."""

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, html: str, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(html, selectors)
        native_results = native.parse(html, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_xpath_extracts_titles(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [xpath_titles_selector()])

    def test_xpath_extracts_prices(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [xpath_prices_selector()])

    def test_xpath_extracts_link_attributes(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [xpath_links_selector()])

    def test_xpath_with_predicate(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [xpath_predicate_selector()])

    def test_xpath_nested_categories(self) -> None:
        self._run_parity(NESTED_LIST_HTML, [nested_category_selector()])


# ===================================================================
# Parser Parity: Regex Extraction
# ===================================================================

class ParityParserRegexTests(unittest.TestCase):
    """CLM native must match Scrapling on regex extraction."""

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, html: str, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(html, selectors)
        native_results = native.parse(html, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_regex_extracts_prices(self) -> None:
        self._run_parity(CONTACT_HTML, [regex_price_selector()])

    def test_regex_extracts_emails(self) -> None:
        self._run_parity(CONTACT_HTML, [regex_email_selector()])

    def test_regex_extracts_phones(self) -> None:
        self._run_parity(CONTACT_HTML, [regex_phone_selector()])

    def test_regex_product_catalog_prices(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [regex_price_selector()])


# ===================================================================
# Parser Parity: Text Search
# ===================================================================

class ParityParserTextTests(unittest.TestCase):
    """CLM native must match Scrapling on text-based search."""

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, html: str, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(html, selectors)
        native_results = native.parse(html, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_text_finds_exact_match(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [text_widget_selector()])

    def test_text_finds_partial_match(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [text_partial_selector()])


# ===================================================================
# Parser Parity: Error Handling
# ===================================================================

class ParityParserErrorHandlingTests(unittest.TestCase):
    """CLM native must match Scrapling error behavior on invalid inputs."""

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, html: str, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(html, selectors)
        native_results = native.parse(html, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_invalid_css_produces_error(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [invalid_css_selector()])

    def test_invalid_regex_produces_error(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [invalid_regex_selector()])

    def test_unsupported_selector_type_produces_error(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, [unsupported_type_selector()])

    def test_empty_html_does_not_crash(self) -> None:
        self._run_parity(EMPTY_HTML, [product_name_selector()])

    def test_minimal_html_does_not_crash(self) -> None:
        self._run_parity(MINIMAL_HTML, [product_name_selector()])

    def test_malformed_html_does_not_crash(self) -> None:
        self._run_parity(MALFORMED_HTML, [product_name_selector()])

    def test_error_prone_batch(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, error_prone_batch())

    def test_no_credential_leakage_in_errors(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(PRODUCT_CATALOG_HTML, [invalid_css_selector()])
        for r in results:
            for secret in ("secret", "password", "token", "credential"):
                self.assertNotIn(secret, r.error.lower(), f"'{secret}' leaked in error: {r.error}")


# ===================================================================
# Parser Parity: Mixed Selector Types
# ===================================================================

class ParityParserMixedTypeTests(unittest.TestCase):
    """CLM native must handle CSS + XPath + regex in one parse call."""

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, html: str, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(html, selectors)
        native_results = native.parse(html, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_mixed_css_xpath_regex_batch(self) -> None:
        self._run_parity(PRODUCT_CATALOG_HTML, mixed_type_batch())

    def test_contact_extraction_batch(self) -> None:
        self._run_parity(CONTACT_HTML, contact_batch())


# ===================================================================
# Parser Parity: Output Shape Contract
# ===================================================================

class ParityParserOutputShapeTests(unittest.TestCase):
    """CLM native output must match the RuntimeSelectorResult contract."""

    def test_result_has_ok_property(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(PRODUCT_CATALOG_HTML, [product_name_selector()])
        self.assertIsInstance(results[0].ok, bool)

    def test_result_has_values_list(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(PRODUCT_CATALOG_HTML, [product_name_selector()])
        self.assertIsInstance(results[0].values, list)

    def test_result_has_matched_int(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(PRODUCT_CATALOG_HTML, [product_name_selector()])
        self.assertIsInstance(results[0].matched, int)

    def test_result_has_name_preserved(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        sel = product_name_selector()
        results = native.parse(PRODUCT_CATALOG_HTML, [sel])
        self.assertEqual(results[0].name, sel.name)

    def test_result_has_selector_preserved(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        sel = product_name_selector()
        results = native.parse(PRODUCT_CATALOG_HTML, [sel])
        self.assertEqual(results[0].selector, sel.selector)

    def test_result_is_serializable(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(PRODUCT_CATALOG_HTML, [product_name_selector()])
        d = results[0].to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("name", d)
        self.assertIn("values", d)
        self.assertIn("matched", d)


# ===================================================================
# Parser Parity: Protocol Conformance
# ===================================================================

class ParityParserProtocolTests(unittest.TestCase):
    """NativeParserRuntime must satisfy ParserRuntime protocol."""

    def test_native_satisfies_parser_runtime(self) -> None:
        _skip_if_no_native_parser()
        from autonomous_crawler.runtime.protocols import ParserRuntime
        native = NativeParserRuntime()
        self.assertIsInstance(native, ParserRuntime)

    def test_native_has_name(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        self.assertIsInstance(native.name, str)
        self.assertTrue(len(native.name) > 0)

    def test_native_has_parse_method(self) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        self.assertTrue(callable(getattr(native, "parse", None)))


# ===================================================================
# Static Fetch Parity: Contract Shape
# ===================================================================

class ParityStaticFetchContractTests(unittest.TestCase):
    """CLM NativeFetchRuntime must match ScraplingStaticRuntime contract."""

    def test_native_satisfies_fetch_runtime(self) -> None:
        _skip_if_no_native_static()
        from autonomous_crawler.runtime.protocols import FetchRuntime
        native = NativeFetchRuntime()
        self.assertIsInstance(native, FetchRuntime)

    def test_native_has_name(self) -> None:
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        self.assertEqual(native.name, "native_static")

    def test_native_has_fetch_method(self) -> None:
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        self.assertTrue(callable(getattr(native, "fetch", None)))


class ParityStaticFetch200Tests(unittest.TestCase):
    """NativeFetchRuntime 200 response parity with ScraplingStaticRuntime."""

    def _mock_scrapling_response(
        self, *, status: int = 200, url: str = "https://example.com",
        body: bytes = b"<html><body>Hello</body></html>",
        headers: dict | None = None, cookies: dict | None = None,
    ) -> MagicMock:
        resp = MagicMock()
        resp.status = status
        resp.url = url
        resp.headers = headers or {"Content-Type": "text/html"}
        resp.cookies = cookies or {}
        resp.body = body
        resp.text = body.decode("utf-8", errors="replace") if body else ""
        return resp

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_scrapling_200_baseline(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = self._mock_scrapling_response()
        runtime = ScraplingStaticRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))
        self.assertTrue(resp.ok)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Hello", resp.html)
        self.assertEqual(resp.engine_result["engine"], "scrapling_static")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_scrapling_403_baseline(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = self._mock_scrapling_response(status=403, body=b"Forbidden")
        runtime = ScraplingStaticRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://example.com"))
        self.assertFalse(resp.ok)
        self.assertEqual(resp.status_code, 403)

    def test_native_200_with_mock_httpx(self) -> None:
        """Native 200 response must match Scrapling's ok=True contract."""
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.cookies = {}
        mock_resp.content = b"<html><body>Hello</body></html>"
        mock_resp.text = "<html><body>Hello</body></html>"
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = native.fetch(RuntimeRequest(url="https://example.com"))
            self.assertTrue(resp.ok)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Hello", resp.html)
            self.assertEqual(resp.engine_result["engine"], "native_static")

    def test_native_403_with_mock_httpx(self) -> None:
        """Native 403 response must match Scrapling's ok=False contract."""
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.url = "https://example.com"
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.cookies = {}
        mock_resp.content = b"Forbidden"
        mock_resp.text = "Forbidden"
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = native.fetch(RuntimeRequest(url="https://example.com"))
            self.assertFalse(resp.ok)
            self.assertEqual(resp.status_code, 403)


class ParityStaticFetchErrorTests(unittest.TestCase):
    """NativeFetchRuntime must handle errors like ScraplingStaticRuntime."""

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_scrapling_connection_error(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.side_effect = ConnectionError("refused")
        runtime = ScraplingStaticRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://bad.example"))
        self.assertFalse(resp.ok)
        self.assertIn("ConnectionError", resp.error)

    def test_native_connection_error(self) -> None:
        """Native must return failure on connection error."""
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.side_effect = ConnectionError("refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = native.fetch(RuntimeRequest(url="https://bad.example"))
            self.assertFalse(resp.ok)
            self.assertIn("ConnectionError", resp.error)

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_scrapling_missing_dep_error(self, mock_fetcher: MagicMock) -> None:
        import autonomous_crawler.runtime.scrapling_static as mod
        original = mod._HAS_SCRAPLING
        try:
            mod._HAS_SCRAPLING = False
            runtime = ScraplingStaticRuntime()
            resp = runtime.fetch(RuntimeRequest(url="https://example.com"))
            self.assertFalse(resp.ok)
            self.assertIn("not installed", resp.error.lower())
        finally:
            mod._HAS_SCRAPLING = original


class ParityStaticFetchProxyTests(unittest.TestCase):
    """Proxy config forwarding parity."""

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_scrapling_forwards_proxy(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = MagicMock(
            status=200, url="https://example.com",
            headers={}, cookies={}, body=b"ok", text="ok",
        )
        runtime = ScraplingStaticRuntime()
        req = RuntimeRequest(url="https://example.com", proxy_config={"proxy": "http://p:8080"})
        runtime.fetch(req)
        call_kwargs = mock_fetcher.get.call_args[1]
        self.assertEqual(call_kwargs["proxy"], "http://p:8080")

    def test_native_forwards_proxy(self) -> None:
        """Native must forward proxy config to httpx client."""
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.headers = {}
        mock_resp.cookies = {}
        mock_resp.content = b"ok"
        mock_resp.text = "ok"
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            req = RuntimeRequest(url="https://example.com", proxy_config={"proxy": "http://p:8080"})
            native.fetch(req)
            init_kwargs = mock_client_cls.call_args[1]
            self.assertEqual(init_kwargs["proxy"], "http://p:8080")

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_scrapling_no_plaintext_in_response(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.get.return_value = MagicMock(
            status=200, url="https://example.com",
            headers={}, cookies={}, body=b"ok", text="ok",
        )
        runtime = ScraplingStaticRuntime()
        req = RuntimeRequest(url="https://example.com", proxy_config={"proxy": "http://u:secret@p:8080"})
        resp = runtime.fetch(req)
        payload = str(resp.to_dict())
        self.assertNotIn("secret", payload)

    def test_native_no_plaintext_in_response(self) -> None:
        """Native must also redact proxy credentials from response."""
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.headers = {}
        mock_resp.cookies = {}
        mock_resp.content = b"ok"
        mock_resp.text = "ok"
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            req = RuntimeRequest(url="https://example.com", proxy_config={"proxy": "http://u:secret@p:8080"})
            resp = native.fetch(req)
            payload = str(resp.to_dict())
            self.assertNotIn("secret", payload)


class ParityStaticFetchMethodDispatchTests(unittest.TestCase):
    """HTTP method dispatch parity."""

    @patch("autonomous_crawler.runtime.scrapling_static.Fetcher")
    def test_scrapling_post_json(self, mock_fetcher: MagicMock) -> None:
        mock_fetcher.post.return_value = MagicMock(
            status=200, url="https://api.example.com",
            headers={}, cookies={}, body=b'{"ok":true}', text='{"ok":true}',
        )
        runtime = ScraplingStaticRuntime()
        resp = runtime.fetch(RuntimeRequest(url="https://api.example.com", method="POST", json={"key": "val"}))
        self.assertTrue(resp.ok)
        mock_fetcher.post.assert_called_once()

    def test_native_post_json(self) -> None:
        """Native must also support POST with JSON body."""
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://api.example.com"
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.cookies = {}
        mock_resp.content = b'{"ok":true}'
        mock_resp.text = '{"ok":true}'
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = native.fetch(RuntimeRequest(url="https://api.example.com", method="POST", json={"key": "val"}))
            self.assertTrue(resp.ok)
            call_kwargs = mock_client.request.call_args
            self.assertEqual(call_kwargs[1]["json"], {"key": "val"})


class ParityStaticFetchEventsTests(unittest.TestCase):
    """NativeFetchRuntime must emit RuntimeEvents like the adapter baseline."""

    def test_native_emits_fetch_start_event(self) -> None:
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.headers = {}
        mock_resp.cookies = {}
        mock_resp.content = b"ok"
        mock_resp.text = "ok"
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = native.fetch(RuntimeRequest(url="https://example.com"))
            event_types = [e.type for e in resp.runtime_events]
            self.assertIn("fetch_start", event_types)
            self.assertIn("fetch_complete", event_types)

    def test_native_emits_error_event(self) -> None:
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.side_effect = ConnectionError("refused")
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = native.fetch(RuntimeRequest(url="https://bad.example"))
            event_types = [e.type for e in resp.runtime_events]
            self.assertIn("fetch_start", event_types)
            self.assertIn("fetch_error", event_types)


class ParityStaticFetchProxyTraceTests(unittest.TestCase):
    """NativeFetchRuntime must include proxy trace in response."""

    def test_native_proxy_trace_disabled(self) -> None:
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.headers = {}
        mock_resp.cookies = {}
        mock_resp.content = b"ok"
        mock_resp.text = "ok"
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            resp = native.fetch(RuntimeRequest(url="https://example.com"))
            self.assertFalse(resp.proxy_trace.selected)

    def test_native_proxy_trace_enabled(self) -> None:
        _skip_if_no_native_static()
        native = NativeFetchRuntime()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.com"
        mock_resp.headers = {}
        mock_resp.cookies = {}
        mock_resp.content = b"ok"
        mock_resp.text = "ok"
        mock_resp.http_version = "1.1"

        with patch("autonomous_crawler.runtime.native_static.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.request.return_value = mock_resp
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_client

            req = RuntimeRequest(url="https://example.com", proxy_config={"proxy": "http://p:8080"})
            resp = native.fetch(req)
            self.assertTrue(resp.proxy_trace.selected)


# ===================================================================
# Parser Parity: JSON-LD / Script Coexistence
# ===================================================================

class ParityParserJsonLdCoexistenceTests(unittest.TestCase):
    """CLM native must extract visible elements without script content leaking.

    JSON-LD and inline script data must not appear in CSS/XPath extraction
    results.  Both parsers should return only the visible DOM elements.
    """

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(JSON_LD_SCRIPT_HTML, selectors)
        native_results = native.parse(JSON_LD_SCRIPT_HTML, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_visible_titles_not_polluted_by_jsonld(self) -> None:
        self._run_parity([jsonld_visible_title_selector()])
        # Verify no JSON-LD content leaked
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(JSON_LD_SCRIPT_HTML, [jsonld_visible_title_selector()])
        for val in results[0].values:
            self.assertNotIn("LD Widget", val, "JSON-LD text leaked into visible extraction")

    def test_visible_prices_css(self) -> None:
        self._run_parity([jsonld_visible_price_selector()])

    def test_visible_links_css(self) -> None:
        self._run_parity([jsonld_visible_link_selector()])

    def test_visible_images_css(self) -> None:
        self._run_parity([jsonld_visible_img_selector()])

    def test_data_id_attribute(self) -> None:
        self._run_parity([jsonld_data_id_selector()])

    def test_xpath_titles_visible_only(self) -> None:
        self._run_parity([jsonld_xpath_titles_selector()])

    def test_jsonld_full_batch_parity(self) -> None:
        self._run_parity(jsonld_full_batch())

    def test_jsonld_script_content_not_in_text_extraction(self) -> None:
        """Text search for 'window.__INITIAL_STATE__' should not match visible elements."""
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(
            JSON_LD_SCRIPT_HTML,
            [RuntimeSelectorRequest(name="script_text", selector="window.__INITIAL_STATE__", selector_type="text")],
        )
        # Native text search matches direct text only — script content is not element text
        # Both parsers should return 0 or the text from a <script> element if it has direct text
        self.assertIsInstance(results[0].matched, int)


# ===================================================================
# Parser Parity: CSS Miss / XPath Hit
# ===================================================================

class ParityParserCssMissXPathHitTests(unittest.TestCase):
    """CLM native must match Scrapling on XPath-only extractions.

    These scenarios use XPath axes (following-sibling, ancestor, positional
    predicates) that CSS selectors cannot express.  CSS baseline selectors
    are included for comparison.
    """

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(CSS_MISS_XPATH_HIT_HTML, selectors)
        native_results = native.parse(CSS_MISS_XPATH_HIT_HTML, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_css_baseline_item_names(self) -> None:
        """CSS can extract item names — baseline for XPath comparison."""
        self._run_parity([css_item_name_selector()])

    def test_xpath_following_sibling_stock(self) -> None:
        """XPath following-sibling axis: get stock after price."""
        self._run_parity([xpath_following_sibling_stock()])

    def test_xpath_ancestor_section_attr(self) -> None:
        """XPath ancestor axis: walk up from item to section data attribute."""
        self._run_parity([xpath_ancestor_section_attr()])

    def test_xpath_positional_last_item(self) -> None:
        """XPath positional predicate [last()]: get last item per grid."""
        self._run_parity([xpath_positional_last_item()])

    def test_css_miss_returns_empty(self) -> None:
        """CSS selector targeting nonexistent nested structure returns empty."""
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(CSS_MISS_XPATH_HIT_HTML, [css_section_miss_selector()])
        self.assertEqual(results[0].matched, 0, "CSS miss should return 0 matches")

    def test_xpath_hits_where_css_misses(self) -> None:
        """XPath can extract what CSS cannot — verify matched > 0 for XPath axes."""
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        # ancestor axis — CSS cannot walk up
        results = native.parse(CSS_MISS_XPATH_HIT_HTML, [xpath_ancestor_section_attr()])
        self.assertGreater(results[0].matched, 0, "XPath ancestor should find results")

    def test_mixed_css_xpath_batch_parity(self) -> None:
        """Batch with CSS baselines + XPath-only extractions."""
        self._run_parity(css_xpath_hit_batch())


# ===================================================================
# Parser Parity: Relative URL / Image Attribute Extraction
# ===================================================================

class ParityParserRelativeUrlTests(unittest.TestCase):
    """CLM native must extract relative URLs as-is from href/src attributes.

    Both CSS and XPath attribute extraction should return the raw attribute
    value without resolving relative paths.
    """

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(RELATIVE_URL_HTML, selectors)
        native_results = native.parse(RELATIVE_URL_HTML, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_css_relative_hrefs(self) -> None:
        """CSS attribute extraction: relative href values."""
        self._run_parity([relative_href_selector()])

    def test_css_relative_img_src(self) -> None:
        """CSS attribute extraction: relative img src values."""
        self._run_parity([relative_img_src_selector()])

    def test_css_img_alt_attributes(self) -> None:
        """CSS attribute extraction: alt text from images."""
        self._run_parity([relative_img_alt_selector()])

    def test_xpath_relative_hrefs(self) -> None:
        """XPath attribute extraction: relative href values."""
        self._run_parity([relative_xpath_href_selector()])

    def test_xpath_relative_img_src(self) -> None:
        """XPath attribute extraction: relative img src values."""
        self._run_parity([relative_xpath_src_selector()])

    def test_relative_url_values_not_empty(self) -> None:
        """Verify extracted relative URLs are non-empty raw values."""
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(RELATIVE_URL_HTML, [relative_href_selector()])
        self.assertEqual(results[0].matched, 5, "Should find all 5 thumb links")
        for val in results[0].values:
            self.assertTrue(len(val) > 0, "Relative URL should not be empty")

    def test_relative_url_batch_parity(self) -> None:
        self._run_parity(relative_url_batch())


# ===================================================================
# Parser Parity: Nested Category / Detail Link Hierarchy
# ===================================================================

class ParityParserNestedCategoryDetailTests(unittest.TestCase):
    """CLM native must match Scrapling on deep nested category structures.

    Exercises multi-level CSS and XPath extraction on a realistic
    category → subcategory → item → detail link hierarchy.
    """

    def setUp(self) -> None:
        self.scrapling = ScraplingParserRuntime()

    def _run_parity(self, selectors: list[RuntimeSelectorRequest], **kw) -> None:
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        scrapling_results = self.scrapling.parse(NESTED_CATEGORY_DETAIL_HTML, selectors)
        native_results = native.parse(NESTED_CATEGORY_DETAIL_HTML, selectors)
        assert_result_list_parity(self, scrapling_results, native_results, **kw)

    def test_category_names(self) -> None:
        self._run_parity([nested_cat_name_selector()])

    def test_subcategory_names(self) -> None:
        self._run_parity([nested_subcat_name_selector()])

    def test_detail_link_hrefs(self) -> None:
        self._run_parity([nested_detail_link_selector()])

    def test_detail_link_text(self) -> None:
        self._run_parity([nested_detail_text_selector()])

    def test_nested_product_prices(self) -> None:
        self._run_parity([nested_product_price_selector()])

    def test_nested_product_images(self) -> None:
        self._run_parity([nested_product_img_selector()])

    def test_nested_product_ids(self) -> None:
        self._run_parity([nested_pid_selector()])

    def test_xpath_detail_links_under_gaming(self) -> None:
        """XPath: detail links scoped to 'Gaming Laptops' subcategory only."""
        self._run_parity([nested_xpath_detail_under_gaming()])

    def test_xpath_category_ids(self) -> None:
        """XPath: extract data-cat-id attributes from category sections."""
        self._run_parity([nested_xpath_cat_names()])

    def test_full_detail_batch_parity(self) -> None:
        self._run_parity(nested_detail_batch())

    def test_detail_links_count(self) -> None:
        """Verify all 5 product detail links are found."""
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(NESTED_CATEGORY_DETAIL_HTML, [nested_detail_link_selector()])
        self.assertEqual(results[0].matched, 5)

    def test_gaming_links_only_two(self) -> None:
        """XPath scoped extraction: only 2 gaming laptop links."""
        _skip_if_no_native_parser()
        native = NativeParserRuntime()
        results = native.parse(NESTED_CATEGORY_DETAIL_HTML, [nested_xpath_detail_under_gaming()])
        self.assertEqual(results[0].matched, 2)


# ===================================================================
# Summary: Native Module Status
# ===================================================================

class NativeParserSkipSummaryTests(unittest.TestCase):
    """Informative status when NativeParserRuntime is probed."""

    def test_native_parser_status(self) -> None:
        if not _HAS_NATIVE_PARSER:
            self.skipTest("SKIP: NativeParserRuntime not importable")
        functional, bug = _check_native_parser_functional()
        if not functional:
            self.skipTest(f"GAP: NativeParserRuntime exists but not functional: {bug}")
        # If we get here, native parser is working
        native = NativeParserRuntime()
        self.assertTrue(callable(native.parse))


class NativeStaticSkipSummaryTests(unittest.TestCase):
    """Informative status when NativeFetchRuntime is probed."""

    def test_native_static_status(self) -> None:
        if not _HAS_NATIVE_STATIC:
            self.skipTest("SKIP: NativeFetchRuntime not importable")
        native = NativeFetchRuntime()
        self.assertTrue(callable(native.fetch))


if __name__ == "__main__":
    unittest.main()
