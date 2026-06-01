"""Fixture tests for evidence-driven ecommerce extractors."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from autonomous_crawler.tools.ecommerce_extractors import (
    extract_demandware_product_tile_items,
    extract_gtm_data_attribute_items,
    extract_gtm_item_objects,
    extract_items_from_contract,
    extract_jsonld_itemlist_items,
    extract_jsonld_product_items,
    extract_next_data_graphql_ssr_items,
    extract_next_data_json_from_html,
    extract_next_data_product_wall_items,
    extract_shopify_product_grid_items,
    UnsupportedExtractorContract,
)


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "dev_logs"
    / "training"
    / "xiaomi_recon_2026_05_28"
    / "fixtures"
)


def _read_text(*parts: str) -> str:
    return (FIXTURE_ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def _read_json(*parts: str):
    return json.loads(_read_text(*parts))


class GtmDataAttributeExtractorTests(unittest.TestCase):
    def test_superdry_extracts_products_from_html(self) -> None:
        html = _read_text("superdry_com", "raw_evidence_list_page.html")
        items = extract_gtm_data_attribute_items(
            html,
            source_url="https://www.superdry.com/womens/tops",
        )

        self.assertEqual(len(items), 3)
        first = items[0]
        self.assertEqual(first["title"], "Athletic Essentials Stripe Jersey Polo Shirt")
        self.assertEqual(first["highest_price"], 29.99)
        self.assertEqual(first["currency"], "GBP")
        self.assertEqual(first["color"], "NAVY")
        self.assertEqual(first["category_level_1"], "Womens")
        self.assertEqual(first["category_level_2"], "Tops")
        self.assertEqual(first["brand"], "SUPERDRY")
        self.assertEqual(first["sku"], "277146")
        self.assertTrue(first["image_url"].startswith("https://images.laguna-live.sd.co.uk/"))
        self.assertIn("width=546", first["image_url"])
        self.assertEqual(
            first["product_url"],
            "https://www.superdry.com/womens/tops/athletic-essentials-stripe-jersey-polo-shirt-277146.html",
        )
        self.assertIn("size", first["missing_reasons"])
        self.assertIn("description", first["missing_reasons"])

    def test_superdry_maps_parsed_gtm_objects(self) -> None:
        raw_items = _read_json("superdry_com", "raw_evidence_gtm_sample.json")
        items = extract_gtm_item_objects(
            raw_items,
            source_url="https://www.superdry.com/womens/tops",
        )

        self.assertEqual(len(items), 5)
        self.assertEqual(items[1]["title"], "Cami Top")
        self.assertEqual(items[1]["highest_price"], 22.99)
        self.assertEqual(items[1]["color"], "GREEN")
        self.assertIsNone(items[1]["image_url"])
        self.assertIn("image_url", items[1]["missing_reasons"])

    def test_gtm_missing_tiles_returns_empty(self) -> None:
        self.assertEqual(extract_gtm_data_attribute_items("<html></html>"), [])

    def test_gtm_malformed_json_is_skipped(self) -> None:
        html = '<div class="product-tile" data-gtm="{broken"></div>'
        self.assertEqual(extract_gtm_data_attribute_items(html), [])

    def test_contract_routes_superdry_html(self) -> None:
        contract = _read_json("superdry_com", "extraction_contract.json")
        html = _read_text("superdry_com", "raw_evidence_list_page.html")
        items = extract_items_from_contract(html, contract)

        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["title"], "Athletic Essentials Stripe Jersey Polo Shirt")


class NextDataProductWallExtractorTests(unittest.TestCase):
    def test_nike_extracts_product_wall_json_list(self) -> None:
        payload = _read_json("nike_com", "raw_evidence_next_data_sample.json")
        expected = _read_json("nike_com", "expected_items_sample.json")["items"]
        items = extract_next_data_product_wall_items(
            payload,
            source_url="https://www.nike.com/gb/w/womens-clothing-5e1x6z6ymx6",
        )

        self.assertEqual(len(items), 6)
        self.assertEqual(items[0]["title"], expected[0]["title"])
        self.assertEqual(items[0]["highest_price"], expected[0]["highest_price"])
        self.assertEqual(items[0]["currency"], "GBP")
        self.assertEqual(items[0]["color"], "Chalk/White")
        self.assertEqual(items[0]["product_url"], expected[0]["product_url"])
        self.assertEqual(items[0]["image_url"], expected[0]["image_url"])
        self.assertEqual(items[0]["category_level_1"], "APPAREL")
        self.assertEqual(items[0]["brand"], "Nike")
        self.assertEqual(items[0]["sku"], "IF0552-103")
        self.assertIn("category_level_2", items[0]["missing_reasons"])

    def test_nike_extracts_from_nested_next_data_payload(self) -> None:
        payload = _read_json("nike_com", "raw_evidence_next_data_sample.json")
        nested = {"props": {"pageProps": {"initialState": {"Wall": {"productGroupings": [{"products": payload[:2]}]}}}}}
        items = extract_next_data_product_wall_items(nested)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[1]["sku"], "IF0552-010")

    def test_next_data_json_from_html(self) -> None:
        html = '<html><script id="__NEXT_DATA__">{"props":{"pageProps":{}}}</script></html>'
        parsed = extract_next_data_json_from_html(html)

        self.assertEqual(parsed, {"props": {"pageProps": {}}})

    def test_nike_missing_next_data_returns_empty(self) -> None:
        self.assertEqual(extract_next_data_product_wall_items("<html></html>"), [])

    def test_contract_routes_nike_json(self) -> None:
        contract = _read_json("nike_com", "extraction_contract.json")
        payload = _read_json("nike_com", "raw_evidence_next_data_sample.json")
        items = extract_items_from_contract(payload, contract)

        self.assertEqual(len(items), 6)
        self.assertEqual(items[0]["brand"], "Nike")


class GraphqlSsrExtractorTests(unittest.TestCase):
    def test_marksandspencer_extracts_graphql_sample(self) -> None:
        payload = _read_json("marksandspencer_com", "raw_evidence_graphql_sample.json")
        expected = _read_json("marksandspencer_com", "expected_items_sample.json")["items"]
        items = extract_next_data_graphql_ssr_items(
            payload,
            source_url="https://www.marksandspencer.com/l/women/dresses",
        )

        self.assertEqual(len(items), 5)
        self.assertEqual(items[0]["title"], expected[0]["title"])
        self.assertEqual(items[0]["highest_price"], 50.0)
        self.assertEqual(items[0]["currency"], "GBP")
        self.assertEqual(items[0]["color"], "BLACKMIX")
        self.assertEqual(items[0]["size"], "6 Regular")
        self.assertEqual(items[0]["brand"], "M&S")
        self.assertEqual(items[0]["sku"], "60786172002")
        self.assertEqual(items[0]["image_url"], expected[0]["image_url"])
        self.assertEqual(items[0]["product_url"], expected[0]["product_url"])
        self.assertEqual(items[0]["category_level_1"], "Dresses")
        self.assertIn("description", items[0]["missing_reasons"])

    def test_marksandspencer_extracts_nested_next_data_payload(self) -> None:
        payload = _read_json("marksandspencer_com", "raw_evidence_graphql_sample.json")
        nested = {
            "props": {
                "pageProps": {
                    "serverSideGqlResponseFed": {
                        "productPageData": {"search": {"results": payload}}
                    }
                }
            }
        }
        items = extract_next_data_graphql_ssr_items(nested)

        self.assertEqual(len(items), 5)
        self.assertEqual(items[1]["title"], "Cotton Rich Striped Midi Column Dress")

    def test_marksandspencer_empty_products_returns_empty(self) -> None:
        self.assertEqual(extract_next_data_graphql_ssr_items({"products": []}), [])

    def test_marksandspencer_missing_variant_is_partial_not_crash(self) -> None:
        payload = {
            "products": [
                {
                    "title": "No Variant Product",
                    "price": {"listPrice": {"amount": 10}, "currency": "GBP"},
                    "seoPath": "/no-variant/p/clp1",
                    "productDefinition": "Dresses",
                    "variants": [],
                }
            ]
        }
        items = extract_next_data_graphql_ssr_items(payload)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "No Variant Product")
        self.assertIsNone(items[0]["size"])
        self.assertIn("size", items[0]["missing_reasons"])

    def test_contract_routes_marksandspencer_json(self) -> None:
        contract = _read_json("marksandspencer_com", "extraction_contract.json")
        payload = _read_json("marksandspencer_com", "raw_evidence_graphql_sample.json")
        items = extract_items_from_contract(payload, contract)

        self.assertEqual(len(items), 5)
        self.assertEqual(items[0]["color"], "BLACKMIX")

    def test_contract_rejects_unknown_strategy(self) -> None:
        with self.assertRaises(UnsupportedExtractorContract):
            extract_items_from_contract({}, {"parser_strategy": {"name": "unknown"}})


# ---------------------------------------------------------------------------
# Inline fixtures for new extractors (no external files needed)
# ---------------------------------------------------------------------------

_JSONLD_PRODUCT_HTML = """\
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Classic Leather Jacket",
  "description": "A timeless leather jacket.",
  "image": "https://example.com/img/jacket.jpg",
  "sku": "CLJ-001",
  "brand": {"@type": "Brand", "name": "Acme"},
  "category": "Clothing > Jackets",
  "offers": {
    "@type": "Offer",
    "price": "199.99",
    "priceCurrency": "GBP",
    "availability": "https://schema.org/InStock"
  }
}
</script>
</head><body></body></html>
"""

_JSONLD_ITEMLIST_HTML = """\
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "item": {
        "@type": "Product",
        "name": "Running Shoes",
        "image": "https://example.com/shoes.jpg",
        "sku": "RS-100",
        "offers": {"@type": "Offer", "price": "89.00", "priceCurrency": "USD"}
      }
    },
    {
      "@type": "ListItem",
      "position": 2,
      "item": {
        "@type": "Product",
        "name": "Trail Boots",
        "sku": "TB-200",
        "offers": {"@type": "Offer", "price": "129.50", "priceCurrency": "EUR"}
      }
    }
  ]
}
</script>
</head><body></body></html>
"""

_SHOPIFY_PRODUCTS_JSON = {
    "products": [
        {
            "id": 101,
            "title": "Organic Cotton Tee",
            "handle": "organic-cotton-tee",
            "body_html": "<p>Soft and sustainable.</p>",
            "product_type": "T-Shirts",
            "vendor": "GreenWear",
            "image": {"src": "https://cdn.shopify.com/tee.jpg"},
            "images": [{"src": "https://cdn.shopify.com/tee.jpg"}],
            "options": [
                {"name": "Color", "values": ["White", "Black"]},
                {"name": "Size", "values": ["S", "M", "L"]},
            ],
            "variants": [
                {
                    "sku": "GWT-WHT-M",
                    "price": "24.99",
                    "compare_at_price": "29.99",
                }
            ],
        },
        {
            "id": 102,
            "title": "Denim Jacket",
            "handle": "denim-jacket",
            "body_html": "",
            "product_type": "Jackets",
            "vendor": "RetroCo",
            "image": {"src": "https://cdn.shopify.com/jacket.jpg"},
            "options": [{"name": "Color", "values": ["Blue"]}],
            "variants": [{"sku": "DJ-001", "price": "59.00"}],
        },
    ]
}

_DEMANDWARE_TILE_HTML = """\
<html><body>
<div class="product-tile" data-pid="SKU-1234">
  <a class="pdp-link" href="/product/sku-1234.html">
    <span class="product-tile__name">Wireless Headphones</span>
  </a>
  <div class="product-tile__price">
    <span class="sales"><span class="value" content="79.99">$79.99</span></span>
  </div>
  <div class="product-tile__image">
    <img src="https://example.com/hp.jpg" alt="Wireless Headphones">
  </div>
