# Ingest 与人工审核

## 前置读取

读取 `知识库说明·WIKI.md`、`config.json`、`state.json`、`处理接续·HANDOFF.md` 和 `ingest-ledger.jsonl`。运行 `discover_sources.py`，按最早修改时间选择单轮 3—6 份。

## 每份来源的固定流程

1. 确认文件位于 Sources，计算 SHA-256。
2. 全文读取。长文可分块，但必须记录全部块已覆盖，不能用开头代替全文。
3. 提取作者、日期、场景、核心判断、边界、反例和敏感风险。
4. 与 Concepts、Methodologies、Inbox 和台账按核心判断查重，不能只比标题。
5. 只能选择一个结果：
   - `跳过·Skip`：无正文、无关、无法安全处理。
   - `保留原文·Preserve`：有参考价值，无独立净新知识。
   - `更新建议·Update`：补条件、反例、来源或修正；不直接改正式知识。
   - `候选草稿·Candidate`：有独立新判断、来源和边界。
6. Candidate 只写 Inbox，带 `status: candidate`、`source_path` 和 `source_sha256`。
7. 运行 `verify_run.py` 回读候选、校验来源全文哈希、追加单源 ledger，再更新 state。

## 长文覆盖证明

对超过 Agent 单次读取上限的文件，维护 coverage JSON：来源路径、全文哈希、总字节数，以及每块的起止字节与 SHA-256。只有无缺口覆盖 `[0, file_size)` 才能判定全文已读。超过 200000 字节时，`verify_run.py` 强制要求 `--coverage` 并逐块回读校验。来源哈希证明处理对象未变化，但不能替代语义上的全文阅读。

## 人工晋升

人工审核必须回答：是否独立、来源是否可靠、边界是否清楚、是否含敏感信息、应新建还是合并、是否需要过期。审核决定写入审核队列或日志，再由人授权修改正式知识。

不得把同一作者的两份材料当成两份独立验证；单一来源默认 `confidence: low`。
