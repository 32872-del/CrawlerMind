"""Tests for HTML pagination detection."""
from __future__ import annotations

import unittest

from autonomous_crawler.tools.pagination import detect_pagination_links


class TestPaginationDetection(unittest.TestCase):
    """Test pagination link detection."""

    def test_rel_next_link(self) -> None:
        html = """
        <html><body>
        <nav class="pagination">
            <a href="/page/1">1</a>
            <span class="current">2</span>
            <a href="/page/3" rel="next">Next</a>
        </nav>
        </body></html>
        """
        urls = detect_pagination_links(html, "https://example.com/page/2")
        self.assertEqual(len(urls), 1)
        self.assertIn("/page/3", urls[0])

    def test_link_rel_next_in_head(self) -> None:
        html = """
        <html><head><link rel="next" href="/products?page=3"></head>
        <body></body></html>
        """
        urls = detect_pagination_links(html, "https://example.com/products?page=2")
        self.assertTrue(len(urls) >= 1)
        self.assertIn("page=3", urls[0])

    def test_text_next_link(self) -> None:
        html = """
        <html><body>
        <div class="pagination">
            <a href="?page=1">1</a>
            <a href="?page=2" class="active">2</a>
            <a href="?page=3">Next &raquo;</a>
        </div>
        </body></html>
        """
        urls = detect_pagination_links(html, "https://example.com/list?page=2")
        self.assertTrue(len(urls) >= 1)
        self.assertIn("page=3", urls[0])

    def test_page_number_links(self) -> None:
        html = """
        <html><body>
        <ul class="pagination">
            <li><a href="?page=1">1</a></li>
            <li class="active"><a href="?page=2">2</a></li>
            <li><a href="?page=3">3</a></li>
            <li><a href="?page=4">4</a></li>
            <li><a href="?page=5">5</a></li>
        </ul>
        </body></html>
        """
        urls = detect_pagination_links(html, "https://example.com/list?page=2")
        self.assertTrue(len(urls) >= 1)

    def test_url_pattern_pagination(self) -> None:
        html = """
        <html><body>
        <div class="products">
            <div class="item">Product 1</div>
        </div>
        </body></html>
        """
        urls = detect_pagination_links(
            html, "https://example.com/products?page=1", max_pages=3
        )
        self.assertTrue(len(urls) >= 1)
        self.assertIn("page=2", urls[0])

    def test_chinese_next_text(self) -> None:
        html = """
        <html><body>
        <div class="pagination">
            <a href="/list?page=1">1</a>
            <span>2</span>
            <a href="/list?page=3">下一页</a>
        </div>
        </body></html>
        """
        urls = detect_pagination_links(html, "https://example.com/list?page=2")
        self.assertTrue(len(urls) >= 1)
        self.assertIn("page=3", urls[0])

    def test_no_pagination(self) -> None:
        html = """
        <html><body>
        <div class="content">
            <p>No pagination here</p>
        </div>
        </body></html>
        """
        urls = detect_pagination_links(html, "https://example.com/page")
        self.assertEqual(len(urls), 0)

    def test_relative_urls_resolved(self) -> None:
        html = """
        <html><body>
        <nav class="pagination">
            <a href="/products?page=3" rel="next">Next</a>
        </nav>
        </body></html>
        """
        urls = detect_pagination_links(html, "https://shop.example.com/products?page=2")
        self.assertTrue(len(urls) >= 1)
        self.assertTrue(urls[0].startswith("https://shop.example.com"))
        self.assertIn("page=3", urls[0])

    def test_max_pages_respected(self) -> None:
        html = """
        <html><body>
        <nav class="pagination">
            <a href="?page=2" rel="next">Next</a>
        </nav>
        </body></html>
        """
        urls = detect_pagination_links(
            html, "https://example.com/list?page=1", max_pages=3
        )
        self.assertLessEqual(len(urls), 3)


if __name__ == "__main__":
    unittest.main()
