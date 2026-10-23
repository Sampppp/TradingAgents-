# Workflow: Make Money

This workflow triggers the full quantitative research and trading pipeline to identify and propose high-probability trades, including auditing existing positions for exit signals.

## Trigger
- **Command**: `/make_money`
- **Intent**: "Audit my current portfolio for sell/trim signals, find new high-probability opportunities, analyze them deeply, and propose risk-adjusted orders."

## Operational Pipeline

### 1. Discovery (The Eyes)
- **Goal**: Identify a universe of 3-8 candidates for analysis (Existing + New).
- **Action**: 
  1. **Portfolio Audit**: Call `rboin__get_equity_positions` to identify all current holdings. Every current position is automatically a candidate for analysis.
  2. **Market Scan**: Use `rboin__run_scan` or `rboin__create_scan` to find 3-5 new high-probability candidates.
- **Criteria**: Focus on quantitative value/momentum (e.g., PEG < 1.2, RSI 30-60, High Volume).
- **Fallback**: If no scan is available, use `rboin__get_popular_watchlists` $\rightarrow$ `rboin__get_watchlist_items`.

### 2. Thesis Recall & Deep Analysis (The Brain)
- **Goal**: Move from raw data to a conviction-based decision (Buy, Hold, or Sell) while maintaining continuity.
- **Action**: For each candidate (Existing and New):
  1. **Recall**: If the ticker has a journal file in `/home/spak/TradingAgents/trading_journal/<TICKER>.md`, read it to recall the original thesis.
  2. **Analyze**: Launch the analysis CLI using the **Background & Poll** pattern:
     - **Launch**: `nohup /home/spak/TradingAgents/.venv/bin/python -m cli.main --ticker <TICKER> --date $(date +%Y-%m-%d) --analysts market,news --save --no-show > /home/spak/.tradingagents/logs/cli_last_run.log 2>&1 &`
     - **Poll**: Check for the existence of `/home/spak/.tradingagents/logs/reports/<TICKER_...>/complete_report.md`.
- **Constraint**: **DO NOT** substitute this with direct MCP tool calls for the final decision.

### 3. Synthesis & Ranking
- **Goal**: Identify the best risk-adjusted opportunities (New Buys or Necessary Sells).
- **Action**: Read all generated `complete_report.md` files. Compare current findings against the original thesis in the journal. Rank by `confidence_score` and `Rating` (Buy > Overweight > Hold > Underweight > Sell).

### 4. Portfolio & Risk Audit (The Filter)
- **Goal**: Ensure the proposed action fits the actual account constraints.
- **Action**: 
  1. Call `rboin__get_portfolio` and `rboin__get_equity_positions`.
  2. Read `/home/spak/TradingAgents/risk_profile.json`.
  3. Calculate exact share quantity (including fractional) based on `max_position_pct` and `max_position_usd`.

### 5. Verification & Proposal
- **Goal**: Present a professional, audited trade proposal.
- **Action**: 
  1. Print the **Verification Checklist**:
     - [ ] Current portfolio audited for candidates
     - [ ] Market scan completed for new candidates
     - [ ] Original theses recalled from `trading_journal/`
     - [ ] `cli.main` executed for all candidates (via background poll)
     - [ ] `complete_report.md` synthesized
     - [ ] Portfolio audit performed
     - [ ] `risk_profile.json` validated
  2. Present the **Structured Proposal**:
     - **Ticker**: [SYMBOL]
     - **Thesis**: [Brief summary from report + comparison to original thesis]
     - **Action**: [Buy/Sell/Trim] at [Entry/Exit Price] with Stop at [Stop Loss]
     - **Sizing**: [Quantity] shares (~$[Amount])
     - **Risk Check**: [PASSED/FAILED]

### 6. Execution & Journaling (The Hands)
- **Goal**: Safe, deterministic order placement and persistent record keeping.
- **Action**: 
  1. **Await explicit user approval**.
  2. If approved: `rboin__review_equity_order` $\rightarrow$ `rboin__place_equity_order`.
  3. **Journal**: Immediately update or create the ticker's journal file in `/home/spak/TradingAgents/trading_journal/<TICKER>.md` with the entry/exit details and the final thesis.

## Strict Constraints
- **No Shortcuts**: MCP tools are for discovery; the CLI is for decisions.
- **No Vacuum Trades**: Every trade must be audited against the real portfolio.
- **Absolute Paths**: Always use `/home/spak/TradingAgents/.venv/bin/python`.
- **Safety**: Never execute a trade without a prior review and user confirmation.

Refer to `.agents/skills/trading/SKILL.md` for detailed logic and technical standards.

