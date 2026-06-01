# 2026-05-20 API Replay Runtime Bridge v1

## Summary

继续按“后端硬实力优先”的路线推进。这一轮把 API replay 从
`replay_diagnostics` 的诊断层推进到 profile runner 的可执行层：

```text
captured API evidence -> replay diagnostics -> hook/sandbox plan ->
execute replay -> patch query/header/json body -> profile longrun request
```

## What Changed

- 新增 `autonomous_crawler/tools/api_replay_runtime.py`
  - 从 `SiteProfile.api_hints.replay_diagnostics` / `replay_runtime` /
    `replay_plan` 生成 `HookSandboxPlan`。
  - 调用现有 `replay_executor.execute_replay()`。
  - 将 replay 输出绑定到 query/header/json body。
  - 支持 profile 提供 `hook_sources`，让真实站点签名函数后续可以进入
    Node sandbox 执行。
- 更新 `autonomous_crawler/runners/profile_ecommerce.py`
  - API seed request 和 API pagination request 都会先刷新动态输入，再执行
    replay runtime patch。
  - 没有 replay plan/binding 时保持原行为。
- 更新 `autonomous_crawler/api/app.py`
  - managed AI/profile patch allowlist 新增：
    - `api_hints.replay_runtime`
    - `api_hints.replay_plan`
- 新增 `autonomous_crawler/tests/test_api_replay_runtime.py`
  - 覆盖 signed component -> executable plan。
  - 覆盖 header/query/json body 绑定。
  - 覆盖自定义 JS hook source。
  - 覆盖 profile initial request 和 next page request 都执行签名 patch。
- 更新 `docs/runbooks/FRONTEND_PRODUCT_WORKFLOW_API.md`
  - 记录 `replay_runtime` / `replay_plan` 的 profile 使用方式。

## Verification

Passed:

```text
python -m unittest autonomous_crawler.tests.test_api_replay_runtime -v
python -m unittest autonomous_crawler.tests.test_api_replay_runtime autonomous_crawler.tests.test_replay_diagnostics autonomous_crawler.tests.test_managed_actions autonomous_crawler.tests.test_product_workflow_api -v
python -m compileall autonomous_crawler
```

## Impact

这一块不是针对某个站点写规则，而是补了一层通用 runtime 能力：

- 发现签名字段后，不再只给“需要 hook/sandbox”的建议。
- Profile 可以携带签名执行配置。
- 长跑分页每一页都可以重新生成签名/动态字段。
- 以后 browser hook、JS 静态分析、LLM 生成修复 profile 都可以往同一个
  `api_hints.replay_runtime` 合同里写。

## Remaining Gaps

- 真实站点的签名函数定位和提取仍需要继续加强：
  - JS AST/source map 定位
  - CDP hook 捕获真实输入输出
  - 从浏览器 session 提取需要的 token/context
- 当前 `secret_key` 等 runtime context 主要用于 profile/训练场景，真实站点
  需要由会话、hook 或用户授权配置提供。
- replay runtime 的执行细节还没有进入前端可视化时间线，后续可以把
  plan/result 摘要加入 run event 或 diagnostics。
