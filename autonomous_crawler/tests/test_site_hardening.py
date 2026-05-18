import tempfile
import unittest

from autonomous_crawler.tools.site_hardening import (
    cache_key,
    category_levels,
    clean_product_images,
    extract_json_script,
    is_bad_html,
    normalize_url,
    read_good_page_cache,
    write_good_page_cache,
)


class SiteHardeningTests(unittest.TestCase):
    def test_normalize_url_sorts_or_drops_query(self):
        self.assertEqual(
            normalize_url("/p/1?b=2&a=1", "https://Example.test/root", keep_query=True),
            "https://example.test/p/1?a=1&b=2",
        )
        self.assertEqual(
            normalize_url("/p/1?b=2", "https://example.test", keep_query=False),
            "https://example.test/p/1",
        )

    def test_bad_html_detection(self):
        self.assertTrue(is_bad_html("Just a moment", 200))
        self.assertTrue(is_bad_html("<html></html>", 200))
        self.assertTrue(is_bad_html("x" * 1000, 503))
        self.assertFalse(is_bad_html("x" * 1000, 200))

    def test_good_page_cache_skips_bad_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = cache_key("https://example.test")
            self.assertFalse(write_good_page_cache(tmp, key, url="https://example.test", text="short"))
            self.assertIsNone(read_good_page_cache(tmp, key))
            self.assertTrue(write_good_page_cache(tmp, key, url="https://example.test", text="x" * 1000))
            self.assertEqual(read_good_page_cache(tmp, key)["url"], "https://example.test")

    def test_clean_product_images_filters_noise_and_dedupes(self):
        images = clean_product_images(
            [
                "/media/catalog/product/a/b/item.jpg?width=100",
                "/media/catalog/product/a/b/item.jpg?width=500",
                "/footer/paypal.svg",
                "data:image/png;base64,abc",
            ],
            base_url="https://shop.test",
            required_contains=("/media/catalog/product/",),
        )

        self.assertEqual(len(images), 1)
        self.assertIn("/media/catalog/product/a/b/item.jpg", images[0])

    def test_category_levels_and_hydration_extract(self):
        self.assertEqual(category_levels(["A", "B", "C", "D"]), ("A", "B", "C > D"))
        payload = extract_json_script('<script id="__NEXT_DATA__">{"props":{"x":1}}</script>', script_id="__NEXT_DATA__")
        self.assertEqual(payload["props"]["x"], 1)


if __name__ == "__main__":
    unittest.main()
