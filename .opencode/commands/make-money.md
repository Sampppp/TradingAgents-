---
description: "Execute the trading agent workflow"
---

# Workflow: Make Money

This workflow triggers the end-to-end quantitative research and trading pipeline to reconcile open orders, audit existing positions, discover new whole-share and fractional opportunities, analyze them via the CLI, and execute risk-adjusted orders or watchlist triggers.

**Reference Skill**: Strictly adhere to `.opencode/skills/trading/SKILL.md` for CLI batch execution, order type selection, sizing math, and journaling standards.

## Trigger
- **Command**: `/make-money`
- **Intent**: "Reconcile my orders and portfolio, audit holdings for exit/trim signals, find new opportunities, analyze them deeply via the CLI, and propose risk-adjusted Limit, Stop, Market, or Watchlist/Alert actions."

## Operational Pipeline

### 1. Portfolio, Order & Tax Audit + Discovery (The Eyes)
- **Goal**: Reconcile account state, audit current holdings, and identify 3–5 new candidates (total universe: 3–8 tickers).
- **Action**:
  1. **Account, Order & Tax Audit**:
     - Call `tools.robinhood.get_portfolio`, `tools.robinhood.get_equity_positions`, `tools.robinhood.get_equity_orders`, and `tools.robinhood.get_equity_tax_lots` (retain this state for the entire workflow).
     - Read `/home/spak/TradingAgents/risk_profile.json` (`max_position_pct`, `max_position_usd`, `min_confidence`, `default_stop_loss_pct`).
     - Reconcile any prior `PENDING` journal entries against `tools.robinhood.get_equity_orders` and flag stale open orders that should be canceled (`tools.robinhood.cancel_equity_order`).
     - Every current equity position is automatically a candidate for analysis.
  2. **Market Scan & Pre-CLI Vetting**:
     - Use `tools.robinhood.run_scan` or `tools.robinhood.create_scan` to identify 3–5 new candidates (fallback: `tools.robinhood.get_popular_watchlists` $\rightarrow$ `tools.robinhood.get_watchlist_items`).
     - **Price-Tier Diversity**: Include at least 1–2 candidates priced low enough that target allocation buys **$\ge 1$ whole share** (enabling resting `Limit` and `Stop` orders alongside fractional mega-caps).
     - **Catalyst & Spread Vetting**: Call `tools.robinhood.get_earnings_calendar` and `tools.robinhood.get_equity_quotes` on candidates to flag imminent earnings (< 3 days) and check live prices.

### 2. Thesis Recall & Deep Analysis (The Brain)
- **Goal**: Generate deep multi-agent conviction reports (`market,news,fundamentals,social` across 2 Debate Rounds and 2 Risk Rounds).
- **Action**:
  1. **Recall**: Read `/home/spak/TradingAgents/trading_journal/<TICKER>.md` for every candidate that has an existing journal.
  2. **Batch Analyze**: Launch `cli.main` for all candidates in a single sequential background loop using the **Batch Launch & Live Progress Pattern** in `SKILL.md`.
  3. **Handoff & Wait**: Provide the user with both the **Quick Status & Report Paths Check** command and the **Live Stage Attach (`watch`)** command from `SKILL.md`. Wait for user confirmation. **DO NOT** poll automatically.

### 3. Two-Bucket Dialectical Synthesis & Ranking
- **Goal**: Prioritize capital protection and exits before allocating capital to new buys.
- **Action**: Read all generated `complete_report.md` files from `batch_manifest.txt`, extracting `Rating`, `confidence_score`, the **Bear Researcher's counter-thesis**, and the **Risk Management Team's recommendation**:
  1. **Bucket A — Existing Holdings (Sell / Trim / Hold)**:
     - Compare `complete_report.md` against `<TICKER>.md` and check `tools.robinhood.get_equity_tax_lots` for tax/wash-sale impact.
     - If rated `Underweight` or `Sell`, default to **Exit/Trim** unless the original catalyst in `<TICKER>.md` explicitly overrides short-term weakness (must be justified in the proposal).
  2. **Bucket B — New Candidates (Buys & Waitlist)**:
     - Filter out any candidate with `Rating` of `Hold` or lower, OR `confidence_score < min_confidence` (check `tools.robinhood.get_realized_pnl` / tax lots to ensure no 30-day Wash Sale violation).
     - Rank remaining candidates by `confidence_score` and `Rating` (`Buy > Overweight`).

