# Assignment: Scrapling Static + Parser Adapter

Date: 2026-05-14

Employee: LLM-2026-001

Project role: Runtime Adapter Worker

Capability IDs:

- CAP-1.1 HTTP/HTML crawling
- CAP-5.3 自动探索 / profile-driven extraction foundation
- SCRAPLING-RUNTIME-1

## Mission

把 Scrapling 的 static fetch 和 parser 能力接入 CLM Runtime 体系，作为 Scrapling-first runtime 的第一块可运行后端。

## Write Scope

你可以修改或新增：

- `autonomous_crawler/runtime/`
- `autonomous_crawler/tests/test_scrapling_static_runtime.py`
- `autonomous_crawler/tests/test_scrapling_parser_runtime.py`

避免修改：

- `autonomous_crawler/agents/executor.py`
- `autonomous_crawler/tools/browser_*`
- `autonomous_crawler/tools/proxy_*`
- docs/team 看板

主管会负责 executor 主路由和最终整合。

## Requirements

1. 先检查 `F:\datawork\Scrapling-0.4.8` 的 `Fetcher`、`Selector`、`Response` API。
2. 设计最小协议对象，如果主管已经创建了 `runtime/protocols.py` 或 `runtime/models.py`，请沿用。
3. 实现 static fetch adapter：
   - 输入 URL、headers、cookies、timeout、proxy config。
   - 输出统一 runtime response。
   - 网络错误必须结构化返回，不抛到 workflow 顶层。
4. 实现 parser adapter：
   - CSS selector extraction。
   - XPath selector extraction。
   - text / attr pseudo selector 支持。
   - selector miss 不能算 runtime crash。
5. 测试必须包含：
   - local HTML string parser。
   - mock/fixture HTML extraction。
   - invalid selector。
   - missing Scrapling dependency graceful skip or clear failure。
   - no proxy credential leakage。

## Acceptance

运行：

```text
python -m unittest autonomous_crawler.tests.test_scrapling_static_runtime autonomous_crawler.tests.test_scrapling_parser_runtime -v
python -m compileall autonomous_crawler
```

完成后写 handoff：

```text
docs/memory/handoffs/2026-05-14_LLM-2026-001_scrapling_static_parser_adapter.md
```

handoff 必须包含：

- changed files
- tests run
- adapter API summary
- known risks
- next integration recommendation

## Important

你不是单独写一个站点爬虫。你是在构建 CLM 的通用采集运行时后端。不要硬编码任何站点 selector。
