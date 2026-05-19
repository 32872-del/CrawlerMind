# CLM 新手操作文档

日期: 2026-05-18

适用对象: 第一次拿到 Crawler-Mind / CLM 的使用者、测试人员、前端体验人员。

本文目标: 不讲架构，先把项目跑起来，并完成一次从网页工作台发起的采集测试。

## 1. 你需要准备什么

建议环境:

- Python 3.11+
- Node.js 18+
- Git
- Windows PowerShell 或普通终端

如果要测试浏览器渲染能力，还需要安装 Playwright 浏览器:

```powershell
playwright install
```

如果只是先测试前端工作台和基础 API，可以暂时不跑真实复杂网站。

## 2. 安装后端依赖

在项目根目录运行:

```powershell
cd F:\datawork\agent
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

可选检查:

```powershell
python clm.py check
```

如果输出没有明显报错，后端基础依赖基本可用。

## 3. 安装前端依赖

打开一个终端:

```powershell
cd F:\datawork\agent\frontend
npm install
```

验证前端能构建:

```powershell
npm run build
```

如果只看到 Ant Design chunk 偏大的 warning，可以先忽略。

## 4. 启动后端服务

打开第一个终端:

```powershell
cd F:\datawork\agent
uvicorn autonomous_crawler.api.app:app --reload --host 127.0.0.1 --port 8000
```

浏览器打开:

```text
http://127.0.0.1:8000/docs
```

看到 FastAPI 文档页面，说明后端启动成功。

## 5. 启动前端工作台

打开第二个终端:

```powershell
cd F:\datawork\agent\frontend
npm run dev -- --port 5174
```

浏览器打开:

```text
http://127.0.0.1:5174
```

你应该看到 `CLM 采集工作台`。

## 6. 第一次建议用演示模式测试

进入前端后:

1. 打开 `系统设置`。
2. 把 `API 模式` 设为 `演示数据`。
3. 点击保存。
4. 打开 `新建任务`。
5. 输入测试网址:

```text
https://dummyjson.com/products
```

6. 字段需求可以写:

```text
采集商品标题、价格、描述和图片
```

7. 点击分析、选择字段、进入运行步骤。
8. 选择 `试跑`。
9. 导出格式选择 `xlsx`。
10. 提交任务。

演示模式不会真的抓网站，主要用于确认前端流程是否顺畅。

## 7. 连接真实后端测试

确认后端服务还在运行后:

1. 打开 `系统设置`。
2. 设置 `CLM API 地址`:

```text
http://127.0.0.1:8000
```

3. 设置 `API 模式` 为 `自动` 或 `真实后端`。
4. 默认导出目录可填:

```text
F:\datawork\agent\dev_logs\exports
```

5. 点击 `检查并创建`。

如果显示目录存在或可写，就可以继续。

## 8. 配置 LLM

如果你暂时不想使用 LLM，可以跳过本节。CLM 可以用确定性规则先跑。

如果要使用 LLM:

1. 打开 `系统设置`。
2. 选择服务商预设，或手动填写:

```text
接口 Base URL: https://你的中转站或模型服务/v1
API Key: 你的 key
```

3. 点击 `获取模型列表`。
4. 从下拉框选择模型。
5. 如果模型列表获取失败，可以手动输入模型名。

常见格式:

```text
https://api.openai.com/v1
https://api.deepseek.com/v1
https://api.siliconflow.cn/v1
http://127.0.0.1:11434/v1
```

## 9. 跑一次真实任务

新手建议先用简单公开 API 或静态页面，不要一上来就跑复杂电商站。

示例:

```text
https://dummyjson.com/products
```

操作:

1. 打开 `新建任务`。
2. 输入目标网址。
3. 输入字段需求。
4. 点击站点分析。
5. 勾选字段。
6. 选择 `试跑`。
7. 确认导出路径。
8. 提交任务。
9. 打开 `任务详情` 查看进度。
10. 完成后点击导出。

## 10. 导出结果

当前支持:

```text
json, csv, xlsx, sqlite, db
```

新手建议先用:

```text
xlsx
```

导出路径示例:

```text
F:\datawork\agent\dev_logs\exports\test-products.xlsx
```

如果导出失败，先检查:

- 后端是否还在运行
- 导出目录是否存在
- 导出目录是否可写
- 任务是否真的产生了数据

## 11. 命令行备用测试

如果前端出现问题，可以用 CLI 判断后端是否正常。

基础检查:

```powershell
python clm.py check
```

mock 采集:

```powershell
python clm.py crawl "collect product titles and prices" mock://catalog --output dev_logs/runtime/mock_result.json
```

百度热搜 smoke:

```powershell
python clm.py crawl "collect top 30 hot searches" "https://top.baidu.com/board?tab=realtime" --output dev_logs/runtime/baidu_hot.json
```

## 12. 常见问题

### 前端提示无法连接后端

检查后端终端是否还在运行:

```powershell
uvicorn autonomous_crawler.api.app:app --reload --host 127.0.0.1 --port 8000
```

前端 `CLM API 地址` 应该是:

```text
http://127.0.0.1:8000
```

### 获取模型列表失败

检查:

- Base URL 是否带 `/v1`
- API Key 是否正确
- 服务商是否支持 `/v1/models`
- 中转站是否允许模型列表接口

即使模型列表失败，也可以手动输入模型名。

### 导出失败

先在 `系统设置` 里点击 `检查并创建`。

推荐使用项目内目录:

```text
F:\datawork\agent\dev_logs\exports
```

### 页面打开后不是首页

前端会把上次状态保存在浏览器 localStorage。

这是正常行为。可以点击左侧菜单回到 `工作台` 或 `新建任务`。

### 复杂网站采集效果不好

当前 CLM 已经有浏览器、API、长跑、诊断和导出基础，但复杂电商站仍需要继续训练和 profile 优化。

新手测试请先用简单目标确认流程，再逐步换成更难的网站。

## 13. 新手测试清单

建议按顺序完成:

- 后端能启动
- 前端能启动
- 演示模式能跑通
- 真实后端模式能连接
- LLM 模型列表能获取或能手动填模型
- 导出目录能检查并创建
- 试跑任务能提交
- 任务详情能刷新
- 结果能导出 xlsx

完成这 9 项后，就可以开始做真实网站训练。