</div>
<div class="product-tile" data-pid="SKU-5678">
  <a class="pdp-link" href="/product/sku-5678.html">
    <span class="product-tile__name">Bluetooth Speaker</span>
  </a>
  <div class="product-tile__price">
    <span class="sales"><span class="value" content="49.50">$49.50</span></span>
  </div>
  <div class="product-tile__image">
    <img src="https://example.com/spk.jpg" alt="Speaker">
  </div>
</div>
</body></html>
"""


class JsonLdProductExtractorTests(unittest.TestCase):
    def test_extract_product_from_html(self) -> None:
        items = extract_jsonld_product_items(
            _JSONLD_PRODUCT_HTML,
            source_url="https://example.com/jacket",
        )
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "Classic Leather Jacket")
        self.assertEqual(item["highest_price"], 199.99)
        self.assertEqual(item["currency"], "GBP")
        self.assertEqual(item["image_url"], "https://example.com/img/jacket.jpg")
        self.assertEqual(item["sku"], "CLJ-001")
        self.assertEqual(item["brand"], "Acme")
        self.assertEqual(item["category_level_1"], "Clothing > Jackets")
        self.assertIn("color", item["missing_reasons"])
        self.assertIn("size", item["missing_reasons"])

    def test_extract_itemlist_from_html(self) -> None:
        items = extract_jsonld_product_items(
            _JSONLD_ITEMLIST_HTML,
            source_url="https://example.com/shoes",
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Running Shoes")
        self.assertEqual(items[0]["highest_price"], 89.0)
        self.assertEqual(items[0]["currency"], "USD")
        self.assertEqual(items[1]["title"], "Trail Boots")
        self.assertEqual(items[1]["highest_price"], 129.5)
        self.assertEqual(items[1]["currency"], "EUR")

    def test_itemlist_as_dict(self) -> None:
        itemlist = {
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "item": {"@type": "Product", "name": "Hat", "offers": {"price": "15", "priceCurrency": "USD"}}},
            ],
        }
        items = extract_jsonld_itemlist_items(itemlist)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hat")

    def test_product_as_dict(self) -> None:
        product = {"@type": "Product", "name": "Socks", "offers": {"price": "5.99", "priceCurrency": "USD"}}
        items = extract_jsonld_itemlist_items(product)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Socks")

    def test_list_of_products(self) -> None:
        products = [
            {"@type": "Product", "name": "A", "offers": {"price": "10", "priceCurrency": "USD"}},
            {"@type": "Product", "name": "B", "offers": {"price": "20", "priceCurrency": "EUR"}},
        ]
        items = extract_jsonld_itemlist_items(products)
        self.assertEqual(len(items), 2)

    def test_malformed_json_ld_is_skipped(self) -> None:
        html = '<html><script type="application/ld+json">{broken</script></html>'
        items = extract_jsonld_product_items(html)
        self.assertEqual(items, [])

    def test_missing_script_returns_empty(self) -> None:
        items = extract_jsonld_product_items("<html><body>no ld+json</body></html>")
        self.assertEqual(items, [])

    def test_non_product_schema_ignored(self) -> None:
        html = '<html><script type="application/ld+json">{"@type": "Organization", "name": "Acme"}</script></html>'
        items = extract_jsonld_product_items(html)
        self.assertEqual(items, [])

    def test_product_offers_as_list(self) -> None:
        html = """\
