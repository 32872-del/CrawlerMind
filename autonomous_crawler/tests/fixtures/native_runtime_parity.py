"""Shared fixtures for native-vs-transition runtime parity tests.

Each fixture is designed to exercise a specific parsing or fetching behavior
so that ScraplingParserRuntime and (future) NativeParserRuntime can be
compared on identical inputs.
"""
from __future__ import annotations

from autonomous_crawler.runtime.models import RuntimeSelectorRequest

# ---------------------------------------------------------------------------
# HTML Fixtures
# ---------------------------------------------------------------------------

#: Product card catalog — exercises CSS multi-node, attribute, text extraction
PRODUCT_CATALOG_HTML = """\
<html>
<head><title>Parity Catalog</title></head>
<body>
  <main class="catalog">
    <article class="product-card" data-sku="SKU-001" data-stock="12">
      <a class="product-link" href="/items/alpha-jacket">
        <img class="product-photo" src="/img/alpha.jpg" alt="Alpha Jacket" />
        <h2 class="product-name">Alpha Jacket</h2>
        <span class="product-price" data-currency="USD">$129.90</span>
        <span class="product-brand">Northwind</span>
      </a>
      <p class="product-desc">Waterproof outdoor jacket with sealed seams.</p>
    </article>
    <article class="product-card" data-sku="SKU-002" data-stock="0">
      <a class="product-link" href="/items/beta-pants">
        <img class="product-photo" src="/img/beta.jpg" alt="Beta Pants" />
        <h2 class="product-name">Beta Pants</h2>
        <span class="product-price" data-currency="USD">$89.50</span>
        <span class="product-brand">Northwind</span>
      </a>
      <p class="product-desc">Lightweight hiking pants, quick-dry fabric.</p>
    </article>
    <article class="product-card" data-sku="SKU-003" data-stock="5">
      <a class="product-link" href="/items/gamma-hat">
        <img class="product-photo" src="/img/gamma.jpg" alt="Gamma Hat" />
        <h2 class="product-name">Gamma Hat</h2>
        <span class="product-price" data-currency="USD">$24.00</span>
        <span class="product-brand">Contoso</span>
      </a>
      <p class="product-desc">UV-protection bucket hat for summer.</p>
    </article>
  </main>
  <footer>
    <p class="copyright">Copyright 2026 Parity Test Corp</p>
    <p class="contact">Contact: test@parity.example</p>
  </footer>
</body>
</html>
"""

#: Nested list with mixed content — exercises XPath axes and predicates
NESTED_LIST_HTML = """\
<html>
<body>
  <div class="category" data-level="1">
    <h3>Electronics</h3>
    <ul class="items">
      <li class="item" data-id="101"><span class="name">Laptop</span><span class="price">$999</span></li>
      <li class="item" data-id="102"><span class="name">Phone</span><span class="price">$699</span></li>
      <li class="item" data-id="103"><span class="name">Tablet</span><span class="price">$499</span></li>
    </ul>
  </div>
  <div class="category" data-level="1">
    <h3>Books</h3>
    <ul class="items">
      <li class="item" data-id="201"><span class="name">Python Cookbook</span><span class="price">$45</span></li>
      <li class="item" data-id="202"><span class="name">Web Scraping</span><span class="price">$39</span></li>
    </ul>
  </div>
</body>
</html>
"""

#: Malformed HTML — exercises parser recovery
MALFORMED_HTML = """\
<html><body>
<div class="unclosed<p>text inside</p>
<span class="broken"attr='val'>content</span>
<table><tr><td>cell1<td>cell2</tr></table>
</body></html>
"""

#: Empty document — exercises empty input handling
EMPTY_HTML = ""

#: Minimal valid document
MINIMAL_HTML = "<html><head><title>T</title></head><body></body></html>"

#: Data table with structured rows — exercises table parsing
DATA_TABLE_HTML = """\
<html>
<body>
  <table class="data-table">
    <thead>
      <tr><th class="col-id">ID</th><th class="col-name">Name</th><th class="col-value">Value</th></tr>
    </thead>
    <tbody>
      <tr data-row="0"><td class="col-id">1</td><td class="col-name">Alpha</td><td class="col-value">100</td></tr>
      <tr data-row="1"><td class="col-id">2</td><td class="col-name">Beta</td><td class="col-value">200</td></tr>
      <tr data-row="2"><td class="col-id">3</td><td class="col-name">Gamma</td><td class="col-value">300</td></tr>
    </tbody>
  </table>
</body>
</html>
"""

