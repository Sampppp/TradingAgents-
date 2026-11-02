# TradingAgents → Robinhood MCP Agent Skill

## Purpose
Establish the technical standards, multi-order execution rules, risk guardrails, and journaling schemas for automating market discovery through deterministic trade execution with human-in-the-loop approval.

## STRICT ADHERENCE RULES (Non-Negotiable)
To prevent "shortcut reasoning," the agent MUST adhere to these boundaries:

1. **Discovery vs. Decision**:
   - **MCP Tools** (`rboin__run_scan`, `rboin__get_financials`, `rboin__get_equity_technical_indicators`, `rboin__get_earnings_calendar`, `rboin__get_equity_quotes`, etc.) are for **DISCOVERY, PRE-SCREENING & ORDER EXECUTION**.
   - **The CLI** (`cli.main`) is for **DECISIONS**. No trade (Equity or Option Buy, Trim, or Sell) may be proposed without a corresponding `complete_report.md` generated today by the CLI.
2. **No Vacuum Recommendations**:
   - Every recommendation MUST be audited against the user's live portfolio (`rboin__get_portfolio`, `rboin__get_equity_positions`), open order state (`rboin__get_equity_orders`), tax lots (`rboin__get_equity_tax_lots`), and `/home/spak/TradingAgents/risk_profile.json`.
3. **Quantitative Sizing & Dialectical Synthesis**:
   - Every proposal MUST include: **Ticker, Order Type (`Limit`, `Market`, `Stop`, `Stop-Limit`, or `Waitlist Alert`), Entry/Exit Price, Stop Loss, Exact Quantity, Bear Counter-Thesis (from the 2-round Researcher Debate), and Risk Manager Verdict (from the 2-round Risk Debate)**.

## 🛠 Technical Execution & Live Progress Standards
To avoid timeouts, buffered logs, and blind waiting during `TRADINGAGENTS_MAX_DEBATE_ROUNDS=2` and `TRADINGAGENTS_MAX_RISK_ROUNDS=2` runs, the agent MUST use this exact batch pattern:

- **Python Path**: `/home/spak/TradingAgents/.venv/bin/python -u` (always pass `-u` / `PYTHONUNBUFFERED=1` so pipeline stages flush in real time).
- **Default Analysts**: Always pass `--analysts market,news,fundamentals,social` so all four analyst teams feed the 2-round researcher debate.
- **Report Storage Directory**: Reports are stored by ticker and timestamp at:
  `/home/spak/.tradingagents/logs/reports/<TICKER>_<YYYYMMDD>_<HHMMSS>/complete_report.md`
- **Batch Launch & Live Progress Pattern**:
  1. **Verify & Launch Batch**: Run all candidates sequentially in a background loop that tracks ticker index, logs unbuffered stage progress, and records exact report paths into `batch_manifest.txt`:
     ```bash
     nohup bash -c '
       export PYTHONUNBUFFERED=1
       DATE=$(date +%Y-%m-%d)
       TICKERS=(TICKER1 TICKER2 TICKER3)
       TOTAL=${#TICKERS[@]}
       LOG_DIR="/home/spak/.tradingagents/logs"
       > "$LOG_DIR/batch_manifest.txt"
       echo "STARTING BATCH (0/$TOTAL)" > "$LOG_DIR/batch_status.txt"

       for i in "${!TICKERS[@]}"; do
         TICKER="${TICKERS[$i]}"
         NUM=$((i + 1))
         EXISTING=$(find "$LOG_DIR/reports/" -path "*${TICKER}_$(date +%Y%m%d)*/complete_report.md" 2>/dev/null | sort | tail -n 1)

         if [ -n "$EXISTING" ]; then
           echo "[SKIPPED - ALREADY EXISTS] $TICKER -> $EXISTING" >> "$LOG_DIR/batch_manifest.txt"
         else
           RUN_LOG="$LOG_DIR/cli_${TICKER}_${DATE}.log"
           echo "RUNNING [$NUM/$TOTAL]:$TICKER (Log: $RUN_LOG)" > "$LOG_DIR/batch_status.txt"
           /home/spak/TradingAgents/.venv/bin/python -u -m cli.main \
             --ticker "$TICKER" \
             --date "$DATE" \
             --analysts market,news,fundamentals,social \
             --save --no-show \
             > "$RUN_LOG" 2>&1
           NEW_REPORT=$(find "$LOG_DIR/reports/" -path "*${TICKER}_*/complete_report.md" -mtime -1 2>/dev/null | sort | tail -n 1)
           echo "[COMPLETED $NUM/$TOTAL]$TICKER -> ${NEW_REPORT:-FAILED_CHECK_LOG}" >> "$LOG_DIR/batch_manifest.txt"
         fi
       done
       echo "COMPLETE ($TOTAL/$TOTAL)" > "$LOG_DIR/batch_status.txt"
     ' >/dev/null 2>&1 &
     ```
  2. **Handoff (Live Progress & Manifest Commands)**: Provide the user with two commands:
     - **Quick Status & Report Paths Check**:
       ```bash
       cat /home/spak/.tradingagents/logs/batch_status.txt && echo "--- Reports ---" && cat /home/spak/.tradingagents/logs/batch_manifest.txt
       ```
     - **Live Stage Attach (see active ticker + current Analyst / Debate Round / Risk Step)**:
       ```bash
       watch -n 2 'cat /home/spak/.tradingagents/logs/batch_status.txt; echo "--- Completed Reports ---"; cat /home/spak/.tradingagents/logs/batch_manifest.txt; echo "--- Live CLI Stage ---"; ACTIVE_LOG=$(sed -n "s/.*Log: \(.*\))/\1/p" /home/spak/.tradingagents/logs/batch_status.txt); if [ -f "$ACTIVE_LOG" ]; then tail -n 12 "$ACTIVE_LOG"; fi'
       ```
  3. **Wait**: Instruct the user to monitor progress and reply when `batch_status.txt` reads `COMPLETE`. **DO NOT** poll automatically.
  4. **Verify**: Read the exact `complete_report.md` paths listed in `/home/spak/.tradingagents/logs/batch_manifest.txt`.

