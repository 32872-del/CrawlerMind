# Assignment: Scrapling Runtime Docs + Source Tracking Audit

Date: 2026-05-14

Employee: LLM-2026-004

Project role: Runtime Documentation Auditor

Capability IDs:

- CAP-6.2 Evidence / audit
- CAP-7.3 部署 / 维护
- SCRAPLING-RUNTIME-DOCS

## Mission

把 Scrapling-first runtime 作为 CLM 近期主线写入文档体系，并为后续 vendor / 二次开发建立 source tracking 记录。

## Write Scope

你可以修改或新增：

- `docs/runbooks/`
- `docs/plans/`
- `docs/memory/handoffs/2026-05-14_LLM-2026-004_scrapling_runtime_docs_audit.md`
- `dev_logs/audits/2026-05-14_scrapling_runtime_docs_audit.md`

避免修改：

- `autonomous_crawler/` 代码
- `docs/team/TEAM_BOARD.md`
- 员工 assignment 文件

## Requirements

1. 阅读：
   - `docs/plans/2026-05-14_SCRAPLING_FIRST_RUNTIME_PLAN.md`
   - `docs/plans/2026-05-12_TOP_CRAWLER_CAPABILITY_ROADMAP.md`
   - `docs/plans/2026-05-12_CAPABILITY_IMPLEMENTATION_MATRIX.md`
   - `F:\datawork\Scrapling-0.4.8\LICENSE`
   - `F:\datawork\Scrapling-0.4.8\pyproject.toml`
2. 建议新增一份 runbook：
   - `docs/runbooks/SCRAPLING_FIRST_RUNTIME.md`
3. runbook 需要说明：
   - CLM 为什么采用 Scrapling-first runtime。
   - CLM Runtime Protocol 与 Scrapling 能力的边界。
   - Phase 1/2/3 近期开发路径。
   - source tracking / license notice 归档要求。
   - 不把站点规则固化到核心 runtime。
4. 审计 README、能力矩阵、看板是否需要后续更新，列出 findings。

## Acceptance

运行：

```text
python -m compileall autonomous_crawler
```

handoff 必须包含：

- docs changed
- source tracking recommendation
- stale docs findings
- next documentation edits

## Important

文档语气要面向开发者产品和基础设施架构，不写成泛泛的宣传稿。
