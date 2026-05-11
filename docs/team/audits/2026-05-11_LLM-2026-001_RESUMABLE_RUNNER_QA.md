# Audit: Resumable Batch Runner QA

Employee: LLM-2026-001
Date: 2026-05-11

## Scope

Read-only QA audit of the resumable batch runner infrastructure:

- `autonomous_crawler/storage/frontier.py` — URL frontier with lease-based batch claiming
- `autonomous_crawler/storage/product_store.py` — SQLite product store with batch upsert
- `docs/runbooks/LONG_RUNNING_ECOMMERCE_RUNS.md` — operational runbook
- `docs/process/ECOMMERCE_CRAWL_WORKFLOW.md` — workflow definition

Goal: identify risks, missing guards, and test gaps for long-running ecommerce
crawls that must survive interruption, resume from checkpoint, and handle
thousands of URLs across multiple batches.

## Architecture Summary

```
                     ┌──────────────┐
                     │  URL Frontier │  (frontier.sqlite3)
                     │  queued →     │
                     │  running →    │
                     │  done / failed│
                     └──────┬───────┘
                            │ next_batch() / mark_done() / mark_failed()
                            ▼
                     ┌──────────────┐
                     │  Batch Loop  │
                     │  claim →     │
                     │  fetch →     │
                     │  extract →   │
                     │  validate    │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ ProductStore │  (products.sqlite3)
                     │ upsert_many  │
                     │ run stats    │
                     └──────────────┘
```

Two independent SQLite databases. No cross-database transaction.
The batch loop (caller) is responsible for the claim→process→save→mark_done
sequence. Frontier and ProductStore are stateless services.

## Findings

### F-RR001: `_mark` silently accepts zero matches (severity: medium, type: bug risk)

`frontier.py:150-166` — `_mark()` iterates items, executes UPDATE for each,
and counts `cursor.rowcount`. If the item ID or URL does not exist, `rowcount`
is 0 and the method returns a count less than `len(items)`. No exception is
raised.

**Risk:** A caller passing a stale ID list (e.g., from a crashed batch that
was already reclaimed by lease expiry) will think fewer items were marked but
won't know which ones failed. There is no way to distinguish "item doesn't
exist" from "item was already marked done by another worker."

**Suggested test:**
```python
def test_mark_done_nonexistent_id_returns_zero(self):
    changed = self.frontier.mark_done([99999])
    self.assertEqual(changed, 0)

def test_mark_done_already_done_returns_zero(self):
    # add URL, claim, mark_done, mark_done again
    # second mark_done should return 0 (already done)
```

**Fix direction:** Consider returning a structured result `{"changed": N, "missing": M}`
or at minimum logging when `rowcount == 0`.

---

### F-RR002: No retry/attempts limit — infinite re-queue loop (severity: high, type: bug)

`frontier.py:142-143` — `mark_failed(retry=True)` sets status back to `'queued'`
unconditionally. The `attempts` counter increments each time `next_batch()`
claims a URL, but nothing checks it against a maximum.

**Risk:** A URL that always fails (404, permanently blocked, malformed) will be
re-queued forever. Over hours of a long run, the frontier fills with poison
pills that waste cycles and never complete.

**Suggested test:**
```python
def test_mark_failed_retry_increments_attempts(self):
    # add URL, claim batch (attempts=1), mark_failed(retry=True)
    # claim again (attempts=2), mark_failed(retry=True)
    # assert attempts == 2

def test_poison_url_requeued_forever(self):
    # add URL, loop: claim → fail → retry 100 times
    # assert URL is still in 'queued' status (demonstrates the problem)
```

**Fix direction:** Add `max_retries` parameter to `mark_failed()`. When
`attempts >= max_retries`, set status to `'failed'` instead of `'queued'`.
Default `max_retries=3`.

---

### F-RR003: Lease expiration race condition (severity: medium, type: concurrency)

`frontier.py:112-132` — `next_batch()` runs two statements in one transaction:
1. SELECT rows where `status='queued' OR (status='running' AND locked_at < expired)`
2. UPDATE those rows to `status='running'` with new lease_token

Under SQLite's default isolation, two concurrent workers calling `next_batch()`
could SELECT the same rows before either UPDATE commits. Both would then claim
the same batch.

**Risk:** Duplicate processing. Two workers fetch and extract the same URLs.
ProductStore dedupe prevents duplicate records, but wasted work and potential
rate-limit violations occur.

**Suggested test:**
```python
def test_concurrent_next_batch_no_overlap(self):
    # Add 20 URLs. Call next_batch(10) from two connections.
    # Assert total claimed <= 20, no ID appears in both batches.
```

**Fix direction:** Use `BEGIN IMMEDIATE` or `BEGIN EXCLUSIVE` instead of
default deferred transactions. Alternatively, use `UPDATE ... RETURNING id`
(SQLite 3.35+) to atomically claim in a single statement.

