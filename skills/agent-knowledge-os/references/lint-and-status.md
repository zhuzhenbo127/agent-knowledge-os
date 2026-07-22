# Lint 与状态维护

运行：

```bash
python3 scripts/lint_vault.py --vault "/absolute/vault/path" --json
```

检查项：固定目录、配置完整、占位符、UTF-8 和跨平台路径、候选越层、来源缺失/漂移、过期与到期复查、未解析双链和可能孤岛。

Lint 是只读诊断：

- `error`：架构或安全铁律被破坏，需要处理后再继续写入。
- `warning`：过期、断链、来源变化或孤岛，需要人工判断。

不得让 lint 自动删除、晋升、补写来源或解决冲突。修复后重新运行，用报告差异证明问题消失。
