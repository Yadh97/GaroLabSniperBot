# Filename: performance_reporter.py

import json
import os
import time
from datetime import datetime

POSITIONS_FILE = "simulated_positions.json"
REPORT_FILE = "performance_summary.json"


def load_positions():
    if not os.path.exists(POSITIONS_FILE):
        return {}
    with open(POSITIONS_FILE, "r") as f:
        return json.load(f)


def summarize_performance(positions):
    closed = [p for p in positions.values() if p.get("status") == "closed"]
    open_ = [p for p in positions.values() if p.get("status") == "open"]

    result = {
        "total_trades": len(closed),
        "open_positions": len(open_),
        "winning_trades": 0,
        "losing_trades": 0,
        "avg_win_pct": 0.0,
        "avg_loss_pct": 0.0,
        "total_profit_sol": 0.0,
        "best_trade": None,
        "worst_trade": None,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    if not closed:
        return result

    profits = []
    losses = []

    for trade in closed:
        pnl = trade.get("pnl_percent", 0)
        if pnl >= 0:
            profits.append(pnl)
        else:
            losses.append(pnl)

    result["winning_trades"] = len(profits)
    result["losing_trades"] = len(losses)
    result["avg_win_pct"] = round(sum(profits) / len(profits), 2) if profits else 0.0
    result["avg_loss_pct"] = round(sum(losses) / len(losses), 2) if losses else 0.0
    result["total_profit_sol"] = round(sum([t.get("profit_sol", 0) for t in closed]), 4)

    if closed:
        result["best_trade"] = max(closed, key=lambda t: t.get("pnl_percent", 0))
        result["worst_trade"] = min(closed, key=lambda t: t.get("pnl_percent", 0))

    return result


def save_summary(summary):
    with open(REPORT_FILE, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[📊] Performance summary written to {REPORT_FILE}")


def generate_report():
    positions = load_positions()
    summary = summarize_performance(positions)
    save_summary(summary)


if __name__ == "__main__":
    generate_report()
