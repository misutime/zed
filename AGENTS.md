.rules

## Local zh-CN i18n

This fork includes a single-repository zh-CN localization workflow.
Run commands from the repository root:

- `uv run zed-i18n info`
- `uv run zed-i18n extract`
- `uv run zed-i18n validate --language zh-CN --no-cleanup`
- `uv run zed-i18n apply --language zh-CN`

The source tree is the current repository. Localization data lives in `i18n/`, and generated reports live under `i18n/reports/`.
`apply` and `sync` must not mutate the source tree; they generate a localized checkout under `target/zed-i18n/zh-CN`.
