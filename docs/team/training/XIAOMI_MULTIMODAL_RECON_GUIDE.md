# Xiaomi Multimodal Recon Guide

更新日期：2026-05-28

## 目的

这份规范给多模态模型使用。它的任务不是替代 CLM 后端采集，也不是写最终爬虫代码，而是把网页截图、HTML 摘要、网络摘要转成可验证的视觉 evidence。

这些 evidence 后续会进入 CLM 的：

```text
Managed Crawl State
-> LLM Decision
-> Structured Action Plan
-> Action Executor
-> Failure Diagnosis
```

## 输入材料

每个任务尽量包含：

- `site_url`
- 页面截图
- HTML 摘要
- 可选：网络请求摘要
- 可选：当前 CLM run/status/evidence pack
- 可选：用户希望采集的字段

如果只有截图，也可以工作，但必须降低置信度。

## 输出文件

每个页面输出一个 JSON 文件：

```text
visual_序号_域名_page_slug.json
```

建议目录：

```text
F:\datawork\agent\dev_logs\training\xiaomi_visual_recon_2026_05_28\
```

## JSON Schema

```json
{
  "schema_version": "clm-visual-recon-v1",
  "site_url": "",
  "page_url": "",
  "domain": "",
  "checked_at": "",
  "input_artifacts": {
    "screenshot_path": "",
    "html_summary_path": "",
    "network_summary_path": ""
  },
  "page_type": "",
  "visual_state": "",
  "is_product_listing": false,
  "is_product_detail": false,
  "visible_catalog": [],
  "visible_product_cards": {
    "detected": false,
    "count_estimate": 0,
    "layout": "",
    "evidence": "",
    "confidence": 0
  },
  "field_regions": {
    "title": [],
    "highest_price": [],
    "colors": [],
    "sizes": [],
    "description": [],
    "image_urls": [],
    "product_url": []
  },
  "blocking_signals": [],
  "pagination_signals": [],
  "visual_action_hints": [],
  "recommended_action_plan": [],
  "confidence": {
    "page_type": 0,
    "product_cards": 0,
    "fields": 0,
    "blocking": 0,
    "pagination": 0,
    "overall": 0
  },
  "evidence_log": [],
  "missing_evidence": [],
  "needs_backend_verification": true,
  "needs_human_review": true
}
```

## 枚举规范

### page_type

只能使用：

```text
home
catalog
product_listing
product_detail
search_results
cart
login
blocked
empty
error
unknown
```

### visual_state

只能使用：

```text
normal
loading
empty_content
cookie_banner
age_gate
geo_redirect
language_redirect
login_wall
challenge
captcha
blocked
broken_layout
unknown
```

## visible_catalog

如果截图中能看到目录/导航，输出：

```json
{
  "label": "",
  "level_hint": 1,
  "visible_text": "",
  "position_hint": "top_nav",
  "confidence": 0,
  "evidence_type": "observed"
}
```

`position_hint` 可用：

```text
top_nav
side_nav
mega_menu
breadcrumb
footer
mobile_menu
unknown
```

不要把 footer 的隐私政策、账号、帮助中心误判为商品目录。

## field_regions

每个字段区域输出：

```json
{
  "region_id": "",
  "scope": "list",
  "position_hint": "",
  "visible_text_sample": "",
  "nearby_visual_clues": [],
  "selector_hint": "",
  "confidence": 0,
  "evidence_type": "observed"
}
```

`scope` 只能是：

```text
list
detail
global
unknown
```

`position_hint` 示例：

```text
product_card_top
product_card_middle
product_card_bottom
hero_area
right_panel
left_gallery
below_title
near_price
near_variant_selector
unknown
```

注意：

- 视觉模型只能给区域和线索，不要声称 selector 一定可用。
- `selector_hint` 只能是低置信度提示，必须由 CLM 后端验证。

## blocking_signals

每个阻塞信号：

```json
{
  "kind": "",
  "visible_text": "",
  "evidence": "",
  "impact": "",
  "suggested_handling": "",
  "confidence": 0
}
```

`kind` 可用：

```text
cloudflare
captcha
cookie_banner
age_gate
login_wall
geo_block
language_redirect
empty_listing
loading_spinner
js_not_rendered
rate_limit
unknown
```

## pagination_signals

每个分页信号：

```json
{
  "kind": "",
  "visible_text": "",
  "position_hint": "",
  "confidence": 0,
  "evidence_type": "observed"
}
```

`kind` 可用：

```text
page_numbers
next_button
load_more
infinite_scroll
filter_sort_panel
product_count_text
unknown
```

## visual_action_hints

这不是最终 action plan，而是视觉层建议：

```json
{
  "hint": "",
  "reason": "",
  "confidence": 0
}
```

示例：

```text
use_browser_runtime
wait_for_product_cards
accept_cookie_banner
inspect_xhr_after_scroll
extract_breadcrumb_categories
probe_detail_page_for_variants
```

## recommended_action_plan

如果要输出 action plan，只能使用 CLM canonical action：

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

每个 action：

```json
{
  "action": "",
  "priority": "medium",
  "reason": "",
  "params": {},
  "depends_on_evidence": []
}
```

要求：

- 不要输出自由发挥动作名。
- 视觉证据不足时，优先建议 `analyze_site`、`switch_runtime`、`run_test`。
- 不要直接强推 selector patch，除非截图和 HTML 摘要都支持。

## 置信度规则

```text
0.0 - 0.2：几乎没有证据
0.3 - 0.4：弱视觉线索
0.5 - 0.6：截图中能看到明显区域，但缺少 HTML/API 支撑
0.7 - 0.8：截图 + HTML 摘要互相支持
0.9 - 1.0：截图 + HTML/API/运行结果都支持
```

只有截图时，`overall` 一般不要超过 0.65。

## 自检清单

提交前必须确认：

- JSON 可解析。
- 没有 Markdown 包裹。
- 没有尾逗号。
- confidence 均为 0 到 1。
- 所有 action 都是 canonical action。
- `needs_backend_verification` 默认为 true。
- 未把视觉判断写成已验证 selector。
- 未伪造看不到的 API、DOM、XHR。

## 批次报告

每 20 个页面输出一个 batch report：

```text
1. 页面数量
2. product_listing 数量
3. product_detail 数量
4. blocked/challenge/captcha 数量
5. cookie_banner 数量
6. 有明显商品卡片的页面数量
7. 有明显分页信号的页面数量
8. 最常见视觉失败原因
9. 最建议 CLM 后端补强的能力
10. 需要人工复核的页面列表
```

## 禁止事项

- 禁止修改 CLM 代码。
- 禁止伪造 API 或 selector。
- 禁止把截图猜测写成后端验证结果。
- 禁止输出不可解析 JSON。
- 禁止长篇自然语言代替结构化字段。
- 禁止覆盖其他员工的输出目录。

