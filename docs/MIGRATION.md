# V2 兼容迁移

V2 包位于 `trading_os/`，不替换现有脚本。旧的 Skill、安装命令、计划 JSON、Gate CLI、TestNet runner、Live Manifest schema 与 SHA-256 算法保持原样。

迁移顺序：

1. 继续用旧 `validate_plan.py` 接受公开字段。
2. 新工作流用 `python -m trading_os.cli research` 产生 V2 研究对象。
3. 用 PAPER 和 replay 验证账本，再独立评审 TestNet 接入。
4. LIVE_PROPOSAL v2 与旧 manifest v1 并存，不改变旧指纹。

旧数据不能被直接认作 V2 成交。导入时必须标明来源、模式和 schema，缺失身份、时间、费用或成交 ID 时进入争议/研究状态。
