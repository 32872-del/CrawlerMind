# Round 2 Assignment: Real Dynamic And Protected Training

Date: 2026-05-14

Employee: `LLM-2026-001`

Priority: P0

Track: `SCRAPLING-ABSORB-2I / CAP-4.2 / CAP-5.2`

## Mission

After finishing the current browser profile-pool task, run the native browser
backend through real dynamic/protected training and produce evidence that tells
us where the final gaps are.

## Scope

Use:

- `NativeBrowserRuntime`
- `BrowserPoolManager`
- browser profile rotation from your current task
- optional `browser_config.visual_recon=true`
- existing dynamic comparison helpers

## Requirements

1. Add a real-training script or extend the existing comparison runner so it can
   run at least three external dynamic cases:
   - JS-rendered catalog/list page
   - infinite scroll or delayed content page
   - protected/challenge-like page that should produce structured failure
     evidence rather than crash
2. Capture:
   - rendered HTML length
   - selector hit counts
   - XHR count
   - profile/pool evidence
   - failure classification
   - screenshot/visual_recon evidence when enabled
3. No site-specific extraction rules in core runtime.
4. Save JSON evidence under `dev_logs/training/`.
5. Add focused tests for any new runner/config code.

## Acceptance

Report:

- sites/cases run
- pass/fail/degraded counts
- which failure classes appeared
- whether profile rotation changed evidence
- what remains before production protected-site use
