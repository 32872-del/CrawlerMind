"""Quick re-training to verify bug fixes."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from autonomous_crawler.tools.product_quality import parse_price, parse_lowest_price
from autonomous_crawler.tools.pagination import detect_pagination_links
from autonomous_crawler.runners.managed_actions import (
    ManagedActionPlan,
    ManagedCrawlAction,
    build_deterministic_action_plan,
    execute_managed_action_plan,
)
from autonomous_crawler.llm.provider_registry import build_registry_from_config


def test_price_fix():
    """Verify price range parsing is fixed."""
    print("[1/3] Price Range Fix Verification")
    cases = [
        ("£13 - £26", 26.0, 13.0),
        ("$49.99 - $99.99", 99.99, 49.99),
        ("EUR 139", 139.0, 139.0),
        ("1,299.95", 1299.95, 1299.95),
        ("free", 0.0, 0.0),
    ]
    for text, expected_high, expected_low in cases:
        high = parse_price(text)
        low = parse_lowest_price(text)
        ok_h = abs(high - expected_high) < 0.01 if high else False
        ok_l = abs(low - expected_low) < 0.01 if low else False
        status = "OK" if ok_h and ok_l else "FAIL"
        print(f"  [{status}] '{text}' -> high={high}, low={low}")
    print()


def test_pagination_fix():
    """Verify pagination detection works."""
    print("[2/3] Pagination Detection Verification")
    # Simulate a paginated HTML page
    html = """
    <html><body>
    <div class="products">
        <div class="item">Product 1</div>
        <div class="item">Product 2</div>
    </div>
    <nav class="pagination">
        <a href="/products?page=1">1</a>
        <span class="current">2</span>
        <a href="/products?page=3" rel="next">Next</a>
    </nav>
    </body></html>
    """
    urls = detect_pagination_links(html, "https://example.com/products?page=2")
    print(f"  Detected {len(urls)} pagination URLs:")
    for url in urls[:5]:
        print(f"    - {url}")
    print()


def test_managed_actions():
    """Verify managed actions work with new actions."""
    print("[3/3] Managed Actions (with new actions)")
    # Build registry
    registry = build_registry_from_config("clm_config.json")
    advisor = registry.get_advisor()

    target_url = "https://dummyjson.com/products"
    profile = {
        "name": "dummyjson",
        "target_url": target_url,
        "target_fields": ["title", "price", "description"],
    }
    plan = build_deterministic_action_plan(
        target_url=target_url,
        profile=profile,
    )
    print(f"  Plan actions: {len(plan.actions)}")
    for a in plan.actions:
        print(f"    - {a.action}")

    result = execute_managed_action_plan(
        plan=plan,
        target_url=target_url,
        profile=profile,
        advisor=advisor,
        llm_decide=advisor is not None,
    )
    print(f"  Executed: {len(result.get('results') or [])} actions")
    print(f"  Source: {result.get('plan_source', 'unknown')}")
    print()


if __name__ == "__main__":
    print("=" * 50)
    print("Bug Fix Verification Suite")
    print("=" * 50)
    print()
    test_price_fix()
    test_pagination_fix()
    test_managed_actions()
    print("=" * 50)
    print("Done!")
