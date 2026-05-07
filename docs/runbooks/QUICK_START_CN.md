# 项目上手指南

## 1. 先看什么

按这个顺序读：

1. `PROJECT_STATUS.md`
2. `docs/team/TEAM_BOARD.md`
3. `docs/runbooks/EMPLOYEE_TAKEOVER.md`
4. `docs/memory/EMPLOYEE_MEMORY_MODEL.md`
5. 最新的 `docs/reports/*_DAILY_REPORT.md`
6. 你当前对应的 `docs/team/assignments/*`

如果你是新接入的 AI，先确认自己要操作的 `Employee ID` 和当前任务。

## 2. 环境准备

在项目根目录执行：

```powershell
python -m pip install -r requirements.txt
playwright install
```

如果你只想先跑纯本地确定性流程，`playwright install` 可以后装。

## 3. 最小跑通

先跑单测和编译检查：

```powershell
python -m unittest discover -s autonomous_crawler/tests
python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py
```

再跑一个本地流程：

```powershell
python run_skeleton.py "collect product titles and prices" mock://catalog
```

如果这一步成功，说明主流程是通的。

## 4. 跑百度热搜 smoke test

```powershell
python run_baidu_hot_test.py
```

通过标准：

- 最终状态是 `completed`
- 采到 30 条
- 验证通过

结果会写到 `dev_logs/baidu_hot_smoke_result.json`。

## 5. 接 LLM 运行

这个项目支持 OpenAI-compatible 接口。先配置环境变量：

```powershell
$env:CLM_LLM_ENABLED='1'
$env:CLM_LLM_BASE_URL='https://api.openai.com/v1'
$env:CLM_LLM_MODEL='gpt-4o-mini'
$env:CLM_LLM_API_KEY='你的key'
```

然后运行：

```powershell
python run_skeleton.py --llm "collect product titles and prices" https://example.com
```

如果你用的是本地兼容服务，通常只要改：

- `CLM_LLM_BASE_URL`
- `CLM_LLM_MODEL`
- `CLM_LLM_API_KEY` 可以留空

## 6. 启动 API

```powershell
uvicorn autonomous_crawler.api.app:app --reload
```

可用接口：

- `GET /health`
- `POST /crawl`
- `GET /crawl/{task_id}`
- `GET /history`

## 7. 结果查看

```powershell
python run_results.py list
python run_results.py show <task_id>
python run_results.py items <task_id>
python run_results.py export-json <task_id> output.json
python run_results.py export-csv <task_id> output.csv
```

## 8. 常见问题

### `LLM configuration error: CLM_LLM_BASE_URL is required`

你传了 `--llm`，但没配 LLM 环境变量。先设置 `CLM_LLM_BASE_URL`
和 `CLM_LLM_MODEL`。

### `Browser not found`

说明浏览器二进制没装好。运行：

```powershell
playwright install
```

### 单测通过但 LLM 结果不稳定

先看 `llm_decisions` 和 `llm_errors`，不要先怀疑主流程。这个项目的
原则是：LLM 只能增强，不应该破坏 deterministic fallback。

## 9. 每天怎么工作

建议流程：

1. 先 `git pull origin main`
2. 看 `PROJECT_STATUS.md` 和 `docs/reports/*_DAILY_REPORT.md`
3. 接自己的 `docs/team/assignments/*`
4. 写实现
5. 跑测试
6. 写 `dev_logs/`
7. 提交给主管验收

## 10. 下一步建议

如果你刚上手，建议先做这三件事：

1. 跑通 `run_skeleton.py`
2. 跑通 `run_baidu_hot_test.py`
3. 用 `--llm` 接一次真实兼容模型