---

### F-RR004: ProductStore and frontier are separate databases (severity: medium, type: design gap)

ProductStore writes to `products.sqlite3`. Frontier writes to `frontier.sqlite3`.
There is no atomic "save products AND mark URLs done" operation.

**Risk:** A crash between `ProductStore.upsert_many()` and
`frontier.mark_done()` leaves the system in an inconsistent state:
- Products are saved but frontier URLs still show `running` (lease expiry will reclaim → duplicate upsert, mitigated by dedupe key)
- Products are NOT saved but frontier URLs are marked `done` (data loss)

The second case is the dangerous one. The runbook says "keep runtime SQLite
files" for recovery, but there's no mechanism to detect which URLs were
processed but not marked done.

**Suggested test:**
```python
def test_crash_between_save_and_mark_done(self):
    # Add URLs, claim batch, save products, but DON'T mark_done.
    # Simulate restart: check frontier stats — URLs still 'running'.
    # After lease expiry, next_batch reclaims them.
    # Verify ProductStore dedupe prevents double-insert.
```

**Fix direction:** Consider writing a lightweight "batch progress" row to
frontier or a shared database that records which URLs were product-saved.
On resume, skip URLs that are already product-saved even if frontier shows
`running`.

---

### F-RR005: No batch-level progress tracking (severity: medium, type: gap)

`docs/runbooks/LONG_RUNNING_ECOMMERCE_RUNS.md:28` says "Write a compact
progress event." Neither frontier.py nor product_store.py implements this.

**Risk:** For a 30,000-URL run, there's no way to query:
- How many URLs have been processed in this run
- What the throughput is (URLs/minute)
- Estimated time remaining
- Which batch is currently in progress

The caller must compute this from `frontier.stats()` + `ProductStore.count_total()`,
which requires knowing the run_id and making two queries across two databases.

**Suggested test:**
```python
def test_progress_queryable_after_batches(self):
    # Process 3 batches of 10 URLs each.
    # Query progress: expect 30 processed, 30 done in frontier.
```

**Fix direction:** Add a `progress_events` table to frontier.sqlite3 with
columns `(run_id, batch_num, urls_claimed, urls_done, urls_failed, products_saved, timestamp)`.
Write one row per batch completion.

---

### F-RR006: `mark_done` by URL string is fragile (severity: low, type: risk)

`frontier.py:162-164` — `_mark()` with a string item does:
```sql
UPDATE frontier_urls SET status=? WHERE url=?
```

This matches on the `url` column. But URLs are canonicalized on insertion via
`canonical_url()`. If the caller passes a slightly different URL (trailing
slash, different case in scheme, query param order), the UPDATE matches nothing.

**Risk:** Low — the caller typically uses IDs from `next_batch()` return value.
But if a recovery script passes raw URLs, matches may fail silently.

**Suggested test:**
```python
def test_mark_done_by_url_requires_exact_match(self):
    self.frontier.add_urls(["https://example.com/page"])
    # mark_done with "https://example.com/page/" (trailing slash) → 0 changed
```

**Fix direction:** Either document that `_mark` by URL requires exact
canonicalized form, or canonicalize the input URL in `_mark` before matching.

---

### F-RR007: No per-domain concurrency control (severity: medium, type: gap)

`next_batch()` claims URLs ordered by `priority DESC, created_at ASC` with no
domain filtering. Two workers can claim URLs from the same domain and fire
concurrent requests.

**Risk:** Rate limit violations, IP blocks, or degraded response quality. For
a long run hitting a single site, all URLs come from one domain. Multiple
workers would overwhelm it.

**Suggested test:**
```python
def test_next_batch_can_return_single_domain(self):
    # Add 20 URLs from same domain.
    # next_batch(20) returns all 20 — no domain spread.
```

**Fix direction:** Add optional `max_per_domain` parameter to `next_batch()`.
Or the caller can use domain-aware batching (one worker per domain).

---

### F-RR008: SQLite WAL mode not explicitly configured (severity: low, type: risk)

Neither `frontier.py` nor `product_store.py` sets `PRAGMA journal_mode=WAL`.
SQLite defaults to DELETE journal mode, which uses file-level locking.

**Risk:** Under DELETE mode, concurrent readers and writers block each other.
For a single-worker scenario this is fine. For multi-worker with separate
connections, performance degrades significantly.

**Suggested test:**
```python
def test_journal_mode_is_wal(self):
    conn = self.frontier.connect()
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    # If WAL is desired: self.assertEqual(mode, "wal")
```

**Fix direction:** Add `PRAGMA journal_mode=WAL` in `connect()` or
`initialize()` if multi-worker support is planned.

---

### F-RR009: `next_batch` lease_token re-fetch is redundant but safe (severity: info, type: code quality)

