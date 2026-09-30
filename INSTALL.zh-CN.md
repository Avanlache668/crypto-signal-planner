# Crypto Signal Planner 安装与 Gate API 联调说明

## 1. 安装 Skill

```bash
git clone https://github.com/Avanlache668/crypto-signal-planner.git
cd crypto-signal-planner
bash install.sh shared
```

仅 Codex：

```bash
bash install.sh codex
```

仅 OpenClaw：

```bash
bash install.sh openclaw
```

## 2. Gate API 配置

不要把 API Key/Secret 发到聊天、提交到 GitHub 或写入示例文件。

```bash
cp .env.example .env
```

推荐先使用：

```bash
export GATE_MODE=live-readonly
export GATE_API_KEY='你的本地Key'
export GATE_API_SECRET='你的本地Secret'
```

`live-readonly` 只允许：行情读取、现货账户读取、订单预览；真实资金下单路径被代码硬性阻断。

## 3. 测试行情和账户读取

```bash
python3 scripts/gate_client.py ticker BTC_USDT
python3 scripts/gate_client.py balances --currency USDT
```

## 4. 订单预览

```bash
python3 scripts/gate_client.py preview BTC_USDT buy 0.001 50000
```

只生成订单 JSON，不提交。

## 5. Gate TestNet 自动下单

为 TestNet 创建单独的 API 凭证，然后：

```bash
export GATE_MODE=testnet
export GATE_HOST=https://api-testnet.gateapi.io
export GATE_API_KEY='TestNet Key'
export GATE_API_SECRET='TestNet Secret'

python3 scripts/gate_client.py testnet-order BTC_USDT buy 0.001 50000
```

或者使用经过 `validate_plan.py` 验证的计划：

```bash
python3 scripts/auto_testnet_runner.py verified-plan.json
python3 scripts/auto_testnet_runner.py verified-plan.json --execute
```

第二条命令只会提交到官方 Gate TestNet。若 `GATE_MODE` 不是 `testnet`，程序直接拒绝。

## 6. 安全建议

- API Key 使用最小权限。
- 能设置 IP 白名单时启用。
- 不开启提现/转账权限。
- 不把真实资金交易交给无人值守代理。
- TestNet 下单成功不代表策略有收益能力。
