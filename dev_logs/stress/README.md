# Private Stress Assets

The full CLM stress-test output set was moved out of the public CrawlerMind
repository on 2026-06-13.

## Where It Lives

Private repository:

```text
32872-del/ClawWork
```

Private package path:

```text
stress_assets_20260613/dev_logs_stress
```

## What Was Moved

This directory used to contain local stress reports and the
`2026-05-09_stress_export_30000.xlsx` generated export.

These files are useful for private performance-history comparison, but they are
not required for a clean public source checkout.

## Restore Locally

From a local checkout of the private `ClawWork` repository:

```powershell
$clm = "F:\datawork\agent"
New-Item -ItemType Directory -Force -Path "$clm\dev_logs" | Out-Null
Copy-Item -LiteralPath ".\stress_assets_20260613\dev_logs_stress" `
  -Destination "$clm\dev_logs\stress" `
  -Recurse -Force
```

Do not commit generated stress outputs back to the public repository unless they
have been intentionally reduced and sanitized.
