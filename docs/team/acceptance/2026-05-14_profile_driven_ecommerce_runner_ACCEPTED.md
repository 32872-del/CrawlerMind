# Acceptance: Site Profile And Profile-Driven Ecommerce Runner

Date: 2026-05-14

Employee: `LLM-2026-004`

Assignment: `SCRAPLING-ABSORB-3G`

Status: accepted

## Verdict

Accepted. The long-run spider layer can now consume explicit site profiles and
run ecommerce extraction through generic callbacks instead of hard-coded site
rules.

## Accepted Evidence

- `SiteProfile` provides a structured place for selectors, access config,
  pagination/link hints, and quality expectations.
- `LangGraphBatchProcessor` wraps the existing workflow in a batch-processor
  shape for resumable runs.
- `profile_ecommerce.py` translates site profiles into selector, record, and
  link callbacks for `SpiderRuntimeProcessor`.
- The fixture profile proves category/list/detail flow without external
  network access.
- Smoke evidence is saved at
  `dev_logs/smoke/2026-05-14_profile_ecommerce_runner_smoke.json`.

## Verification

Supervisor focused verification:

```text
python -m unittest autonomous_crawler.tests.test_spider_runner autonomous_crawler.tests.test_profile_ecommerce_runner autonomous_crawler.tests.test_checkpoint_store -v
Ran 18 tests
OK
```

## Follow-Up

- Wire observed API pagination into profile-driven ecommerce runs.
- Persist profile-level quality summaries into run reports.
- Add real ecommerce profile training cases after the native baseline is
  committed.

