# Workflow: Make Money

This workflow triggers the end-to-end quantitative research and trading pipeline to audit existing positions for exit/trim signals, discover new high-probability opportunities, and propose risk-adjusted orders.

**Reference Skill**: Strictly adhere to `.agents/skills/trading/SKILL.md` for CLI batch execution, sizing math, and journaling standards.

## Trigger
- **Command**: `/make-money`
- **Intent**: "Audit my current portfolio for sell/trim signals, find new high-probability opportunities if buying power permits, analyze them deeply via the CLI, and propose risk-adjusted orders."

## Operational Pipeline

### 1. Portfolio Audit & Discovery (The Eyes)
- **Goal**: Establish account constraints first, audit all current holdings, and identify 3–5 new candidates (total universe: 3–8 tickers).
- **Action**:
  1. **Account & Risk Audit**:
     - Call `rboin__get_portfolio` and `rboin__get_equity_positions` (retain this state for the entire workflow; do not re-fetch unnecessarily).
     - Read `/home/spak/TradingAgents/risk_profile.json` to determine available buying power, `max_position_pct`, and `max_position_usd`.
     - Every current equity position is automatically a candidate for analysis.
  2. **Market Scan (If Buying Power Exists or Rebalancing)**:
     - Use `rboin__run_scan` or `rboin__create_scan` to identify 3–5 new high-probability candidates.
     - **Criteria**: Quantitative value and momentum (e.g., PEG < 1.2, RSI 30–60, High Relative Volume), refined via discovery MCP tools (`rboin__get_financials`, `rboin__get_equity_technical_indicators`).
     - **Fallback**: If scans are unavailable, use `rboin__get_popular_watchlists` $\rightarrow$ `rboin__get_watchlist_items`.

### 2. Thesis Recall & Deep Analysis (The Brain)
- **Goal**: Generate deep multi-agent conviction reports while maintaining historical thesis continuity.
- **Action**:
  1. **Recall**: For every candidate that has a file in `/home/spak/TradingAgents/trading_journal/<TICKER>.md`, read it to recall the original thesis and exit plan.
  2. **Batch Analyze**: Launch `cli.main` for all candidates (Existing + New) in a single sequential background loop using the **Batch Launch & Handoff Pattern** defined in `SKILL.md`.
  3. **Handoff & Wait**: Provide the user with the batch verification command (`cat /home/spak/.tradingagents/logs/batch_status.txt && find ...`) and wait for confirmation. **DO NOT** poll automatically and **DO NOT** substitute `complete_report.md` with direct MCP tool calls.

### 3. Two-Bucket Synthesis & Ranking
- **Goal**: Prioritize capital protection and exits before allocating capital to new buys.
- **Action**: Read all generated `complete_report.md` files, extracting both `Rating` and `confidence_score`:
  1. **Bucket A — Existing Holdings (Sell / Trim / Hold)**:
     - Compare `complete_report.md` against the original thesis and Stop Loss in `trading_journal/<TICKER>.md`.
     - If a holding is rated `Underweight` or `Sell`, default to **Exit/Trim** unless the original catalyst in `<TICKER>.md` explicitly overrides short-term weakness (if overriding to `Hold`, you MUST justify why in the proposal).
  2. **Bucket B — New Candidates (Buys)**:
     - Filter out any candidate with `Rating` of `Hold` or lower, OR `confidence_score < min_confidence` (from `risk_profile.json`).
     - Rank remaining candidates by `confidence_score` and `Rating` (`Buy > Overweight`).

### 4. Position Sizing & Order Type Selection (The Filter)
- **Goal**: Calculate exact share/dollar quantities within account limits and select a valid broker order type.
- **Action**:
  - Using Step 1 portfolio data and `risk_profile.json` (plus any cash freed by proposed Sells), calculate the target allocation within `max_position_pct` and `max_position_usd`.
  - **Order Type Rule**: If the target allocation results in **fractional shares**, specify `Market Order ($Dollar_Amount)` (as Robinhood rejects fractional limit orders). Only specify `Limit Order` for whole-share quantities.
  - Set the Stop Loss using the report's support level, capped at a maximum drawdown of `default_stop_loss_pct` from the live entry price.

### 5. Verification & Proposal
- **Goal**: Present a transparent, fully audited trade proposal.
- **Action**:
  1. Print the **Verification Checklist**:
     - [ ] Portfolio, positions, and `risk_profile.json` (`max_position_pct`, `max_position_usd`, `min_confidence`, `default_stop_loss_pct`) loaded upfront
     - [ ] Original theses recalled from `trading_journal/` for existing holdings
     - [ ] Market scan completed for new candidates
     - [ ] `cli.main` executed for all candidates (via Batch Launch & Handoff verification)
     - [ ] All `complete_report.md` files synthesized with `Rating` and `confidence_score`
     - [ ] Fractional orders set to `Market ($)` and sizing validated against risk caps
  2. Present the **Structured Proposal** (list Bucket A Holdings/Exits first, followed by Bucket B New Buys):
     - **Ticker**: [SYMBOL]
     - **Rating & Confidence**: [Rating] (`confidence_score` vs. `min_confidence`)
     - **Thesis**: [Summary from report + comparison to original journal thesis; justify any `Hold` on an `Underweight` rating]
     - **Action & Order Type**: [Buy / Sell / Trim / Hold] — [Market ($Amount) for fractional | Limit ($Price) for whole shares] | **Target Stop Loss**: $[Stop Loss]
     - **Sizing**: [Quantity] shares (~$[Total USD Amount])
     - **Risk Check**: [PASSED / FAILED] (cite `%` of portfolio, USD cap, and `min_confidence` check)

### 6. Execution & Journaling (The Hands)
- **Goal**: Safe, deterministic order placement and 100% journal coverage across both buckets.
- **Action**:
  1. **Await explicit user approval** for proposed trades.
  2. If approved: Execute `rboin__review_equity_order` $\rightarrow$ `rboin__place_equity_order`. (If `review_equity_order` reveals live price slippage `> 2%` above the report price, adjust the Stop Loss proportionally).
  3. **Journal All Candidates (Trades + Holds)**:
     - For **new files**, create `/home/spak/TradingAgents/trading_journal/<TICKER>.md`.
     - For **existing files** (including all Bucket A positions held without trades), append a timestamped update block using `cat << 'EOF' >> ...` in a single batch shell command.