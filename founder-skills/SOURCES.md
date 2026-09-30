# 资料与兼容性说明

研究日期：2026-10-01（Asia/Shanghai）。人物资料只依据公开文章与官方整理的访谈，未获取私人资料或内部文档。

## 人物资料

逐条原文、发布日期、归因限制分别随安装目录保留：

- [CZ 来源表](skills/cz-strategy/references/sources.md)
- [何一来源表](skills/he-yi-growth/references/sources.md)

CZ 的决策影响、可逆性、专业判断、互利和责任边界有公开出处。何一的用户一线、透明、公平、带教和创业者能力筛选有公开出处。三方案表、实验卡、漏斗、指标和输出标签为本包的应用设计。

两套框架存在用户导向的共同部分；按“战略决策 / 用户运营”分工是为了任务路由，不推断二人全部人格，也不声称重建其私人思维。官方公司材料是公开自述，并非独立审计或收益验证。

## 平台与格式资料

| 文档 | 本包使用的部分 |
| --- | --- |
| [OpenAI Build skills](https://developers.openai.com/codex/skills/) | name / description、SKILL.md、引用目录、Codex 发现路径、显式调用 |
| [OpenClaw Skills](https://docs.openclaw.ai/tools/skills) | Agent Skills 格式、workspace / state 路径、优先级、allowlist、显式调用 |
| [OpenAI skill-creator](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-creator/SKILL.md) | 简洁核心指令、渐进读取、接口元数据、初始化与格式验证 |
| [openai.yaml 规范](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-creator/references/openai_yaml.md) | 显示名、25–64 字符简述、含显式 skill 名称的默认提示词 |

安装与发现可能随发行版本变化。使用用户手册中的自定义 root；不要把所有兼容路径同时写入配置。每个 SKILL.md 只含 name 与 description，OpenClaw 使用默认可调用行为；agents/openai.yaml 为 Codex UI 附加信息，不影响通用文本指令。

本包的日常安装与 validate 不需要第三方库或网络。只有开发校验从固定提交下载官方脚本，并用 PyYAML 检查真实 YAML；自动 CI 与本地安装分别记录，不能据 CI 推断真实宿主模型输出一致。

## 更新准则

每次更新先核对原文发布主体与日期，再更新来源表、版本和验收案例。不要保存网页完整副本，不把官方镜像计为独立证据，不将其他受访者发言误归因。对现任职位、用户规模、规则与行情在使用当时重新核实。
