import unittest

from autonomous_crawler.models.product import ProductRecord
from autonomous_crawler.tools.product_quality import (
    BLOCKED_WITHOUT_NOTES,
    DATA_IMAGE_URL,
    EMPTY_IMAGES,
    MISSING_DEDUPE_KEY,
    MISSING_TITLE,
    MISSING_URL,
    NEGATIVE_PRICE,
    NOISE_ONLY_IMAGES,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    has_errors,
    issue_counts,
    parse_price,
    validate_product_record,
)


def codes(issues):
    return [issue.code for issue in issues]


def issue_by_code(issues, code):
    for issue in issues:
        if issue.code == code:
            return issue
    raise AssertionError(f"Missing issue code: {code}")


class ParsePriceTests(unittest.TestCase):
    def test_parses_common_price_formats(self):
        cases = {
            "\u20ac139": 139.0,
            "\u20ac64,95": 64.95,
            "299.9 PLN": 299.9,
            "129,99 z\u0142": 129.99,
            "$129.90": 129.9,
            "\u00a349.99": 49.99,
            "1.299,95": 1299.95,
            "Free": 0.0,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_price(raw), expected)

    def test_price_range_returns_highest_value(self):
        self.assertEqual(parse_price("\u20ac49.99 - \u20ac99.99"), 99.99)

    def test_negative_price_is_parseable_for_validation(self):
        self.assertEqual(parse_price("-5"), -5.0)

    def test_unparseable_values_return_none(self):
        self.assertIsNone(parse_price(None))
        self.assertIsNone(parse_price(""))
        self.assertIsNone(parse_price("ask in store"))
        self.assertIsNone(parse_price(True))


