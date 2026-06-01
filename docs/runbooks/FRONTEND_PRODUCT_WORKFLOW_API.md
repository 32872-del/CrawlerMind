# Frontend Product Workflow API

Date: 2026-05-18

This runbook defines the first product-facing API flow for a CLM frontend. The
goal is to make the crawler agent usable as:

```text
configure -> analyze site -> select catalog/fields -> test 100 rows -> full run -> monitor -> export
```

## 1. Configure

The frontend should collect:

- LLM provider config: `base_url`, `api_key`, `model`, provider name.
- Optional model execution knobs: `reasoning_effort` (`low`, `medium`, `high`,
  `xhigh`) and `stream` (`true`/`false`).
- Crawl config: `item_workers`, timeout, retry, browser/proxy options.
- Export config: format, output path, optional template path, field mapping.

Existing LLM-compatible crawl config still uses the `LLMConfig` shape exposed by
`POST /crawl`.

## 2. Import Catalog

Endpoint:

```text
POST /catalog/import
```

Body:

```json
{
  "catalog": {
    "Women": {
      "Products": {
        "Leggings": "https://shop.test/leggings"
      }
    }
  }
}
```

The importer is compatible with the nested menu style used by:

```text
F:\datawork\spider\0000_data.json
```

Response shape:

```json
{
  "schema_version": "catalog-tree/v1",
  "catalog_tree": [
    {
      "id": "...",
      "label": "Women",
      "url": "",
      "path": ["Women"],
      "children": []
    }
  ],
  "node_count": 3,
  "leaf_count": 1
}
```

Leaf nodes include:

```text
url, path, level1, level2, level3
```

## 3. Analyze Site

Endpoint:

```text
POST /site/analyze
```

Body:

```json
{
  "target_url": "https://shop.test",
  "field_goal": "采集商品标题、原价、颜色、尺码、描述和图片",
  "imported_catalog": {
    "Women": {
      "Leggings": "https://shop.test/leggings"
    }
  }
}
```

The response returns:

- `catalog_tree`: imported catalog if supplied, otherwise agent-discovered menu
  candidates.
- `field_candidates`: canonical ecommerce fields plus detected selectors.
- `profile`: draft `SiteProfile` for test/full runs.
- `extraction_contract_discovery`: automatic extraction contract candidates
  detected from the analyzed HTML/JSON evidence. Current strategies include
  GTM data attributes, JSON-LD Product/ItemList, Next.js product data,
  GraphQL SSR product cache, Shopify product JSON, and Demandware/SFCC product
  tiles.
- `extraction_context`: compact execution readiness summary for contract-based
  extraction. When `can_execute_extract_from_contract=true`, the returned
  `profile.constraints` already contains the best contract and bounded evidence
  needed by managed actions.
- `recon_summary`: framework/rendering/anti-bot/basic DOM evidence.

Important frontend handoff:

```text
/site/analyze response.profile
  -> pass unchanged into /runs/test or /runs/full
  -> /runs/{task_id}/managed-actions can execute extract_from_contract
     without the frontend resending large HTML evidence.
```

The frontend should render `extraction_context.parser_strategy`,
`sample_count`, `confidence`, and `can_execute_extract_from_contract` on the
site-analysis page so users can see whether CLM found a stronger extraction
path than generic selectors.

## 4. Resolve Fields

Endpoint:

```text
POST /fields/resolve
```

Body:

```json
{
  "available_fields": [
    {"name": "title"},
    {"name": "highest_price"},
    {"name": "colors"}
  ],
  "natural_language": "我要标题、原价和颜色"
}
```

The response returns selected canonical fields such as:

```text
title, highest_price, colors, sizes, description, image_urls
```

Unknown requested fields are returned in `missing_fields` so托管模式 can ask the
LLM/browser/API refinement loop to locate them.

## 5. Test Run

Endpoint:

```text
POST /runs/test
```

Body:

```json
{
  "target_url": "https://shop.test",
  "profile": {},
  "catalog_nodes": [],
  "selected_fields": ["title", "highest_price", "image_urls"],
  "item_workers": 8,
  "test_limit": 100,
  "runtime_dir": "dev_logs/runtime/shop-test",
  "export": {
    "format": "xlsx",
    "output_path": "dev_logs/exports/shop-test.xlsx"
  },
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name",
    "provider": "openai-compatible",
    "reasoning_effort": "medium",
    "stream": false
  },
  "managed_ai": {
    "enabled": true,
    "mode": "supervised",
    "pre_run_review": true,
    "post_run_diagnosis": true,
    "auto_repair": false
  }
}
```

This creates a profile-run job with bounded batches. The response returns a
`task_id` and `run_id`.

`managed_ai` is optional. When omitted or disabled, `/runs/test` and
`/runs/full` remain deterministic. When enabled, `llm.enabled=true`,
`llm.base_url`, and `llm.model` are required.

Supported `managed_ai.mode` values:

```text
analysis_only, supervised, full_managed
```

Current backend behavior:

- `supervised` and `full_managed` run an LLM pre-run plan review before the
  background job starts.
- When `apply_pre_run_patch=true`, an allowlisted profile patch from the
  pre-run review can update seeds, runtime mode, waits, selectors, pagination,
  and quality expectations before execution. Accepted/rejected patch keys are
  exposed as `ai_patch_applications`.
- `supervised` and `full_managed` run an LLM post-run diagnosis after the
  profile runner finishes.
- `supervised` enables runtime supervision in observe mode. Batch-level health
  events are recorded but do not stop the job by themselves.
- `full_managed` enables runtime supervision in managed mode. Consecutive empty
  batches, high failure rates, or very low yield can pause/abort the run and
  expose a recommended next action such as `ai_rerun`.
- `full_managed` or `auto_repair=true` can automatically execute managed crawl
  actions after a low-quality/paused/failed run and start one repaired child
  run. The child run is started in `supervised` mode with `auto_repair=false`,
  so the system does not loop forever.
- Model decisions are recorded in job state and exposed through status/events.

## 6. Full Run

Endpoint:

```text
POST /runs/full
```

The body is the same as `/runs/test`, but the backend creates an unbounded
profile long-run (`max_batches=0`) using selected catalog nodes as seeds.

## 7. Monitor

Endpoints:

```text
GET /runs/{task_id}/status
GET /runs/{task_id}/events
```

Status includes:

```text
status, record_count, accepted, progress.records_saved, progress.failed,
progress.queued, progress.done, progress.completion, quality,
managed_ai, ai_decisions, ai_diagnostics, ai_repair_suggestions,
ai_patch_applications, diagnostics, supervision, managed_actions,
managed_steps, managed_auto_repair, llm_traces, evidence_pack
```

Events include job lifecycle, failure snippets, export events, and AI decision
events such as:

```text
ai_pre_run_review
ai_post_run_diagnosis
llm_trace_pre_run_review
llm_trace_post_run_diagnosis
llm_trace_managed_actions
supervision_pause
supervision_abort
supervision_repair_after_run
managed_auto_repair_started
managed_auto_repair_skipped
```

`llm_traces` is the visible audit trail for model participation. It intentionally
does not expose hidden chain-of-thought. Each record contains:

```text
stage, status, provider, model, duration_ms, input_summary, output_summary,
error, created_at
```

The frontend should render this as the "model decision process" visible to the
user: what stage called the model, what evidence summary was sent, what bounded
JSON/action summary came back, and whether the call failed. This is currently
polling friendly. A future frontend can wrap it with SSE/WebSocket for true
incremental UI updates.

`evidence_pack` is the compact evidence object CLM uses for managed decisions.
It bridges backend capability and AI usefulness: the backend collects crawler
state, while the model sees a smaller action-oriented packet instead of a large
raw job dump.

