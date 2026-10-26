# TradingAgents → Robinhood MCP Agent Skill

## Purpose
Establish the technical standards, risk guardrails, and journaling schemas for automating market discovery through deterministic trade execution with human-in-the-loop approval.

## STRICT ADHERENCE RULES (Non-Negotiable)
To prevent "shortcut reasoning," the agent MUST adhere to these boundaries:

1. **Discovery vs. Decision**:
   - **MCP Tools** (`rboin__get_financials`, `rboin__get_equity_technical_indicators`, `rboin__run_scan`, etc.) are for **DISCOVERY ONLY**. Use them to find candidates and narrow the universe.
   - **The CLI** (`cli.main`) is for **DECISIONS**. No trade (Buy, Trim, or Sell) may be proposed without a corresponding `complete_report.md` generated today by the CLI.
2. **No Vacuum Recommendations**:
   - Never recommend a "Buy" or "Sell" based solely on market data. Every recommendation MUST be audited against the user's actual portfolio (`rboin__get_portfolio`, `rboin__get_equity_positions`) and `/home/spak/TradingAgents/risk_profile.json`.
3. **Quantitative Sizing**:
   - "Strong Buy" is not a proposal. Every proposal MUST include: **Ticker, Action, Entry/Exit Price, Stop Loss, and Exact Share Quantity (including fractional shares)** bounded by `risk_profile.json` caps (`max_position_pct` and `max_position_usd`).

## 🛠 Technical Execution Standards
To avoid timeouts, log clobbering, and API rate limits, the agent MUST use these patterns:

- **Python Path**: Always use `/home/spak/TradingAgents/.venv/bin/python` (executed from the `/home/spak/TradingAgents` working directory).
- **Default Analysts**: Always pass `--analysts market,news,fundamentals` so both technical/catalyst and valuation metrics are evaluated.
- **Batch Launch & Handoff Pattern (Long-Running CLI)**:
  Since `cli.main` takes several minutes per ticker, do NOT run it synchronously and do NOT launch parallel processes that overwrite logs. Run all candidates sequentially in a single background batch:

  1. **Verify & Launch Batch**: Pass all target tickers into a single background loop that skips tickers already analyzed today, logs per ticker, and writes a completion flag when finished:
     ```bash
     nohup bash -c '
       DATE=$(date +%Y-%m-%d)
       echo "RUNNING" > /home/spak/.tradingagents/logs/batch_status.txt
       for TICKER in TICKER1 TICKER2 TICKER3; do
         EXISTING=$(find /home/spak/.tradingagents/logs/reports/ -path "*${TICKER}*/complete_report.md" -newermt "$DATE" 2>/dev/null)
         if [ -z "$EXISTING" ]; then
           /home/spak/TradingAgents/.venv/bin/python -m cli.main \
             --ticker "$TICKER" \
             --date "$DATE" \
             --analysts market,news,fundamentals \
             --save --no-show \
             > "/home/spak/.tradingagents/logs/cli_${TICKER}_${DATE}.log" 2>&1
         fi
       done
       echo "COMPLETE" > /home/spak/.tradingagents/logs/batch_status.txt
     ' >/dev/null 2>&1 &
     ```
  2. **Handoff**: Provide the user with a single verification command to check batch progress and generated reports:
     ```bash
     cat /home/spak/.tradingagents/logs/batch_status.txt && find /home/spak/.tradingagents/logs/reports/ -name "complete_report.md" -mtime -1
     ```
  3. **Wait**: Explicitly instruct the user to run the verification command and notify the agent when `batch_status.txt` reads `COMPLETE`. **DO NOT** poll for files automatically.
  4. **Verify**: Once the user confirms completion, verify and read each ticker's `complete_report.md` before proceeding to Synthesis.

## 🛡 Order Execution & Stop-Loss Standards
- **Two-Step Execution**: Never call `rboin__place_equity_order` without first calling `rboin__review_equity_order` and receiving explicit user approval.
- **Stop-Loss Handling**: Standard equity buy orders cannot attach a contingent Stop Loss prior to fill. The proposed Stop Loss MUST be recorded in the ticker's journal under **Exit Plan** to be placed after fill confirmation or enforced during subsequent portfolio audits.

## 📓 Journaling Standards
To prevent "Thesis Amnesia" across sessions, maintain a persistent record in `/home/spak/TradingAgents/trading_journal/<TICKER>.md`.

- **Recall**: Before analyzing any ticker already in the portfolio, read `<TICKER>.md` to recall the original entry thesis and exit triggers.
- **Entry Record (BUY)**: Upon executing a BUY, create or update `<TICKER>.md` with:
  - **Date, Order Status (`FILLED` or `PENDING`), Entry/Limit Price, Quantity**.
  - **Original Thesis**: The core catalyst and valuation rationale from `complete_report.md`.
  - **Exit Plan**: The exact Stop Loss price and specific fundamental/technical conditions that break the thesis.
- **Update Record (HOLD)**: When an existing position is audited and held, append a timestamped audit note at the end of `<TICKER>.md` (using standard file replacement at the EOF or `cat << 'EOF' >> /home/spak/TradingAgents/trading_journal/<TICKER>.md`) explaining why the thesis remains intact. Never overwrite historical entries.
- **Exit Record (SELL/TRIM)**: Upon executing a SELL or TRIM, append:
  - **Date, Order Status (`FILLED` or `PENDING`), Exit Price, Quantity Sold, Realized PnL**.
  - **Post-Mortem**: Did the original thesis hold, or which exit condition was triggered?