# E2E Training Summary v2 - 2026-06-02
Generated: 2026-06-02 10:11:49

## Overview
- Total sites: 8
- Success (pass): 7
- Failed: 1
- Total records: 196
- Avg field coverage: 79.5%

## v2 Metrics
- Pagination followed: 0/0
- SPA auto-upgrade: 0/0
- Price range OK: 7/8

## Batch 1 - Easy

### ✅ batch1_dummyjson_products
- URL: https://dummyjson.com/products
- Records: 30, Coverage: 96.4%
- Elapsed: 3.83s
- Notes: ["Sample fields: ['id', 'title', 'description', 'category', 'price', 'discountPercentage', 'rating', 'stock', 'tags', 'brand', 'sku', 'weight', 'dimensions', 'warrantyInformation', 'shippingInformation', 'availabilityStatus', 'reviews', 'returnPolicy', 'minimumOrderQuantity', 'meta', 'images', 'thumbnail', 'link', 'image', 'hot_score', 'summary', 'rank', 'index']"]

### ✅ batch1_dummyjson_categories
- URL: https://dummyjson.com/products/categories
- Records: 24, Coverage: 70.0%
- Elapsed: 4.3s
- Notes: ["Sample fields: ['slug', 'name', 'url', 'title', 'link', 'image', 'hot_score', 'summary', 'rank', 'index']"]

### ✅ batch1_jsonplaceholder_posts
- URL: https://jsonplaceholder.typicode.com/posts
- Records: 100, Coverage: 70.0%
- Elapsed: 5.21s
- Notes: ["Sample fields: ['userId', 'id', 'title', 'body', 'link', 'image', 'hot_score', 'summary', 'rank', 'index']"]

## Batch 2 - Medium

### ✅ batch2_scrapingcourse_ecommerce
- URL: https://www.scrapingcourse.com/ecommerce/
- Records: 16, Coverage: 100.0%
- Elapsed: 8.05s
- Notes: ["Sample fields: ['url', 'index', 'title', 'price', 'image', 'link']"]

### ✅ batch2_scrapingcourse_pagination
- URL: https://www.scrapingcourse.com/pagination/
- Records: 12, Coverage: 100.0%
- Elapsed: 8.95s
- Notes: ["Sample fields: ['url', 'index', 'title', 'price', 'image', 'link']"]

## Batch 3 - Hard

### ✅ batch3_marksandspencer
- URL: https://www.marksandspencer.com/
- Records: 10, Coverage: 100.0%
- Elapsed: 5.27s
- Notes: ["Sample fields: ['url', 'index', 'title', 'price', 'image', 'link']"]

### ❌ batch3_nike
- URL: https://www.nike.com/
- Records: 0, Coverage: 0.0%
- Elapsed: 3.7s

### ✅ batch3_superdry
- URL: https://www.superdry.com/
- Records: 4, Coverage: 100.0%
- Elapsed: 6.46s
- Price: ❌ range parsing issue
- Notes: ["Sample fields: ['url', 'index', 'title', 'price', 'image', 'link']", "Price range detected in output: Women's Brands Bench New Athletic Essentials Women's Clothing Trending on TikTok New Jackets & Coats Hoodies & Sweatshirts Dresses New Tops Bottoms T-Shirts View All New Men's Brands Bench New Vintage Carhartt College Prep Men's Clothing Trending on TikTok New Jackets & Coats New Hoodies & Sweatshirts T-Shirts Tops & Shirts View All New"]
