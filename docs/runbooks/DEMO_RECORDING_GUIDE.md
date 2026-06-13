# CLM Demo Recording Guide

This guide describes the shortest useful demo for Crawler-Mind.

The goal is to show that CLM is not just a scraper script. A good demo should
show:

- environment check
- one-command ecommerce demo
- generated report
- optional API server
- optional Chinese workbench
- clear next step toward AI managed crawling

## Demo Length

Recommended length:

```text
60 - 120 seconds
```

## Script

### 1. Start From A Clean Terminal

```bash
python clm.py check
```

Narration:

```text
CLM first checks local Python dependencies, output folders, and optional LLM
configuration.
```

### 2. Run The Recommended Demo

```bash
python clm.py demo ecommerce
```

Narration:

```text
The default demo runs offline. It proves profile-driven ecommerce collection,
pause/resume, checkpointing, product storage, and quality gate reporting without
depending on a public website.
```

Expected result:

```text
Demo accepted
records: 55
status: completed
```

### 3. Show The Report

Open:

```text
dev_logs/runtime/clm_demo_ecommerce.json
```

Point out:

- scenario
- status
- record count
- quality gate
- highlights

### 4. Optional: Start The API

```bash
uvicorn autonomous_crawler.api.app:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

Point out managed endpoints:

```text
/site/analyze
/runs/managed/execute-and-run
/runs/managed/diagnose-and-repair
/runs/{task_id}/managed-control-loop
```

### 5. Optional: Start The Workbench

```bash
cd frontend
npm install
npm run dev -- --port 5174
```

Open:

```text
http://127.0.0.1:5174
```

Point out:

- LLM configuration
- site analysis
- task detail
- managed action panels
- export path controls

## What Not To Overclaim

Do not present CLM as a finished SaaS product yet.

Correct framing:

```text
CLM is an active AI-managed crawler engineering platform. The backend and
workbench are usable locally, and the current milestone is real-site managed
loop hardening.
```

Avoid saying:

```text
CLM can solve every difficult website automatically today.
```

## GitHub README Demo Block

The README should point to:

```bash
python clm.py demo ecommerce
```

and then link here for recording details.
