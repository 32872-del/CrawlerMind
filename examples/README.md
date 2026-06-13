# CLM Examples

This directory contains stable demo paths for first-time users and reviewers.
The examples are intentionally small and mostly offline so a fresh clone can
show useful CLM behavior without depending on a changing public website.

## 1. Quick Ecommerce Demo

Recommended first command:

```bash
python clm.py demo ecommerce
```

What it demonstrates:

- profile-driven ecommerce collection
- checkpointed pause/resume
- product store writes
- quality gate summary
- report generation

The demo uses a deterministic local fixture runtime and writes:

```text
dev_logs/runtime/clm_demo_ecommerce.json
```

Expected result:

```text
Demo accepted
records: 55
status: completed
```

## 2. Basic Mock Crawl

```bash
python clm.py demo mock
```

What it demonstrates:

- the original crawl workflow path
- mock target support
- deterministic product title and price extraction

Expected result:

```text
accepted: true
records: 2
```

## 3. Native Spider Demo

```bash
python clm.py demo spider
```

What it demonstrates:

- URL frontier
- link discovery
- detail-page extraction
- checkpoint persistence
- pause/resume behavior
- failure bucket recording

Expected result:

```text
accepted: true
records: 2
failures: 1
```

## 4. Public Page Smoke

This command touches a public website, so it can change over time:

```bash
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --output dev_logs/runtime/baidu_hot.json
```

It is useful for showing the older end-to-end ranking-list workflow on a real
page.

## 5. API / GraphQL / Browser Training Commands

Developer training commands are listed by:

```bash
python clm.py train
```

Important historical training outputs are preserved under:

```text
dev_logs/training/
docs/reports/
```

## Suggested Demo Order

For a short recording or live walkthrough:

1. `python clm.py check`
2. `python clm.py demo ecommerce`
3. Show `dev_logs/runtime/clm_demo_ecommerce.json`
4. Start the API server:

   ```bash
   uvicorn autonomous_crawler.api.app:app --reload --host 127.0.0.1 --port 8000
   ```

5. Start the frontend:

   ```bash
   cd frontend
   npm install
   npm run dev -- --port 5174
   ```

6. Open the Chinese workbench at:

   ```text
   http://127.0.0.1:5174
   ```

This gives reviewers a quick path from CLI proof to product surface.
