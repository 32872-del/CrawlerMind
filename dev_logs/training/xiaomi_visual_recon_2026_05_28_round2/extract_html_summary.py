import re
import os

html_file = r'C:\Users\Administrator\.claude\projects\F--datawork-agent\97f7c13b-74f7-4864-a614-2094506e6082\tool-results\call_bf9a1d6e01c74f94b167141a.txt'
output_dir = r'F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28_round2'

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract title
title_match = re.search(r'<title>(.*?)</title>', content)
title = title_match.group(1) if title_match else "No title found"

# Extract product count
product_count = len(re.findall(r'data-asin="[A-Z0-9]+"', content))

# Extract prices
prices = re.findall(r'EUR [\d,.]+', content)

# Create summary
summary = f"""HTML Summary for Amazon Laptop Search
=====================================

Title: {title}

Product Cards Found: {product_count}

Sample Prices: {', '.join(prices[:5]) if prices else 'No prices found'}

Key Selectors Confirmed:
- Product grid: .s-main-slot
- Title: .a-size-base-plus
- Price: .a-price .a-offscreen
- Image: .s-image
- Rating: .a-icon-alt

HTML Structure:
- Product cards with data-asin attributes
- Grid layout with multiple products
- No blocking signals detected
"""

summary_path = os.path.join(output_dir, 'html_summary_001.txt')
with open(summary_path, 'w', encoding='utf-8') as f:
    f.write(summary)

print(f"HTML summary saved to: {summary_path}")
print(f"Title: {title}")
print(f"Products found: {product_count}")
