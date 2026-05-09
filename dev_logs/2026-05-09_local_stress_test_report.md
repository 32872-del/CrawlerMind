# 2026-05-09 Local Stress Test Report

This is a local synthetic test. It does not send requests to public websites.

## Config

- items: 30000
- batch_size: 500
- keep_excel: True

## Timing

- frontier add: 2.373s
- frontier claim/mark: 8.002s
- result store save: 2.726s
- result store load: 1.372s
- Excel export: 21.654s

## Sizes

- frontier db: 12267520 bytes
- result db: 38539264 bytes
- Excel file: 2161256 bytes
- peak memory: 196.07 MB

## Findings

- PASS: frontier inserted, claimed, and completed all unique synthetic URLs.
- PASS: duplicate and invalid URL paths were exercised.
- PASS: result store saved and loaded all synthetic records.
- PASS: Excel export completed for the requested row count.
- RISK: current CrawlResultStore duplicates large result payloads in final_state_json and crawl_items, so very large crawls need checkpointed product storage before real long runs.
- RISK: FastAPI job registry remains in-memory; process restart loses running job state.
