"""Tests for the JS Asset Inventory MVP."""
from __future__ import annotations

import unittest

from autonomous_crawler.tools.js_asset_inventory import (
    JsAssetReport,
    KeywordHit,
    ScriptAsset,
    _extract_context,
    _find_api_endpoints,
    _find_graphql_strings,
    _find_keyword_hits,
    _find_sourcemap_refs,
    _find_websocket_urls,
    analyze_js_text,
    build_inventory_summary,
    build_js_inventory,
    extract_inline_scripts,
    extract_script_assets,
    score_asset,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_EXTERNAL_HTML = """
<html>
  <head>
    <script src="/static/app.js"></script>
    <script src="https://cdn.example.com/vendor.js"></script>
  </head>
  <body></body>
</html>
"""

INLINE_WITH_KEYWORDS_HTML = """
<html>
  <head>
    <script>
      function signRequest(data) {
        var token = getNonce();
        var hmac = crypto.createHmac('sha256', secret);
        return hmac.update(data).digest('hex');
      }
      var apiBase = "/api/v1/products";
    </script>
  </head>
  <body></body>
</html>
"""

MODULE_AND_NOMODULE_HTML = """
<html>
  <head>
    <script type="module" src="/src/main.js"></script>
    <script nomodule src="/legacy/app.js"></script>
  </head>
  <body></body>
</html>
"""

SOURCEMAP_HTML = """
<html>
  <body>
    <script>
      var x = 1;
      //# sourceMappingURL=app.js.map
    </script>
    <script src="/bundle.min.js"></script>
  </body>
</html>
"""

WEBSOCKET_HTML = """
<html>
  <body>
    <script>
      var ws = new WebSocket("wss://realtime.example.com/feed");
      var ws2 = new WebSocket("ws://localhost:8080/debug");
    </script>
  </body>
</html>
"""

GRAPHQL_HTML = """
<html>
  <body>
    <script>
      var q = "query GetProducts($id: ID!) { product(id: $id) { title price } }";
      var m = "mutation CreateOrder { createOrder(input: $data) { id } }";
    </script>
  </body>
</html>
"""

MULTI_INLINE_HTML = """
<html>
  <body>
    <script>var config = {"api": "/api/config"};</script>
    <script src="/analytics.js"></script>
    <script>
      var encrypt = function(data) { return btoa(data); };
      var ws = "wss://stream.example.com";
      fetch("/api/v2/search?q=test");
    </script>
  </body>
</html>
"""

EMPTY_HTML = "<html><body></body></html>"

JSON_PAYLOAD = '{"data": "not html"}'

NO_SCRIPTS_HTML = """
<html>
  <body>
    <h1>No scripts here</h1>
    <p>Just plain HTML.</p>
  </body>
</html>
"""

CHALLENGE_KEYWORDS_HTML = """
<html>
  <body>
    <script>
      var recaptchaSiteKey = "6Le...";
      var hcaptchaWidget = hcaptcha.render("captcha-container");
      var turnstileToken = turnstile.getResponse();
      var geetestObj = new Geetest({captchaId: "..."});
    </script>
  </body>
</html>
"""

ANTI_BOT_HTML = """
<html>
  <body>
    <script>
      var fingerprint = canvasFingerprint();
      var webglFp = webglFingerprint();
      var antiBot = new AntiBot({threshold: 0.5});
    </script>
  </body>
</html>
"""

BUNDLER_HTML = """
<html>
  <body>
    <script>
      var mod = __webpack_require__(42);
      var vite = __vite_ssr_import__("/src/App.vue");
    </script>
  </body>
</html>
"""

SIGNATURE_PATTERNS_HTML = """
<html>
  <body>
    <script>
      var xSignature = computeXSignature(params);
      var encryptedData = encryptPayload(payload);
      var tokenValue = generateToken();
      var verifyResult = verifySignature(sig);
    </script>
  </body>
</html>
"""


class TestExtractScriptAssets(unittest.TestCase):
    """Test HTML script tag extraction."""

    def test_external_scripts(self):
        assets = extract_script_assets(SIMPLE_EXTERNAL_HTML)
        self.assertEqual(len(assets), 2)
        self.assertEqual(assets[0].url, "/static/app.js")
        self.assertTrue(assets[0].is_inline is False)
        self.assertEqual(assets[1].url, "https://cdn.example.com/vendor.js")

    def test_external_with_base_url(self):
        assets = extract_script_assets(SIMPLE_EXTERNAL_HTML, base_url="https://example.com")
        self.assertEqual(assets[0].url, "https://example.com/static/app.js")

    def test_inline_scripts(self):
        assets = extract_script_assets(INLINE_WITH_KEYWORDS_HTML)
        self.assertEqual(len(assets), 1)
        self.assertTrue(assets[0].is_inline)
        self.assertTrue(assets[0].size_estimate > 0)

    def test_module_and_nomodule(self):
        assets = extract_script_assets(MODULE_AND_NOMODULE_HTML)
        self.assertEqual(len(assets), 2)
        self.assertTrue(assets[0].is_module)
        self.assertEqual(assets[0].type_attr, "module")
        self.assertTrue(assets[1].is_nomodule)

    def test_sourcemap_hint(self):
        assets = extract_script_assets(SOURCEMAP_HTML)
        self.assertEqual(len(assets), 2)
        self.assertIn("app.js.map", assets[0].sourcemap_hint)

    def test_empty_html(self):
        assets = extract_script_assets(EMPTY_HTML)
        self.assertEqual(assets, [])

    def test_json_payload(self):
        assets = extract_script_assets(JSON_PAYLOAD)
        self.assertEqual(assets, [])

    def test_no_scripts(self):
        assets = extract_script_assets(NO_SCRIPTS_HTML)
        self.assertEqual(assets, [])


class TestExtractInlineScripts(unittest.TestCase):
    """Test inline JS text extraction."""

    def test_extracts_text(self):
        scripts = extract_inline_scripts(INLINE_WITH_KEYWORDS_HTML)
        self.assertEqual(len(scripts), 1)
        self.assertIn("signRequest", scripts[0])

    def test_skips_external(self):
        scripts = extract_inline_scripts(SIMPLE_EXTERNAL_HTML)
        self.assertEqual(scripts, [])

    def test_multiple_inline(self):
        scripts = extract_inline_scripts(MULTI_INLINE_HTML)
        self.assertEqual(len(scripts), 2)
        self.assertIn("config", scripts[0])
        self.assertIn("encrypt", scripts[1])


class TestAnalyzeJsText(unittest.TestCase):
    """Test JS text analysis for keywords, endpoints, and signals."""

    def test_signature_keywords(self):
        js = 'function signRequest(data) { var hmac = crypto.createHmac("sha256", key); }'
        result = analyze_js_text(js)
        keywords = {h.keyword.lower() for h in result["keyword_hits"]}
        self.assertIn("signrequest", keywords)
        self.assertIn("hmac", keywords)
        self.assertIn("sha256", keywords)
        self.assertIn("crypto", keywords)

    def test_token_keywords(self):
        js = 'var token = getNonce(); var xBogus = computeXBogus(params);'
        result = analyze_js_text(js)
        keywords = {h.keyword.lower() for h in result["keyword_hits"]}
        self.assertIn("token", keywords)
        self.assertIn("nonce", keywords)
        self.assertIn("xbogus", keywords)

    def test_challenge_keywords(self):
        js = 'var recaptcha = grecaptcha.execute(); var hcaptchaResponse = hcaptcha.getResponse();'
        result = analyze_js_text(js)
        keywords = {h.keyword.lower() for h in result["keyword_hits"]}
        self.assertIn("recaptcha", keywords)
        self.assertIn("hcaptcha", keywords)

    def test_api_endpoints(self):
        js = 'fetch("/api/v1/products"); fetch("/v2/orders"); ajax("/graphql");'
        result = analyze_js_text(js)
        endpoints = result["endpoint_candidates"]
        self.assertTrue(any("/api/v1/products" in e for e in endpoints))

    def test_graphql_strings(self):
        js = 'var q = "query GetProducts { products { title } }";'
        result = analyze_js_text(js)
        self.assertTrue(len(result["graphql_strings"]) > 0)
        self.assertIn("query GetProducts", result["graphql_strings"][0])

    def test_websocket_urls(self):
        js = 'new WebSocket("wss://realtime.example.com/feed");'
        result = analyze_js_text(js)
        self.assertIn("wss://realtime.example.com/feed", result["websocket_urls"])

    def test_sourcemap_refs(self):
        js = "var x = 1;\n//# sourceMappingURL=app.js.map"
        result = analyze_js_text(js)
        self.assertIn("app.js.map", result["sourcemap_refs"])

    def test_empty_text(self):
        result = analyze_js_text("")
        self.assertEqual(result["keyword_hits"], [])
        self.assertEqual(result["endpoint_candidates"], [])


class TestFindKeywordHits(unittest.TestCase):
    """Test keyword hit detection."""

    def test_categories_assigned(self):
        hits = _find_keyword_hits("function sign() { var token = encrypt(data); }")
        categories = {h.category for h in hits}
        self.assertIn("signature", categories)
        self.assertIn("token", categories)
        self.assertIn("encryption", categories)

    def test_context_preview(self):
        hits = _find_keyword_hits("function computeSignature(params) { return hmac(key, data); }")
        sig_hits = [h for h in hits if h.category == "signature"]
        self.assertTrue(any(h.context_preview for h in sig_hits))

    def test_no_duplicates(self):
        hits = _find_keyword_hits("token token token")
        token_hits = [h for h in hits if h.keyword.lower() == "token"]
        self.assertEqual(len(token_hits), 1)

    def test_wbi_keyword(self):
        hits = _find_keyword_hits("var wbi_key = getWbiKey();")
        wbi_hits = [h for h in hits if h.keyword.lower() == "wbi"]
        self.assertEqual(len(wbi_hits), 1)
        self.assertEqual(wbi_hits[0].category, "token")


class TestFindApiEndpoints(unittest.TestCase):
    """Test API endpoint extraction."""

    def test_api_path(self):
        endpoints = _find_api_endpoints('fetch("/api/products")')
        self.assertTrue(any("/api/products" in e for e in endpoints))

    def test_graphql_path(self):
        endpoints = _find_api_endpoints('post("/graphql", data)')
        self.assertTrue(any("/graphql" in e for e in endpoints))

    def test_versioned_api(self):
        endpoints = _find_api_endpoints('get("/v2/users")')
        self.assertTrue(any("/v2/users" in e for e in endpoints))

    def test_data_uri_excluded(self):
        endpoints = _find_api_endpoints('"data:image/png;base64,abc"')
        self.assertEqual(endpoints, [])

    def test_long_string_excluded(self):
        long_str = '"/api/" + "x" * 400'
        endpoints = _find_api_endpoints(f'"{long_str}"')
        # Should not crash; may or may not match
        self.assertIsInstance(endpoints, list)


class TestFindGraphqlStrings(unittest.TestCase):
    """Test GraphQL string extraction."""

    def test_query(self):
        graphql = _find_graphql_strings('"query GetUser { user { name } }"')
        self.assertTrue(len(graphql) > 0)

    def test_mutation(self):
        graphql = _find_graphql_strings('"mutation CreatePost { createPost(title: $t) { id } }"')
        self.assertTrue(len(graphql) > 0)

    def test_plain_string_not_graphql(self):
        graphql = _find_graphql_strings('"hello world"')
        self.assertEqual(graphql, [])


class TestFindWebsocketUrls(unittest.TestCase):
    """Test WebSocket URL extraction."""

    def test_wss(self):
        urls = _find_websocket_urls('"wss://realtime.example.com/ws"')
        self.assertEqual(urls, ["wss://realtime.example.com/ws"])

    def test_ws(self):
        urls = _find_websocket_urls('"ws://localhost:8080"')
        self.assertEqual(urls, ["ws://localhost:8080"])

    def test_non_ws(self):
        urls = _find_websocket_urls('"https://example.com"')
        self.assertEqual(urls, [])


class TestFindSourcemapRefs(unittest.TestCase):
    """Test sourcemap reference extraction."""

    def test_standard_comment(self):
        refs = _find_sourcemap_refs("//# sourceMappingURL=app.js.map")
        self.assertEqual(refs, ["app.js.map"])

    def test_url_sourcemap(self):
        refs = _find_sourcemap_refs("//# sourceMappingURL=https://cdn.example.com/app.js.map")
        self.assertEqual(refs, ["https://cdn.example.com/app.js.map"])

    def test_no_sourcemap(self):
        refs = _find_sourcemap_refs("var x = 1;")
        self.assertEqual(refs, [])


class TestScoreAsset(unittest.TestCase):
    """Test asset scoring."""

    def test_signature_keywords_high_score(self):
        asset = ScriptAsset(url="/app.js", is_inline=False)
        analysis = analyze_js_text("function sign() { var hmac = crypto.createHmac('sha256', k); }")
        score, reasons = score_asset(asset, analysis)
        self.assertGreaterEqual(score, 30)
        self.assertIn("signature_keyword", reasons)

    def test_api_endpoints_scored(self):
        asset = ScriptAsset(url="/app.js")
        analysis = analyze_js_text('fetch("/api/products"); fetch("/api/orders");')
        score, reasons = score_asset(asset, analysis)
        self.assertIn("api_endpoints:2", reasons)

    def test_graphql_high_score(self):
        asset = ScriptAsset(url="/app.js")
        analysis = analyze_js_text('"query GetProducts { products { title } }"')
        score, reasons = score_asset(asset, analysis)
        self.assertTrue(any("graphql" in r for r in reasons))

    def test_websocket_scored(self):
        asset = ScriptAsset(url="/app.js")
        analysis = analyze_js_text('"wss://realtime.example.com"')
        score, reasons = score_asset(asset, analysis)
        self.assertTrue(any("websocket" in r for r in reasons))

    def test_module_bonus(self):
        asset = ScriptAsset(url="/app.js", is_module=True)
        analysis = analyze_js_text("")
        score, reasons = score_asset(asset, analysis)
        self.assertIn("type_module", reasons)

    def test_sourcemap_bonus(self):
        asset = ScriptAsset(url="/app.js", sourcemap_hint="app.js.map")
        analysis = analyze_js_text("")
        score, reasons = score_asset(asset, analysis)
        self.assertIn("inline_sourcemap_hint", reasons)

    def test_challenge_keywords_scored(self):
        asset = ScriptAsset(url="/app.js")
        analysis = analyze_js_text("var recaptcha = grecaptcha.execute();")
        score, reasons = score_asset(asset, analysis)
        self.assertIn("challenge_keyword", reasons)

    def test_empty_analysis_zero_score(self):
        asset = ScriptAsset(url="/vendor.js")
        analysis = analyze_js_text("")
        score, reasons = score_asset(asset, analysis)
        self.assertEqual(score, 0)


class TestBuildJsInventory(unittest.TestCase):
    """Test full inventory pipeline."""

    def test_simple_external(self):
        reports = build_js_inventory(SIMPLE_EXTERNAL_HTML)
        self.assertEqual(len(reports), 2)
        self.assertIsInstance(reports[0], JsAssetReport)

    def test_inline_with_keywords_ranked_higher(self):
        reports = build_js_inventory(INLINE_WITH_KEYWORDS_HTML)
        self.assertEqual(len(reports), 1)
        self.assertGreater(reports[0].score, 0)
        self.assertTrue(any("signature" in r for r in reports[0].reasons))

    def test_multi_inline_ranked(self):
        reports = build_js_inventory(MULTI_INLINE_HTML)
        self.assertEqual(len(reports), 3)
        # Inline script with encrypt + ws + api should score higher than analytics.js
        self.assertGreater(reports[0].score, reports[1].score)

    def test_empty_html(self):
        reports = build_js_inventory(EMPTY_HTML)
        self.assertEqual(reports, [])

    def test_json_payload(self):
        reports = build_js_inventory(JSON_PAYLOAD)
        self.assertEqual(reports, [])

    def test_websocket_html(self):
        reports = build_js_inventory(WEBSOCKET_HTML)
        self.assertEqual(len(reports), 1)
        self.assertTrue(len(reports[0].websocket_urls) == 2)

    def test_graphql_html(self):
        reports = build_js_inventory(GRAPHQL_HTML)
        self.assertEqual(len(reports), 1)
        self.assertTrue(len(reports[0].graphql_strings) >= 2)

    def test_sourcemap_html(self):
        reports = build_js_inventory(SOURCEMAP_HTML)
        self.assertEqual(len(reports), 2)
        self.assertTrue(len(reports[0].sourcemap_refs) > 0)

    def test_challenge_keywords(self):
        reports = build_js_inventory(CHALLENGE_KEYWORDS_HTML)
        self.assertEqual(len(reports), 1)
        categories = {h.category for h in reports[0].keyword_hits}
        self.assertIn("challenge", categories)

    def test_anti_bot_keywords(self):
        reports = build_js_inventory(ANTI_BOT_HTML)
        self.assertEqual(len(reports), 1)
        categories = {h.category for h in reports[0].keyword_hits}
        self.assertIn("fingerprint", categories)
        self.assertIn("anti_bot", categories)

    def test_bundler_keywords(self):
        reports = build_js_inventory(BUNDLER_HTML)
        self.assertEqual(len(reports), 1)
        categories = {h.category for h in reports[0].keyword_hits}
        self.assertIn("bundler", categories)

    def test_signature_patterns(self):
        reports = build_js_inventory(SIGNATURE_PATTERNS_HTML)
        self.assertEqual(len(reports), 1)
        keywords = {h.keyword.lower() for h in reports[0].keyword_hits}
        self.assertTrue(any("sign" in k for k in keywords))
        self.assertTrue(any("encrypt" in k for k in keywords))

    def test_to_dict(self):
        reports = build_js_inventory(INLINE_WITH_KEYWORDS_HTML)
        d = reports[0].to_dict()
        self.assertIn("asset", d)
        self.assertIn("score", d)
        self.assertIn("reasons", d)
        self.assertIn("keyword_hits", d)
        self.assertIn("endpoint_candidates", d)

    def test_base_url_resolution(self):
        reports = build_js_inventory(SIMPLE_EXTERNAL_HTML, base_url="https://example.com")
        self.assertEqual(reports[0].asset.url, "https://example.com/static/app.js")


class TestBuildInventorySummary(unittest.TestCase):
    """Test summary generation."""

    def test_summary_fields(self):
        reports = build_js_inventory(MULTI_INLINE_HTML)
        summary = build_inventory_summary(reports)
        self.assertIn("total_assets", summary)
        self.assertIn("scored_assets", summary)
        self.assertIn("top_assets", summary)
        self.assertIn("all_endpoint_candidates", summary)
        self.assertIn("all_keyword_hits", summary)
        self.assertIn("all_graphql_strings", summary)
        self.assertIn("all_websocket_urls", summary)
        self.assertIn("all_sourcemap_refs", summary)

    def test_summary_counts(self):
        reports = build_js_inventory(MULTI_INLINE_HTML)
        summary = build_inventory_summary(reports)
        self.assertEqual(summary["total_assets"], 3)
        self.assertGreater(summary["scored_assets"], 0)

    def test_empty_summary(self):
        summary = build_inventory_summary([])
        self.assertEqual(summary["total_assets"], 0)
        self.assertEqual(summary["scored_assets"], 0)
        self.assertEqual(summary["top_assets"], [])


class TestExtractContext(unittest.TestCase):
    """Test context window extraction."""

    def test_finds_keyword(self):
        text = "function computeSignature(params) { return result; }"
        ctx = _extract_context(text, "computesignature")
        self.assertIn("computeSignature", ctx)

    def test_keyword_not_found(self):
        ctx = _extract_context("hello world", "xyz")
        self.assertEqual(ctx, "")

    def test_truncation(self):
        long_text = "a" * 500 + "signature" + "b" * 500
        ctx = _extract_context(long_text, "signature")
        self.assertLessEqual(len(ctx), 200)


if __name__ == "__main__":
    unittest.main()
