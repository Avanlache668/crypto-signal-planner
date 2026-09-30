# Crypto Signal Planner

A **portable OpenClaw / Codex Agent Skill** for researched cryptocurrency candidate selection and *conditional spot-only trading plans*. It checks for duplicate recommendations, current quotes, exact coin/network identity, documented catalysts, token-supply risk, and risk-adjusted trade sizing. RENDER is a **historical illustration**, not a live recommendation.

> **No autonomous trading.** The skill does not fetch market data by itself, connect an exchange, submit orders, guarantee returns, or claim simulated/real fills. A host agent needs its own approved web or market data tools. If data cannot be verified, the skill returns `NO_ACTION`.

## Install directly from GitHub

### OpenClaw

Git-install when this repository is published (for the connected GitHub account):

```bash
openclaw skills install git:Avanlache668/crypto-signal-planner@main
openclaw skills info crypto-signal-planner
openclaw skills check
```

OpenClaw Git installation requires `SKILL.md` at the repository root, as provided here. For remote Gateways, run against the intended agent/Gateway. [OpenClaw skills docs](https://docs.openclaw.ai/cli/skills).

### Codex

```bash
git clone https://github.com/Avanlache668/crypto-signal-planner.git
cd crypto-signal-planner
bash install.sh codex
python3 scripts/smoke_test.py
```

Default target: `~/.agents/skills/crypto-signal-planner`. Restart the Codex session if needed; then use `$crypto-signal-planner` or `/skills`.

### Same local machine, both systems

```bash
bash install.sh shared
```

OpenClaw uses `~/.agents/skills` **only with its default local state**. For a custom or remote OpenClaw Gateway, install separately into the actual agent's workspace:

```bash
OPENCLAW_WORKSPACE=/path/to/your/agent/workspace bash install.sh openclaw-workspace
```

The installer refuses to overwrite an existing skill installation and copies only required skill files. See [中文安装说明](INSTALL.zh-CN.md).

## Contents

| File | Purpose |
|---|---|
| `SKILL.md` | Main portable skill instructions |
| `references/market-evidence.md` | Quote freshness, source and identity checks |
| `references/strategy-policy.md` | Ranking, two entry branches and risk rules |
| `assets/response-template.md` | Chinese report template |
| `scripts/position_size.py` | Deterministic spot-long sizing and first-target after-cost risk/reward |
| `scripts/validate_plan.py` | Structural validation and source timestamp checks; **cannot authenticate source claims** |
| `scripts/smoke_test.py` | Offline regression tests |
| `examples/` | Hypothetical and historical examples |
| `install.sh` | Safe local installer |
| `publish_github.sh` | Owner-run one-time public publishing helper |

## Offline validation

Python 3.9+; no packages or API keys required:

```bash
python3 scripts/smoke_test.py
python3 scripts/position_size.py \
  --equity 100000 --entry 10 --stop 9 --target 12.3 \
  --risk-pct 0.005 --allocation-pct 0.05
python3 scripts/validate_plan.py examples/hypothetical-plan.json --allow-fixture
```

`--allow-fixture` is **only** for offline example checks. PASS is not a backtest, live quote verification, profitable strategy proof, order, or simulated fill.

## Invoke

**OpenClaw:** `/crypto-signal-planner 推荐一个没有重复的现货币种，核验行情并给条件交易计划`

**Codex:** `$crypto-signal-planner Research a new spot crypto candidate with two verified quote sources; calculate after-cost sizing or return NO_ACTION.`

## Publishing and license

To create a **new public** GitHub repository from an extracted copy, see [publishing instructions](PUBLISH.md). **This repository currently does not grant a reuse or redistribution license**; being public on GitHub is not equivalent to open-source licensing. The owner may add a LICENSE later.

This is analytical tooling, not personalized investment advice. Stop orders may experience slippage, and cryptocurrency can lose substantial value.
