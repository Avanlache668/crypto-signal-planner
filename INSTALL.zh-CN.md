# Crypto Signal Planner 双平台安装说明

仓库根目录的 `SKILL.md` 可以直接被 OpenClaw 从 GitHub 安装，也可以复制到 Codex 默认 Skills 目录。

## 1. GitHub 公开仓库发布后：OpenClaw

已填写连接的 GitHub 用户名：

```bash
openclaw skills install git:Avanlache668/crypto-signal-planner@main
openclaw skills info crypto-signal-planner
openclaw skills check
```

默认安装到活动 OpenClaw 工作区。若通过远程 Gateway 使用，确保安装到正确的 Gateway/Agent。

## 2. Codex

```bash
git clone https://github.com/Avanlache668/crypto-signal-planner.git
cd crypto-signal-planner
bash install.sh codex
python3 scripts/smoke_test.py
```

重新启动或刷新 Codex 会话，使用 `$crypto-signal-planner` 显式调用。

## 3. 同一台本地机器同时安装

```bash
bash install.sh shared
```

默认位置：`~/.agents/skills/crypto-signal-planner`。OpenClaw 仅在默认本地状态下兼容该路径；自定义状态、远程 Gateway 要单独安装：

```bash
bash install.sh openclaw        # 到 ~/.openclaw/skills/ 或 OPENCLAW_STATE_DIR/skills/
OPENCLAW_WORKSPACE=/path/to/workspace bash install.sh openclaw-workspace
```

安装器不会覆盖已有同名 Skill。安装完成后运行 `openclaw skills info crypto-signal-planner` 验证实际 Gateway 可见状态。

## 4. 调用案例

OpenClaw：`/crypto-signal-planner 再推荐一个币，避开 SOL、SUI、LINK、AAVE、ONDO 和 RENDER；不满足验证就 NO_ACTION。`

Codex：`$crypto-signal-planner 分析 RENDER 当前行情，并计算包含费用和滑点的单笔仓位风险。`

## 5. 离线自检

```bash
python3 scripts/smoke_test.py
python3 scripts/validate_plan.py examples/hypothetical-plan.json --allow-fixture
```

`PASS` 只证明本地计算与规则自检；不代表连通实时行情、完成回测或已真实下单。没有行情来源时，Skill 应只做研究，不提供执行信号。

## 6. 从本地副本发布

参见 `PUBLISH.md`。发布需你自己的 GitHub 登录授权。公共可见性不等于开源授权；本仓库尚未设定 LICENSE。
