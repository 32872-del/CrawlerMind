"""Local site-zoo fixtures for crawler capability tests."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SiteZooFixture:
    name: str
    url: str
    html: str
    category: str
    description: str


STATIC_LIST_HTML = """
<html><body>
  <main class="catalog-grid">
    <article class="catalog-card">
      <a class="product-link" href="/products/alpha">
        <img class="product-photo" src="/images/alpha.jpg" />
        <h2 class="product-name">Alpha Jacket</h2>
        <span class="product-price">$129.90</span>
      </a>
    </article>
    <article class="catalog-card">
      <a class="product-link" href="/products/beta">
        <img class="product-photo" src="/images/beta.jpg" />
        <h2 class="product-name">Beta Pants</h2>
        <span class="product-price">$89.50</span>
      </a>
    </article>
  </main>
</body></html>
"""

PRODUCT_DETAIL_HTML = """
<html><body>
  <article class="product-detail" data-sku="ALPHA-001">
    <h1 class="product-title">Alpha Jacket</h1>
    <span class="product-price">$129.90</span>
    <div class="product-description">Waterproof shell jacket.</div>
    <img class="product-photo" src="/images/alpha.jpg" />
    <a class="variant-link" href="/products/alpha-red" data-color="red">Red</a>
    <a class="variant-link" href="/products/alpha-blue" data-color="blue">Blue</a>
  </article>
</body></html>
"""

VARIANT_DETAIL_HTML = """
<html><body>
  <article class="product-detail" data-sku="ALPHA-RED">
    <h1 class="product-title">Alpha Jacket Red</h1>
    <span class="product-price">$139.90</span>
    <span class="variant-color">Red</span>
    <span class="variant-size">M</span>
    <img class="product-photo" src="/images/alpha-red.jpg" />
  </article>
</body></html>
"""

SPA_SHELL_HTML = """
<html><body>
  <div id="root"></div>
  <script src="/static/runtime.js"></script>
  <script src="/static/app.js"></script>
  <script>fetch('/api/products?page=1')</script>
  <script>console.log('hydrate')</script>
  <script>console.log('render')</script>
</body></html>
"""

API_HINT_STATIC_HTML = """
<html><body>
  <main>
    <h1>API backed catalog</h1>
    <script>window.catalogEndpoint = "mock://api/products";</script>
    <a href="/products/fallback">Fallback product</a>
  </main>
</body></html>
"""

STRUCTURED_HTML = """
<html><head>
  <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"Schema Boots","offers":{"price":"79.00"}}
  </script>
  <script id="__NEXT_DATA__" type="application/json">
    {"props":{"pageProps":{"items":[{"title":"Schema Boots","price":79}]}}}
  </script>
</head><body><h1>Schema Boots</h1></body></html>
"""

CHALLENGE_HTML = """
<html><head><title>Just a moment...</title></head>
<body><div id="cf-challenge">Checking your browser before accessing this site.</div></body></html>
"""

API_LIST_JSON = {
    "items": [
        {"title": "API Alpha", "price": 10.5, "link": "/p/api-alpha"},
        {"title": "API Beta", "price": 20.0, "link": "/p/api-beta"},
    ]
}


SITE_ZOO: dict[str, SiteZooFixture] = {
    "static_list": SiteZooFixture(
        name="static_list",
        url="mock://site-zoo/static-list",
        html=STATIC_LIST_HTML,
        category="static",
        description="Static product-list page with repeated product cards.",
    ),
    "product_detail": SiteZooFixture(
        name="product_detail",
        url="mock://site-zoo/product-detail",
        html=PRODUCT_DETAIL_HTML,
        category="detail",
        description="Product detail page with variant links.",
    ),
    "variant_detail": SiteZooFixture(
        name="variant_detail",
        url="mock://site-zoo/variant-detail",
        html=VARIANT_DETAIL_HTML,
        category="variant",
        description="Variant detail page with color and size fields.",
    ),
    "spa_shell": SiteZooFixture(
        name="spa_shell",
        url="mock://site-zoo/spa-shell",
        html=SPA_SHELL_HTML,
        category="spa",
        description="Client-rendered shell with API hint.",
    ),
    "structured": SiteZooFixture(
        name="structured",
        url="mock://site-zoo/structured",
        html=STRUCTURED_HTML,
        category="structured",
        description="Page with JSON-LD and Next.js data.",
    ),
    "api_hint_static": SiteZooFixture(
        name="api_hint_static",
        url="mock://site-zoo/api-hint-static",
        html=API_HINT_STATIC_HTML,
        category="api",
        description="Static page that points at a mock JSON product API.",
    ),
    "challenge": SiteZooFixture(
        name="challenge",
        url="mock://site-zoo/challenge",
        html=CHALLENGE_HTML,
        category="challenge",
        description="Challenge-like page used for diagnosis tests.",
    ),
}


def get_fixture(name: str) -> SiteZooFixture:
    try:
        return SITE_ZOO[name]
    except KeyError as exc:
        raise ValueError(f"unknown site-zoo fixture: {name}") from exc


def fixture_by_url(url: str) -> SiteZooFixture | None:
    for fixture in SITE_ZOO.values():
        if fixture.url == url:
            return fixture
    return None
