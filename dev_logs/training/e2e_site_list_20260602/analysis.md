# E2E Site List 全覆盖训练分析 - 2026-06-02

**训练脚本:** `run_e2e_site_list_20260602.py`
**训练时间:** 2026-06-02 11:29 ~ 11:38
**环境:** Windows 10, Python 3.13, PowerShell, Playwright 未安装
**站点数:** 13 个（6 电商、1 API、2 内容、1 SPA、1 GraphQL、2 反爬诊断）

---

## 一、总体统计

| 指标 | 数值 |
|------|------|
| 总站点数 | 13 |
| 通过（有数据） | 4 (30.8%) |
| 空跑（完成但 0 条） | 6 (46.2%) |
| 失败（paused） | 3 (23.1%) |
| 总提取记录数 | 60 |
| 平均每通过站点记录数 | 15.0 |
| 总耗时 | ~476 秒（约 8 分钟） |

---

## 二、按场景分类结果

### 电商 (Ecommerce) — 6 站点，3 通过，58 条记录

| 站点 | 记录 | 质量 | 耗时 | 备注 |
|------|------|------|------|------|
| dummyjson.com/products | 30 | ✅ pass | 14.0s | JSON API，稳定通过 |
| jsonplaceholder.typicode.com | 0 | ⚠️ empty | 23.7s | JSON API，API 自动检测失败 |
| scrapingcourse.com/ecommerce | 16 | ✅ pass | 29.3s | SSR，稳定通过 |
| scrapingcourse.com/pagination | 0 | ⚠️ empty | 67.9s | 分页测试，未自动翻页 |
| marksandspencer.com | 12 | ✅ pass | 19.9s | 硬难度，稳定 |
| superdry.com | 0 | ❌ fail | 21.4s | 之前 4 条（导航项），现在归零 |

**表现最好的场景** — 电商类通过率 50%，是所有场景中最高的。

### API — 1 站点，0 通过，0 条记录

| 站点 | 记录 | 质量 | 耗时 | 备注 |
|------|------|------|------|------|
| hacker-news.firebaseio.com | 0 | ⚠️ empty | 23.3s | Firebase API，未正确解析 |

**问题:** API 自动检测未生效（`api_hints_detected: false`），尽管这是纯 JSON API 端点。

### 内容 (Content) — 2 站点，0 通过，0 条记录

| 站点 | 记录 | 质量 | 耗时 | 备注 |
|------|------|------|------|------|
| quotes.toscrape.com | 0 | ⚠️ empty | 26.8s | 简单 SSR，应该能抓 |
| douban.com/top250 | 0 | ❌ fail | 6.4s | 反爬检测，快速失败 |

**问题:** quotes.toscrape.com 是一个非常简单的 SSR 站点，0 条说明选择器匹配失败。豆瓣被反爬拦截。

### SPA — 1 站点，0 通过，0 条记录

| 站点 | 记录 | 质量 | 耗时 | 备注 |
|------|------|------|------|------|
| nike.com | 0 | ⚠️ empty | 10.2s | Next.js SPA，需 Playwright |

**问题:** Playwright 未安装，静态 HTTP 无法渲染 SPA。与上次一致。

### GraphQL — 1 站点，0 通过，0 条记录

| 站点 | 记录 | 质量 | 耗时 | 备注 |
|------|------|------|------|------|
| countries.trevorblades.com | 0 | ⚠️ empty | 38.4s | GraphQL 端点 |

**问题:** GraphQL 请求未被正确构造。爬虫尝试了普通 HTTP 请求而非 GraphQL query。

### 反爬诊断 (Diagnosis) — 2 站点，1 通过，2 条记录

| 站点 | 记录 | 质量 | 耗时 | 备注 |
|------|------|------|------|------|
| scrapfly.io/fingerprint | 2 | ✅ pass | 92.9s | 诊断模式，成功采集指纹数据 |
| scrapingcourse.com/cloudflare | 0 | ❌ fail | 62.8s | Cloudflare 挑战，被拦截 |

**表现最差的场景** — 诊断类 50% 通过率，但 Cloudflare 挑战无法绕过（无浏览器）。

---

## 三、与上次 E2E 训练对比

### 上次训练概况（e2e_run_20260602）
- 8 个站点，7 通过（87.5%），196 条记录
- 使用直接 crawl 方式（非 managed loop）

### 本次训练概况（e2e_site_list_20260602）
- 13 个站点，4 通过（30.8%），60 条记录
- 使用 managed loop 7 步管道

### 逐站点对比

| 站点 | 上次记录 | 本次记录 | 变化 | 分析 |
|------|----------|----------|------|------|
| dummyjson.com/products | 30 | 30 | ➡️ 持平 | 管道修复确认，稳定 30 条 |
| dummyjson.com/categories | 24 | — | 🆕 未测 | 本次未包含 |
| jsonplaceholder/posts | 100 | 0 | 🔴 退步 | managed loop 未能正确解析 API |
| scrapingcourse/ecommerce | 16 | 16 | ➡️ 持平 | SSR 提取稳定 |
| scrapingcourse/pagination | 12 | 0 | 🔴 退步 | 上次 12 条（仅首页），本次 0 条 |
| marksandspencer.com | 10 | 12 | 🟢 改善 | +2 条，选择器略有改善 |
| nike.com | 0 | 0 | ➡️ 持平 | SPA 仍无法处理（无 Playwright） |
| superdry.com | 4 | 0 | 🔴 退步 | 上次 4 条（导航项），本次归零 |
| quotes.toscrape.com | — | 0 | 🆕 新增 | 首次测试，0 条 |
| douban.com/top250 | — | 0 | 🆕 新增 | 首次测试，被反爬拦截 |
| hackernews API | — | 0 | 🆕 新增 | 首次测试，API 解析失败 |
| graphql/countries | — | 0 | 🆕 新增 | 首次测试，GraphQL 未支持 |
| scrapfly/fingerprint | — | 2 | 🆕 新增 | 诊断模式通过 |
| cloudflare/challenge | — | 0 | 🆕 新增 | Cloudflare 拦截 |