Important evidence fields:

```text
task
progress
run_spec_summary
profile_summary
quality_gaps
access_evidence
failure_evidence.failure_buckets
failure_evidence.recent_failures
diagnostics.supervision
managed_history.latest_llm_errors
recommended_focus
```

The frontend should show at least `recommended_focus`, `failure_buckets`, and
quality gaps near the managed step controls.

`access_evidence` is an `access-evidence/v1` snapshot built from already
available backend state. It is not a second crawl. It samples recent failures,
failure buckets, runtime events, XHR/API candidates, and browser artifacts into
a compact packet for AI decisions.

For frontends that want a dedicated access view, CLM now also exposes:

```text
POST /runs/{task_id}/access-probe
```

This endpoint returns a `access-probe-response/v1` envelope with:

```text
snapshot
base_snapshot
probe_snapshot
```

Use `snapshot` for the latest display state, `base_snapshot` as the historical
fallback, and `probe_snapshot` when live probe is enabled. The workbench should
render these three layers side by side so the user can see what comes from
recorded run evidence and what comes from the latest runtime probe.

The managed access sampler now also folds in the latest live probe when the
`inspect_access` action is run with `live_probe=true` or the environment flag
`CLM_LIVE_ACCESS_PROBE=1`. That probe uses the native browser runtime to do a
small runtime sample and adds its result under `probe_snapshot`.

Important `access_evidence` fields:

```text
summary.challenge_like
summary.recommended_runtime
summary.missing_evidence
recent_failures
challenge_evidence
runtime_events
xhr_samples
artifact_samples
decision_hints
```

When managed actions execute `inspect_access`, the action result also returns a
`managed-action-evidence/v1` object. `managed-step` copies the latest access
snapshot back into `evidence_pack.access_evidence`, so the workbench can show
what evidence the AI used before asking for a child rerun.

`inspect_access` now returns two layers:

- `snapshot`: the best available access snapshot for the job, including any
  live probe result
- `base_snapshot`: the compact historical snapshot from existing job evidence

The frontend should prefer `snapshot` for decision display and keep
`base_snapshot` as fallback or comparison material.

`access_probe_history` and `latest_access_probe` are also exposed from
`GET /runs/{task_id}/status`, so the frontend can show the latest probe without
calling the action layer again.

### API/XHR Replay Promotion

`inspect_access` can now promote product-like XHR samples into an executable API
profile patch. This is a backend capability, not only a diagnosis. When a live
probe or recorded access snapshot contains a JSON XHR response with product-like
items, CLM can infer:

```text
api_hints.endpoint
api_hints.method
api_hints.format
api_hints.kind
api_hints.items_path
api_hints.field_mapping
api_hints.headers
api_hints.post_json
pagination_hints.type/page_param/offset_param/cursor_param/page_size
pagination_hints.json_page_path/json_page_size_path/json_cursor_path
crawl_preferences.seed_kind=api
```

As of 2026-05-19, this promotion also handles POST JSON and GraphQL-style
product listing calls. The browser runtime keeps replay-safe request headers and
POST body previews from captured XHR/fetch traffic. The managed action layer can
turn those samples into `api_hints.post_json`, `api_hints.headers`, and JSON
body pagination paths, so the product runner can replay the same endpoint while
incrementing `variables.currentPage` or replacing a cursor in the POST body.

This matters for modern ecommerce sites where page changes are not visible in
the URL. For example:

```json
{
  "api_hints": {
    "endpoint": "https://shop.test/graphql",
    "method": "POST",
    "format": "graphql",
    "kind": "graphql",
    "post_json": {
      "operationName": "CategoryProducts",
      "variables": {
        "currentPage": 1,
        "pageSize": 24
      }
    }
  },
  "pagination_hints": {
    "type": "page",
    "json_page_path": "variables.currentPage",
    "json_page_size_path": "variables.pageSize",
    "page_size": 24
  }
}
```