`frontier.py:133-136` — After UPDATE, the method re-SELECTs rows matching the
new `lease_token`. Since UUIDs are unique, this always returns exactly the rows
just claimed. The re-fetch is safe but unnecessary — the IDs are already known.

**Risk:** None. Minor performance overhead for the extra query.

**Fix direction:** Could return the rows from the UPDATE...RETURNING clause
(SQLite 3.35+) or just use the IDs from the initial SELECT.

---

### F-RR010: No maximum frontier size guard (severity: medium, type: gap)

`add_urls()` inserts without checking total frontier size. A runaway category
discovery could insert millions of URLs.

**Risk:** SQLite database grows unbounded. `next_batch()` queries slow down.
Memory pressure increases.

**Suggested test:**
```python
def test_frontier_allows_large_insert(self):
    # Insert 100K URLs — should succeed but may be slow.
    # Consider adding a max_frontier_size parameter.
```

**Fix direction:** Add optional `max_frontier_size` check in `add_urls()`.
Reject or warn when frontier exceeds threshold.

---

### F-RR011: `attempts` counter never resets on success (severity: info, type: design)

`attempts` increments every time `next_batch()` claims a URL, including the
first claim. A URL claimed 3 times (2 failures + 1 success) shows `attempts=3`
in the done row. This is informational but could confuse retry-limit logic if
added later.

**Suggested test:**
```python
def test_attempts_increments_on_each_claim(self):
    # Claim → fail → retry → claim → done
    # assert attempts == 3 (not 2)
```

**Fix direction:** If retry limiting is added, compare `attempts` against
`max_retries` at `mark_failed` time, not at `next_batch` time.

---

### F-RR012: No run-level isolation in frontier (severity: low, type: gap)

Frontier has no `run_id` concept. All URLs share one table. If two crawl runs
target different sites, their URLs intermingle. `next_batch()` could claim
URLs from either run.

**Risk:** Low for current usage (one run at a time). But if parallel runs
are ever needed, the frontier cannot distinguish them.

**Suggested test:**
```python
def test_no_run_isolation(self):
    # Add URLs for "run-A" and "run-B" to same frontier.
    # next_batch() returns mixed URLs — no way to filter.
```

**Fix direction:** Add optional `run_id` column to frontier_urls if parallel
runs are needed. Otherwise document single-run assumption.

---

## Test Gap Summary

| # | Test Needed | Priority |
|---|---|---|
| 1 | `mark_done` on nonexistent ID returns 0 | medium |
| 2 | `mark_failed(retry=True)` re-queues without limit | **high** |
| 3 | Concurrent `next_batch` no overlap | medium |
| 4 | Crash between product save and mark_done | medium |
| 5 | Batch progress queryable after processing | medium |
| 6 | `mark_done` by URL requires exact canonical form | low |
| 7 | `next_batch` returns single-domain batches | medium |
| 8 | SQLite journal mode check | low |
| 9 | Retry limit enforcement (when added) | **high** |
| 10 | Frontier size guard | medium |
| 11 | Attempts counter behavior across claim lifecycle | info |
| 12 | Run-level isolation (if parallel runs needed) | low |

## Risk Summary

| Finding | Severity | Type |
|---------|----------|------|
| F-RR001 `_mark` silent zero match | medium | bug risk |
| F-RR002 No retry limit — infinite re-queue | **high** | bug |
| F-RR003 Lease expiration race condition | medium | concurrency |
| F-RR004 Separate databases — no atomicity | medium | design gap |
| F-RR005 No batch-level progress tracking | medium | gap |
| F-RR006 `mark_done` by URL fragile | low | risk |
| F-RR007 No per-domain concurrency control | medium | gap |
| F-RR008 WAL mode not configured | low | risk |
| F-RR009 Redundant lease_token re-fetch | info | code quality |
| F-RR010 No max frontier size guard | medium | gap |
| F-RR011 Attempts never resets on success | info | design |
| F-RR012 No run-level isolation | low | gap |

**Highest severity: high** (F-RR002). A permanently-failing URL will be
re-queued forever, consuming cycles in every batch until the run is manually
stopped. This is the most impactful bug for long-running crawls.

## Recommended Fix Priority

1. **F-RR002** — Add `max_retries` to `mark_failed()`. Blocks safe long runs.
2. **F-RR005** — Add progress events table. Required for operational visibility.
3. **F-RR003** — Use `BEGIN IMMEDIATE` for `next_batch()`. Blocks multi-worker.
4. **F-RR004** — Design batch-progress checkpoint. Required for reliable resume.
5. **F-RR001** — Return structured result from `_mark()`. Improves debuggability.
6. **F-RR007** — Add domain-aware batching. Required for polite crawling.
7. **F-RR010** — Add frontier size limit. Safety net for runaway discovery.

## No Code Changed

This is a read-only QA audit. No implementation files modified.
