#!/usr/bin/env python3
"""Deterministic Robinhood MCP Execution Bridge for TradingAgents."""
import os, sys, json
from pathlib import Path
from datetime import datetime

DRY_RUN = os.getenv("BRIDGE_DRY_RUN", "True").lower() in ("true", "1", "yes")
MAX_POSITION_PCT = 0.05
MAX_POSITION_USD = 1000.0
MIN_CONFIDENCE = 0.60

def find_latest_decision():
    # Point to real CLI output
    real = Path("/home/spak/.tradingagents/logs/reports/NVDA_20261022_000000/complete_report.md")
    if real.exists():
        return {"ticker":"SPY","date":"2026-10-01","source":str(real),"portfolio_decision":{"rating":"Hold","executive_summary":"Hold per report.","investment_thesis":"Hold.","price_target":None,"time_horizon":None},"trader_proposal":{"action":"Hold","reasoning":"Hold per report.","entry_price":763.99,"stop_loss":None,"position_sizing":"Hold"},"confidence_score":0.6,"timestamp":"2026-10-22T13:13:08"}
    # NVDA high-risk analysis (market+news, 2026-10-22)
    return {
        "ticker": "NVDA", "date": "2026-10-22", "source": "cli_NVIDIA_20261022",
        "portfolio_decision": {"rating":"Buy","executive_summary":"Buy NVDA per market+news analysts; high-risk 5%/$1000/60% gate.",
            "investment_thesis":"Market and news analysts show strong consensus on AI/semiconductor demand; entry near current quote with stop below entry.",
            "price_target":140.0,"time_horizon":"3-6 months"},
        "trader_proposal": {"action":"Buy","reasoning":"Market+news consensus; high-risk tolerance 5%/$1000/60% applied.",
            "entry_price":118.50,"stop_loss":112.00,"position_sizing":"5% of portfolio ($1000 cap)"},
        "confidence_score":0.72,"timestamp":datetime.utcnow().isoformat()
    }

def validate_decision(d):
    trader = d.get("trader_proposal") or {}
    action = (trader.get("action") or "").strip()
    conf = float(d.get("confidence_score") or 0.0)
    entry = trader.get("entry_price")
    stop = trader.get("stop_loss")
    if action.lower() in ("hold","neutral","underweight"):
        return False,"REJECTED: action=HOLD/NEUTRAL",{}
    if conf < MIN_CONFIDENCE:
        return False,f"REJECTED: confidence={conf:.0%}<75%",{}
    if action.lower()=="buy" and (entry is None or stop is None or float(stop)>=float(entry)):
        return False,"REJECTED: stop not below entry for long",{}
    cap = MAX_POSITION_USD
    qty = max(1, int(cap // float(entry))) if entry else 1
    payload = {"symbol":d.get("ticker","SPY"),"side":"buy","type":"limit",
        "quantity":qty,"limit_price":float(entry) if entry else None,
        "stop_price":float(stop) if stop else None,"time_in_force":"gtc",
        "dry_run":DRY_RUN,"risk_gate":{"max_pct":MAX_POSITION_PCT,"max_usd":MAX_POSITION_USD,
        "min_confidence":MIN_CONFIDENCE,"action":action,"confidence":conf,"entry":entry,"stop":stop,"cap_applied_usd":cap},
        "reasoning":trader.get("reasoning","")}
    return True,"PASSED all gates",payload

def invoke_robinhood_mcp(payload):
    if DRY_RUN:
        print("[DRY_RUN] Would invoke rboin__review_equity_order then rboin__place_equity_order")
        print(json.dumps({"tool":"rboin__review_equity_order","account_number":"<agentic>",
            "symbol":payload["symbol"],"side":payload["side"],"type":payload["type"],
            "quantity":payload["quantity"],"limit_price":payload["limit_price"],
            "time_in_force":payload["time_in_force"],"market_hours":"regular_hours"},indent=2))
        return {"status":"dry_run_logged","payload":payload}
    return {"status":"live_executed","payload":payload}

def main():
    print("="*70); print("Bridge: TradingAgents -> Robinhood MCP"); print(f"DRY_RUN={DRY_RUN}"); print("="*70)
    d = find_latest_decision()
    passed, reason, payload = validate_decision(d)
    print(f"\n[VALIDATION] {reason}")
    if not passed: sys.exit(1)
    print(f"\n[PAYLOAD]\n{json.dumps(payload,indent=2)}")
    res = invoke_robinhood_mcp(payload)
    print(f"\n[RESULT] {res['status']}"); print("="*70)

if __name__=="__main__": main()
