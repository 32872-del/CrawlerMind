# Crawler-Mind Crawling Governance

Date: 2026-05-14

## Purpose

This document is the place for CLM usage policy, customer responsibility,
commercial deployment rules, audit expectations, and compliance language.

Capability documents should describe what the crawler can do and what still
needs engineering work. Governance documents describe how the product should be
used, packaged, audited, and offered to customers.

## Working Rule

```text
Capability layer: build strong crawler runtime and agent abilities.
Governance layer: define usage rules, enterprise terms, approval flows, and logs.
```

This separation keeps engineering documents focused on capability while still
preserving a clear place for release, customer, and legal review.

## Areas Covered Here

- customer access responsibility
- enterprise authorization language
- data handling and retention policy
- credential and proxy secret handling
- audit log requirements
- optional provider integrations
- release checklist language
- commercial terms and accepted-use policy

## Engineering Documents Should Link Here When Needed

Use this file as the policy reference from README, release notes, enterprise
pilots, and deployment documents. Do not bury governance rules inside runtime
modules, crawler adapters, or capability matrices.

## Current Engineering Implication

CLM should continue building advanced crawler capabilities aggressively:

- Scrapling-first runtime
- browser/protected runtime profiles
- proxy pool adapters
- JS reverse-engineering evidence and execution tracks
- CAPTCHA/OCR/visual recognition plug-ins
- long-running spider/checkpoint infrastructure
- real-site training and stress testing

Before public release or enterprise deployment, product owners can attach
customer terms, permission requirements, provider rules, and audit defaults here.
