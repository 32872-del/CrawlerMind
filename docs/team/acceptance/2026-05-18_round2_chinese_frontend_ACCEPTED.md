# Acceptance: Chinese Product Workbench Round 2

Date: 2026-05-18

Employee: LLM-2026-004

Assignment: `docs/team/assignments/2026-05-18_ROUND2_LLM-2026-004_CHINESE_UI_MODEL_EXPORT_POLISH.md`

Status: accepted

## Accepted Scope

- Converted the workbench UI to Chinese for visible user-facing pages.
- Added provider presets and model-list loading from `POST /llm/models`.
- Added export directory validation and final path preview using the new backend
  path endpoints.
- Added localStorage persistence under `clm-workbench-state-v2`.
- Added task-detail auto polling with pause/resume polling controls and last
  refresh time.
- Improved dashboard/task/detail/settings visual hierarchy and operations
  console feel.

## Verification

```text
npm run build
OK

Invoke-WebRequest http://127.0.0.1:5174/
StatusCode: 200
```

Browser DOM check:

```text
title: CLM 采集工作台
visible menu: 工作台 / 新建任务 / 站点分析 / 任务详情 / 历史任务 / 系统设置
task detail: 状态、当前阶段、最后刷新、事件流、质量与导出
```

## Notes

- Build still warns that the Ant Design bundle chunk is larger than 500 kB.
  This is acceptable for MVP, but code splitting should be a frontend follow-up.
- Some technical labels remain intentionally mixed, such as `API Key`,
  `Base URL`, and `CLM`.

