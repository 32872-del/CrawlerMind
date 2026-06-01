from __future__ import annotations

import json
from pathlib import Path
import unittest

from autonomous_crawler.tools.extraction_contracts import (
    build_extract_from_contract_extra_context,
    discover_best_extraction_contract,
    discover_extraction_contracts,
)

from autonomous_crawler.tests.test_ecommerce_extractors import (
    _DEMANDWARE_TILE_HTML,
    _JSONLD_ITEMLIST_HTML,
    _JSONLD_PRODUCT_HTML,
    _SHOPIFY_PRODUCTS_JSON,
)


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "dev_logs"
    / "training"
    / "xiaomi_recon_2026_05_28"
    / "fixtures"
)


def _read_text(*parts: str) -> str:
    return FIXTURE_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def _read_json(*parts: str):
    return json.loads(_read_text(*parts))


class ExtractionContractDiscoveryTests(unittest.TestCase):
    def test_discovers_gtm_data_attribute_contract_from_superdry_html(self) -> None:
        html = _read_text("superdry_com", "raw_evidence_list_page.html")
        result = discover_extraction_contracts(
            html,
            source_url="https://www.superdry.com/womens/tops",
        )

        best = result["best_contract"]
        self.assertEqual(best["parser_strategy"]["name"], "gtm_data_attribute_extractor")
        self.assertEqual(best["site"], "superdry.com")
        self.assertGreaterEqual(result["best_sample_count"], 3)
        self.assertGreater(result["best_confidence"], 0.75)
        self.assertIn("data-gtm", " ".join(result["candidates"][0]["reasons"]))

    def test_discovers_nike_next_data_contract_from_json(self) -> None:
        payload = _read_json("nike_com", "raw_evidence_next_data_sample.json")
        result = discover_extraction_contracts(
            payload,
            source_url="https://www.nike.com/gb/w/womens-clothing-5e1x6z6ymx6",
        )

        best = result["best_contract"]
        self.assertEqual(best["parser_strategy"]["name"], "next_data_product_wall_extractor")
        self.assertGreaterEqual(result["best_sample_count"], 6)
        self.assertEqual(result["candidates"][0]["sample_items"][0]["brand"], "Nike")

    def test_discovers_graphql_ssr_contract_from_marksandspencer_json(self) -> None:
        payload = _read_json("marksandspencer_com", "raw_evidence_graphql_sample.json")
        result = discover_extraction_contracts(
            payload,
            source_url="https://www.marksandspencer.com/l/women/dresses",
        )

        best = result["best_contract"]
        self.assertEqual(best["parser_strategy"]["name"], "next_data_graphql_ssr_cache_extractor")
        self.assertGreaterEqual(result["best_sample_count"], 5)
        self.assertEqual(result["candidates"][0]["sample_items"][0]["color"], "BLACKMIX")

    def test_discovers_jsonld_product_contract_from_html(self) -> None:
        result = discover_extraction_contracts(
            _JSONLD_PRODUCT_HTML,
            source_url="https://example.com/jacket",
        )

        best = result["best_contract"]
        self.assertEqual(best["parser_strategy"]["name"], "jsonld_product_extractor")
        self.assertEqual(result["best_sample_count"], 1)
        self.assertEqual(result["candidates"][0]["sample_items"][0]["title"], "Classic Leather Jacket")

    def test_discovers_jsonld_itemlist_contract_from_html(self) -> None:
        result = discover_extraction_contracts(
            _JSONLD_ITEMLIST_HTML,
            source_url="https://example.com/shoes",
        )

        best = result["best_contract"]
        self.assertEqual(best["parser_strategy"]["name"], "jsonld_itemlist_extractor")
        self.assertEqual(result["best_sample_count"], 2)

    def test_discovers_shopify_product_grid_contract_from_json(self) -> None:
        result = discover_extraction_contracts(
            _SHOPIFY_PRODUCTS_JSON,
            source_url="https://shop.example.com/collections/all",
        )

        best = result["best_contract"]
        self.assertEqual(best["parser_strategy"]["name"], "shopify_product_grid_extractor")
        self.assertEqual(result["best_sample_count"], 2)
        self.assertEqual(result["candidates"][0]["sample_items"][0]["highest_price"], 29.99)

    def test_discovers_demandware_tile_contract_from_html(self) -> None:
        result = discover_extraction_contracts(
            _DEMANDWARE_TILE_HTML,
            source_url="https://store.example.com/headphones",
        )

        best = result["best_contract"]
        self.assertEqual(best["parser_strategy"]["name"], "demandware_product_tile_extractor")
        self.assertEqual(result["best_sample_count"], 2)
        self.assertEqual(result["candidates"][0]["sample_items"][0]["sku"], "SKU-1234")

    def test_returns_no_contract_for_empty_html(self) -> None:
        result = discover_extraction_contracts(
            "<html><body>No products here</body></html>",
            source_url="https://example.com/empty",
        )

        self.assertEqual(result["candidate_count"], 0)
        self.assertIsNone(result["best_contract"])
        self.assertIn("No supported extraction evidence pattern detected.", result["warnings"])

    def test_best_contract_helper_returns_contract_or_none(self) -> None:
        contract = discover_best_extraction_contract(
            _JSONLD_PRODUCT_HTML,
            source_url="https://example.com/jacket",
        )
        missing = discover_best_extraction_contract("<html></html>")

        self.assertIsNotNone(contract)
        self.assertEqual(contract["parser_strategy"]["name"], "jsonld_product_extractor")
        self.assertIsNone(missing)

    def test_build_extra_context_can_feed_managed_extract_action(self) -> None:
        context = build_extract_from_contract_extra_context(
            _SHOPIFY_PRODUCTS_JSON,
            source_url="https://shop.example.com/collections/all",
            max_items=20,
        )

        self.assertEqual(
            context["extraction_contract"]["parser_strategy"]["name"],
            "shopify_product_grid_extractor",
        )
        self.assertIs(context["extraction_evidence"], _SHOPIFY_PRODUCTS_JSON)
        self.assertEqual(context["max_items"], 20)
        self.assertEqual(context["extraction_contract_discovery"]["best_sample_count"], 2)


if __name__ == "__main__":
    unittest.main()