### Replay Diagnostics

API/XHR candidates may now include `api_hints.replay_diagnostics` or
`candidate.replay_diagnostics`. This tells the workbench why an API replay may
be fragile and what the backend can refresh automatically.

Common fields:

```text
replay_required
risk_level
dynamic_inputs
signed_components
session_requirements
recommendations
```

Examples:

- `dynamic_inputs`: timestamp, nonce, request id, or body fields that should be
  refreshed before each API request.
- `signed_components`: query/header/body fields that look like signature or
  token components.
- `session_requirements`: headers such as store, CSRF, XSRF, cookie, or
  authorization-like inputs that indicate the replay should reuse a browser
  session or profile headers.

The product runner now consumes `api_hints.replay_diagnostics.dynamic_inputs`
and refreshes generic timestamp/nonce/request-id values when building API seed
requests and API pagination requests.

As of 2026-05-20, replay diagnostics can also become executable through
`api_hints.replay_runtime` or an explicit `api_hints.replay_plan`. The profile
runner builds a hook/sandbox replay plan, executes it with the existing replay
executor, and applies the output to signed query/header/body fields before each
API seed request and each API pagination request. This moves signed API replay
from "diagnosed" to "runnable profile capability" for profiles that provide the
needed signing source or fixture/context inputs.

Minimal signed-header example:

```json
{
  "api_hints": {
    "endpoint": "https://shop.test/api/products",
    "method": "GET",
    "items_path": "items",
    "replay_diagnostics": {
      "schema_version": "replay-diagnostics/v1",
      "replay_required": true,
      "signed_components": [
        {"location": "header", "name": "x-signature", "kind": "signature_or_token"}
      ]
    },
    "replay_runtime": {
      "hook_name": "api_request_signature",
      "secret_key": "profile-or-session-secret",
      "output_bindings": [
        {
          "source": "api_request_signature",
          "location": "header",
          "path": "x-signature",
          "value_type": "hook"
        }
      ]
    }
  }
}
```

For custom site logic, `replay_runtime.hook_sources` can supply bounded JS source
for the sandbox executor, keyed by hook name. If no custom source is present,
CLM can still use deterministic fixture hooks for local tests and profile
training. Real protected sites still require the correct session, keys, or
captured hook source; the important upgrade is that CLM now has a runtime slot
where that knowledge can execute instead of remaining an inert note.

The managed action result exposes:

```text
result.api_replay_promotion
result.api_replay_promotions
result.profile_patch.api_hints
result.profile_patch.pagination_hints
```

When `managed-control-loop` is called with `include_access_probe=true` and
`start_child_run=true`, the child run can switch from browser/DOM collection to
API pagination automatically. The patch application is visible in the child run
status under `ai_patch_applications`, and `product_run_spec.profile.api_hints`
shows the API profile used by the rerun.

Frontend behavior:

- Show `api_replay_promotion.promoted`, `confidence`, `candidate.url`, and
  `candidate.reasons` in the access/AI panel.
- If promoted, label the next rerun as "API replay candidate" and show the
  inferred endpoint, items path, field mapping, and pagination mode.
- Prefer `managed-control-loop` for one-click repair because it can observe,
  probe XHR, apply the API patch, and start the child run in one visible chain.

## 7.1 AI Repair Rerun

Endpoint:

```text
POST /runs/{task_id}/ai-rerun
```

Use this after a test/full product run has AI diagnostics. The backend reads
`ai_diagnostics.next_run_overrides`, applies bounded run/profile changes, and
starts a child product run.

If the run has runtime `supervision` but no LLM `next_run_overrides`, the backend
still builds a deterministic repair plan. For example, consecutive empty batches
produce overrides that switch to dynamic browser mode, enable API capture,
extend waits, and add conservative title selector fallback. Frontend users can
then click one repair rerun button instead of rebuilding the task manually.

