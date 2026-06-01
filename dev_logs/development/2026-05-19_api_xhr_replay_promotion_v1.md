# 2026-05-19 API/XHR Replay Promotion v1

## Summary

本轮补的是后端硬能力：CLM 不再只是把 XHR/API 证据展示出来，而是可以把产品型 JSON XHR 自动晋升为可执行的 `SiteProfile` patch，并进入 managed child rerun。

## Changes

- 新增 `autonomous_crawler/runners/api_replay_promotion.py`
  - 归一化 access probe / job snapshot / captured_xhr 中的 XHR 样本。
  - 对 JSON body、数组 payload、商品字段、分页参数、URL token 做候选评分。
  - 推断 `api_hints.endpoint/method/format/items_path/field_mapping`。
  - 推断 `pagination_hints.type/page_param/offset_param/cursor_param/page_size`。
  - 输出 `crawl_preferences.seed_kind=api`，让下一轮可以走 API seed。

- 更新 `managed_actions.inspect_access`
  - 在 live probe 或历史 access snapshot 中发现高置信产品 JSON XHR 时，自动把 API replay patch 合并到 `profile_patch/run_overrides`。
  - action result 现在暴露 `api_replay_promotion` 和 `api_replay_promotions`，便于前端展示晋升原因、候选 URL 和置信度。

- 更新 API 层 patch allowlist
  - `_apply_managed_profile_patch()` 现在接受受控的 `api_hints`。
  - `_apply_managed_run_overrides()` 现在会把 `api_hints` 作为 profile patch 应用到 child run。
  - `/runs/{task_id}/status` 增加 `product_run_spec`，方便前端看到当前任务实际执行的 profile。

- 更新 access evidence bridge
  - `build_access_evidence_snapshot()` 可以读取 `latest_access_probe.snapshot/probe_snapshot`，避免已完成的 access probe 证据丢失。

- 更新 runbook
  - `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md` 增加 API/XHR replay promotion 说明。

## Verification

已通过：

```text
python -m unittest autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_ai_can_apply_api_replay_profile_patch autonomous_crawler.tests.test_product_workflow_api.ManagedAIRunTests.test_managed_control_loop_can_promote_xhr_api_and_start_api_child_run -v
```

覆盖点：

- live access probe 捕获 JSON XHR 后生成 API patch。
- 历史 job access snapshot 中的 XHR 也能被晋升。
- 生成的 patch 可以构造 `SiteProfile` 并产生 API 初始请求。
- managed control loop 可以把 XHR 晋升结果应用到 child run。
- LLM pre-run profile patch 也可以安全写入 `api_hints`。

## Current Limits

- v1 主要覆盖 GET JSON API 和基础 page/offset/cursor 参数推断。
- GraphQL、复杂 POST body replay、签名参数重放、动态 token 刷新仍需要后续增强。
- 晋升逻辑是通用候选评分，不写站点专属规则。
