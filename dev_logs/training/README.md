# Private Training Assets

The full CLM training asset set was moved out of the public CrawlerMind
repository on 2026-06-13.

## Where It Lives

Private repository:

```text
32872-del/ClawWork
```

Private package path:

```text
training_assets_full_20260613/dev_logs_training
```

## What Was Moved

This directory used to contain real-site training runs, visual reconnaissance
screenshots, extraction contract samples, generated exports, managed-loop E2E
results, replay/API evidence, and failure taxonomy reports.

Those files are valuable private training evidence and are intentionally not
kept in the public Community repository.

## Restore Locally

From a local checkout of the private `ClawWork` repository:

```powershell
$clm = "F:\datawork\agent"
New-Item -ItemType Directory -Force -Path "$clm\dev_logs" | Out-Null
Copy-Item -LiteralPath ".\training_assets_full_20260613\dev_logs_training" `
  -Destination "$clm\dev_logs\training" `
  -Recurse -Force
```

Before restoring, check `training_assets_full_20260613/MANIFEST.json` and
`SHA256SUMS.json` if you need evidence-grade integrity verification.

## Public Repo Rule

Do not commit generated training data, screenshots, large `.xlsx` exports, or
real-site raw evidence back into this public path. Keep public examples small,
sanitized, and intentional.
