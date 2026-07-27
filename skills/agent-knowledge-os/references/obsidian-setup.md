# Obsidian 设置

## 应用检测与自动安装

首先静默检测，这一步不会修改系统：

```bash
python3 scripts/install_obsidian.py --check
```

如果已安装，直接继续配置 Vault，不再询问。如果未安装，向用户展示脚本返回的系统、安装渠道和作用范围，并将“是否自动安装”放入最终确认单。

用户明确确认后运行：

```bash
python3 scripts/install_obsidian.py --install --confirmed
```

脚本优先降低操作难度：

- macOS：有 Homebrew 时使用 cask；否则从 Obsidian 官方 Release 下载 DMG，验证代码签名后安装到用户的 `~/Applications`，避免管理员密码。
- Windows：优先使用 `winget`；不可用时下载官方 EXE，验证 Authenticode 后静默安装。
- Linux：根据 CPU 架构下载官方 AppImage，安装到用户的 `~/.local/bin/obsidian`，不要求 root。

只允许 `https://obsidian.md/download` 所指向的 `obsidianmd/obsidian-releases` 官方 Release。不接受用户传入的镜像或任意下载地址。系统或 Agent 弹出权限确认时，请用户确认该次安装；不绕过操作系统安全机制。

官方来源：[Obsidian Download](https://obsidian.md/download)、[Download and install Obsidian](https://help.obsidian.md/install)。

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

- 未获用户确认时，不下载或安装 Obsidian 应用。
- 不覆盖 `app.json` 或 workspace 布局。
- 不关闭已有插件。
- 未选社区插件时，不改变 Restricted Mode 和社区插件列表。
