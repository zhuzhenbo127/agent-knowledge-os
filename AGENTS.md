# Agent Knowledge OS Repository Instructions

## Installation intent

When a user provides this repository URL and explicitly asks to **install**, **use**, **enable**, or **set up** Agent Knowledge OS, treat that as authorization to install the repository's `agent-knowledge-os` Skill for the current Agent.

A bare URL without installation intent is not authorization to change the user's environment. Ask one concise question: “要我安装并使用这个 Skill 吗？”

Do not run this installation protocol when the user asks to review, modify, audit, fork, or contribute to the repository.

## Preferred installation

1. Prefer the current Agent's native GitHub Skill installer when available.
2. Otherwise detect the current Agent identifier and run the compatible Agent Skills installer non-interactively:

```bash
npx --yes skills@latest add https://github.com/zhuzhenbo127/agent-knowledge-os --skill agent-knowledge-os -g -a <current-agent> -y
```

Common identifiers:

- Codex: `codex`
- Claude Code: `claude-code`
- Cursor: `cursor`

3. If `npx skills` does not support the current Agent, clone the public repository and copy `skills/agent-knowledge-os/` into that Agent's documented global Skills directory.
4. Do not ask the user to log in to GitHub. This is a public repository and supports anonymous Git reads.
5. Do not request GitHub `repo` or `workflow` permissions for installation. Those permissions are only for repository maintainers.
6. Do not install Obsidian itself. Community Obsidian plugins remain optional and require the user's explicit choice during onboarding.

If the Agent's security policy requires approval before global installation or command execution, show the exact action and request that single required approval. Do not claim to have bypassed it.

## Verification

After installation:

1. Confirm the installed folder contains `SKILL.md`, `references/`, `scripts/`, and `assets/`.
2. Confirm `SKILL.md` frontmatter contains `name: agent-knowledge-os`.
3. Report the installed scope and Agent target.
4. Immediately invoke the Skill and begin with:

> 使用 `agent-knowledge-os` 帮我搭建知识库。先完成引导，在我确认设置前不要写入文件。

5. Ask only the first onboarding question. Do not dump all eight questions at once.

## Safe fallback

If installation cannot complete, explain the missing capability precisely: native Skill support, Node/npx, Git, filesystem permission, or command approval. Do not replace installation with a generic summary of the repository.