Body:

```json
{
  "run_kind": "test",
  "apply_diagnostics": true,
  "extra_overrides": {
    "item_workers": 8,
    "access_config": {
      "mode": "dynamic",
      "wait_until": "networkidle"
    },
    "selectors": {
      "title": "h1.product-title"
    },
    "export": {
      "format": "csv"
    }
  },
  "managed_ai": {
    "enabled": true,
    "mode": "supervised",
    "pre_run_review": true,
    "post_run_diagnosis": true,
    "apply_pre_run_patch": true
  },
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name"
  }
}
```

Supported `run_kind`:

```text
test, full
```

The response returns a new `task_id`, plus:

```text
parent_task_id, repair_source, patch_application
```

The child run status also includes `parent_task_id`, `repair_source`, and
`ai_patch_applications`, so the workbench can show exactly which AI suggestions
were accepted or rejected.

## 7.2 Managed Crawl Actions

Endpoint:

```text
POST /runs/{task_id}/managed-actions
```

This endpoint gives managed mode a concrete crawler tool space. It can plan and
optionally execute bounded actions, then store the action record on the run. The
latest action result is also consumed by `/runs/{task_id}/ai-rerun`.

Supported actions:

```text
reanalyze_site
discover_catalog
probe_fields
inspect_access
repair_selectors
adjust_runtime
evaluate_quality
prepare_export
prepare_rerun
extract_from_contract
```

Action meaning:

- `reanalyze_site`: rerun site analysis and merge fresh profile evidence.
- `discover_catalog`: repair missing catalog/category seeds and imported menus.
- `probe_fields`: prepare target fields and selector fallbacks.
- `inspect_access`: enable runtime evidence collection, browser waits, API capture,
  and cookie acceptance.
- `repair_selectors`: add conservative field selector fallbacks.
- `adjust_runtime`: change runtime mode, waits, and browser knobs.
- `evaluate_quality`: set required fields, minimum records, and coverage gates.
- `prepare_export`: prepare export format/path/mapping for the next run.
- `prepare_rerun`: mark that accumulated changes should feed `/ai-rerun`.
- `extract_from_contract`: run a known extraction contract against matching
  HTML/JSON evidence and return normalized ecommerce items. This is useful when
  the workbench or training data already has a parser strategy such as GTM
  data attributes, JSON-LD, Next.js page data, GraphQL SSR cache, Shopify, or
  Demandware/SFCC product tiles.

Body:

```json
{
  "execute": true,
  "use_llm": true,
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name"
  },
  "extra_context": {
    "field_goal": "title, price, colors, sizes, description, images",
    "selected_fields": ["title", "highest_price", "colors", "sizes"],
    "imported_catalog": {},
    "extraction_contract": {
      "site": "example.com",
      "source_url": "https://example.com/category",
      "parser_strategy": {"name": "json_ld_product_extractor"}
    },
    "extraction_evidence": "<html>...</html>",
    "export": {
      "format": "csv",
      "output_path": "F:/datawork/exports/shop.csv"
    }
  }
}
```

If `use_llm=true`, the model chooses from the supported action list. If the LLM
is disabled, unavailable, or returns no usable actions, CLM builds a
deterministic plan from progress, diagnostics, and supervision evidence.

When failures are classified as `challenge_like`, `captcha`,
`managed_challenge`, or `http_blocked`, the deterministic fallback now escalates
to a stronger protected runtime profile for the next run:

```text
access_config.mode=protected
browser_config.capture_api=true
browser_config.persistent_context=true
browser_config.pool_enabled=true
browser_config.close_persistent_context=false
item_workers=1
proxy_policy.strategy=rotate_on_challenge
```

This is a general hardening path for challenge/access failures. It is not tied
to a single website.

