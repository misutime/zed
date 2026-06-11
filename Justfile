set shell := ["sh", "-c"]
set windows-shell := ["pwsh.exe", "-NoLogo", "-NoProfile", "-Command"]

locale := "zh-CN"

# Show local i18n commands.
default:
    @just i18n-help

# Show local i18n status.
i18n-help:
    @uv run zed-i18n info

# One command: generate and bundle the zh-CN app for the current platform.
doit:
    uv run zed-i18n bundle --language "{{locale}}"

# One command with manifest refresh before bundling.
doit-fresh:
    uv run zed-i18n bundle --language "{{locale}}" --extract

# Extract source strings from this repository into i18n/catalog and i18n/manifest.
i18n-extract:
    uv run zed-i18n extract

# Audit untranslated/string candidates in this repository.
i18n-audit:
    uv run zed-i18n audit-candidates

# Validate the zh-CN translation file against the manifest.
i18n-validate:
    uv run zed-i18n validate --language "{{locale}}" --no-cleanup

# Generate a zh-CN checkout under target/zed-i18n/zh-CN without modifying this source tree.
i18n-apply:
    uv run zed-i18n apply --language "{{locale}}"

# One-command workflow: validate, then generate the zh-CN checkout.
i18n-sync:
    uv run zed-i18n sync --language "{{locale}}"

# Prepare AI translation batches for missing zh-CN strings.
i18n-prepare:
    uv run zed-i18n extract
    uv run zed-i18n audit-candidates
    uv run zed-i18n prepare-translation --language "{{locale}}"

# Merge AI translation batch results and validate.
i18n-merge:
    uv run zed-i18n merge-translation --language "{{locale}}"
    just i18n-validate

# Run the generated translated Zed dev build.
i18n-run:
    cd target/zed-i18n/zh-CN && cargo run -p zed