#: Mixed text with email, phone, prices — exercises regex extraction
CONTACT_HTML = """\
<html>
<body>
  <div class="contact-card">
    <h2>John Doe</h2>
    <p>Email: john@example.com</p>
    <p>Phone: +1-555-0123</p>
    <p>Alt Phone: (555) 987-6543</p>
  </div>
  <div class="contact-card">
    <h2>Jane Smith</h2>
    <p>Email: jane@test.org</p>
    <p>Phone: +1-555-4567</p>
  </div>
  <div class="prices">
    <span class="deal">$19.99</span>
    <span class="deal">$5.00</span>
    <span class="deal">$1,234.56</span>
  </div>
</body>
</html>
"""

#: JSON-LD + inline script data coexisting with visible product elements.
#: Exercises parser robustness: script content must not pollute element extraction.
JSON_LD_SCRIPT_HTML = """\
<html>
<head>
  <title>Shop with Structured Data</title>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "itemListElement": [
      {"@type": "ListItem", "position": 1, "name": "LD Widget A", "url": "/ld/widget-a"},
      {"@type": "ListItem", "position": 2, "name": "LD Widget B", "url": "/ld/widget-b"}
    ]
  }
  </script>
  <script>
    window.__INITIAL_STATE__ = {"products":[{"id":1,"title":"Script Gadget","price":"$9.99"}]};
  </script>
</head>
<body>
  <main class="storefront">
    <article class="product" data-id="P-100">
      <h3 class="product-title">Visible Widget Alpha</h3>
      <span class="product-price">$49.00</span>
      <a class="product-url" href="/products/alpha">Details</a>
      <img class="product-img" src="/img/alpha-widget.jpg" alt="Alpha Widget" />
    </article>
    <article class="product" data-id="P-200">
      <h3 class="product-title">Visible Widget Beta</h3>
      <span class="product-price">$79.00</span>
      <a class="product-url" href="/products/beta">Details</a>
      <img class="product-img" src="/img/beta-widget.jpg" alt="Beta Widget" />
    </article>
  </main>
  <script type="application/ld+json">
  {"@type": "Organization", "name": "Example Store", "url": "https://store.example.com"}
  </script>
</body>
</html>
"""

#: CSS selector miss / XPath selector hit scenarios.
#: Elements that CSS cannot target but XPath axes (following-sibling, preceding,
#: ancestor, positional predicates) can reach.
CSS_MISS_XPATH_HIT_HTML = """\
<html>
<body>
  <div class="catalog-section" data-section="electronics">
    <h2>Electronics</h2>
    <div class="item-grid">
      <div class="item" data-idx="1">
        <span class="item-name">Laptop Pro</span>
        <span class="item-price">$1299</span>
        <span class="item-stock">In Stock</span>
      </div>
      <div class="item" data-idx="2">
        <span class="item-name">Tablet Air</span>
        <span class="item-price">$599</span>
        <span class="item-stock">Out of Stock</span>
      </div>
      <div class="item" data-idx="3">
        <span class="item-name">Phone Mini</span>
        <span class="item-price">$399</span>
        <span class="item-stock">In Stock</span>
      </div>
    </div>
  </div>
  <div class="catalog-section" data-section="clothing">
    <h2>Clothing</h2>
    <div class="item-grid">
      <div class="item" data-idx="4">
        <span class="item-name">Winter Jacket</span>
        <span class="item-price">$189</span>
        <span class="item-stock">In Stock</span>
      </div>
      <div class="item" data-idx="5">
        <span class="item-name">Running Shoes</span>
        <span class="item-price">$129</span>
        <span class="item-stock">Out of Stock</span>
      </div>
    </div>
  </div>
  <footer>
    <p class="total-items">Total: 5 items</p>
  </footer>
</body>
</html>
"""

