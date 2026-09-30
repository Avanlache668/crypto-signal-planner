# Screening, planning, and tracking policy

## Candidate ranking (research heuristic; not a trained model)
100-point scoring: credible spot liquidity (25), defensible trend/momentum from actual candles (20), fundamentals + concrete near-term official catalyst (15), supply/security and token value capture (15), BTC/macro regime resilience (10), risk/reward and entry-quality (15). Publish factors and missing-data penalties; never present this as historical edge or validated prediction. Require >=70 for conditional candidate **and** pass all identity/evidence/risk gates. Otherwise WATCH/NO_ACTION. Select one strong candidate rather than force a new ticker.

## Two mutually exclusive active entry branches
- Pullback: wait for documented support/ATR-informed zone; trigger only on observable reclaim, volume and BTC context. A lower zone is **not an automatic averaging-down order**. Re-evaluate after support fails.
- Breakout: wait for a *closed daily candle* above documented resistance, acceptable spot volume and successful retest or follow-through. Do not chase a vertical breakout into bad R:R.
- Historical example ratios such as 40/30/30 are just **maximum intended allocation of the planned trade**, not three resting orders. If both branches become possible, choose one and recompute total portfolio exposure; never double the budget.

## Position sizing and risk
For a long spot scenario with entry E, stop S < E, capital C, max trade risk r and max asset allocation a:
- Risk cap = C*r; risk-based units = (C*r)/(E-S)
- Allocation cap = C*a; allocation-based units = (C*a)/E
- Suggested cap = min(units), rounded DOWN to supported quantity step.
- Realistically include fees, slippage and gap risk; a trigger/stop is not guaranteed fill. Use `{baseDir}/scripts/position_size.py` to calculate both price-only and fee-adjusted risk/reward and cap size. Default r=0.005 and a=0.05 when not otherwise specified. For large volatility, choose a lower limit.
- Default first target net reward/risk >=2; if not, wait, improve entry, or reject. Do not overfit target simply to reach 2R.
- STOP is a planned risk exit, not guaranteed protection in gaps/illiquid markets.

## Risk state and macro overlay
Caution or block newly proposed risk on BTC sell-off, extreme altcoin funding/OI spikes, unlock uncertainty, widened spreads, major policy event, abnormal USD/yields/risk-off, or data degradation. Do not turn speculative comments about macro into numeric thresholds without source-backed levels.

## Monitoring / dedup
State machine: RESEARCH_ONLY -> WATCH -> CONDITIONAL_WATCH_BUY -> BUY_CANDIDATE, or -> DEFENSIVE / REJECT when invalidated. Separate state from order/fill.
Persist state if host workspace grants file writes. For each candidate, dedup on `(symbol, chain, market_pair, research_state, model_signal, risk_state, evidence_window)`; emit only novel material state transitions, verified paper fills, or user-set threshold crossings. Re-evaluate all previously published price zones using current data rather than treating them as eternal.

## Honest outcomes
Without connected account, never claim real position or real fill. Without a saved paper trade ledger, do not declare paper fill. Without scheduler/notification setup, don't claim the user will be alerted later. Cite or show retrieval metadata for each market-moving catalyst. A recommendation is research, not a guaranteed return.
