"""Tests for the JS Static Analysis MVP."""
from __future__ import annotations

import unittest

from autonomous_crawler.tools.js_static_analysis import (
    CallClue,
    FunctionClue,
    StaticAnalysisReport,
    StringEntry,
    analyze_js_static,
    extract_endpoint_strings,
    extract_functions,
    extract_strings,
    extract_suspicious_calls,
    score_static_analysis,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Simple JS with quoted strings
QUOTED_STRINGS_JS = """
var host = "https://api.example.com";
var path = '/v2/products';
var name = "Alice";
var empty = "";
"""

# Template literals
TEMPLATE_JS = """
var url = `https://api.example.com/products/${id}`;
var msg = `Hello ${name}, welcome!`;
var simple = `no interpolation`;
"""

# URL and API endpoint strings
ENDPOINT_JS = """
fetch("https://api.example.com/v1/products");
fetch('/api/users');
var ws = "wss://realtime.example.com/feed";
var home = "https://example.com";
"""

# Function declarations
FUNC_DECL_JS = """
function computeSignature(data) {
  return hmac(data);
}
function processData(items) {
  return items.map(transform);
}
function encryptPayload(payload) {
  return aes.encrypt(payload);
}
"""

# Arrow and assignment functions
FUNC_ASSIGN_JS = """
const signRequest = (data) => crypto.sign(data);
const verifyToken = (token) => jwt.verify(token);
var transform = function(x) { return x * 2; };
let getToken = () => localStorage.getItem("token");
"""

# Method shorthand
METHOD_JS = """
class ApiClient {
  fetchData(url) { return fetch(url); }
  signPayload(data) { return hmac(data); }
  encrypt(body) { return aes.encrypt(body); }
}
"""

# Suspicious calls
SUSPICIOUS_CALLS_JS = """
var sig = computeHmac(data, key);
var token = generateToken();
var encrypted = encryptPayload(payload);
var valid = verifySignature(sig, data);
var captchaToken = hcaptcha.getResponse();
var fp = getFingerprint();
var result = normalFunction(a, b);
"""

# Minified-ish JS
MINIFIED_JS = 'var a="https://api.example.com/v1";var b="/api/auth";function sign(c){return hmac(c)}var d=encrypt(e);'

# Multiline complex JS
MULTILINE_JS = """
(function() {
  var API_BASE = "https://api.example.com/v1";
  var WS_URL = "wss://stream.example.com/events";

  function signRequest(data) {
    var key = getSecretKey();
    var nonce = generateNonce();
    var signature = hmacSHA256(data + nonce, key);
    return { signature: signature, nonce: nonce };
  }

  const encryptPayload = (payload) => {
    var iv = crypto.getRandomValues(new Uint8Array(16));
    return aesEncrypt(payload, iv);
  };

  function verifyResponse(response) {
    var expected = signRequest(response.body);
    return expected.signature === response.headers["x-signature"];
  }

  var captchaSiteKey = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI";
  var recaptchaToken = grecaptcha.getResponse();

  fetch(API_BASE + "/products", {
    headers: { "Authorization": "Bearer " + getToken() }
  });

  var ws = new WebSocket(WS_URL);
})();
"""

# Harmless JS: no suspicious content
HARMLESS_JS = """
var x = 10;
var y = 20;
function add(a, b) { return a + b; }
function greet(name) { return "Hello, " + name; }
var items = ["apple", "banana", "cherry"];
"""

# Empty JS
EMPTY_JS = ""

# Only comments
COMMENTS_JS = """
// This is a comment
/* block comment */
var x = 1;
"""

# JS with WBI and x-bogus (Bilibili-style)
BILIBILI_STYLE_JS = """
function getWbiKey(imgKey, subKey) {
  var mixinKey = imgKey + subKey;
  return mixinKey.substring(0, 32);
}
function signWbi(params, wbiKey) {
  var sorted = Object.keys(params).sort();
  var query = sorted.map(k => k + "=" + params[k]).join("&");
  return md5(query + wbiKey);
}
var xBogus = computeXBogus(url, data);
"""


class TestExtractStrings(unittest.TestCase):
    """Test string literal extraction."""

    def test_double_quoted(self):
        entries = extract_strings(QUOTED_STRINGS_JS)
        values = [e.value for e in entries]
        self.assertIn("https://api.example.com", values)
        self.assertIn("Alice", values)

    def test_single_quoted(self):
        entries = extract_strings(QUOTED_STRINGS_JS)
        values = [e.value for e in entries]
        self.assertIn("/v2/products", values)

    def test_template_literals(self):
        entries = extract_strings(TEMPLATE_JS)
        values = [e.value for e in entries]
        self.assertTrue(any("https://api.example.com/products/" in v for v in values))
        self.assertIn("no interpolation", values)

    def test_template_interpolation_replaced(self):
        entries = extract_strings(TEMPLATE_JS)
        values = [e.value for e in entries]
        # Interpolation should be replaced with <expr>
        self.assertTrue(any("<expr>" in v for v in values))

    def test_empty_string_skipped(self):
        entries = extract_strings(QUOTED_STRINGS_JS)
        values = [e.value for e in entries]
        self.assertNotIn("", values)

    def test_url_flagged(self):
        entries = extract_strings(ENDPOINT_JS)
        url_entries = [e for e in entries if e.is_url]
        self.assertTrue(len(url_entries) > 0)

    def test_endpoint_flagged(self):
        entries = extract_strings(ENDPOINT_JS)
        endpoint_entries = [e for e in entries if e.is_endpoint]
        endpoint_values = [e.value for e in endpoint_entries]
        self.assertTrue(any("/api/" in v or "/v" in v for v in endpoint_values))

    def test_empty_js(self):
        entries = extract_strings(EMPTY_JS)
        self.assertEqual(entries, [])

    def test_deduplication(self):
        js = 'var a = "hello"; var b = "hello";'
        entries = extract_strings(js)
        hello_count = sum(1 for e in entries if e.value == "hello")
        self.assertEqual(hello_count, 1)

    def test_max_strings_limit(self):
        js = "\n".join(f'var v{i} = "string{i}";' for i in range(100))
        entries = extract_strings(js, max_strings=10)
        self.assertLessEqual(len(entries), 10)


class TestExtractEndpointStrings(unittest.TestCase):
    """Test endpoint/URL string extraction."""

    def test_https_url(self):
        endpoints = extract_endpoint_strings(ENDPOINT_JS)
        self.assertTrue(any("https://api.example.com/v1/products" in e for e in endpoints))

    def test_api_path(self):
        endpoints = extract_endpoint_strings(ENDPOINT_JS)
        self.assertTrue(any("/api/users" in e for e in endpoints))

    def test_websocket(self):
        endpoints = extract_endpoint_strings(ENDPOINT_JS)
        self.assertTrue(any("wss://realtime.example.com/feed" in e for e in endpoints))

    def test_empty(self):
        endpoints = extract_endpoint_strings(EMPTY_JS)
        self.assertEqual(endpoints, [])


class TestExtractFunctions(unittest.TestCase):
    """Test function declaration/assignment extraction."""

    def test_function_declarations(self):
        funcs = extract_functions(FUNC_DECL_JS)
        names = [f.name for f in funcs]
        self.assertIn("computeSignature", names)
        self.assertIn("processData", names)
        self.assertIn("encryptPayload", names)

    def test_declaration_kind(self):
        funcs = extract_functions(FUNC_DECL_JS)
        sig_func = next(f for f in funcs if f.name == "computeSignature")
        self.assertEqual(sig_func.kind, "declaration")

    def test_arrow_functions(self):
        funcs = extract_functions(FUNC_ASSIGN_JS)
        names = [f.name for f in funcs]
        self.assertIn("signRequest", names)
        self.assertIn("verifyToken", names)
        self.assertIn("getToken", names)

    def test_assignment_kind(self):
        funcs = extract_functions(FUNC_ASSIGN_JS)
        transform_func = next(f for f in funcs if f.name == "transform")
        self.assertEqual(transform_func.kind, "assignment")

    def test_arrow_kind(self):
        funcs = extract_functions(FUNC_ASSIGN_JS)
        sign_func = next(f for f in funcs if f.name == "signRequest")
        self.assertEqual(sign_func.kind, "arrow")

    def test_methods(self):
        funcs = extract_functions(METHOD_JS)
        names = [f.name for f in funcs]
        self.assertIn("fetchData", names)
        self.assertIn("signPayload", names)
        self.assertIn("encrypt", names)

    def test_suspicious_flagged(self):
        funcs = extract_functions(FUNC_DECL_JS)
        sig_func = next(f for f in funcs if f.name == "computeSignature")
        self.assertTrue(sig_func.suspicious)
        self.assertEqual(sig_func.suspicion_reason, "signature")

    def test_encryption_flagged(self):
        funcs = extract_functions(FUNC_DECL_JS)
        enc_func = next(f for f in funcs if f.name == "encryptPayload")
        self.assertTrue(enc_func.suspicious)
        self.assertEqual(enc_func.suspicion_reason, "encryption")

    def test_non_suspicious(self):
        funcs = extract_functions(FUNC_DECL_JS)
        proc_func = next(f for f in funcs if f.name == "processData")
        self.assertFalse(proc_func.suspicious)
        self.assertEqual(proc_func.suspicion_reason, "")

    def test_empty_js(self):
        funcs = extract_functions(EMPTY_JS)
        self.assertEqual(funcs, [])


class TestExtractSuspiciousCalls(unittest.TestCase):
    """Test suspicious call extraction."""

    def test_hmac_call(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        hmac_calls = [c for c in calls if c.matched_keyword.lower() in ("hmac", "computehmac")]
        # At least one call containing hmac
        self.assertTrue(any("hmac" in c.matched_keyword.lower() for c in calls))

    def test_token_call(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        self.assertTrue(any("token" in c.matched_keyword.lower() for c in calls))

    def test_encrypt_call(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        self.assertTrue(any("encrypt" in c.matched_keyword.lower() for c in calls))

    def test_verify_call(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        self.assertTrue(any("verify" in c.matched_keyword.lower() for c in calls))

    def test_captcha_call(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        self.assertTrue(any("captcha" in c.matched_keyword.lower() for c in calls))

    def test_fingerprint_call(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        self.assertTrue(any("fingerprint" in c.matched_keyword.lower() for c in calls))

    def test_normal_function_not_suspicious(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        call_keywords = [c.matched_keyword.lower() for c in calls]
        self.assertNotIn("normalfunction", call_keywords)

    def test_category_assigned(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        sig_calls = [c for c in calls if c.category == "signature"]
        self.assertTrue(len(sig_calls) > 0)

    def test_context_present(self):
        calls = extract_suspicious_calls(SUSPICIOUS_CALLS_JS)
        self.assertTrue(any(c.context for c in calls))

    def test_empty_js(self):
        calls = extract_suspicious_calls(EMPTY_JS)
        self.assertEqual(calls, [])


class TestScoreStaticAnalysis(unittest.TestCase):
    """Test scoring logic."""

    def test_endpoint_strings_scored(self):
        entries = [StringEntry(value="/api/products", is_endpoint=True)]
        score, reasons = score_static_analysis(entries, [], [])
        self.assertGreater(score, 0)
        self.assertTrue(any("endpoint" in r for r in reasons))

    def test_suspicious_func_signature(self):
        funcs = [FunctionClue(name="signRequest", kind="declaration", suspicious=True, suspicion_reason="signature")]
        score, reasons = score_static_analysis([], funcs, [])
        self.assertTrue(any("signature" in r for r in reasons))

    def test_suspicious_call_high_score(self):
        calls = [CallClue(call_expression="hmac(data)", matched_keyword="hmac", category="signature")]
        score, reasons = score_static_analysis([], [], calls)
        self.assertGreaterEqual(score, 30)
        self.assertIn("signature_call", reasons)

    def test_empty_analysis_zero(self):
        score, reasons = score_static_analysis([], [], [])
        self.assertEqual(score, 0)

    def test_large_string_table_bonus(self):
        entries = [StringEntry(value=f"str{i}") for i in range(150)]
        score, reasons = score_static_analysis(entries, [], [])
        self.assertTrue(any("large_string_table" in r for r in reasons))


class TestAnalyzeJsStatic(unittest.TestCase):
    """Test full static analysis pipeline."""

    def test_multiline_js(self):
        report = analyze_js_static(MULTILINE_JS)
        self.assertGreater(report.string_count, 0)
        self.assertGreater(report.score, 0)
        self.assertTrue(len(report.suspicious_functions) > 0 or len(report.suspicious_calls) > 0)

    def test_multiline_endpoints(self):
        report = analyze_js_static(MULTILINE_JS)
        # API_BASE is "https://api.example.com/v1" which is a URL string
        self.assertTrue(any("api.example.com" in e for e in report.url_strings))

    def test_multiline_suspicious_funcs(self):
        report = analyze_js_static(MULTILINE_JS)
        names = [f.name for f in report.suspicious_functions]
        self.assertTrue(any("sign" in n.lower() or "encrypt" in n.lower() or "verify" in n.lower() for n in names))

    def test_multiline_suspicious_calls(self):
        report = analyze_js_static(MULTILINE_JS)
        categories = {c.category for c in report.suspicious_calls}
        self.assertTrue(len(categories) > 0)

    def test_minified_js(self):
        report = analyze_js_static(MINIFIED_JS)
        self.assertGreater(report.string_count, 0)
        self.assertTrue(len(report.endpoint_strings) > 0)

    def test_harmless_js(self):
        report = analyze_js_static(HARMLESS_JS)
        # Harmless JS should have low or zero score
        self.assertLessEqual(report.score, 10)
        self.assertEqual(report.suspicious_calls, [])

    def test_empty_js(self):
        report = analyze_js_static(EMPTY_JS)
        self.assertEqual(report.string_count, 0)
        self.assertEqual(report.score, 0)
        self.assertEqual(report.suspicious_functions, [])
        self.assertEqual(report.suspicious_calls, [])

    def test_comments_only(self):
        report = analyze_js_static(COMMENTS_JS)
        self.assertLessEqual(report.score, 5)

    def test_bilibili_style(self):
        report = analyze_js_static(BILIBILI_STYLE_JS)
        names = [f.name for f in report.suspicious_functions]
        self.assertTrue(any("wbi" in n.lower() or "sign" in n.lower() for n in names))
        categories = {c.category for c in report.suspicious_calls}
        self.assertTrue("token" in categories or "signature" in categories)

    def test_to_dict(self):
        report = analyze_js_static(MULTILINE_JS)
        d = report.to_dict()
        self.assertIn("string_count", d)
        self.assertIn("endpoint_strings", d)
        self.assertIn("suspicious_functions", d)
        self.assertIn("suspicious_calls", d)
        self.assertIn("score", d)
        self.assertIn("reasons", d)

    def test_quoted_strings_js(self):
        report = analyze_js_static(QUOTED_STRINGS_JS)
        self.assertGreater(report.string_count, 0)

    def test_endpoint_js(self):
        report = analyze_js_static(ENDPOINT_JS)
        self.assertTrue(len(report.endpoint_strings) > 0 or len(report.url_strings) > 0)

    def test_suspicious_calls_js(self):
        report = analyze_js_static(SUSPICIOUS_CALLS_JS)
        categories = {c.category for c in report.suspicious_calls}
        self.assertIn("signature", categories)
        self.assertIn("token", categories)
        self.assertIn("encryption", categories)

    def test_score_nonzero_for_suspicious(self):
        report = analyze_js_static(SUSPICIOUS_CALLS_JS)
        self.assertGreater(report.score, 0)

    def test_reasons_present(self):
        report = analyze_js_static(MULTILINE_JS)
        self.assertTrue(len(report.reasons) > 0)


if __name__ == "__main__":
    unittest.main()