<html><script type="application/ld+json">
{"@type": "Product", "name": "Multi Offer", "sku": "MO-1",
 "offers": [{"price": "10", "priceCurrency": "USD"}, {"price": "12", "priceCurrency": "USD"}]}
</script></html>"""
        items = extract_jsonld_product_items(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["highest_price"], 10.0)

    def test_product_image_as_string(self) -> None:
        html = """\
<html><script type="application/ld+json">
{"@type": "Product", "name": "Img", "image": "https://x.com/a.jpg", "offers": {"price": "1"}}
</script></html>"""
        items = extract_jsonld_product_items(html)
        self.assertEqual(items[0]["image_url"], "https://x.com/a.jpg")

    def test_contract_routes_jsonld(self) -> None:
        contract = {"parser_strategy": {"name": "jsonld_product_extractor"}, "site": "example.com"}
        items = extract_items_from_contract(_JSONLD_PRODUCT_HTML, contract)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Classic Leather Jacket")


class ShopifyProductGridExtractorTests(unittest.TestCase):
    def test_extract_products_from_json(self) -> None:
        items = extract_shopify_product_grid_items(
            _SHOPIFY_PRODUCTS_JSON,
            source_url="https://shop.example.com/collections/all",
        )
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first["title"], "Organic Cotton Tee")
        self.assertEqual(first["highest_price"], 29.99)  # compare_at_price > price
        self.assertEqual(first["color"], "White")
        self.assertEqual(first["size"], "S")
        self.assertEqual(first["brand"], "GreenWear")
        self.assertEqual(first["sku"], "GWT-WHT-M")
        self.assertIn("organic-cotton-tee", first["product_url"])
        self.assertEqual(first["category_level_1"], "T-Shirts")

    def test_compare_at_price_preferred(self) -> None:
        product = {
            "products": [
                {
                    "id": 1,
                    "title": "Sale Item",
                    "handle": "sale",
                    "variants": [{"price": "19.99", "compare_at_price": "39.99"}],
                    "options": [],
                    "image": {"src": "https://x.com/sale.jpg"},
                }
            ]
        }
        items = extract_shopify_product_grid_items(product)
        self.assertEqual(items[0]["highest_price"], 39.99)

    def test_list_of_products(self) -> None:
        products = [
            {"id": 1, "title": "X", "handle": "x", "variants": [{"price": "5"}], "options": []},
        ]
        items = extract_shopify_product_grid_items(products)
        self.assertEqual(len(items), 1)

    def test_missing_optional_fields(self) -> None:
        product = {"products": [{"id": 1, "title": "Minimal", "handle": "min", "variants": []}]}
        items = extract_shopify_product_grid_items(product)
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0]["image_url"])
        self.assertIn("image_url", items[0]["missing_reasons"])
        self.assertIn("color", items[0]["missing_reasons"])

    def test_empty_products(self) -> None:
        self.assertEqual(extract_shopify_product_grid_items({"products": []}), [])

    def test_malformed_string_returns_empty(self) -> None:
        self.assertEqual(extract_shopify_product_grid_items("not json at all"), [])

    def test_analytics_meta_product(self) -> None:
        evidence = {"Shopify": {"analytics": {"meta": {"product": {"id": 99, "title": "Meta Prod", "handle": "meta-prod", "variants": [{"price": "10"}]}}}}}
        items = extract_shopify_product_grid_items(evidence)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Meta Prod")

    def test_contract_routes_shopify(self) -> None:
        contract = {"parser_strategy": {"name": "shopify_product_grid_extractor"}, "site": "shop.example.com"}
        items = extract_items_from_contract(_SHOPIFY_PRODUCTS_JSON, contract)
        self.assertEqual(len(items), 2)


class DemandwareProductTileExtractorTests(unittest.TestCase):
    def test_extract_tiles_from_html(self) -> None:
        items = extract_demandware_product_tile_items(
            _DEMANDWARE_TILE_HTML,
            base_url="https://store.example.com",
            source_url="https://store.example.com/headphones",
        )
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first["title"], "Wireless Headphones")
        self.assertEqual(first["highest_price"], 79.99)
        self.assertEqual(first["sku"], "SKU-1234")
        self.assertEqual(first["image_url"], "https://example.com/hp.jpg")
        self.assertEqual(first["product_url"], "https://store.example.com/product/sku-1234.html")
        self.assertIn("color", first["missing_reasons"])
        self.assertIn("size", first["missing_reasons"])
        self.assertIn("description", first["missing_reasons"])

    def test_missing_optional_fields(self) -> None:
        html = """\
