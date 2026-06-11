# 中文版快速打包

这份文档只讲本地一键打包中文简体应用。当前仓库已经内置中文本地化工具，不再需要维护单独的 `zed-i18n` 仓库。

## 最快使用

macOS 和 Windows 都使用同一个命令：

```bash
just doit
```

它会自动执行：

1. 校验 `i18n/translations/zh-CN.json`。
2. 生成独立中文源码副本：

   ```text
   target/zed-i18n/zh-CN
   ```

3. 只在这个副本里应用中文翻译。
4. 自动识别当前平台和 CPU 架构。
5. 在中文副本里调用 Zed 官方打包脚本。
6. 把最终产物复制到：

   ```text
   i18n/dist/
   ```

原始源码目录 `D:\misutime\zed` 不会被翻译改写，内部仍保持英文。

## 常用命令

```bash
just i18n-help      # 查看本地化状态
just i18n-extract   # 源码字符串变化后刷新 manifest
just i18n-sync      # 只生成中文源码副本，不打包
just i18n-run       # 运行中文副本的 dev build
just i18n-validate  # 校验 zh-CN 翻译
just doit           # 生成并打包中文应用
just doit-fresh     # 先刷新 manifest，再生成并打包中文应用
```

等价的底层命令：

```bash
uv run zed-i18n bundle --language zh-CN
```

默认 `just doit` 不会每次重新提取源码字符串，这样打包启动更快。源码 UI 字符串变化后，先运行：

```bash
just i18n-extract
```

或者直接运行：

```bash
just doit-fresh
```

如果你已经生成过中文副本，只想重新打包：

```bash
uv run zed-i18n bundle --language zh-CN --skip-sync
```

## macOS

`just doit` 会在中文副本里运行：

```bash
bash ./script/bundle-mac <当前架构>
```

产物一般是 `.dmg`，并会复制到 `i18n/dist/`。

## Windows

`just doit` 会在中文副本里运行：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File script/bundle-windows.ps1 -Architecture <当前架构>
```

需要本机已有 Zed 的 Windows 构建环境，例如 Rust、Visual Studio C++ build tools、Windows SDK、CMake、PowerShell 7、Inno Setup、`uv` 和 `just`。

产物一般是安装器 `.exe`，并会复制到 `i18n/dist/`。

## 更新翻译

当源码新增英文 UI 字符串时：

```bash
just i18n-prepare
```

工具会生成翻译批次到：

```text
i18n/reports/translation/zh-CN/
```

把 AI 或人工翻译结果放到 `results/` 后运行：

```bash
just i18n-merge
just doit
```

## 注意

- `target/zed-i18n/zh-CN` 是生成副本，可以删除后重新生成。
- `i18n/dist/` 是打包产物目录，已被 Git 忽略。
- `just doit` 使用当前仓库已提交的 `HEAD` 生成中文副本。如果你刚改了 Zed 源码，请先提交，再打包。
