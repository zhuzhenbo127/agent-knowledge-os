# Obsidian 设置

## 默认核心插件

静默启用 File Explorer、Search、Backlinks、Outgoing Links、Graph、Tags、Properties、Templates、File Recovery、Bases。这些是 Obsidian 自带功能，不下载第三方代码。

运行：

```bash
python3 scripts/setup_obsidian.py --vault "/absolute/vault/path"
```

脚本增量合并 `.obsidian/core-plugins.json`，保留已有插件并在变化时备份。不得关闭用户已有插件。

## 社区插件白名单

- `dataview`：高级查询包。
- `templater`：手工模板包。

只有用户在引导确认单中明确选择后运行：

```bash
python3 scripts/setup_obsidian.py --vault "/absolute/vault/path" --community-pack dataview --community-confirmed
```

社区插件执行第三方代码。脚本只通过 Obsidian 1.12.7+ 官方 CLI 安装白名单；CLI 不可用时停止，不直接下载插件、不改 Restricted Mode。用户明确确认后，脚本才通过 `plugins:restrict off` 关闭 Restricted Mode 并安装；若首次安装失败且原来处于 Restricted Mode，会尝试恢复。不得静默更新社区插件。

## 边界

- 不安装 Obsidian 应用。
- 不覆盖 `app.json` 或 workspace 布局。
- 不关闭已有插件。
- 未选社区插件时，不改变 Restricted Mode 和社区插件列表。
