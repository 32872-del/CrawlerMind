# Dev Log - 2026-05-04 18:00 - Baidu Hot Search Smoke Test

## Goal

Use the current Agent framework to collect the top 30 items from:

```text
https://top.baidu.com/board?tab=realtime
```

## What changed before the test

### 1. Executor supports bundled fnspider engine path

- Updated `autonomous_crawler/agents/executor.py`.
- Added `engine="fnspider"` branch.
- The branch can run `site_spec_draft` through the bundled fnspider adapter and
  read generated SQLite rows back into `extracted_data`.

### 2. Extractor supports generic fields

- Updated `autonomous_crawler/agents/extractor.py`.
- Selectors are no longer limited to product fields.
- Ranking/list fields such as `rank`, `hot_score`, and `summary` can be
  extracted with the same selector contract.
- Added `max_items` support.
- `rank` is normalized to extraction order when requested.

### 3. Validator supports non-product tasks

- Updated `autonomous_crawler/agents/validator.py`.
- Price is now required only when `price` is one of the requested target fields.

### 4. Tests expanded

- Added generic field extraction test.
- Added ranking-task validator test.

## Baidu selectors used

```json
{
  "item_container": ".category-wrap_iQLoo",
  "rank": ".index_1Ew5p",
  "title": ".title_dIF3B .c-single-text-ellipsis",
  "link": ".title_dIF3B@href",
  "hot_score": ".hot-index_1Bl1a",
  "summary": ".hot-desc_1m_jR",
  "image": ".img-wrapper_29V76 img@src"
}
```

## Test result

```text
status: completed
item_count: 30
validation: passed
anomalies: []
```

Result file:

```text
dev_logs/baidu_hot_smoke_result.json
```

## First 30 titles captured

1. 以实现中华民族伟大复兴为己任
2. 海拔5000米的雪山都堵成了人山
3. 广州有人花300多买了28斤榴莲
4. 返程开启 这份出行指南请收好
5. 曾经爆火的高端牛奶不被买账了
6. 最不爱睡觉的国家举办睡觉大赛
7. 退役军人57秒从8楼飞奔救起落水幼童
8. 329元一晚的酒店像捅了蟑螂窝
9. 5秒击毙歹徒 这群隐身23年的青年获奖
10. “猴山没有锅 挂面塞进去没猴会做”
11. “法拉利大叔”曾是刘亦菲的舞蹈老师
12. 网民编造马路被鞭炮炸出大坑被罚
13. 豆包将上线付费服务
14. 女学生照片被改黄图涉事男子已道歉
15. “10后”小孩哥仅用1秒还原魔方
16. 济南半小时从晴空万里转为狂风骤雨
17. 大西洋一邮轮出现病毒感染 已致3死
18. 中国就日本“核突破”向联合国发警告
19. 商场不倒翁演员从约3米高处摔落
20. 年轻人钱包流向大揭秘
21. 景区突遇暴风雨 游客称像"渡劫"
22. 敦煌鸣沙山坐满游客挤成“拼豆”
23. 著名法学家王连昌逝世
24. 呼伦贝尔三只熊路边直立趴车讨食
25. 请5天年假只批2天 被公司按旷工辞退
26. 网约车乘客强抢方向盘酿车祸
27. “房东”骗完租客转头问AI会被抓吗
28. 赵心童携女友看王楚钦比赛
29. 女子想要40码鞋子遭嘲讽？客服回应
30. 58岁伍佰拄拐杖走路 经纪人回应

## Verification commands

```text
python -m unittest discover autonomous_crawler\tests
Ran 11 tests
OK

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py
OK
```

## Notes

- The page was available through direct HTTP in this test, so browser rendering
  was not required.
- MCP crawler was used for initial access diagnosis and DOM inspection.
- This was a smoke test with manually confirmed selectors. The next step is to
  teach Recon/Strategy to infer and classify ranking-list selectors
  automatically.