### 4. Position Sizing & Multi-Order Selection (The Filter)
- **Goal**: Calculate exact quantities and select the optimal broker order type or waitlist trigger.
- **Action**:
  - Calculate target allocation within `max_position_pct` and `max_position_usd` (including cash freed by proposed Bucket A Sells).
  - Fetch fresh prices/spreads via `tools.robinhood.get_equity_quotes` (and `tools.robinhood.get_equity_price_book` if needed) and select the execution vehicle:
    - **Whole Shares ($\ge 1$ integer qty)**: Propose a `Limit Order` at the report's recommended entry/support level.
    - **Fractional Shares within `<= 1.5%` of Target Entry**: Propose a `Market Order ($Dollar_Amount)`.
    - **Fractional Shares `> 1.5%` above Target Entry**: Propose **Waitlist + Buy-Zone Alert** (`tools.robinhood.add_watchlist_item` + `tools.robinhood.create_alert` at the target pullback price) rather than chasing slippage.
  - Set the Stop Loss using the report's support level, capped at `default_stop_loss_pct` below entry.

### 5. Verification & Proposal
- **Goal**: Present a transparent, fully audited trade proposal.
- **Action**:
  1. Print the **Verification Checklist**:
     - [ ] Portfolio, positions, open orders (`get_equity_orders`), tax lots (`get_equity_tax_lots`), and `risk_profile.json` audited upfront
     - [ ] Original theses recalled from `trading_journal/` and pending orders reconciled
     - [ ] Market scan and earnings calendar check completed for new candidates
     - [ ] `cli.main` (`market,news,fundamentals,social`) executed and verified via `batch_manifest.txt`
     - [ ] 2-Round Bull/Bear Debate and 2-Round Risk Debate synthesized for all candidates
     - [ ] Order types (`Limit`, `Market $`, `Stop`, or `Waitlist Alert`) matched to whole vs. fractional shares and live slippage
  2. Present the **Structured Proposal** (list Stale Order Cancellations and Bucket A Holdings first, followed by Bucket B New Buys/Waitlist):
     - **Ticker**: [SYMBOL] (Report Path: `[path from batch_manifest.txt]`)
     - **Rating & Confidence**: [Rating] (`confidence_score` vs. `min_confidence`)
     - **Dialectical Thesis**: [Bull catalyst + Bear counter-argument + Risk Manager note; justify any `Hold` on an `Underweight` rating]
     - **Action & Vehicle**: [Buy / Sell / Trim / Hold / Waitlist] — [`Limit @ $Price` (Whole Shares) | `Market ($Amount)` (Fractional <=1.5% slippage) | `Waitlist + Alert @ $Price` (Fractional >1.5% slippage)]
     - **Target Stop Loss & Take Profit**: Stop: $[Stop Loss] ([X]% risk) | Target: $[Take Profit]
     - **Sizing**: [Quantity] shares (~$[Total USD Amount])
     - **Risk & Tax Check**: [PASSED / FAILED] (cite `%` of portfolio, USD cap, `min_confidence`, and Wash-Sale/Earnings check)

### 6. Execution & Journaling (The Hands)
- **Goal**: Safe, deterministic order placement and 100% journal coverage.
- **Action**:
  1. **Await explicit user approval** for proposed orders, cancellations, or watchlist additions.
  2. If approved:
     - Cancel any approved stale orders via `tools.robinhood.cancel_equity_order`.
     - Execute trades via `tools.robinhood.review_equity_order` $\rightarrow$ `tools.robinhood.place_equity_order`.
     - For approved Waitlist candidates, call `tools.robinhood.add_watchlist_item`.
  3. **Journal All Candidates (Trades + Holds)**:
     - Create new `/home/spak/TradingAgents/trading_journal/<TICKER>.md` files for first-time positions.
     - Append timestamped update blocks to existing journals (including all Bucket A `HOLD` positions) via `cat << 'EOF' >> ...` in a single batch shell command.

### 7. Stop-Loss & Alert Synchronization (The Alarm)
- **Goal**: Protect every held position and monitor Waitlist buy zones via on-exchange stops or Robinhood alerts.
- **Action**:
  1. **Audit Alerts**: Call `tools.robinhood.get_alerts`.
  2. **Protect Held Positions**:
     - **Whole-Share Positions**: Ask the user if they want an on-exchange resting Stop-Loss order placed (`tools.robinhood.review_equity_order` $\rightarrow$ `tools.robinhood.place_equity_order` with `side: "sell"`, `trigger: "stop"`, `stop_price: Target_Stop_Loss`), AND/OR sync a `price_below` alert.
     - **Fractional Positions**: Sync a Robinhood alert (`tools.robinhood.create_alert` or `tools.robinhood.update_alert` with `condition_type: "price_below"`, `threshold: Target_Stop_Loss`) and optional Take-Profit alert (`condition_type: "price_above"`).
  3. **Set Waitlist Buy-Zone Alerts**: For any Bucket B candidate placed on the Waitlist due to entry slippage, create a `price_below` alert at its target entry price.
  4. **Cleanup**: Call `tools.robinhood.delete_alert` for any tickers fully exited in Step 6.