### 关键对比结论

1. **dummyjson.com 管道修复确认** ✅ — 上次 30 条，本次 30 条，稳定输出
2. **marksandspencer.com 微改善** ✅ — 从 10 条提升到 12 条
3. **jsonplaceholder 严重退步** 🔴 — 上次 100 条，本次 0 条。managed loop 的 API 自动检测未能识别此端点
4. **scrapingcourse pagination 退步** 🔴 — 上次至少有 12 条（首页），本次 0 条。managed loop 的分页逻辑更差
5. **superdry 退步** 🔴 — 上次 4 条（虽然都是导航项），本次 0 条

---

## 四、发现的问题

### P0 严重问题

#### 1. Managed Loop 退步：多个之前通过的站点现在归零
- **jsonplaceholder:** 100 → 0 条
- **scrapingcourse/pagination:** 12 → 0 条
- **superdry:** 4 → 0 条
- **根因:** managed loop 的 7 步管道（reanalyze_site → inspect_access → repair_selectors → ...）可能干扰了原有的提取逻辑。`api_hints_detected: false` 说明 API 自动检测在 managed loop 中未正确工作。

#### 2. Playwright 未安装导致 SPA 和浏览器依赖站点全军覆没
- 所有 13 个站点都显示 `browser_fallback: true`（回退到静态请求）
- 受影响站点：nike.com、graphql/countries、cloudflare challenge
- **修复:** `pip install playwright && playwright install chromium`

### P1 中等问题

#### 3. API 自动检测失效
- jsonplaceholder（纯 JSON API）和 hackernews Firebase API 都未被识别为 API
- `api_hints_detected: false` 对所有站点
- **影响:** API 端点被当作普通网页处理，自然提取不到数据

#### 4. GraphQL 端点不支持
- countries.trevorblades.com 需要发送 GraphQL query，但爬虫使用普通 GET 请求
- 需要检测 GraphQL 端点并构造正确的 POST 请求体

#### 5. 分页逻辑未工作
- scrapingcourse/pagination: 0 条（上次直接 crawl 能拿 12 条首页）
- `pagination_followed: false` 对所有站点
- managed loop 检测到了分页但未实际执行翻页

### P2 低等问题

#### 6. quotes.toscrape.com 提取失败
- 最简单的 SSR 站点之一，DOM 结构清晰
- 0 条说明选择器匹配逻辑有误，需要检查 `repair_selectors` 步骤的输出

#### 7. douban.com 反爬拦截
- 豆瓣有 User-Agent 检测和频率限制
- 6.4 秒快速失败，可能是 HTTP 403/418
- 需要更真实的请求头或代理

#### 8. field_coverage 普遍偏低
- 通过的站点 field_coverage 仅 50%（上次 70-100%）
- 说明 managed loop 提取的字段不如直接 crawl 丰富

---

## 五、下一步建议

### 立即行动（P0）

1. **安装 Playwright**
   ```powershell
   pip install playwright
   playwright install chromium
   ```
   解决 SPA 站点和浏览器依赖问题。

2. **排查 managed loop 退步原因**
   - 对比 jsonplaceholder 的 managed loop 中间输出与直接 crawl 输出
   - 检查 `reanalyze_site` 步骤是否改变了 API 识别结果
   - 可能需要在 managed loop 中保留 API 自动检测的原始逻辑

### 短期改进（P1）

3. **修复 API 自动检测**
   - 检查 Content-Type 为 `application/json` 的响应
   - 对 JSON 响应体直接解析而非走 DOM 选择器

4. **实现基本分页支持**
   - 检测 `<a>` 标签中的 "next"、页码链接
   - 对 pagination 场景自动跟随下一页

5. **添加 GraphQL 支持**
   - 检测 `/graphql` 端点
   - 构造 Introspection query 获取 schema
   - 发送 POST 请求而非 GET

### 中期优化（P2）

6. **提升 field_coverage**
   - managed loop 的 `repair_selectors` 应保留更多字段
   - 对比 50% vs 100% coverage 的差异字段

7. **改进反爬绕过**
   - 添加真实浏览器 User-Agent
   - 对 douban 等站点添加请求间隔和重试逻辑

8. **添加请求头和代理支持**
   - 可配置的 User-Agent 池
   - 代理轮换支持

---

## 六、结论

本次全覆盖训练暴露了 managed loop 管道的关键问题：**虽然 dummyjson.com 的管道修复确认有效（稳定 30 条），但 managed loop 相比直接 crawl 在多个站点上出现了退步。** jsonplaceholder 从 100 条降到 0 条是最严重的信号，说明 7 步管道中的某一步（很可能是 `reanalyze_site` 或 `inspect_access`）改变了原有的 API 识别和提取路径。

**核心矛盾：** managed loop 设计目标是自动化诊断和修复，但目前它的介入反而降低了提取成功率（87.5% → 30.8%）。下一步的首要任务是排查 managed loop 中哪些步骤引入了退步，并确保管道是"增强"而非"覆盖"原有的提取逻辑。

**优先级排序：**
1. 安装 Playwright（解决 SPA）
2. 修复 managed loop 退步（恢复 jsonplaceholder 等）
3. 修复 API 自动检测
4. 实现分页支持
5. 添加 GraphQL 支持
