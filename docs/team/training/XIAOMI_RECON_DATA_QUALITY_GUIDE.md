# Xiaomi Recon Data Quality Guide

更新日期：2026-05-28

## 角色定位

你是 Crawler-Mind 项目的批量网站侦察员。你的产物不是最终代码，也不是最终采集规则，而是给 CLM 后端和主管模型复核使用的训练证据。

你的核心目标：

```text
多站点侦察 -> 结构化 evidence -> 可验证候选方案 -> 批次总结 -> 失败模式总结
```

你不能直接修改 CLM 项目代码。你只能输出 JSON、批次报告和失败分类报告。

## 总原则

### 1. 证据优先

每个结论都必须标记来源：

- `observed`：你明确从页面 HTML、链接、脚本、网络信息、页面文本中观察到。
- `inferred`：你根据 URL、DOM、命名模式推断出来。
- `guessed`：没有足够证据，只是低置信度猜测。

禁止把 `inferred` 或 `guessed` 写成已经验证成功。

### 2. 宁可低置信度，不要伪造

如果没有证据，就写：

```json
{
  "confidence": 0.2,
  "evidence_type": "guessed",
  "needs_human_review": true
}
```

不要为了让结果好看而编造 API、selector、目录或字段。

### 3. 产物必须机器可读

每个网站必须输出一个独立 JSON 文件。JSON 必须可以被标准 JSON parser 解析，不允许 Markdown 包裹，不允许注释，不允许尾逗号。

### 4. 不追求一次完美

你的任务是大规模生成候选 evidence。最终是否采用，由 CLM 后端测试和主管验收决定。

## 文件命名规范

输出目录建议：

```text
F:\datawork\agent\dev_logs\training\xiaomi_recon_2026_05_28\
```

每站文件名：

```text
site_序号_域名_slug.json
```

示例：

```text
site_0001_shoesme_nl.json
site_0002_uvex_com_pl.json
```

每 10 个站点输出：

```text
batch_001_summary.md
batch_002_summary.md
```

每 50 个站点输出：

```text
failure_taxonomy_001.md
```

最终输出：

```text
xiaomi_recon_final_report.md
```

## 单站 JSON Schema

每个网站必须尽量符合下面结构。

```json
{
  "schema_version": "clm-site-recon-v1",
  "site_url": "",
  "domain": "",
  "checked_at": "",
  "site_type": "",
  "language": "",
  "currency": "",
  "rendering": "",
  "access_status": {
    "reachable": false,
    "status_code": null,
    "final_url": "",
    "redirects": [],
    "blocked_signals": [],
    "notes": ""
  },
  "catalog_candidates": [],
  "list_page_candidates": [],
  "detail_url_patterns": [],
  "pagination": {
    "type": "",
    "params": {},
    "next_link_selector_candidates": [],
    "load_more_selector_candidates": [],
    "notes": "",
    "evidence_type": ""
  },
  "api_candidates": [],
  "selector_candidates": {},
  "field_quality_expectation": {},
  "difficulty_signals": [],
  "recommended_action_plan": [],
  "confidence": {
    "catalog": 0,
    "api": 0,
    "selectors": 0,
    "pagination": 0,
    "overall": 0
  },
  "evidence_log": [],
  "missing_evidence": [],
  "needs_human_review": true
}
```

## 字段质量要求

### site_type

必须使用以下枚举之一：

```text
ecommerce
content
search
listing
spa
api_driven
unknown
```

如果是电商站，优先标 `ecommerce`，再在 `rendering` 里说明是否 SPA/API 驱动。

### rendering

必须使用以下枚举之一：

```text
static
spa
api_driven
hybrid
unknown
```

判断依据写入 `evidence_log`。

### catalog_candidates

目录候选至少包含：

```json
{
  "level1": "",
  "level2": "",
  "level3": "",
  "label": "",
  "url": "",
  "source": "",
  "evidence_type": "",
  "confidence": 0
}
```

质量要求：

- URL 必须尽量是绝对 URL。
- 不确定层级时允许 level2/level3 为空。
- 不能把 footer、博客、隐私政策、登录页当成商品目录。
- 目录数量过大时保留最有价值的前 100 个，并在 `missing_evidence` 说明截断。

### list_page_candidates

列表页候选至少包含：

```json
{
  "url": "",
  "label": "",
  "category_path": [],
  "product_count_hint": null,
  "source": "",
  "evidence_type": "",
  "confidence": 0
}
```

质量要求：

- 优先收集能看到商品卡片或产品列表的 URL。
- 如果只是目录页但未确认有商品，confidence 不得超过 0.6。

### detail_url_patterns

详情页模式至少包含：

```json
{
  "pattern": "",
  "examples": [],
  "evidence_type": "",
  "confidence": 0
}
```

质量要求：

- 必须至少给出 1 个 example，否则 confidence 不得超过 0.4。
- 不要只写泛泛的 `product page pattern`。

### api_candidates

API 候选至少包含：

```json
{
  "method": "GET",
  "url": "",
  "content_type": "",
  "items_path": "",
  "pagination_hints": {},
  "field_mapping": {},
  "request_body_hint": {},
  "headers_hint": {},
  "source": "",
  "evidence_type": "",
  "confidence": 0,
  "risks": []
}
```