<div class="product-tile" data-pid="NO-IMG">
  <span class="product-tile__name">No Image Product</span>
</div>"""
        items = extract_demandware_product_tile_items(html)
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0]["image_url"])
        self.assertIsNone(items[0]["product_url"])
        self.assertIn("image_url", items[0]["missing_reasons"])
        self.assertIn("product_url", items[0]["missing_reasons"])

    def test_empty_html_returns_empty(self) -> None:
        self.assertEqual(extract_demandware_product_tile_items(""), [])

    def test_no_tiles_returns_empty(self) -> None:
        self.assertEqual(extract_demandware_product_tile_items("<html><body>no tiles</body></html>"), [])

    def test_js_fallback_extraction(self) -> None:
        html = """\
<html><body>
<script>
var productImpressions = [
  {"id": "JS-001", "name": "JS Product", "price": "45.00", "category": "Electronics", "url": "/js-product"}
];
</script>
</body></html>"""
        items = extract_demandware_product_tile_items(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "JS Product")
        self.assertEqual(items[0]["highest_price"], 45.0)
        self.assertEqual(items[0]["sku"], "JS-001")
        self.assertEqual(items[0]["category_level_1"], "Electronics")

    def test_contract_routes_demandware(self) -> None:
        contract = {"parser_strategy": {"name": "demandware_product_tile_extractor"}, "site": "store.example.com"}
        items = extract_items_from_contract(_DEMANDWARE_TILE_HTML, contract)
        self.assertEqual(len(items), 2)

    def test_non_html_evidence_returns_empty(self) -> None:
        contract = {"parser_strategy": {"name": "demandware_product_tile_extractor"}, "site": "store.example.com"}
        items = extract_items_from_contract(12345, contract)
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