`extra_context` is optional but recommended from the frontend. It gives the
managed action layer the same context the user selected in the workbench:
natural-language field goals, selected fields, imported catalog/menu JSON,
optional extraction contracts/evidence, and export preferences. The backend
keeps actions bounded and converts them into profile patches, extracted item
payloads, or run overrides for the next executable run.

When `extra_context.extraction_contract` and
`extra_context.extraction_evidence` are present, the LLM does not need to echo
large HTML or JSON evidence back in its action. It can simply choose
`extract_from_contract`; the backend hydrates the action from `extra_context`,
executes the contract extractor, stores the action record, and exposes the
latest extraction summary in `/runs/{task_id}/status.managed_state.extraction_context`.

If a run was created from a `/site/analyze` profile that already contains
`profile.constraints.extraction_contract` and
`profile.constraints.extraction_evidence`, the managed action layer now hydrates
the same context automatically. This means the normal workbench path is:

```text
Analyze Site -> Test Run -> Managed Actions
```

not:

```text
Analyze Site -> manually copy evidence -> Managed Actions
```

Response:

```json
{
  "task_id": "abc123",
  "created_at": "...",
  "executed": true,
  "result": {
    "schema_version": "managed-action-result/v1",
    "plan": {"source": "llm", "actions": []},
    "results": [],
    "evidence": {
      "schema_version": "managed-action-evidence/v1",
      "access_snapshot": {}
    },
    "profile_patch": {},
    "run_overrides": {},
    "rerun_ready": true
  }
}
```

Frontend behavior:

- Show managed action records from `/runs/{task_id}/status.managed_actions`.
- Show action timeline entries from `/runs/{task_id}/events`.
- Enable a repair rerun button when `result.rerun_ready=true`.

## 7.2.1 Managed Step

Endpoint:

```text
POST /runs/{task_id}/managed-step
```

This is the first explicit observe-decide-act API for the workbench. It lets the
frontend ask CLM to take one managed step on the current task instead of only
showing diagnostics.

The backend observes current job status, progress, diagnostics, supervision, and
quality evidence; classifies the step stage; plans managed crawler actions;
executes bounded actions when `execute=true`; optionally starts a repaired child
run when `start_child_run=true`; then stores the result in
`status.managed_steps` and emits `managed_step_executed`.

Step stages:

```text
runtime_supervision
repair_after_failure
quality_review
planning
```

Body:

```json
{
  "execute": true,
  "use_llm": true,
  "start_child_run": false,
  "run_kind": "test",
  "apply_diagnostics": true,
  "extra_context": {
    "field_goal": "标题、价格、颜色、尺码、描述、图片",
    "selected_fields": ["title", "highest_price", "colors"],
    "export": {"format": "csv"}
  },
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name",
    "timeout_seconds": 60,
    "max_tokens": 1200
  },
  "managed_ai": {
    "enabled": true,
    "mode": "supervised"
  }
}
```

Response:

```json
{
  "task_id": "abc123",
  "schema_version": "managed-step/v1",
  "stage": "quality_review",
  "status_before": "completed",
  "progress": {},
  "evidence_pack": {
    "schema_version": "run-evidence-pack/v1",
    "access_evidence": {
      "schema_version": "access-evidence/v1"
    }
  },
  "action_record": {},
  "child_run": null
}
```

Frontend use: add a button such as "让 AI 执行下一步". For normal use, call with
`start_child_run=false` first to show the proposed/executed actions. For
one-click repair, call with `start_child_run=true`.

## 7.2.2 Managed Control Loop

Endpoint:

```text
POST /runs/{task_id}/managed-control-loop
```

This is the product workbench's main "AI takeover one step" API. It combines the
previously separate pieces into one visible loop:

```text
observe current run -> build evidence pack -> optional access probe ->
plan/execute managed actions -> optional repaired child run -> return timeline
```

Body:

```json
{
  "use_llm": true,
  "execute": true,
  "include_access_probe": true,
  "live_probe": false,
  "start_child_run": false,
  "run_kind": "test",
  "apply_diagnostics": true,
  "extra_context": {
    "field_goal": "title, price, colors, sizes, description, images",
    "selected_fields": ["title", "highest_price", "colors"],
    "export": {"format": "csv"}
  },
  "extra_overrides": {},
  "managed_ai": {"enabled": true, "mode": "supervised"},
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name"
  }
}
```

Response includes:

```text
schema_version=managed-control-loop/v1
stage
evidence_before
evidence_after
access_probe
action_record
child_run
timeline
```

The frontend should prefer this endpoint for the main AI control button because
it gives the user one visible chain instead of scattered operations.

Display guidance:

- Use `timeline` for the task detail activity rail.
- Use `evidence_before` and `evidence_after` for AI context comparison.
- Use `access_probe.snapshot` to show access/runtime evidence.
- Use `action_record.result.plan` to show model or deterministic decisions.
- Use `child_run` to switch the active task when a repair rerun starts.

`GET /runs/{task_id}/status` exposes:

```text
managed_control_loops
latest_managed_control_loop
```

`GET /runs/{task_id}/events` emits:

```text
managed_control_loop_completed
access_probe_completed
```

## 7.3 One-Click Managed Repair Rerun

Endpoint:

```text
POST /runs/{task_id}/managed-repair-run
```

This is the frontend-friendly combined endpoint. It first executes managed crawl
actions, stores the action record, then immediately starts a repaired child run
using the latest action `run_overrides`.

Body:

```json
{
  "execute": true,
  "use_llm": true,
  "run_kind": "test",
  "apply_diagnostics": true,
  "extra_context": {
    "field_goal": "title, price, colors, sizes, description, images",
    "selected_fields": ["title", "highest_price", "colors", "sizes"],
    "imported_catalog": {},
    "export": {
      "format": "csv",
      "output_path": "F:/datawork/exports/shop.csv"
    }
  },
  "managed_ai": {
    "enabled": true,
    "mode": "full_managed"
  },
  "llm": {
    "enabled": true,
    "base_url": "https://api.example.com/v1",
    "api_key": "sk-...",
    "model": "model-name"
  }
}
```

Response includes the new child run plus the executed managed action record:

```json
{
  "task_id": "child123",
  "run_id": "test-child123",
  "status": "running",
  "parent_task_id": "abc123",
  "repair_source": "managed_actions",
  "managed_action": {
    "executed": true,
    "result": {
      "plan": {"source": "llm", "actions": []},
      "rerun_ready": true
    }
  }
}
```

The workbench should use this endpoint for the "AI 托管修复并重跑" button on the
task detail page. It should then switch the active task to the returned child
`task_id` and keep polling `/runs/{child_task_id}/status`.

## 7.4 Full Managed Auto Repair

When a product run is launched with:

```json
{
  "managed_ai": {
    "enabled": true,
    "mode": "full_managed",
    "auto_repair": true
  }
}
```

the backend can automatically bridge from diagnosis to action:

1. The profile runner finishes or pauses.
2. Runtime supervision and/or quality metrics are written to job state.
3. The LLM post-run diagnosis runs if configured.
4. If the result is paused, failed, rejected, empty, or quality is unknown/fail,
   the backend calls the managed action planner.
5. The generated action patch is applied to a child rerun.
6. `GET /runs/{task_id}/status` exposes:

```text
managed_auto_repair.attempted
managed_auto_repair.reason
managed_auto_repair.child_task_id
managed_auto_repair.child_run_id
managed_auto_repair.managed_action
```

The frontend should show this as an automatic handoff from the parent failed run
to the repaired child run. The child run currently uses `supervised` mode and
does not auto-repair again.

## 8. Export

Endpoint:

```text
POST /exports
```

Body:

```json
{
  "run_id": "full-abc123",
  "runtime_dir": "dev_logs/runtime/shop-test",
  "format": "xlsx",
  "output_path": "dev_logs/exports/shop-test.xlsx",
  "field_mapping": {
    "title": "Title",
    "highest_price": "Price"
  }
}
```

