from __future__ import annotations

import unittest

from autonomous_crawler.tools.js_evidence import build_js_evidence_report


INLINE_HTML = """
<html>
  <head>
    <script>
      const api = "/api/v1/products";
      function signRequest(payload) {
        return crypto.createHmac("sha256", "secret").update(payload);
      }
      fetch(api);
    </script>
  </head>
</html>
"""


class JsEvidenceReportTests(unittest.TestCase):
    def test_inline_html_builds_combined_evidence(self) -> None:
        report = build_js_evidence_report(INLINE_HTML, base_url="https://example.com")
        payload = report.to_dict()

        self.assertEqual(len(payload["items"]), 1)
        item = payload["items"][0]
        self.assertEqual(item["source"], "inline")
        self.assertGreater(item["total_score"], 0)
        self.assertIn("/api/v1/products", payload["top_endpoints"])
        self.assertTrue(any("signature" in value for value in item["keyword_categories"]))
        self.assertTrue(item["crypto_analysis"]["likely_signature_flow"])
        self.assertIn("hash:sha256", payload["top_crypto_signals"])
        self.assertTrue(any("hook analysis" in value for value in payload["recommendations"]))

    def test_captured_js_preview_is_analyzed(self) -> None:
        captured = [{
            "url": "https://example.com/app.js",
            "sha256": "abc",
            "size_bytes": 128,
            "text_preview": 'const endpoint="/graphql"; function tokenSigner(){ return signToken(endpoint); }',
        }]

        report = build_js_evidence_report("", captured_js_assets=captured)
        payload = report.to_dict()
        item = payload["items"][0]

        self.assertEqual(item["source"], "captured")
        self.assertEqual(item["url"], "https://example.com/app.js")
        self.assertEqual(item["sha256"], "abc")
        self.assertIn("/graphql", payload["top_endpoints"])
        self.assertTrue(item["suspicious_functions"])
        self.assertTrue(item["suspicious_calls"])
        self.assertIn("crypto_analysis", item)
        self.assertIn("top_crypto_signals", payload)

    def test_captured_js_crypto_signature_flow_is_reported(self) -> None:
        captured = [{
            "url": "https://example.com/app.js",
            "text_preview": (
                "function signRequest(params){"
                "const query=Object.keys(params).sort().map(k=>k+'='+params[k]).join('&');"
                "const nonce=randomString(16);"
                "return md5(query+Date.now()+nonce);"
                "}"
            ),
        }]

        report = build_js_evidence_report("", captured_js_assets=captured)
        payload = report.to_dict()
        item = payload["items"][0]

        self.assertTrue(item["crypto_analysis"]["likely_signature_flow"])
        self.assertTrue(item["crypto_analysis"]["likely_timestamp_nonce_flow"])
        self.assertIn("hash:md5", payload["top_crypto_signals"])
        self.assertTrue(any("signature" in value.lower() for value in payload["recommendations"]))

    def test_captured_metadata_without_text_is_kept_but_not_ranked_high(self) -> None:
        report = build_js_evidence_report("", captured_js_assets=[{
            "url": "https://example.com/vendor.js",
            "sha256": "def",
            "size_bytes": 1000,
        }])
        item = report.to_dict()["items"][0]

        self.assertEqual(item["source"], "captured")
        self.assertEqual(item["total_score"], 0)
        self.assertIn("captured_js_metadata_only", item["reasons"])

    def test_max_items_limits_output_after_sorting(self) -> None:
        captured = [
            {"url": "https://example.com/a.js", "text_preview": 'function signA(){return signToken("/api/a")}'},
            {"url": "https://example.com/b.js", "text_preview": 'console.log("hello")'},
        ]

        report = build_js_evidence_report("", captured_js_assets=captured, max_items=1)
        payload = report.to_dict()

        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["url"], "https://example.com/a.js")


if __name__ == "__main__":
    unittest.main()