#: Relative URL and image attribute extraction.
#: Exercises href/src with relative paths, protocol-relative, and fragment URLs.
RELATIVE_URL_HTML = """\
<html>
<head><base href="https://shop.example.com/catalog/"></head>
<body>
  <div class="gallery">
    <a class="thumb-link" href="/products/item-1.html">
      <img class="thumb-img" src="/img/items/thumb-1.jpg" alt="Item 1" />
    </a>
    <a class="thumb-link" href="./products/item-2.html">
      <img class="thumb-img" src="./img/items/thumb-2.jpg" alt="Item 2" />
    </a>
    <a class="thumb-link" href="../category/shoes.html">
      <img class="thumb-img" src="../img/cat/shoes.jpg" alt="Shoes" />
    </a>
    <a class="thumb-link" href="//cdn.example.com/products/item-4.html">
      <img class="thumb-img" src="//cdn.example.com/img/items/thumb-4.jpg" alt="Item 4" />
    </a>
    <a class="thumb-link" href="#section-reviews">
      <img class="thumb-img" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="Placeholder" />
    </a>
  </div>
</body>
</html>
"""

#: Deep nested category → subcategory → item → detail link hierarchy.
#: Exercises multi-level CSS and XPath extraction on a realistic site structure.
NESTED_CATEGORY_DETAIL_HTML = """\
<html>
<body>
  <nav class="breadcrumb">
    <a href="/">Home</a> &gt; <a href="/catalog">Catalog</a> &gt; <span>Electronics</span>
  </nav>
  <main class="catalog">
    <section class="category" data-cat-id="C-1">
      <h2 class="category-name">Laptops</h2>
      <div class="subcategory" data-sub-id="S-1A">
        <h3 class="subcategory-name">Gaming Laptops</h3>
        <ul class="product-list">
          <li class="product-item" data-pid="P-101">
            <a class="detail-link" href="/catalog/laptops/gaming/rog-strix">ROG Strix G16</a>
            <span class="price">$1,599.00</span>
            <img class="product-thumb" src="/img/p101.jpg" alt="ROG Strix" />
          </li>
          <li class="product-item" data-pid="P-102">
            <a class="detail-link" href="/catalog/laptops/gaming/legion-5">Legion 5 Pro</a>
            <span class="price">$1,399.00</span>
            <img class="product-thumb" src="/img/p102.jpg" alt="Legion 5" />
          </li>
        </ul>
      </div>
      <div class="subcategory" data-sub-id="S-1B">
        <h3 class="subcategory-name">Ultrabooks</h3>
        <ul class="product-list">
          <li class="product-item" data-pid="P-103">
            <a class="detail-link" href="/catalog/laptops/ultra/xps-13">XPS 13 Plus</a>
            <span class="price">$1,299.00</span>
            <img class="product-thumb" src="/img/p103.jpg" alt="XPS 13" />
          </li>
        </ul>
      </div>
    </section>
    <section class="category" data-cat-id="C-2">
      <h2 class="category-name">Phones</h2>
      <div class="subcategory" data-sub-id="S-2A">
        <h3 class="subcategory-name">Flagship</h3>
        <ul class="product-list">
          <li class="product-item" data-pid="P-201">
            <a class="detail-link" href="/catalog/phones/flagship/pixel-9">Pixel 9 Pro</a>
            <span class="price">$999.00</span>
            <img class="product-thumb" src="/img/p201.jpg" alt="Pixel 9" />
          </li>
          <li class="product-item" data-pid="P-202">
            <a class="detail-link" href="/catalog/phones/flagship/galaxy-s25">Galaxy S25 Ultra</a>
            <span class="price">$1,199.00</span>
            <img class="product-thumb" src="/img/p202.jpg" alt="Galaxy S25" />
          </li>
        </ul>
      </div>
    </section>
  </main>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Selector Request Fixtures
# ---------------------------------------------------------------------------

def product_name_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_name", selector=".product-name", selector_type="css")

def product_price_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_price", selector=".product-price", selector_type="css")

def product_link_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_link", selector=".product-link", selector_type="css", attribute="href")

def product_image_src_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_img", selector=".product-photo", selector_type="css", attribute="src")

def product_sku_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_sku", selector=".product-card", selector_type="css", attribute="data-sku")

def product_brand_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_brand", selector=".product-brand", selector_type="css")

def product_first_only_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="first_product", selector=".product-name", selector_type="css", many=False)

def missing_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="missing", selector=".does-not-exist", selector_type="css")

def xpath_titles_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="title", selector="//article[@class='product-card']//h2", selector_type="xpath")

def xpath_prices_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="price", selector="//span[@class='product-price']", selector_type="xpath")

def xpath_links_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="link", selector="//a[@class='product-link']/@href", selector_type="xpath")

def xpath_predicate_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="first_card", selector="//article[@class='product-card'][1]//h2", selector_type="xpath")

def regex_price_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="prices", selector=r"\$[\d,]+\.\d{2}", selector_type="regex")

def regex_email_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="emails", selector=r"[\w.+-]+@[\w-]+\.[\w.]+", selector_type="regex")

def regex_phone_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="phones", selector=r"\+?[\d\-() ]{7,}", selector_type="regex")

def text_widget_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="widget_text", selector="Alpha Jacket", selector_type="text")

def text_partial_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="partial_text", selector="Alpha", selector_type="text")

def invalid_css_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="bad_css", selector=">>>invalid<<<", selector_type="css")

def invalid_regex_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="bad_regex", selector=r"[unclosed", selector_type="regex")

def unsupported_type_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="bogus", selector="something", selector_type="bogus")

def table_cell_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="cell_name", selector=".col-name", selector_type="css")

def table_row_attr_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="row_id", selector="tbody tr", selector_type="css", attribute="data-row")

def nested_item_name_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="item_name", selector=".item .name", selector_type="css")

def nested_category_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="category", selector="//div[@class='category']/h3", selector_type="xpath")

# ---------------------------------------------------------------------------
# JSON-LD / Script coexistence selectors
# ---------------------------------------------------------------------------

def jsonld_visible_title_selector() -> RuntimeSelectorRequest:
    """CSS: extract visible product titles, must not include JSON-LD text."""
    return RuntimeSelectorRequest(name="visible_title", selector=".product-title", selector_type="css")

def jsonld_visible_price_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="visible_price", selector=".product-price", selector_type="css")

def jsonld_visible_link_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="visible_link", selector=".product-url", selector_type="css", attribute="href")

def jsonld_visible_img_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="visible_img", selector=".product-img", selector_type="css", attribute="src")

def jsonld_data_id_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="data_id", selector=".product", selector_type="css", attribute="data-id")

def jsonld_xpath_titles_selector() -> RuntimeSelectorRequest:
    """XPath: same visible titles via XPath."""
    return RuntimeSelectorRequest(name="xpath_title", selector="//article[@class='product']//h3", selector_type="xpath")

# ---------------------------------------------------------------------------
# CSS miss / XPath hit selectors
# ---------------------------------------------------------------------------

def xpath_following_sibling_stock() -> RuntimeSelectorRequest:
    """XPath: get stock text following the price — CSS cannot express this axis."""
    return RuntimeSelectorRequest(
        name="stock_after_price",
        selector="//span[@class='item-price']/following-sibling::span[@class='item-stock']",
        selector_type="xpath",
    )

def xpath_ancestor_section_attr() -> RuntimeSelectorRequest:
    """XPath: get ancestor section data-section from item — CSS cannot walk up."""
    return RuntimeSelectorRequest(
        name="ancestor_section",
        selector="//span[@class='item-name']/ancestor::div[@class='catalog-section']/@data-section",
        selector_type="xpath",
    )

def xpath_positional_last_item() -> RuntimeSelectorRequest:
    """XPath: get last item name in each item-grid — positional predicate."""
    return RuntimeSelectorRequest(
        name="last_item_per_grid",
        selector="//div[@class='item-grid']/div[@class='item'][last()]/span[@class='item-name']",
        selector_type="xpath",
    )

def xpath_count_items_per_section() -> RuntimeSelectorRequest:
    """XPath: count items per section — XPath function, CSS can't do this."""
    return RuntimeSelectorRequest(
        name="item_count_per_section",
        selector="count(//div[@class='catalog-section'][1]//div[@class='item'])",
        selector_type="xpath",
    )

