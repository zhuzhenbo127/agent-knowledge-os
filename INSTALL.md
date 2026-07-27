# 把这个链接发给 Agent，它会完成安装

客户不需要打开 GitHub，不需要注册 GitHub，也不需要自己输入终端命令。

只需把下面这句话原样发给支持 Agent Skills 的 Agent：

> 安装并使用这个 Skill：https://github.com/zhuzhenbo127/agent-knowledge-os

Agent 应该自动完成：

1. 识别这是一个公开的 Agent Skills 仓库。
2. 使用原生 Skill 安装器，或调用通用 `npx skills` 安装器。
3. 把 `agent-knowledge-os` 安装到当前 Agent 的全局 Skills 目录。
4. 检查 `SKILL.md` 和配套资源是否完整。
5. 报告安装结果。
6. 自动开始知识库八步引导，每次只问一个问题。

引导的 Obsidian 步骤会先自动检测应用。如果电脑没有安装，Agent 会在最终设置确认单中说明安装渠道和范围；客户确认一次后，Agent 自动完成安装。系统自身仍可能弹出一次安全确认。

## 客户会不会遇到 GitHub 双重验证

不会。安装使用公开仓库的匿名读取能力，不需要 GitHub 账号。

仓库维护者在创建仓库、推送代码或上传 GitHub Actions 时可能需要双重验证，这和客户安装无关。

## 为什么不能只发一个裸链接

裸链接没有说明用户想做什么。有些 Agent 会打开网页或总结仓库，而不是修改本机环境。

因此最短可靠表达是：

> 安装这个 Skill：仓库地址

“安装”两个字用于给 Agent 明确授权，仓库内的 `AGENTS.md` 会告诉 Agent 后续安装和验证步骤。

## 可能出现的一次确认

部分 Agent 会在执行全局安装或终端命令前弹出安全确认。客户只需确认这一次操作。

这是 Agent 自身的安全策略，公开仓库无法也不应该绕过。它不是 GitHub 登录，也不是双重验证。

## Agent 没有自动安装怎么办

让客户补发：

> 不要总结网页。请按照仓库根目录的 `AGENTS.md` 安装 `agent-knowledge-os`，验证成功后立即开始首次引导。

如果 Agent 仍然无法安装，通常表示它不支持 Skills、不能运行 Git/终端命令，或没有文件写入权限。此时需要换到支持 Agent Skills 和 GitHub 拉取的客户端。

## 手工安装只作为备用

面向技术用户或 Agent 无法自动执行时，才使用：

```bash
npx --yes skills@latest add https://github.com/zhuzhenbo127/agent-knowledge-os --skill agent-knowledge-os -g -y
```

普通客户不需要自己运行这条命令。
