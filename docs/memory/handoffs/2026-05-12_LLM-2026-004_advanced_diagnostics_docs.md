# Handoff: Advanced Diagnostics Public Docs Pass

Employee ID: `LLM-2026-004`
Display Name: Worker Delta
Date: 2026-05-12
Status: complete

## Files Updated

- `README.md`

## Files Created

- `docs/runbooks/ADVANCED_DIAGNOSTICS.md`
- `dev_logs/audits/2026-05-12_18-36_advanced_diagnostics_docs.md`
- `docs/memory/handoffs/2026-05-12_LLM-2026-004_advanced_diagnostics_docs.md`

## Summary

Created a public-facing advanced diagnostics runbook for open-source users,
new employees, and enterprise evaluators. README now links to it from Important
Docs without adding internal detail to the front page.

The runbook covers:

- transport diagnostics
- browser interception
- browser network observation
- WebSocket observation
- runtime fingerprint probe
- JS evidence and crypto evidence
- proxy pool and proxy health
- StrategyEvidenceReport

Each capability states:

- current maturity
- how to enable it
- what evidence it outputs
- what it does not do

## Safety Notes

The wording avoids overclaiming. It explicitly says CLM does not:

- crack logins
- solve or bypass CAPTCHAs by default
- automatically bypass Cloudflare
- recover private keys or signing keys
- run a production proxy platform by default
- perform full JavaScript reverse engineering

## Recommended Supervisor Action

Accept this docs pass. Future public docs can link to
`docs/runbooks/ADVANCED_DIAGNOSTICS.md` when users ask what advanced diagnostic
features exist and where the safety boundaries are.
