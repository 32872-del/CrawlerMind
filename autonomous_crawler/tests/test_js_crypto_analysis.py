"""Tests for JS crypto/signature evidence analysis."""
from __future__ import annotations

import unittest

from autonomous_crawler.tools.js_crypto_analysis import analyze_js_crypto


SIGNATURE_JS = """
function signRequest(params) {
  const keys = Object.keys(params).sort();
  const query = keys.map(k => k + "=" + encodeURIComponent(params[k])).join("&");
  const ts = Date.now();
  const nonce = randomString(16);
  return md5(query + ts + nonce + SECRET);
}
"""

WEBCRYPTO_JS = """
async function signPayload(payload, key) {
  const data = new TextEncoder().encode(payload);
  const signature = await crypto.subtle.sign("HMAC", key, data);
  return btoa(String.fromCharCode(...new Uint8Array(signature)));
}
"""

ENCRYPTION_JS = """
const iv = crypto.getRandomValues(new Uint8Array(16));
const encrypted = CryptoJS.AES.encrypt(JSON.stringify(body), key, { iv });
const rsa = new JSEncrypt();
rsa.setPublicKey(publicKey);
"""

CUSTOM_TOKEN_JS = """
function getWbiKey(imgKey, subKey) { return imgKey + subKey; }
function signWbi(params, wbiKey) {
  return md5(Object.keys(params).sort().map(k => `${k}=${params[k]}`).join("&") + wbiKey);
}
const xBogus = computeXBogus(url, data);
"""

HARMLESS_JS = """
function add(a, b) { return a + b; }
const name = "shirt";
"""


class JsCryptoAnalysisTests(unittest.TestCase):
    def test_detects_signature_flow(self) -> None:
        report = analyze_js_crypto(SIGNATURE_JS)
        categories = set(report.categories)

        self.assertTrue(report.likely_signature_flow)
        self.assertTrue(report.likely_timestamp_nonce_flow)
        self.assertIn("hash", categories)
        self.assertIn("sorting", categories)
        self.assertIn("query_build", categories)
        self.assertIn("timestamp", categories)
        self.assertIn("nonce", categories)
        self.assertGreaterEqual(report.score, 50)

    def test_detects_webcrypto_sign(self) -> None:
        report = analyze_js_crypto(WEBCRYPTO_JS)
        names = {signal.name for signal in report.signals}

        self.assertIn("subtle.sign", names)
        self.assertIn("base64", names)
        self.assertTrue(any("WebCrypto" in rec for rec in report.recommendations))

    def test_detects_encryption_flow(self) -> None:
        report = analyze_js_crypto(ENCRYPTION_JS)
        categories = set(report.categories)

        self.assertTrue(report.likely_encryption_flow)
        self.assertIn("encryption", categories)
        self.assertIn("webcrypto", categories)
        self.assertGreater(report.score, 40)

    def test_detects_custom_token_flow(self) -> None:
        report = analyze_js_crypto(CUSTOM_TOKEN_JS)
        names = {signal.name for signal in report.signals}

        self.assertIn("xbogus", names)
        self.assertTrue(report.likely_signature_flow)
        self.assertTrue(any("custom token" in rec.lower() for rec in report.recommendations))

    def test_harmless_js_has_low_score(self) -> None:
        report = analyze_js_crypto(HARMLESS_JS)

        self.assertEqual(report.signals, [])
        self.assertFalse(report.likely_signature_flow)
        self.assertLessEqual(report.score, 5)

    def test_report_to_dict_shape(self) -> None:
        report = analyze_js_crypto(SIGNATURE_JS)
        data = report.to_dict()

        self.assertIn("signals", data)
        self.assertIn("categories", data)
        self.assertIn("likely_signature_flow", data)
        self.assertIn("score", data)
        self.assertIsInstance(data["signals"], list)

    def test_context_is_bounded(self) -> None:
        report = analyze_js_crypto("x" * 1000 + SIGNATURE_JS + "y" * 1000)

        self.assertTrue(report.signals)
        self.assertTrue(all(len(signal.context) <= 180 for signal in report.signals))


if __name__ == "__main__":
    unittest.main()
