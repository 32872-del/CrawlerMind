# Developer Evidence Log

`dev_logs/` stores timestamped implementation notes and selected run artifacts.
Long-lived project knowledge belongs in `docs/`; raw or repeatable execution
evidence belongs here.

## Layout

- `development/` - developer implementation logs and supervisor close-out notes.
- `audits/` - local audit and QA notes that are not formal team acceptance docs.
- `training/` - real-site training summaries, JSON exports, and Excel exports.
- `smoke/` - small smoke-test outputs such as Baidu hot-list and runner smoke.
- `stress/` - local stress-test reports and large synthetic export evidence.
- `runtime/` - untracked scratch outputs from local commands.

## Rules

- Use `YYYY-MM-DD_HH-MM_topic.md` for human-written developer logs.
- Put public training exports under `training/`.
- Put generated one-off command state under `runtime/`; this directory is
  gitignored.
- Keep formal reports in `docs/reports/`, plans in `docs/plans/`, employee
  handoffs in `docs/memory/handoffs/`, and accepted work in
  `docs/team/acceptance/`.
- Do not store secrets, cookies, private tokens, proxy credentials, or local
  runtime databases here.

## Migration Note

On 2026-05-11, the previous flat `dev_logs/` directory was split into the
sections above. Historical filenames were kept intact; only their parent
directory changed.
