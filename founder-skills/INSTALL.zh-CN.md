# 安装操作说明书 · v1.0.0

本说明针对两个独立 skill：`cz-strategy` 与 `he-yi-growth`。同一份 Agent Skills 文件可由 Codex 与 OpenClaw 读取，不需要维护四份不同提示词。

## 1. 准备

- 已有可用的 Codex 或 OpenClaw；模型、账号及宿主配置由使用者自行维护。
- 推荐 Git 和 Python 3.10+。安装工具仅使用 Python 标准库。
- 若使用 Docker、远程 Gateway 或另一台电脑，安装路径必须位于真正运行宿主的机器，并在需要时挂载到容器。
- 不需要币安 API Key、钱包私钥或助记词。

官方文档核对日期：2026-10-01（北京时间）。发行版本和 profile 配置可能改变发现路径，可用自定义 `--root` 指定。

## 2. 下载

macOS / Linux：

```bash
git clone https://github.com/Avanlache668/crypto-signal-planner.git
cd crypto-signal-planner/founder-skills
python3 --version
python3 manage.py validate
```

Windows PowerShell：

```powershell
git clone https://github.com/Avanlache668/crypto-signal-planner.git
Set-Location crypto-signal-planner/founder-skills
py -3 --version
py -3 manage.py validate
```

如果已克隆，进入现有仓库后用 `git pull --ff-only` 更新，再进入 `founder-skills`。如无 Git，在仓库页面选择 Code → Download ZIP，解压后进入 `founder-skills`。

`validate` 成功应返回 `"valid": true` 与两个名称。它检查结构，未启动宿主或调用模型。

## 3. 用户级安装

先预览：

```bash
python3 manage.py install --target both --dry-run
```

执行：

```bash
python3 manage.py install --target both
```

选择平台或其中一个：

```bash
python3 manage.py install --target codex
python3 manage.py install --target openclaw
python3 manage.py install --target codex --skill cz-strategy
python3 manage.py install --target openclaw --skill he-yi-growth
```

Windows 使用同样参数，把开头 `python3` 换成 `py -3`。

| 目标 | 默认目的根目录 | 安装后的文件示例 |
| --- | --- | --- |
| Codex | `~/.agents/skills` | `~/.agents/skills/cz-strategy/SKILL.md` |
| OpenClaw 默认 state | `~/.openclaw/skills` | `~/.openclaw/skills/he-yi-growth/SKILL.md` |
| OpenClaw 设置 OPENCLAW_STATE_DIR | `<OPENCLAW_STATE_DIR>/skills` | 当前 state 目录下的对应 skill |
| OpenClaw profile 或自定义路径 | 用 `--root` 明确指定 | 以宿主当前 profile 为准 |

安装工具不读取或改写宿主配置。设置了 `OPENCLAW_PROFILE` 而未提供 state 路径时，它要求明确 `--root`，避免装到错误 profile。若 profile 只通过 CLI 参数选择，也请显式提供路径。

## 4. 项目级或自定义路径

将两个 skill 安装到指定工作区：

```bash
python3 manage.py install --target both --scope project --workspace /absolute/path/to/project
```

- Codex 目的目录是该项目的 `.agents/skills`；从该项目目录启动 Codex。
- OpenClaw 目的目录是该工作区的 `skills`；确认它是当前 agent 配置的工作区。

自定义单个平台的根目录：

```bash
python3 manage.py install --target openclaw --root /absolute/path/to/active-state/skills
python3 manage.py install --target codex --root /absolute/path/to/codex-skill-root
```

`--root` 是包含两个 skill 文件夹的目录，不是 `SKILL.md` 文件路径，且必须选择单个平台。某些旧版 Codex 使用 `~/.codex/skills` 或 `$CODEX_HOME/skills`；只有确认该版本实际扫描此路径后才将它作为 `--root`，不要同时安装到多处制造同名条目。

路径含空格时用双引号；Windows 可使用 `--workspace "C:\Users\YourName\My Project"`。

## 5. 无 Python 的手动安装

将完整 `skills/cz-strategy` 与 `skills/he-yi-growth` 文件夹复制到上表中宿主实际使用的根目录。必须保留 `references` 与 `agents`，并保证目录名与 frontmatter 的 name 相同。

不要只复制两个 `SKILL.md`，也不要把 `founder-skills` 整个包作为单个 skill。确认目标没有同名旧目录；有旧版时先把它移到根目录之外备份，避免复制时多嵌套一层。

## 6. 在宿主中发现与调用

