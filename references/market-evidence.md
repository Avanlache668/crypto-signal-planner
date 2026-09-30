# Data and evidence standard

## Source ladder
1. Coin identity / migration / tokenomics: official docs, official chain explorer and verifiable on-chain events; label announcements vs observed execution separately.
2. Spot quote and liquidity: named exchange trading-pair API with UTC data timestamp, compared against an independent price aggregator/exchange. For on-chain quotes, verify contract and pool liquidity.
3. Catalyst: dated official changelog, governance forum, exchange notice or regulatory filing, corroborated by reputable reporting when materially important.
4. Macro: official central-bank releases, treasury data and named market-data provider. For equities use latest valid session and never treat weekend price as a new session.

## Recency / trust gates (editable defaults; not market facts)
- Intended *actionable* spot quote <=15 minutes old; if only delayed or archived, downgrade to research-only.
- Daily trend: latest fully closed UTC daily candle and >=50 valid daily candles for 50-day indicator claims, >=200 for EMA200. No partial candle described as daily close.
- Two price sources should differ <=1% for primary quote; if not, explicitly flag price disagreement and pause candidate action.
- Turnover/liquidity: prefer >=USD 50m credible 24h spot volume and <=0.5% observed spread as screening heuristics; if volume inflated or absent, mark uncertain, not pass.
- Token unlock: list source + whether scheduled, vested, claimable, claimed, transferred, or exchange-deposited. These are distinct; conflicting third-party calendars => UNVERIFIED.
- TVL, volume, fees, active addresses or ETF access ≠ token price appreciation. Check emissions, holder entitlements, vesting, security incidents and asset capture.
- Link to the specific page and annotate observed UTC time, delayed/live status, market/pair, chain and measurement units.

## Reject or downgrade
Unknown project identity; wrapped/old-contract confusion; suspicious liquidity; highly concentrated supply without reliable disclosure; unavailable OHLCV; known major security incident not assessed; quote discrepancy >1%; inadequate expected R:R; obviously correlated exposure exceeding portfolio budget.

## Candidate uniqueness
For consecutive “再推荐一个”, check current thread and any provided candidate history. Sample preceding suggestions: SOL / SUI / LINK / AAVE / ONDO / RENDER. These are a historical discussion list, not automatically live exclusions forever; report the exclusion decision and update only user-approved local state.
