# Crypto Signal Planner

A **portable OpenClaw / Codex Agent Skill** for researched cryptocurrency candidate selection, conditional spot-trading plans, and a guarded Gate API bridge.

> **Real-money autonomous trading is intentionally blocked.** The Gate integration supports live public/private **read-only** access plus order previews, and actual spot LIMIT order submission **only on Gate TestNet**. It does not expose live-money order, withdrawal, transfer, margin, futures, borrowing, or staking actions.

## Gate API modes

Gate API v4 separates live and TestNet endpoints. This repository uses two modes:

- `GATE_MODE=live-readonly`: ticker reads, authenticated spot-account reads, and order previews.
- `GATE_MODE=testnet`: the above plus spot LIMIT orders to the official TestNet host.

Copy the environment template locally and never commit credentials:

```bash
cp .env.example .env
# export values from your local secret manager or shell; do not commit .env
```

Examples:

```bash
# Public ticker (no credentials required)
python3 scripts/gate_client.py ticker BTC_USDT

# Private spot balances (requires API key/secret; live-readonly is fine)
export GATE_MODE=live-readonly
export GATE_API_KEY='...'
export GATE_API_SECRET='...'
python3 scripts/gate_client.py balances --currency USDT

# Preview only: never submits anything
python3 scripts/gate_client.py preview BTC_USDT buy 0.001 50000

# TestNet only: actual TestNet LIMIT order
export GATE_MODE=testnet
export GATE_HOST=https://api-testnet.gateapi.io
python3 scripts/gate_client.py testnet-order BTC_USDT buy 0.001 50000
```

For a validated plan JSON, `auto_testnet_runner.py` can size and submit a TestNet order:

```bash
python3 scripts/auto_testnet_runner.py /path/to/verified-plan.json           # preview
python3 scripts/auto_testnet_runner.py /path/to/verified-plan.json --execute # TestNet only
```

The runner refuses live mode and non-official TestNet hosts.

## Unattended live pre-trade pipeline

If you want the system to run unattended against live **read-only** data, use `live_order_manifest.py`. It validates a verified plan, calculates the bounded spot position size, builds the exact LIMIT-order proposal, and emits a SHA-256 fingerprint for audit/review. It does **not** sign or submit a live write request.

```bash
python3 scripts/live_order_manifest.py /path/to/verified-plan.json \
  --output /path/to/order-proposal.json
```

The resulting manifest is explicitly marked `PROPOSAL_ONLY` and `live_submission_available=false`. This is the closest supported path to unattended live operation: everything through order construction can be automated; real-money execution remains outside this repository.

## Install directly from GitHub

### OpenClaw

```bash
openclaw skills install git:Avanlache668/crypto-signal-planner@main
openclaw skills info crypto-signal-planner
openclaw skills check
```

### Codex

```bash
git clone https://github.com/Avanlache668/crypto-signal-planner.git
cd crypto-signal-planner
bash install.sh codex
python3 scripts/smoke_test.py
python3 scripts/test_gate_client.py
```

### Same local machine, both systems

```bash
bash install.sh shared
```

## Contents

| File | Purpose |
|---|---|
| `SKILL.md` | Main portable skill instructions |
| `references/market-evidence.md` | Quote freshness, source and identity checks |
| `references/strategy-policy.md` | Ranking and risk rules |
| `references/gate-integration.md` | Gate modes, credentials, execution boundaries |
| `scripts/gate_client.py` | Gate API v4 safe bridge |
| `scripts/auto_testnet_runner.py` | Validated-plan → Gate TestNet spot LIMIT order |
| `scripts/live_order_manifest.py` | Validated-plan → deterministic live order proposal/fingerprint; no submission |
| `scripts/test_gate_client.py` | Offline Gate signing and safety-guard tests |
| `scripts/position_size.py` | Deterministic spot-long sizing and R:R |
| `scripts/validate_plan.py` | Candidate-plan validation |
| `.env.example` | Non-secret Gate configuration template |
| `.github/workflows/ci.yml` | Offline regression checks |

## Security rules

- Never paste or commit API secrets.
- Prefer a dedicated API key with the minimum permissions needed.
- Use Gate's IP whitelist where practical.
- Keep real-money trading outside this skill and behind a user-controlled execution step.
- TestNet success is not evidence of profitability or live execution safety.

Gate API v4 private requests use `KEY`, `Timestamp`, and an HMAC-SHA512 `SIGN`; Gate states that the timestamp gap cannot exceed 60 seconds and supports per-key permission groups and IP whitelists. See the official Gate API v4 documentation.

This is analytical and testing tooling, not personalized investment advice. Cryptocurrency can lose substantial value.