质量要求：

- 没有观察到 XHR/API 时，不要编造 endpoint。
- 只根据脚本名猜测 API，confidence 不得超过 0.4。
- 如果 API 需要 token、签名、cookie、locale、store id，要写进 `risks`。
- `headers_hint` 不要包含真实 cookie、authorization、个人 token。

### selector_candidates

必须按字段分组：

```json
{
  "title": [],
  "highest_price": [],
  "colors": [],
  "sizes": [],
  "description": [],
  "image_urls": [],
  "product_url": [],
  "category_level_1": [],
  "category_level_2": [],
  "category_level_3": []
}
```

每个 selector 候选：

```json
{
  "selector": "",
  "selector_type": "css",
  "scope": "list",
  "sample_value": "",
  "evidence_type": "",
  "confidence": 0
}
```

质量要求：

- `selector_type` 只能是 `css`、`xpath`、`jsonpath`、`meta`。
- `scope` 只能是 `list`、`detail`、`api`、`global`。
- 没有 sample value 的 selector，confidence 不得超过 0.5。
- 颜色、尺码如果在变体 JSON 或脚本里，不要硬写 DOM selector，应该标 `selector_type=jsonpath` 或写入 API 候选。

### difficulty_signals

每个难点信号：

```json
{
  "kind": "",
  "evidence": "",
  "impact": "",
  "suggested_handling": "",
  "confidence": 0
}
```

`kind` 建议使用：

```text
js_rendering
cloudflare
captcha
api_signature
session_token
cookie_gate
geo_redirect
language_redirect
lazy_loading
infinite_scroll
graphql
post_json
rate_limit
robots_block
unknown
```

### recommended_action_plan

动作必须使用 CLM 支持的 canonical action：

```text
analyze_site
select_catalog
resolve_fields
switch_runtime
patch_profile
patch_selector
promote_xhr_to_api
apply_replay_runtime
run_test
rerun_failed
export_results
```

每个动作：

```json
{
  "action": "",
  "priority": "medium",
  "reason": "",
  "params": {},
  "depends_on_evidence": []
}
```

质量要求：

- `priority` 只能是 `low`、`medium`、`high`。
- 不要输出无法执行的自然语言动作。
- `params` 只能放有限、具体、可验证的内容。
- 如果证据弱，先建议 `analyze_site` 或 `run_test`，不要直接强推 profile patch。

## 置信度评分标准

所有 confidence 使用 0 到 1。

```text
0.0 - 0.2：基本没有证据，只是猜测
0.3 - 0.4：有弱模式，但未验证
0.5 - 0.6：有页面/URL/DOM 证据，但未运行验证
0.7 - 0.8：多个证据互相支持
0.9 - 1.0：已经通过实际请求、页面样本或结构化数据强验证
```

如果没有真实运行验证，整体 `overall` 一般不要超过 0.75。

## 自检清单

每个站点提交前必须自检：

- JSON 能否被 parser 解析。
- `site_url`、`domain`、`checked_at` 是否存在。
- `confidence` 是否都是 0 到 1。
- 是否把猜测标成了 observed。
- 是否有至少 3 条 `evidence_log`。
- 是否记录了缺失证据。
- 是否有无法验证却置信度过高的字段。
- 是否包含真实 cookie、token、authorization 等敏感值。
- recommended action 是否都在 CLM canonical action 列表里。

## 批次总结要求

每 10 个站点输出一个 batch summary，包含：

```text
1. 本批站点数量
2. 成功侦察数量
3. 无法访问数量
4. 高置信度 API 候选数量
5. 高置信度目录候选数量
6. 最常见采集难点
7. 最值得 CLM 后端优先支持的能力
8. 需要人工复核的网站列表
```

## 失败模式总结要求

每 50 个站点输出一个 failure taxonomy，按下面分类：

```text
catalog_missing
list_page_unclear
detail_links_missing
selector_weak
api_candidate_weak
api_signature_or_token
js_rendering_required
browser_required
access_blocked
pagination_unclear
field_variant_complex
unknown
```

每类都要写：

- 出现次数
- 代表网站
- 典型证据
- 建议 CLM 增强点
- 是否适合作为自动修复动作

## 禁止事项

- 禁止直接改 CLM 项目代码。
- 禁止伪造已验证数据。
- 禁止输出不可解析 JSON。
- 禁止把个人 token、cookie、authorization 写入结果。
- 禁止为追求数量而省略 evidence。
- 禁止把不确定 selector 写成高置信度。
- 禁止用自然语言替代结构化字段。

## 最终交付

5 天任务结束后，必须交付：

1. 每站一个 `clm-site-recon-v1` JSON。
2. 每 10 站一个 batch summary。
3. 每 50 站一个 failure taxonomy。
4. 一个 final report，说明：
   - 最常见网站类型
   - 最常见失败原因
   - 最有价值 API 模式
   - 最常见 selector 模式
   - CLM 后端最该补的 10 个能力
   - 哪些 evidence 可以进入 fixture
   - 哪些站点适合后续真实训练

