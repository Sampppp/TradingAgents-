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
       echo "RUNNING: $TICKER" > /home/spak/.tradingagents/logs/batch_status.txt
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

## 🛡 Order Execution, Slippage & Risk Profile Standards
- **Risk Profile Enforcement**: Read `/home/spak/TradingAgents/risk_profile.json` and enforce all four parameters:
  - `max_position_pct` & `max_position_usd`: Hard ceiling on total position value (existing + new).
  - `min_confidence`: Reject any New Buy candidate whose `complete_report.md` confidence score is `< min_confidence` (e.g., `0.67`).
  - `default_stop_loss_pct`: If the report's technical stop loss exceeds `default_stop_loss_pct` (e.g., `9%` below actual entry), tighten the Stop Loss to `Entry Price * (1 - default_stop_loss_pct)`.
- **Fractional vs. Whole-Share Order Types (Broker Constraint)**:
  - Robinhood **rejects `limit` orders on fractional shares**.
  - If sizing requires **fractional shares** (`quantity` is not a whole integer), you MUST propose and execute `type: "market"` using `dollar_amount`.
  - Only use `type: "limit"` for **whole-share quantities** (`1, 2, 3...`).
- **Live Price Slippage Check**: `complete_report.md` prices may reflect prior closes. Before finalizing Step 4 sizing or placing a `market` order, check the live price via MCP or `rboin__review_equity_order`. If the live price is `> 2%` above the report's recommended entry price, recalculate the Stop Loss and warn the user in the proposal.
- **Two-Step Execution**: Never call `rboin__place_equity_order` without a matching `rboin__review_equity_order` and explicit user approval. Never silently change an order from `limit` to `market` without re-confirming with the user.

## 📓 Journaling Standards
To prevent "Thesis Amnesia" and avoid `editor` diff errors on existing files, maintain `/home/spak/TradingAgents/trading_journal/<TICKER>.md` using these rules:

- **Recall**: Before analyzing any ticker in the portfolio or watchlist with an existing journal, read `<TICKER>.md`.
- **Creating New Journals (First-Time BUY)**: Use the file creation tool to write `/home/spak/TradingAgents/trading_journal/<TICKER>.md` with:
  - **Date, Order Status (`FILLED` or `PENDING`), Entry Price, Quantity / Dollar Amount**.
  - **Original Thesis**: Core catalyst, Rating, and `confidence_score` from `complete_report.md`.
  - **Exit Plan**: Target Stop Loss price (bounded by `default_stop_loss_pct`) and thesis-breaking conditions.
- **Appending to Existing Journals (Add-On BUY, HOLD, TRIM, or SELL)**:
  - **DO NOT** use `editor` replacement on existing journal files. Always append via shell command to prevent `Missing old_text` errors and save tool calls:
    ```bash
    cat << 'EOF' >> /home/spak/TradingAgents/trading_journal/<TICKER>.md

    ## Audit / Update: YYYY-MM-DD
    - **Action**: [HOLD / BUY / TRIM / SELL] | **Order Status**: [N/A / PENDING / FILLED]
    - **Price / Qty**: $[Price] ([Qty] shares) \vert{} **Stop Loss**:$[Stop]
    - **Report Rating & Confidence**: [Rating] ([confidence_score])
    - **Rationale / Post-Mortem**: [Why thesis holds despite rating, or why trade was executed]
    EOF
    ```
  - **Mandatory HOLD Logging**: Every existing portfolio position that is audited and held (`NVDA`, `SPCX`, `MU`, etc.) MUST receive a timestamped `HOLD` append in Step 6 before concluding the workflow.