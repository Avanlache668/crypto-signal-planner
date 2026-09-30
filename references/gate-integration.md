# Gate API integration policy

This repository integrates Gate API v4 with a hard separation between data access and order execution.

## Supported modes

### `live-readonly`
- Public market data reads.
- Authenticated spot-account balance reads.
- Deterministic order payload previews.
- **No live-money POST/DELETE trading endpoints are exposed.**

### `testnet`
- Uses the official Gate TestNet REST host: `https://api-testnet.gateapi.io/api/v4`.
- Can submit **spot limit orders only** through `scripts/gate_client.py` and `scripts/auto_testnet_runner.py`.
- No margin, futures, borrowing, withdrawals, transfers, earn products, or live-money execution.

## Credentials

Keep `GATE_API_KEY` and `GATE_API_SECRET` in the local environment or a secret manager. Never paste them into prompts, source files, GitHub issues, logs, or examples. Use the minimum permissions required and Gate's IP whitelist where practical.

## Workflow

1. Generate and validate a candidate plan.
2. Run a local order preview.
3. Test against Gate TestNet.
4. Inspect returned order data and reconciliation logs.
5. For real-money execution, keep a human-in-the-loop outside this skill.

The signing implementation follows Gate API v4: uppercase method, request path, query string, SHA-512 payload hash, timestamp, then HMAC-SHA512 with the API secret.