def css_item_name_selector() -> RuntimeSelectorRequest:
    """CSS: basic item name extraction (should work, for comparison with XPath)."""
    return RuntimeSelectorRequest(name="css_item_name", selector=".item .item-name", selector_type="css")

def css_section_miss_selector() -> RuntimeSelectorRequest:
    """CSS: try to get section data attribute from nested item — will miss (returns empty)."""
    return RuntimeSelectorRequest(name="css_section_miss", selector=".item .catalog-section", selector_type="css")

# ---------------------------------------------------------------------------
# Relative URL / image attribute selectors
# ---------------------------------------------------------------------------

def relative_href_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="rel_href", selector=".thumb-link", selector_type="css", attribute="href")

def relative_img_src_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="rel_img_src", selector=".thumb-img", selector_type="css", attribute="src")

def relative_img_alt_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="rel_img_alt", selector=".thumb-img", selector_type="css", attribute="alt")

def relative_xpath_href_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="xpath_href", selector="//a[@class='thumb-link']/@href", selector_type="xpath")

def relative_xpath_src_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="xpath_src", selector="//img[@class='thumb-img']/@src", selector_type="xpath")

# ---------------------------------------------------------------------------
# Nested category / detail link selectors
# ---------------------------------------------------------------------------

def nested_cat_name_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="cat_name", selector=".category-name", selector_type="css")

