from __future__ import annotations

import unittest

from autonomous_crawler.tools.product_tasks import (
    extract_detail_record,
    extract_list_tasks,
    extract_variant_tasks,
)
from autonomous_crawler.tools.site_zoo import get_fixture


class ProductTaskTests(unittest.TestCase):
    def test_extract_list_tasks(self) -> None:
        fixture = get_fixture("static_list")
        tasks = extract_list_tasks(fixture.html, "https://shop.example/catalog", ".product-link@href".split("@")[0])

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].kind, "detail_page")
        self.assertEqual(tasks[0].url, "https://shop.example/products/alpha")

    def test_extract_variant_tasks(self) -> None:
        fixture = get_fixture("product_detail")
        tasks = extract_variant_tasks(fixture.html, "https://shop.example/products/alpha")

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0].kind, "variant_page")
        self.assertEqual(tasks[0].payload["color"], "red")

    def test_extract_detail_record(self) -> None:
        fixture = get_fixture("variant_detail")
        record = extract_detail_record(
            fixture.html,
            "https://shop.example/products/alpha-red",
            {
                "item_container": ".product-detail",
                "title": ".product-title",
                "price": ".product-price",
                "color": ".variant-color",
                "size": ".variant-size",
                "image": ".product-photo@src",
            },
        )

        self.assertEqual(record["title"], "Alpha Jacket Red")
        self.assertEqual(record["color"], "Red")
        self.assertEqual(record["image"], "https://shop.example/images/alpha-red.jpg")


if __name__ == "__main__":
    unittest.main()
