---
name: crypto-signal-planner
description: Research and rank cryptocurrencies, recommend one non-duplicate candidate, and draft a sourced spot-only entry/exit/risk plan. Use when asked to 推荐一个币、再推荐一个、给币的操作方法, assess a coin such as RENDER, connect Gate API for market/account reads and Gate TestNet order tests, or generate an unattended live order proposal manifest; never autonomously trade real funds.
user-invocable: true
---

# Crypto Signal Planner (OpenClaw + Codex portable skill)

## Purpose and boundary
Produce **a verifiable research candidate and a conditional spot-trading plan**, never a guaranteed winner or an actual fill. This is an instruction skill with deterministic, local Python risk utilities. It can connect Gate API for live read-only data/account access, can submit spot limit orders to Gate TestNet, and can generate deterministic live order proposals/fingerprints. It does not submit real-money orders. Use the user's language (default Simplified Chinese). When invoked for a named coin, analyze it; when invoked for “再推荐一个”, avoid previously recommended names if conversation or state is available.

## Read on demand
- `references/market-evidence.md` for source priority, recency, token/network identity, and rejection criteria.
- `references/strategy-policy.md` for scoring, entry branches, risk limits, and post-signal tracking.
- `assets/response-template.md` for the final Chinese report.
- `references/gate-integration.md` for Gate API modes, credentials, and execution boundaries.
- `examples/render-case.md` for a **historical illustration only**, never a current quote.
- Use `{baseDir}/scripts/position_size.py` for deterministic sizing and R:R; `{baseDir}/scripts/validate_plan.py` to check a machine-readable plan when requested.

## Operating procedure
1. **Parse user intent.** Identify `recommend_new` or `analyze_symbol`, available risk budget, time horizon, spot-only default, jurisdiction/exchange if explicitly known, and exclusions. Use recent conversation and, if accessible, a persistent candidate history. Previously discussed SOL, SUI, LINK, AAVE, ONDO, and RENDER are *example exclusions only* when relevant; never claim they are the user's live holdings.
2. **Acquire current evidence** using available web/search/market tools. Verify source time in UTC and timezone. For quotes, prefer an exchange market page/API and independent price aggregator. Include current/last known market session and quote delay. If browsing/data tools aren't available, ask for a timestamped exchange quote or emit `RESEARCH_ONLY / NO_ACTION`; never borrow stale chat prices.
3. **Verify exact asset identity:** official project, ticker, chain, contract if on-chain, migration/wrapped versions, exchange's precise listed market. **RENDER is not the old RNDR ERC-20 token.** If identity cannot be verified, reject.
4. **Evidence checks:** price and 24h volume plus historical bars adequate for trend/volatility; spread/depth if available; dated official project developments; token supply and near-term unlocks if first-party/on-chain verified; security/regulatory dependencies; BTC and macro regime. Mark missing fields `unavailable`, never infer numeric values. Prefer two independent current price sources and flag >1% disagreement.
5. **Screen and rank** using the documented criteria. Do not force a buy candidate. Penalize duplication and portfolio concentration if holdings are known. Distinguish protocol product adoption from token holder value accrual; cite both positive and negative evidence. Don't claim technical patterns, RSI, moving averages, institutional flows, ETF approvals, or token unlock dates without data.
6. **Calculate the plan, not a forecast:** choose either a pullback setup *or* a breakout setup as the immediately active branch. Identify entry ranges from verified structure/ATR, invalidation/stop, two plausible targets from observed structure, reasoned holding horizon, and precise event conditions. Do not recycle example numbers. Calculate max units using the script. A candidate with no acceptable first-target net R:R (default >=2.0) becomes WATCH, not BUY. Initial default maximum trade risk = 0.5% of modeled equity and single speculative altcoin maximum allocation = 5%; apply stricter caps if user states them. If equity or entry/stop is unknown, express formulas instead of inventing sizes.
7. **Gate execution boundary:** `live-readonly` may read public market data and authenticated spot balances, but may only preview orders. `testnet` may submit spot limit orders to the official Gate TestNet host. For unattended live workflows, `{baseDir}/scripts/live_order_manifest.py` may generate an exact unsigned order proposal plus SHA-256 fingerprint, but no live private write request is allowed. Never expose or call a real-money order submission path. Read `references/gate-integration.md`.
8. **Separate 3 layers:** `research_state` (WATCH/REJECT/CONDITIONAL_WATCH_BUY), `model_signal` (WATCH_BUY/BUY_CANDIDATE/REDUCE_CANDIDATE/NO_ACTION), `execution_state` (NO_ORDER/PAPER_FILL_VERIFIED/REAL_FILL_VERIFIED). Without the relevant verified broker or paper ledger, always `NO_ORDER`, and report fills as `not verified`, not invented zero. Never move assets or claim a live fill without external verification.
9. **Produce user-facing report** using the template: source time, asset identity, 3 evidenced thesis points, countercase, live-data quality, concise table of *conditional* entry/stop/targets, deterministic risk-size example only when inputs exist, invalidation criteria, and status. Include citations or directly accessible source references supported by host tooling. An event-driven alert is only a *proposal* unless actually scheduled or installed.
10. **Optional machine-readable output:** create JSON using the fields in `examples/hypothetical-plan.json` (replace all hypothetical values) and run `python3 {baseDir}/scripts/validate_plan.py <file>`; fail closed if required evidence or R:R is absent. For a daily monitoring loop, compare latest persisted state with prior confirmed state; only emit changes, never assume a notifier or scheduler exists. If the user wants unattended live preparation, run the validated plan through `live_order_manifest.py` and stop at `PROPOSAL_ONLY`.

## Hard stops
- No fresh quote, conflicting symbol/chain, stale candles, unreliable unlock report, exchange restriction, unexplained spread/depth, adverse macro event, or insufficient reward-to-risk: `NO_ACTION / DATA_UNVERIFIED` as applicable.
- For highly volatile assets and correlated exposures, lower position size instead of implying diversification. No margin, perpetuals, lending, staking, auto-trading, or money transfers are part of this skill.
- Gate helpers may contact Gate for market/account reads; only Gate TestNet may receive an order submission. Live-money trading, withdrawals, transfers, margin, futures, borrowing, and staking remain unavailable.
- Do not convert historical RENDER prices from prior chats into today's signal.