Codex：

1. 打开新一轮对话；如果列表没有刷新，重新启动 Codex。
2. 在 CLI / IDE 对话输入框输入 `/skills` 或 `$`，查找 `cz-strategy`、`he-yi-growth`。
3. 粘贴下面提示词。

OpenClaw：

1. 检查 `openclaw skills list` 和 `openclaw skills check`。
2. 新建对话或刷新当前 skill 快照；较新 UI 的 `$` 选择器可直接选择。
3. 使用下面的 `$skill-name`。仅支持 slash command 的旧版可用 `/cz-strategy` 与 `/he-yi-growth`，具体以该版本 `--help` 为准。

以下是发给模型的文本，不是 shell 命令：

```text
使用 $cz-strategy。我们有 3 人团队、14 天验证窗口，正在做加密研究产品。请比较三个方案，区分事实与假设，给出负责人、资源上限、验证指标与停止条件。
```

```text
使用 $he-yi-growth。我们有 1000 个注册用户、100 个激活用户，D7 留存口径尚未明确。请先指出数据缺口，再设计用户访谈、客服闭环和两个增长实验。
```

组合调用：

```text
先使用 $cz-strategy 评估商业战略，再使用 $he-yi-growth 制作用户与增长计划。共用同一份事实清单，把人物公开主张与本次分析推断分开。
```

技能描述允许宿主按问题自动匹配；显式调用更方便确认是否用了指定框架。不要据调用名称认为模型已成为本人。

## 7. 更新、备份与回滚

先更新仓库，再预览：

```bash
git pull --ff-only
python3 manage.py validate
python3 manage.py install --target both --replace --dry-run
python3 manage.py install --target both --replace
```

完全相同的内容返回 `unchanged`。不同内容默认报错；`--replace` 会先复制并检查新版本，再把原目录移动到 skill 根目录的同级 `founder-skills-backups` 中，输出精确 backup 路径，之后安装新版本。

单个 skill 更新失败时工具尝试恢复它的旧目录；整个多 skill / 多平台安装不保证全局事务，先前已经成功的安装仍会保留。查看输出核对每个目标。

回滚：结束使用中的会话，将当前同名目录移到 skill 根目录之外，再将输出所列备份目录复制或移动回原位置，恢复原名；随后刷新宿主。不要把备份放在发现根目录下，否则会出现重复 skill。

卸载：将需要卸载的对应 skill 文件夹移出宿主 skill 根目录，再刷新。无须删除任何密钥或修改其他 skill。

## 8. 排错与验收

| 现象 | 检查及处理 |
| --- | --- |
| 找不到 skill | 确认真实运行机器、scope、工作区与 profile；检查是否嵌套成两层；开启新对话 |
| OpenClaw list 有但当前 agent 不能用 | 检查该 agent 的 skill allowlist 与同名优先级；不自动覆盖配置 |
| Codex 出现重复名称 | 保留一个有效发现目录中的版本，将其余同名目录移出发现根目录 |
| Existing skill differs | 先查看旧目录；需要更新时使用 `--replace` 保存备份 |
| 权限或只读目录错误 | 选择当前用户可写、且宿主会扫描的根目录；无需管理员权限即可用户级安装 |
| 当前价格或项目数据缺失 | skill 不附带行情工具；宿主有搜索工具则核实，无工具则输出取证计划 |
| 回答像泛泛名言 | 显式调用并提供业务输入；用 [验收表](evals/acceptance.md) 检查结构与具体取舍 |
| 认为安装后能自动下真单 | 本包仅提供分析指令；交易能力与明确授权不由 skill 安装产生 |

验收至少确认：能发现两个独立名称、能读完整引用、能区分来源与推断、缺少实时数据不伪造、每次建议有验证或复盘条件。自动结构测试不能代替真实宿主的回答验收。

## 9. 可复现打包与开发检查

```bash
python3 manage.py package --output /absolute/path/founder-skills-v1.0.0.zip
python3 -m unittest discover -s tests -v
```

ZIP 包含完整两份 skill、安装工具及说明，不含其他仓库内容或本机配置。已有同名 ZIP 时工具拒绝覆盖。开发用官方校验另外需要 PyYAML 与网络：

```bash
python3 -m pip install PyYAML==6.0.2
python3 tools/check_official_creator.py
```

`check_official_creator.py` 会在临时目录下载 manifest 锁定提交的官方 creator 脚本，实际初始化两份临时模板、比较生成的接口文件并运行官方格式校验；不改变已安装 skill。
