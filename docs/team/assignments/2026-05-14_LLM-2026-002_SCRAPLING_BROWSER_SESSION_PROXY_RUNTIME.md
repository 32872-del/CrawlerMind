# Assignment: Scrapling Browser + Session + Proxy Runtime Design

Date: 2026-05-14

Employee: LLM-2026-002

Project role: Browser Runtime Infrastructure Worker

Capability IDs:

- CAP-3.3 可插拔代理池
- CAP-4.1 CDP / Playwright
- CAP-4.2 浏览器指纹一致性
- SCRAPLING-RUNTIME-2

## Mission

研究并落地 Scrapling DynamicFetcher / StealthyFetcher / Session / ProxyRotator 与 CLM runtime 协议的映射，为 Phase 2 browser runtime 接入做准备。

## Write Scope

你可以修改或新增：

- `autonomous_crawler/runtime/`
- `autonomous_crawler/tests/test_scrapling_browser_runtime_contract.py`
- `autonomous_crawler/tests/test_scrapling_proxy_runtime_contract.py`
- `docs/memory/handoffs/2026-05-14_LLM-2026-002_scrapling_browser_session_proxy_runtime.md`

避免修改：

- `autonomous_crawler/agents/executor.py`
- `autonomous_crawler/agents/strategy.py`
- `docs/team/TEAM_BOARD.md`
- README

## Requirements

1. 阅读 `F:\datawork\Scrapling-0.4.8`：
   - `docs/fetching/dynamic.md`
   - `docs/fetching/stealthy.md`
   - `docs/spiders/proxy-blocking.md`
   - `scrapling/engines/toolbelt/proxy_rotation.py`
2. 设计 browser runtime contract：
   - mode: `dynamic` / `protected`
   - headless
   - real_chrome
   - wait_selector
   - wait_until / network_idle
   - capture_xhr
   - blocked_domains / block_ads
   - browser identity config
   - session continuity fields
3. 设计 proxy mapping：
   - CLM ProxyConfig -> Scrapling proxy/proxy_rotator。
   - credential-safe proxy trace。
   - domain-sticky / round-robin 策略映射建议。
4. 如果实现代码，只实现纯转换函数和模型，不接 executor。
5. 测试必须不需要真实代理、不需要真实外网 protected page。

## Acceptance

运行：

```text
python -m unittest autonomous_crawler.tests.test_scrapling_browser_runtime_contract autonomous_crawler.tests.test_scrapling_proxy_runtime_contract -v
python -m compileall autonomous_crawler
```

handoff 必须包含：

- proposed runtime contract
- fields mapping table
- changed files
- tests run
- risks and integration blockers

## Important

这轮重点是基础设施协议和映射，不是实站挑战页演示。保持可测试、可插拔、可分布式扩展。
