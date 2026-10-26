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
- **Action**: Read all generated `complete_report.md` files and split candidates into two buckets:
  1. **Bucket A — Existing Holdings (Sell / Trim / Hold)**:
     - Compare `complete_report.md` against the original thesis and Stop Loss in `trading_journal/<TICKER>.md`.
     - Flag any broken theses, breached stops, or `Underweight`/`Sell` ratings for immediate Exit/Trim, noting how much buying power will be freed.
  2. **Bucket B — New Candidates (Buys)**:
     - Rank new candidates by `confidence_score` and `Rating` (`Buy > Overweight > Hold > Underweight > Sell`).
     - Filter out any candidate rated `Hold` or lower.

### 4. Position Sizing (The Filter)
- **Goal**: Calculate exact share quantities within account limits.
- **Action**:
  - Using the portfolio data and `risk_profile.json` loaded in Step 1 (plus any cash freed by proposed Sells), calculate the exact share quantity (supporting fractional shares) that fits within both `max_position_pct` and `max_position_usd`.
  - Define the exact Entry/Exit Price and Stop Loss level from the report's technical/risk levels.

### 5. Verification & Proposal
- **Goal**: Present a transparent, fully audited trade proposal.
- **Action**:
  1. Print the **Verification Checklist**:
     - [ ] Portfolio, positions, and `risk_profile.json` audited upfront
     - [ ] Original theses recalled from `trading_journal/` for existing holdings
     - [ ] Market scan completed for new candidates
     - [ ] `cli.main` executed for all candidates (via Batch Launch & Handoff verification)
     - [ ] All `complete_report.md` files synthesized into Exit vs. Entry buckets
     - [ ] Position sizing validated against `max_position_pct` and `max_position_usd`
  2. Present the **Structured Proposal** (list Exits/Trims first, followed by New Buys):
     - **Ticker**: [SYMBOL]
     - **Thesis**: [Brief summary from report + comparison to original journal thesis if held]
     - **Action**: [Buy / Sell / Trim / Hold] at $[Entry/Exit Price] | **Target Stop Loss**: $[Stop Loss]
     - **Sizing**: [Quantity] shares (~$[Total USD Amount])
     - **Risk Check**: [PASSED / FAILED] (cite `%` of portfolio and USD cap used)

### 6. Execution & Journaling (The Hands)
- **Goal**: Safe, deterministic order placement and persistent record keeping.
- **Action**:
  1. **Await explicit user approval** for each proposed trade.
  2. If approved: Execute `rboin__review_equity_order` $\rightarrow$ `rboin__place_equity_order`.
  3. **Journal**: Immediately update `/home/spak/TradingAgents/trading_journal/<TICKER>.md` per `SKILL.md` standards, recording whether the order status is `FILLED` or `PENDING`, the thesis/post-mortem, and the Stop Loss exit plan. For held positions where no trade was executed, append the timestamped HOLD audit note.