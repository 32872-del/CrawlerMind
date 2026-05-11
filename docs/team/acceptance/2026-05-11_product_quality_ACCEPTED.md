# Acceptance: Product Quality Foundation

Date: 2026-05-11

Accepted by: LLM-2026-000 Supervisor Codex

Worker output accepted after supervisor cleanup:

- `autonomous_crawler/tools/product_quality.py`
- `autonomous_crawler/tests/test_product_quality.py`

## Acceptance Notes

The product quality layer is accepted as a generic validation module. It does
not hard-code named-site rules. Site differences are expressed through profile
overrides such as `allow_partial`, `price_required`, `image_required`,
`min_description_length`, and `dedupe_key_required`.

The supervisor cleaned up encoding-sensitive test text and rewrote the test
file to avoid terminal mojibake drift.

## Verification

```text
python -m unittest autonomous_crawler.tests.test_product_quality -v
Ran 23 tests
OK
```

Coverage includes:

- common European/US price formats
- highest-price behavior for ranges
- negative price errors
- blocked records with required notes
- partial records
- missing title/URL/image/dedupe warnings and errors
- noise image and data URI detection
- `ProductRecord` dataclass input

## Follow-Ups

- Tune severity levels after more real ecommerce training.
- Add profile files once site profiles become a first-class runtime concept.
