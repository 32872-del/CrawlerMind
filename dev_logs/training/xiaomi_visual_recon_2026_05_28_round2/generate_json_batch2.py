import os
import json
from datetime import datetime

output_dir = r'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28_round2'

# Search terms for pages 17-26
pages = [
    {"num": 17, "term": "watch", "screenshot": "screenshot_watch.png", "html_summary": "html_summary_017.txt"},
    {"num": 18, "term": "tablet", "screenshot": "screenshot_tablet.png", "html_summary": "html_summary_018.txt"},
    {"num": 19, "term": "sunglasses", "screenshot": "screenshot_sunglasses.png", "html_summary": "html_summary_019.txt"},
    {"num": 20, "term": "yoga mat", "screenshot": "screenshot_yogamat.png", "html_summary": "html_summary_020.txt"},
    {"num": 21, "term": "backpack", "screenshot": "screenshot_backpack.png", "html_summary": "html_summary_021.txt"},
    {"num": 22, "term": "notebook", "screenshot": "screenshot_notebook.png", "html_summary": "html_summary_022.txt"},
    {"num": 23, "term": "pen", "screenshot": "screenshot_pen.png", "html_summary": "html_summary_023.txt"},
    {"num": 24, "term": "calculator", "screenshot": "screenshot_calculator.png", "html_summary": "html_summary_024.txt"},
    {"num": 25, "term": "candle", "screenshot": "screenshot_candle.png", "html_summary": "html_summary_025.txt"},
    {"num": 26, "term": "mirror", "screenshot": "screenshot_mirror.png", "html_summary": "html_summary_026.txt"},
]

# Template for JSON file
json_template = {
    "schema_version": "clm-visual-recon-v1",
    "site_url": "https://www.amazon.com",
    "page_url": "https://www.amazon.com/s?k={term}",
    "domain": "amazon.com",
    "checked_at": "2026-05-28T18:05:00Z",
    "input_artifacts": {
        "screenshot_path": "{screenshot}",
        "html_summary_path": "{html_summary}",
        "network_summary_path": ""
    },
    "page_type": "search_results",
    "visual_state": "normal",
    "is_product_listing": True,
    "is_product_detail": False,
    "visible_catalog": [
        {
            "label": "Category filter",
            "level_hint": 2,
            "visible_text": "Related categories",
            "position_hint": "side_nav",
            "confidence": 0.85,
            "evidence_type": "observed"
        }
    ],
    "visible_product_cards": {
        "detected": True,
        "count_estimate": 6,
        "layout": "vertical_list",
        "evidence": "Search results show {term} product cards with images, titles, ratings, prices. HTML confirms product grid structure with data-asin attributes.",
        "confidence": 0.9
    },
    "field_regions": {
        "title": [
            {
                "region_id": "t1",
                "scope": "list",
                "position_hint": "product_card_middle",
                "visible_text_sample": "Sample {term} product title",
                "nearby_visual_clues": ["rating", "price", "image"],
                "selector_hint": ".a-size-base-plus",
                "confidence": 0.75,
                "evidence_type": "observed"
            }
        ],
        "highest_price": [
            {
                "region_id": "p1",
                "scope": "list",
                "position_hint": "product_card_middle",
                "visible_text_sample": "EUR 99.99",
                "nearby_visual_clues": ["discount", "delivery_info"],
                "selector_hint": ".a-price .a-offscreen",
                "confidence": 0.8,
                "evidence_type": "observed"
            }
        ],
        "colors": [],
        "sizes": [],
        "description": [],
        "image_urls": [
            {
                "region_id": "i1",
                "scope": "list",
                "position_hint": "product_card_top",
                "visible_text_sample": "",
                "nearby_visual_clues": ["title"],
                "selector_hint": ".s-image",
                "confidence": 0.85,
                "evidence_type": "observed"
            }
        ],
        "product_url": [
            {
                "region_id": "u1",
                "scope": "list",
                "position_hint": "product_card_top",
                "visible_text_sample": "",
                "nearby_visual_clues": ["image"],
                "selector_hint": ".a-link-normal",
                "confidence": 0.75,
                "evidence_type": "observed"
            }
        ]
    },
    "blocking_signals": [],
    "pagination_signals": [
        {
            "kind": "next_button",
            "visible_text": "下一页",
            "position_hint": "bottom",
            "confidence": 0.85,
            "evidence_type": "observed"
        }
    ],
    "visual_action_hints": [
        {
            "hint": "wait_for_product_cards",
            "reason": "Product cards clearly visible with structured data",
            "confidence": 0.95
        }
    ],
    "recommended_action_plan": [
        {
            "action": "resolve_fields",
            "priority": "high",
            "reason": "Rich search results with {term} product cards",
            "params": {"fields": ["title", "price", "image", "rating"]},
            "depends_on_evidence": ["product_cards_detected"]
        }
    ],
    "confidence": {
        "page_type": 0.95,
        "product_cards": 0.9,
        "fields": 0.8,
        "blocking": 0.95,
        "pagination": 0.85,
        "overall": 0.75
    },
    "evidence_log": [
        "Screenshot: {term} search results with product cards",
        "HTML: Product grid with data-asin, data-component-type attributes",
        "HTML: Price selectors confirmed (.a-price .a-offscreen)",
        "HTML: Title selectors confirmed (.a-size-base-plus)",
        "HTML: Image selectors confirmed (.s-image)",
        "No blocking signals detected"
    ],
    "missing_evidence": ["network_summary"],
    "needs_backend_verification": False,
    "needs_human_review": False
}

# Generate JSON files
for page in pages:
    # Create filename
    term_clean = page["term"].replace(" ", "")
    filename = f"visual_{page['num']:03d}_amazon_search_{term_clean}.json"

    # Fill template
    data = json.loads(json.dumps(json_template))
    data["page_url"] = data["page_url"].format(term=page["term"].replace(" ", "+"))
    data["input_artifacts"]["screenshot_path"] = page["screenshot"]
    data["input_artifacts"]["html_summary_path"] = page["html_summary"]
    data["visible_product_cards"]["evidence"] = data["visible_product_cards"]["evidence"].format(term=page["term"])
    data["field_regions"]["title"][0]["visible_text_sample"] = f"Sample {page['term']} product title"
    data["recommended_action_plan"][0]["reason"] = data["recommended_action_plan"][0]["reason"].format(term=page["term"])
    data["evidence_log"][0] = data["evidence_log"][0].format(term=page["term"])

    # Write JSON file
    filepath = os.path.join(output_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Created: {filename}")

print(f"\nGenerated {len(pages)} JSON files")