class ProductQualityTests(unittest.TestCase):
    def test_shopify_like_record_passes_without_errors(self):
        record = {
            "url": "https://example.test/products/shoe",
            "title": "Canvas Shoe",
            "price": "\u20ac89,95",
            "description": "A lightweight canvas shoe.",
            "image_urls": ["https://cdn.example.test/products/shoe.jpg"],
            "handle": "canvas-shoe",
            "category": "Shoes",
            "dedupe_key": "shopify-1",
        }

        issues = validate_product_record(record)

        self.assertFalse(has_errors(issues))

    def test_magento_like_record_passes_without_errors(self):
        record = {
            "canonical_url": "https://example.test/catalog/product/view/id/1",
            "product_title": "Work Glove",
            "highest_price": 19.99,
            "product_description": "Protective glove.",
            "image_src": "https://example.test/media/glove.png",
            "handle": "work-glove",
            "categories_1": "Safety",
            "sole_id": "sku-1",
        }

        issues = validate_product_record(record)

        self.assertFalse(has_errors(issues))

    def test_uvex_like_record_with_zloty_and_sizes_passes(self):
        record = {
            "url": "https://example.test/p/helmet",
            "title": "Safety Helmet",
            "price": "129,99 z\u0142",
            "description": "Helmet with adjustable sizes S, M and L.",
            "image_urls": ["https://example.test/images/helmet.webp"],
            "sizes": ["S", "M", "L"],
            "handle": "helmet",
            "category": "PPE",
            "dedupe_key": "uvex-helmet",
        }

        issues = validate_product_record(record)

        self.assertFalse(has_errors(issues))

    def test_blocked_record_with_notes_returns_cleanly(self):
        issues = validate_product_record(
            {
                "url": "https://example.test",
                "status": "blocked",
                "notes": "Cloudflare challenge observed.",
            }
        )

        self.assertEqual(issues, [])

    def test_blocked_record_without_notes_warns(self):
        issues = validate_product_record({"url": "https://example.test", "status": "blocked"})

        self.assertIn(BLOCKED_WITHOUT_NOTES, codes(issues))
        self.assertEqual(issue_by_code(issues, BLOCKED_WITHOUT_NOTES).severity, SEVERITY_WARNING)

    def test_partial_record_can_omit_price_and_images(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/bosch",
                "title": "Product family page",
                "status": "partial",
                "description": "",
            }
        )

        self.assertNotIn(EMPTY_IMAGES, codes(issues))
        self.assertFalse(has_errors(issues))

    def test_missing_required_url_is_error(self):
        issues = validate_product_record(
            {
                "title": "Missing URL",
                "price": "10",
                "image_urls": ["https://example.test/a.jpg"],
            }
        )

        self.assertIn(MISSING_URL, codes(issues))
        self.assertEqual(issue_by_code(issues, MISSING_URL).severity, SEVERITY_ERROR)

    def test_missing_title_is_error_by_default(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/no-title",
                "price": "10",
                "image_urls": ["https://example.test/a.jpg"],
            }
        )

        self.assertIn(MISSING_TITLE, codes(issues))
        self.assertEqual(issue_by_code(issues, MISSING_TITLE).severity, SEVERITY_ERROR)

    def test_partial_missing_title_can_be_downgraded(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/no-title",
                "status": "partial",
            }
        )

        self.assertIn(MISSING_TITLE, codes(issues))
        self.assertEqual(issue_by_code(issues, MISSING_TITLE).severity, SEVERITY_WARNING)

    def test_profile_can_force_partial_missing_title_to_error(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/no-title",
                "status": "partial",
            },
            profile={"allow_partial": False},
        )

        self.assertEqual(issue_by_code(issues, MISSING_TITLE).severity, SEVERITY_ERROR)

    def test_empty_images_warns(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/no-image",
                "title": "No image",
                "price": "10",
            }
        )

        self.assertIn(EMPTY_IMAGES, codes(issues))
        self.assertEqual(issue_by_code(issues, EMPTY_IMAGES).severity, SEVERITY_WARNING)

    def test_noise_only_images_warns(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/noise",
                "title": "Noise",
                "price": "10",
                "image_urls": [
                    "https://example.test/logo.png",
                    "https://example.test/payment-visa.png",
                ],
            }
        )

        self.assertIn(NOISE_ONLY_IMAGES, codes(issues))

    def test_data_uri_image_is_info(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/data-image",
                "title": "Data image",
                "price": "10",
                "image_urls": ["data:image/png;base64,abc"],
            }
        )

        self.assertIn(DATA_IMAGE_URL, codes(issues))
        self.assertEqual(issue_by_code(issues, DATA_IMAGE_URL).severity, SEVERITY_INFO)

    def test_negative_price_is_error(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/negative",
                "title": "Negative price",
                "price": "-5",
                "image_urls": ["https://example.test/a.jpg"],
            }
        )

        self.assertIn(NEGATIVE_PRICE, codes(issues))
        self.assertEqual(issue_by_code(issues, NEGATIVE_PRICE).severity, SEVERITY_ERROR)

    def test_profile_can_allow_missing_price(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/no-price",
                "title": "No price",
                "image_urls": ["https://example.test/a.jpg"],
            },
            profile={"price_required": False},
        )

        self.assertNotIn("unparsable_price", codes(issues))

    def test_profile_can_allow_missing_images(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/no-image",
                "title": "No image",
                "price": "10",
            },
            profile={"image_required": False},
        )

        self.assertNotIn(EMPTY_IMAGES, codes(issues))

    def test_profile_can_require_dedupe_key(self):
        issues = validate_product_record(
            {
                "url": "https://example.test/no-dedupe",
                "title": "No dedupe",
                "price": "10",
                "image_urls": ["https://example.test/a.jpg"],
            },
            profile={"dedupe_key_required": True},
        )

        self.assertIn(MISSING_DEDUPE_KEY, codes(issues))
        self.assertEqual(issue_by_code(issues, MISSING_DEDUPE_KEY).severity, SEVERITY_WARNING)

    def test_product_record_dataclass_input_works(self):
        record = ProductRecord(
            run_id="run-1",
            source_site="example",
            source_url="https://example.test/product",
            canonical_url="https://example.test/product",
            title="Dataclass Product",
            highest_price=25.0,
            image_urls=["https://example.test/product.jpg"],
            category="Shoes",
        )

        issues = validate_product_record(record)

        self.assertFalse(has_errors(issues))

    def test_issue_counts_and_has_errors(self):
        issues = validate_product_record(
            {
                "price": "-5",
                "image_urls": ["data:image/png;base64,abc"],
            }
        )

        counts = issue_counts(issues)

        self.assertTrue(has_errors(issues))
        self.assertGreaterEqual(counts[SEVERITY_ERROR], 1)
        self.assertGreaterEqual(counts[SEVERITY_INFO], 1)


if __name__ == "__main__":
    unittest.main()
