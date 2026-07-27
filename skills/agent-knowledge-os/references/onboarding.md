# 八步引导式个性化

## 对话规则

- 每次只问一个问题，给 3—6 个常见选项并允许自由描述。
- 新库走完整引导；旧库先运行 `scan_existing_vault.py`，不重复询问已发现且无冲突的信息。
- 目标为 5—8 分钟，不在初次引导展开高级 Schema 设计。
- 收集阶段只在聊天和临时文件工作，不写正式 Vault。
- 最后展示确认单；只有明确确认后才运行 `bootstrap.py --confirmed`。
- 中断时将 onboarding 视为未完成，不产生“看似完成”的配置。

## 八步

1. **身份**：库名、作者称呼、一句话目标。
2. **首要任务**：最多三个；内容创作、研究、决策、产品业务、项目复盘或自定义。
3. **长期领域**：3—7 个；排除一次性项目。为每个领域确认中文名和简短英文别名。
4. **来源类型**：个人表达、文章书籍、用户问题、会议访谈、项目资料、案例数据或自定义。
5. **资产类型**：概念和方法论必选；案例、模板、表达规则、决策可选。
6. **复查与过期**：默认周期、必须过期的类型、长期保留的第一方经验。
7. **隐私与 AI**：脱敏类型、只读目录、客户/聊天/账号/密钥、AI 写入范围。
8. **Obsidian**：先运行 `install_obsidian.py --check`。已安装则不追问；未安装时询问是否授权自动安装。再分别确认 Dataview、Templater；安装应用的授权不包含社区插件。

`obsidian.app` 记录选择：已安装为 `use_existing`，授权补装为 `install_if_missing`，明确不使用为 `skip`。

## 确认单

确认单必须列出：目标路径、模式、新建/保留目录、身份、任务、领域、来源、资产、复查、隐私、Obsidian 检测结果、安装策略与作用范围、社区插件选择、不会执行的动作。结尾明确询问是否确认。这一次确认可同时授权创建 Vault 和安装 Obsidian，避免重复询问。

用户确认后，如配置为 `install_if_missing`，先运行：

```bash
python3 scripts/install_obsidian.py --install --confirmed
```

安装失败时报告具体原因与官方下载地址，仍可继续生成 Markdown 知识库；不把 Obsidian 安装失败伪装成全流程成功。

## 配置输入示例

```json
{
  "profile": {
    "vault_name": "我的知识操作系统",
    "owner": "作者",
    "purpose": "支持研究与内容创作",
    "primary_workflows": ["内容创作", "学习研究"],
    "domains": [
      {"name_zh": "人工智能", "name_en": "AI"},
      {"name_zh": "内容系统", "name_en": "Content"},
      {"name_zh": "个人业务", "name_en": "Business"}
    ],
    "source_types": ["个人表达", "文章和书籍", "用户问题"],
    "asset_types": ["概念", "方法论", "案例", "模板"],
    "review_policy": {"default_days": 180, "tool_days": 60, "platform_rule_days": 30},
    "privacy_policy": {"redact": ["客户资料", "私人聊天", "密钥"], "read_only_paths": [], "ai_write_requires_confirmation": true},
    "obsidian": {"app": "install_if_missing", "enable_core_plugins": true, "community_packs": []}
  }
}
```

## 再次个性化

先 dry-run 展示字段差异与迁移计划。确认后只更新配置、章程和相关模板；不自动创建、重命名或移动领域目录。备份必须先于写入，修改记录必须可回读。
