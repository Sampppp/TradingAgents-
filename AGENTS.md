# Agents Guide: TradingAgents

## Developer Commands

### Execution
- **Interactive CLI**: `tradingagents` or `python -m cli.main`
- **Headless Run**: `tradingagents --ticker <TICKER> --date <YYYY-MM-DD> --analysts <LIST> --save --no-show`
- **Backtest**: `tradingagents backtest <TICKER1,TICKER2> --start <YYYY-MM-DD> --end <YYYY-MM-DD> --every <N>`
- **Login (ChatGPT Plus/Pro)**: `tradingagents login chatgpt`

### Development & QA
- **Install**: `pip install .` (use `pip install ".[bedrock]"` for AWS Bedrock support)
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Tests**: 
  - Unit/Smoke: `pytest`
  - Integration: `pytest -m integration`

## Architecture & Flow

### Core Logic
- **Framework**: Built on **LangGraph**.
- **Programmatic Entry**: `tradingagents.graph.trading_graph.TradingAgentsGraph`
- **Main Method**: `.propagate(ticker, date, portfolio=None)`
- **Execution Flow**: 
  `Analysts` (Fundamentals, Market, News, Sentiment) $\rightarrow$ `Researchers` (Bull/Bear) $\rightarrow$ `Trader` $\rightarrow$ `Risk Management` $\rightarrow$ `Portfolio Manager`

### Key Components
- **Agents**: Located in `tradingagents/agents/`.
- **Data Vendors**: Located in `tradingagents/dataflows/vendors/` (SEC EDGAR, Yahoo Finance, etc.).
- **LLM Tiers**: 
  - `quick_think_llm`: Used by Analysts, Researchers, and Trader.
  - `deep_think_llm`: Used by Research and Portfolio Managers.

## Critical Context & Quirks

### Data Integrity
- **Point-in-Time**: US fundamentals are fetched from **SEC EDGAR** as filed on the analysis date to prevent look-ahead bias.
- **Yahoo Finance**: Used for non-US companies; does not support historical point-in-time fundamentals.

### Persistence
- **Memory Log**: Decisions and reflections are stored in `~/.tradingagents/memory/trading_memory.md`.
- **Checkpoints**: LangGraph state is persisted in SQLite at `~/.tradingagents/cache/checkpoints/<TICKER>.db` when `--checkpoint` is enabled.

### Configuration
- **Environment Variables**: Use `TRADINGAGENTS_*` (e.g., `TRADINGAGENTS_LLM_PROVIDER`) to override defaults.
- **API Keys**: Required for LLM providers and data vendors (FRED, Alpha Vantage).

## Verification Workflow
1. `ruff check .`
2. `pytest`
3. `tradingagents --ticker AAPL --date 2026-01-01 --no-show` (Quick smoke test)