## 🛡 Order Capabilities, Slippage & Risk Profile Standards
- **Risk Profile Enforcement**: Enforce all parameters in `/home/spak/TradingAgents/risk_profile.json`:
  - `max_position_pct` & `max_position_usd`: Hard ceiling on total position value.
  - `min_confidence`: Reject any Buy candidate with `confidence_score < min_confidence`.
  - `default_stop_loss_pct`: Tighten any Stop Loss that exceeds `Entry Price * (1 - default_stop_loss_pct)`.
- **Full Order Type Selection Matrix**:
  1. **Whole-Share Limit Orders (`quantity >= 1` integer)**: Always prefer `type: "limit"` at the report's support/entry level (checked against `rboin__get_equity_quotes` and `rboin__get_equity_price_book` Level 2 bid/ask spread).
  2. **Whole-Share Stop & Stop-Limit Orders**: For existing whole-share holdings, you may propose on-exchange resting Stop-Loss (`trigger: "stop"`, `stop_price`) or Stop-Limit (`type: "limit"`, `trigger: "stop"`) sell orders.
  3. **Fractional Shares (`quantity < 1` or non-integer)**:
     - Robinhood rejects `limit` and `stop` orders on fractional shares.
     - **If Live Price is within `<= 1.5%` of Target Entry**: Propose a `type: "market"` order by `dollar_amount`.
     - **If Live Price is `> 1.5%` above Target Entry (Anti-Chase Rule)**: Do **NOT** chase with a market order. Propose adding the ticker to a Watchlist (`rboin__add_watchlist_item`) and creating a Buy-Zone Price Alert (`rboin__create_alert`, `condition_type: "price_below"`, `threshold: Target_Entry_Price`).
  4. **Options Orders (Optional / High-Conviction Catalyst or Hedge)**: If `confidence_score >= 0.80` or when hedging portfolio risk, you may inspect chains via `rboin__get_option_chains` and propose single-leg defined-risk options via `rboin__review_option_order` $\rightarrow$ `rboin__place_option_order`.
- **Pre-Trade Reconciliation & Tax Check**:
  - Check `rboin__get_equity_orders` in Step 1 to reconcile prior `PENDING` orders and cancel stale open orders via `rboin__cancel_equity_order`.
  - Check `rboin__get_equity_tax_lots` and `rboin__get_realized_pnl` before selling or re-entering a recently sold ticker to flag 30-day Wash Sale risks.
- **Two-Step Execution**: Always run `rboin__review_equity_order` (or `rboin__review_option_order`) and obtain explicit user approval before calling `place_*_order`.

## 📓 Journaling Standards
Maintain `/home/spak/TradingAgents/trading_journal/<TICKER>.md` using these rules:

- **Recall & Reconcile**: Read `<TICKER>.md` before analyzing any held or previously traded ticker. If the last entry was `PENDING`, update its status based on `rboin__get_equity_orders` / `rboin__get_equity_positions`.
- **Creating New Journals (First-Time BUY)**: Create `/home/spak/TradingAgents/trading_journal/<TICKER>.md` with:
  - **Date, Order Type & Status (`FILLED` or `PENDING`), Entry Price, Quantity / Dollar Amount**.
  - **Original Thesis**: Core catalyst, Rating, and `confidence_score` from `complete_report.md`.
  - **Bear Case & Risk Debate Notes**: Key counter-arguments from the 2-round Researcher and Risk debates.
  - **Exit Plan**: Target Stop Loss price, Take-Profit target, and thesis-breaking conditions.
- **Appending to Existing Journals (Add-On BUY, HOLD, TRIM, or SELL)**:
  - **DO NOT** use `editor` replacement on existing journal files. Always append via shell command:
    ```bash
    cat << 'EOF' >> /home/spak/TradingAgents/trading_journal/<TICKER>.md

    ## Audit / Update: YYYY-MM-DD
    - **Action**: [HOLD / BUY / TRIM / SELL / WAITLIST] | **Order Status**: [N/A / PENDING / FILLED]
    - **Price / Qty**: $[Price] ([Qty] shares) \vert{} **Stop Loss**:$[Stop]
    - **Report Rating & Confidence**: [Rating] ([confidence_score])
    - **Debate & Risk Notes**: [Summary of Bull/Bear & Risk Manager debate]
    - **Rationale / Post-Mortem**: [Why thesis holds, why trade executed, or PnL outcome]
    EOF
    ```