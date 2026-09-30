# Binance Founders Public Methods · v1.0.0

两个分别安装、可组合调用的中文 Agent Skills，兼容 OpenClaw 和 Codex。

| Skill | 提炼对象 | 适用任务 | 主要输出 |
| --- | --- | --- | --- |
| [cz-strategy](skills/cz-strategy/SKILL.md) | 赵长鹏（CZ） | 商业战略、产品取舍、项目研究、合作、复盘 | 决策备忘录、风险条件、最小验证计划 |
| [he-yi-growth](skills/he-yi-growth/SKILL.md) | 何一（Yi He） | 用户增长、客服、品牌、组织、创业者评估 | 用户漏斗、反馈闭环、实验卡、分工与带教 |

“蒸馏”指依据公开资料提炼知识与工作流程；没有训练模型权重。该项目独立、非官方，没有本人或币安背书。两份 skill 保持助手身份，区分事实、来源观点与推断。

## 安装

需要 Git 与 Python 3.10+。用户必须已有可用的 Codex 或 OpenClaw 宿主；安装 skill 不安装模型或提供 API 服务。

```bash
git clone https://github.com/Avanlache668/crypto-signal-planner.git
cd crypto-signal-planner/founder-skills
python3 manage.py validate
python3 manage.py install --target both
```

分别安装：

```bash
python3 manage.py install --target codex --skill cz-strategy
python3 manage.py install --target openclaw --skill he-yi-growth
```

Windows 将 `python3` 换成 `py -3`。无需交易所 API Key；安装工具只在本地复制两个 skill 目录，不进行网络请求。详见 [中文安装操作说明书](INSTALL.zh-CN.md)，包括项目级安装、profile 路径、无 Python 手动安装、更新与回滚。

## 调用

在 Codex / OpenClaw 的对话输入框中输入，勿直接粘贴到 shell：

```text
使用 $cz-strategy 评估这个加密产品的商业战略与风险，给出有预算上限和停止条件的验证计划。
使用 $he-yi-growth 分析用户激活和留存瓶颈，输出客服闭环、增长实验与团队分工。
先使用 $cz-strategy 做战略判断，再使用 $he-yi-growth 做用户与运营计划。分别标明事实、来源观点和推断。
```

独立使用不要求安装另一个 skill。组合调用也是单个助手按顺序应用两个框架。

## 来源与验证

研究截至 2026-10-01（北京时间），涵盖 2022–2026 年公开文章与访谈。每个 skill 自带来源表、应用手册与示例；不收录未经核实的普通用户转述，也不复制长篇原文。

- [来源与兼容性说明](SOURCES.md)
- [语义验收案例及人工评估表](evals/acceptance.md)
- [自动验证工作流](https://github.com/Avanlache668/crypto-signal-planner/actions/workflows/founder-skills.yml)

自动检查验证目录、引用、接口元数据、安装备份、幂等与 ZIP 内容，并运行固定版本官方 skill-creator 的初始化、元数据生成及格式校验。它们不等于已经在每台机器的真实宿主中验证模型行为；最终发现与回答质量按操作手册和语义案例验收。

## 目录

| 路径 | 内容 |
| --- | --- |
| skills/cz-strategy/ | CZ skill 及独立参考材料 |
| skills/he-yi-growth/ | 何一 skill 及独立参考材料 |
| manage.py | 标准库安装、验证、打包工具 |
| INSTALL.zh-CN.md | 用户操作手册 |
| evals/acceptance.md | 触发与回答质量验收 |
| tests/ | 安装工具的隔离临时目录测试 |
| tools/check_official_creator.py | 固定上游版本的开发校验 |
| manifest.json | 版本、来源检索日期、平台路径 |
| LICENSE | 本目录原创代码与文字的 MIT 许可 |

该许可不覆盖第三方原文、商标或肖像。此目录与仓库原有 crypto-signal-planner skill 分开安装。
