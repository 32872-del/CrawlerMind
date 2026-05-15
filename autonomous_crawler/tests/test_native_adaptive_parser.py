"""Tests for CLM-native adaptive parser capabilities."""
from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from lxml import html

from autonomous_crawler.storage.selector_memory import SelectorMemoryStore
from autonomous_crawler.runtime.adaptive_parser import (
    build_element_signature,
    find_similar,
    relocate,
)
from autonomous_crawler.runtime.models import RuntimeSelectorRequest
from autonomous_crawler.runtime.native_parser import NativeParserRuntime


_OLD_HTML = """\
<html><body>
  <main class="catalog">
    <article class="product-card" data-kind="product">
      <h2 class="title">Alpha Jacket</h2>
      <span class="price">$129.90</span>
    </article>
  </main>
</body></html>
"""


_NEW_HTML = """\
<html><body>
  <main class="catalog-v2">
    <article class="product-tile" data-kind="product">
      <h2 class="product-title">Alpha Jacket</h2>
      <span class="amount">$129.90</span>
    </article>
  </main>
</body></html>
"""


_REPEATED_HTML = """\
<html><body>
  <main class="grid">
    <article class="product-card" data-kind="product"><h2>Alpha</h2></article>
    <article class="product-card" data-kind="product"><h2>Beta</h2></article>
    <article class="product-card" data-kind="product"><h2>Gamma</h2></article>
  </main>
</body></html>
"""


def _root(html_text: str):
    return html.fromstring(html_text, parser=html.HTMLParser(recover=True))


class NativeAdaptiveParserTests(unittest.TestCase):
    def test_relocate_finds_changed_element_from_signature(self) -> None:
        old_title = _root(_OLD_HTML).xpath("//h2")[0]
        signature = build_element_signature(old_title)
        matches = relocate(_root(_NEW_HTML), signature, threshold=35)

        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].element.text_content().strip(), "Alpha Jacket")
        self.assertGreaterEqual(matches[0].score, 35)

    def test_native_parser_recovers_selector_miss_with_adaptive_signature(self) -> None:
        old_title = _root(_OLD_HTML).xpath("//h2")[0]
        signature = build_element_signature(old_title)
        parser = NativeParserRuntime()

        results = parser.parse(
            _NEW_HTML,
            [
                RuntimeSelectorRequest(
                    name="title",
                    selector=".title",
                    selector_type="css",
                    many=False,
                )
            ],
            selector_config={
                "adaptive_enabled": True,
                "adaptive_threshold": 35,
                "adaptive_signatures": {"title": signature},
            },
        )

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].ok, results[0].error)
        self.assertEqual(results[0].matched, 1)
        self.assertEqual(results[0].values, ["Alpha Jacket"])

    def test_selector_request_signature_enables_recovery_without_global_flag(self) -> None:
        old_title = _root(_OLD_HTML).xpath("//h2")[0]
        signature = build_element_signature(old_title)
        parser = NativeParserRuntime()

        results = parser.parse(
            _NEW_HTML,
            [
                RuntimeSelectorRequest(
                    name="title",
                    selector=".title",
                    selector_type="css",
                    many=False,
                    signature=signature,
                )
            ],
            selector_config={"adaptive_threshold": 35},
        )

        self.assertEqual(results[0].values, ["Alpha Jacket"])

    def test_find_similar_discovers_repeated_cards_from_seed(self) -> None:
        root = _root(_REPEATED_HTML)
        seed = root.xpath("//article")[0]
        matches = find_similar(seed)

        self.assertEqual(len(matches), 2)
        texts = [match.element.text_content().strip() for match in matches]
        self.assertEqual(texts, ["Beta", "Gamma"])

    def test_auto_save_and_recover_from_selector_memory_path(self) -> None:
        parser = NativeParserRuntime()
        with tempfile.TemporaryDirectory() as tmp:
            memory_path = str(Path(tmp) / "selector_memory.sqlite3")
            save_results = parser.parse(
                _OLD_HTML,
                [
                    RuntimeSelectorRequest(
                        name="title",
                        selector=".title",
                        selector_type="css",
                        many=False,
                    )
                ],
                url="https://shop.example/catalog",
                selector_config={
                    "adaptive_auto_save": True,
                    "adaptive_memory_path": memory_path,
                },
            )
            recover_results = NativeParserRuntime().parse(
                _NEW_HTML,
                [
                    RuntimeSelectorRequest(
                        name="title",
                        selector=".title",
                        selector_type="css",
                        many=False,
                    )
                ],
                url="https://shop.example/catalog",
                selector_config={
                    "adaptive_enabled": True,
                    "adaptive_threshold": 35,
                    "adaptive_memory_path": memory_path,
                },
            )
            rows = SelectorMemoryStore(memory_path).get_all()

        self.assertEqual(save_results[0].values, ["Alpha Jacket"])
        self.assertEqual(recover_results[0].values, ["Alpha Jacket"])
        self.assertEqual(rows[0]["success_count"], 1)
        self.assertEqual(rows[0]["recover_count"], 1)


if __name__ == "__main__":
    unittest.main()