Supported formats:

```text
json, csv, xlsx, sqlite, db
```

The current template behavior is data-first. `template_path` is accepted by the
API, but exact cell-coordinate writing should be a follow-up `TemplateSpec`
slice.

An optional `template` object controls xlsx layout:

```json
{
  "template": {
    "sheet_name": "Products",
    "start_row": 3,
    "start_column": 2,
    "field_to_column": {"title": "Product Name", "highest_price": "Price"},
    "columns": ["title", "highest_price", "colors"]
  }
}
```

## 9. LLM Model List

Endpoint:

```text
POST /llm/models
```

Body:

```json
{
  "base_url": "https://api.openai.com",
  "api_key": "sk-...",
  "provider": "openai-compatible"
}
```

Response:

```json
{
  "provider": "openai-compatible",
  "models": [{"id": "gpt-4", "label": "gpt-4"}, {"id": "gpt-3.5-turbo", "label": "gpt-3.5-turbo"}],
  "raw_count": 2,
  "status": "ok",
  "error": "",
  "latency_ms": 350.2
}
```

Handles common relay shapes: `{data: [...]}`, `{models: [...]}`, flat list.
API keys are redacted from all error messages.

## 10. LLM Health Check

Endpoint:

```text
POST /llm/health
```

Body: same as `/llm/models`.

Response:

```json
{
  "status": "ok",
  "status_code": 200,
  "latency_ms": 150.0,
  "normalized_url": "https://api.openai.com",
  "endpoint": "https://api.openai.com/v1/models",
  "error": ""
}
```

Uses `/v1/models` GET — no chat completion required.

## 10.1 OpenAI-Compatible Chat Compatibility

CLM uses the common `/v1/chat/completions` shape for managed AI decisions. The
adapter now handles common provider/relay differences:

- normal JSON chat-completion responses
- `text/event-stream` / SSE streaming chunks when `stream=true`
- `choices[0].message.content`, content part lists, and `choices[0].text`
- JSON content wrapped in markdown fences
- one automatic retry without unsupported optional parameters such as
  `response_format`, `reasoning_effort`, or `stream`

This means enabling model reasoning strength or stream mode should not break the
entire managed workflow when a third-party relay accepts only a smaller OpenAI
parameter subset.

## 11. Export Path Validation

Endpoint:

```text
POST /exports/validate-path
```

Body:

```json
{"directory": "/path/to/exports", "create": true}
```

Response:

```json
{"exists": true, "created": true, "writable": true, "normalized_path": "/abs/path", "error": ""}
```

## 12. Export Path Resolution

Endpoint:

```text
POST /exports/resolve-path
```

Body:

```json
{"directory": "/tmp/exports", "run_id": "test-abc", "format": "xlsx", "filename": ""}
```

Response:

```json
{"directory": "/tmp/exports", "filename": "test-abc.xlsx", "output_path": "/tmp/exports/test-abc.xlsx", "format": "xlsx"}
```

Auto-appends missing extension. Empty filename defaults to `{run_id}.{ext}`.

## 13. Workbench Config

Endpoint:

```text
GET /workbench/config
```

Response includes: version, supported export formats, max active jobs, default
retention seconds, and all available endpoint paths.

## Current Gaps

- Site analysis uses deterministic HTML recon plus menu heuristics. It does not
  yet do a full browser/XHR catalog discovery pass.
- `template_path` is accepted, but advanced template cell placement is not
  implemented yet.
- `/runs/{id}/events` is polling JSON, not SSE/WebSocket streaming yet. The
  backend exposes trace records, but true token-by-token frontend streaming is a
  follow-up endpoint.
- The managed repair loop can trigger protected/dynamic reruns, but stronger
  catalog discovery and browser/XHR profile refinement still need more real-site
  training.
