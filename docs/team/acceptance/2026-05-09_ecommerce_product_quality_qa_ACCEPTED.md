# Acceptance: Ecommerce Product Quality QA

Employee ID: `LLM-2026-002`

Project role: QA / Product Data Quality Worker

Status: accepted

Date: 2026-05-09

## Accepted Work

- Created `docs/team/audits/2026-05-09_LLM-2026-002_ECOMMERCE_PRODUCT_QUALITY_QA.md`.
- Created `dev_logs/2026-05-09_ecommerce_product_quality_qa.md`.
- Converted `spider_text` ecommerce lessons into a QA plan covering:
  - normalized product schema
  - price normalization
  - image filtering and dedupe
  - body/detail preservation
  - color, size, and variant handling
  - category-aware dedupe
  - three-phase category/list/detail/variant workflow
  - anti-starvation and smoke-flow risks

## Supervisor Review

Accepted. This was a design/QA task, not an implementation task. The audit is
useful because it turns old project experience into concrete acceptance tests
for CLM's next ecommerce layer.

The highest-value finding is the anti-starvation rule: ecommerce crawling must
not spend too long expanding categories/lists while producing no detail records.
The real-site training on 2026-05-09 confirmed this point: useful validation
came from small list pages followed immediately by detail extraction.

## Follow-Up

1. Implement `ProductRecord`, price/body/image/variant normalization helpers,
   and `validate_product_record()`.
2. Convert the real-site ecommerce samples from
   `dev_logs/2026-05-09_ecommerce_training_sample.json` into fixtures.
3. Add tests for Shopify JSON products, Magento list/detail pages, Magento
   `jsonConfig` variant sizes, Cloudflare diagnosis-only rows, and corporate
   product pages without prices.
