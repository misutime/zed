# Zed 中文本地化工具

这个 fork 把中文本地化工具内置在 Zed 仓库里，不再维护单独的 `zed-i18n` 源码缓存仓库。

## 目录

- `i18n/translations/zh-CN.json`：中文翻译表
- `i18n/manifest/ui-strings.json`：可翻译字符串清单和状态
- `i18n/catalog/en-US.json`：英文源字符串目录
- `i18n/prompts/translation/`：AI 翻译提示词
- `i18n/reports/`：提取、校验、翻译批次等生成报告
- `script/zed_i18n/tools/zed_i18n/`：本地化工具代码

## 常用命令

在 Zed 仓库根目录运行：

```powershell
uv run zed-i18n info
uv run zed-i18n extract
uv run zed-i18n validate --language zh-CN --no-cleanup
uv run zed-i18n apply --language zh-CN
```

也可以用 `just`：

```powershell
just i18n-sync
just i18n-run
just doit
```

`i18n-sync` 会校验 `zh-CN.json`，然后生成独立的中文工作副本：

```text
target/zed-i18n/zh-CN
```

英文源码工作树不会被修改。中文翻译只会写入这个生成目录。

`just doit` 会在生成中文副本后继续调用当前平台的 Zed 打包脚本，并把安装包复制到 `i18n/dist/`。

默认 `i18n-sync` / `doit` 不会每次重新提取源码字符串。源码 UI 字符串变化后，先运行 `just i18n-extract`，或直接运行 `just doit-fresh`。

## 更新翻译

当 Zed 源码有新英文字符串时：

```powershell
just i18n-prepare
```

工具会生成：

```text
i18n/reports/translation/zh-CN/
```

把 AI 或人工翻译结果放到其中的 `results/` 后，运行：

```powershell
just i18n-merge
```

## 注意

- `i18n-apply` 和 `i18n-sync` 不会修改当前 Zed 源码，只会重建 `target/zed-i18n/zh-CN`。
- 生成中文副本时使用当前仓库已提交的 `HEAD`。如果源码有未提交改动，请先提交，再重新运行 `just i18n-sync`。
- `i18n/reports/` 是生成目录，可以按需清理；`i18n/reports/README.md` 除外。
- 这个工具链只面向团队内部的 `zh-CN` 版本，已移除单独下载/复制上游 Zed checkout 的工作流。
