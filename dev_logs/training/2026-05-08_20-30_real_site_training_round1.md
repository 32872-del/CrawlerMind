# 2026-05-08 20:30 Real-Site Training Round 1

## Context

The user provided `E:\爬虫Agent实战训练网站清单.md` and asked CLM to assess
feasibility, choose part of the list, add crawl scenarios, and begin training.

## Completed

- Restored the document with UTF-8 reading after an initial mojibake display.
- Classified the list by training risk.
- Selected low-risk public targets for today's first training round:
  - JSONPlaceholder posts
  - Reddit r/python `.json`
  - Countries GraphQL
- Implemented direct JSON URL recognition.
- Implemented GraphQL POST execution support.
- Added configured API/GraphQL Recon fast path.
- Added Reddit-style `data.children[].data` extraction.
- Added `run_training_round1.py`.
- Saved compact training output to:

```text
dev_logs/training/2026-05-08_real_site_training_round1.json
```

## Results

```text
python run_training_round1.py

jsonplaceholder_posts: completed, 10 items, api_json, 4.63s
reddit_python_json: completed, 10 items, api_json, 7.77s
countries_graphql: completed, 10 items, graphql_json, 2.10s
```

## Verification

```text
python -m unittest discover -s autonomous_crawler/tests
Ran 256 tests in 80.200s
OK (skipped=3)

python -m compileall autonomous_crawler run_skeleton.py run_baidu_hot_test.py run_results.py run_simple.py run_training_round1.py
OK
```

## Notes

- Countries GraphQL initially took about 35 seconds because Recon tried to
  inspect/render the playground page before Strategy used the explicit query.
  The configured API Recon path fixed this and brought the run to about 2
  seconds.
- The training list includes high-risk targets such as login-required,
  CAPTCHA, fingerprinting, and strong anti-bot sites. These should be used for
  diagnosis and safety-aware planning first, not bypass implementation.