def nested_subcat_name_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="subcat_name", selector=".subcategory-name", selector_type="css")

def nested_detail_link_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="detail_link", selector=".detail-link", selector_type="css", attribute="href")

def nested_detail_text_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="detail_text", selector=".detail-link", selector_type="css")

def nested_product_price_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_price", selector=".product-item .price", selector_type="css")

def nested_product_img_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_img", selector=".product-thumb", selector_type="css", attribute="src")

def nested_pid_selector() -> RuntimeSelectorRequest:
    return RuntimeSelectorRequest(name="product_id", selector=".product-item", selector_type="css", attribute="data-pid")

def nested_xpath_detail_under_gaming() -> RuntimeSelectorRequest:
    """XPath: detail links only under 'Gaming Laptops' subcategory."""
    return RuntimeSelectorRequest(
        name="gaming_detail_links",
        selector="//h3[contains(text(),'Gaming')]/following-sibling::ul//a[@class='detail-link']/@href",
        selector_type="xpath",
    )

def nested_xpath_cat_names() -> RuntimeSelectorRequest:
    """XPath: category section data-cat-id attributes."""
    return RuntimeSelectorRequest(
        name="cat_ids",
        selector="//section[@class='category']/@data-cat-id",
        selector_type="xpath",
    )

# ---------------------------------------------------------------------------
# Multi-selector batches (for testing multiple selectors in one parse call)
# ---------------------------------------------------------------------------

def product_full_batch() -> list[RuntimeSelectorRequest]:
    """Full product extraction batch — names, prices, links, SKUs."""
    return [
        product_name_selector(),
        product_price_selector(),
        product_link_selector(),
        product_sku_selector(),
    ]

def mixed_type_batch() -> list[RuntimeSelectorRequest]:
    """Batch mixing CSS, XPath, and regex in one parse call."""
    return [
        product_name_selector(),
        xpath_prices_selector(),
        regex_price_selector(),
    ]

def contact_batch() -> list[RuntimeSelectorRequest]:
    """Contact info extraction batch."""
    return [
        regex_email_selector(),
        regex_phone_selector(),
    ]

def error_prone_batch() -> list[RuntimeSelectorRequest]:
    """Batch containing selectors that should produce errors."""
    return [
        product_name_selector(),       # valid
        invalid_css_selector(),         # should error
        invalid_regex_selector(),       # should error
    ]

def jsonld_full_batch() -> list[RuntimeSelectorRequest]:
    """Full extraction from JSON-LD coexistence page — visible elements only."""
    return [
        jsonld_visible_title_selector(),
        jsonld_visible_price_selector(),
        jsonld_visible_link_selector(),
        jsonld_visible_img_selector(),
        jsonld_data_id_selector(),
    ]

def css_xpath_hit_batch() -> list[RuntimeSelectorRequest]:
    """Batch combining CSS baselines with XPath-only extractions."""
    return [
        css_item_name_selector(),
        xpath_following_sibling_stock(),
        xpath_ancestor_section_attr(),
    ]

def relative_url_batch() -> list[RuntimeSelectorRequest]:
    """Full relative URL extraction batch — CSS + XPath."""
    return [
        relative_href_selector(),
        relative_img_src_selector(),
        relative_img_alt_selector(),
    ]

def nested_detail_batch() -> list[RuntimeSelectorRequest]:
    """Full nested category/detail extraction batch."""
    return [
        nested_cat_name_selector(),
        nested_subcat_name_selector(),
        nested_detail_link_selector(),
        nested_detail_text_selector(),
        nested_product_price_selector(),
    ]
