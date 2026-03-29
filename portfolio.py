"""
Portfolio tracker: tracks your holdings and maps them against support/resistance levels.

If 5paisa credentials are configured, it auto-fetches your holdings.
Otherwise, you can manually define your portfolio in config/my_portfolio.py.
"""

import os
import json
from datetime import datetime
from tabulate import tabulate
from config.stocks import ALL_STOCKS
from scanner import scan_stock
from data_fetcher import get_5paisa_client

PORTFOLIO_FILE = "config/my_portfolio.json"


def load_portfolio():
    """
    Load portfolio from file or 5paisa API.
    Returns list of holdings: [{"symbol": str, "qty": int, "avg_price": float}, ...]
    """
    # Try 5paisa first
    client = get_5paisa_client()
    if client is not None:
        try:
            holdings = client.holdings()
            if holdings:
                portfolio = []
                for h in holdings:
                    portfolio.append({
                        "symbol": h.get("Symbol", h.get("ScripName", "")),
                        "qty": h.get("Qty", 0),
                        "avg_price": h.get("AvgRate", 0),
                    })
                return portfolio, client
        except Exception:
            pass

    # Fallback to local file
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f), client

    # No portfolio found — create template
    template = [
        {"symbol": "MARUTI", "qty": 10, "avg_price": 12800},
        {"symbol": "HDFCBANK", "qty": 50, "avg_price": 1650},
        {"symbol": "RELIANCE", "qty": 30, "avg_price": 1400},
    ]
    os.makedirs("config", exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(template, f, indent=2)
    print(f"  Created sample portfolio at {PORTFOLIO_FILE}")
    print(f"  Edit this file with your actual holdings.\n")
    return template, client


def analyze_portfolio():
    """
    Analyze portfolio holdings against support/resistance levels.
    """
    portfolio, client = load_portfolio()

    print(f"\n{'='*80}")
    print(f"  PORTFOLIO LEVEL ANALYSIS — {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    print(f"  Holdings: {len(portfolio)} stocks")
    print(f"{'='*80}\n")

    results = []
    total_invested = 0
    total_current = 0

    for holding in portfolio:
        symbol = holding["symbol"].upper()
        qty = holding["qty"]
        avg_price = holding["avg_price"]

        if symbol not in ALL_STOCKS:
            print(f"  {symbol}: Not in scanner universe, skipping.")
            continue

        print(f"  Scanning {symbol}...", end=" ")
        result = scan_stock(symbol, ALL_STOCKS[symbol], client)

        if result is None:
            print("no data")
            continue

        current_price = result["current_price"]
        pnl = (current_price - avg_price) * qty
        pnl_pct = (current_price - avg_price) / avg_price * 100
        invested = avg_price * qty
        current_val = current_price * qty

        total_invested += invested
        total_current += current_val

        # Determine action based on levels
        action = "HOLD"
        action_reason = ""

        if result["near_support"]:
            nearest = result["near_support"][0]
            if current_price < avg_price:
                action = "ADD MORE"
                action_reason = f"Near support ({nearest['distance_pct']}% away), averaging down"
            else:
                action = "HOLD"
                action_reason = f"Near support, level should hold"

        if result["near_resistance"]:
            nearest = result["near_resistance"][0]
            if pnl_pct > 10:
                action = "BOOK PARTIAL"
                action_reason = f"Near resistance ({nearest['distance_pct']}% away), {pnl_pct:.0f}% profit"
            elif pnl_pct > 0:
                action = "TRAIL SL"
                action_reason = f"Near resistance, protect profits"

        # Check if below key support (danger)
        if result["all_support_zones"]:
            strongest_support = result["all_support_zones"][0]
            if current_price < strongest_support["low"] * 0.97:
                action = "REVIEW"
                action_reason = f"Below strongest support, re-evaluate thesis"

        result["holding"] = {
            "qty": qty,
            "avg_price": avg_price,
            "invested": invested,
            "current_val": current_val,
            "pnl": pnl,
            "pnl_pct": round(pnl_pct, 2),
            "action": action,
            "action_reason": action_reason,
        }

        results.append(result)
        pnl_str = f"+Rs.{pnl:,.0f}" if pnl >= 0 else f"-Rs.{abs(pnl):,.0f}"
        print(f"Rs.{current_price:,.2f} | {pnl_pct:+.1f}% ({pnl_str}) | {action}")

    # Print summary table
    if results:
        print(f"\n  {'='*76}")
        print(f"  PORTFOLIO DASHBOARD")
        print(f"  {'='*76}\n")

        table_data = []
        for r in results:
            h = r["holding"]
            pnl_str = f"+{h['pnl']:,.0f}" if h["pnl"] >= 0 else f"{h['pnl']:,.0f}"
            table_data.append([
                r["symbol"],
                h["qty"],
                f"Rs.{h['avg_price']:,.0f}",
                f"Rs.{r['current_price']:,.0f}",
                f"{h['pnl_pct']:+.1f}%",
                f"Rs.{pnl_str}",
                h["action"],
            ])

        print(tabulate(
            table_data,
            headers=["Stock", "Qty", "Avg Price", "CMP", "P&L %", "P&L", "Action"],
            tablefmt="simple",
            stralign="left",
        ))

        total_pnl = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

        print(f"\n  {'─'*76}")
        print(f"  Total Invested:  Rs.{total_invested:,.0f}")
        print(f"  Current Value:   Rs.{total_current:,.0f}")
        pnl_label = "Profit" if total_pnl >= 0 else "Loss"
        print(f"  {pnl_label}:          Rs.{total_pnl:,.0f} ({total_pnl_pct:+.1f}%)")
        print(f"  {'─'*76}")

        # Action items
        actions = [(r["symbol"], r["holding"]["action"], r["holding"]["action_reason"])
                   for r in results if r["holding"]["action"] != "HOLD"]
        if actions:
            print(f"\n  ACTION ITEMS:")
            for symbol, action, reason in actions:
                print(f"    {symbol}: {action} — {reason}")

    return results


if __name__ == "__main__":
    analyze_portfolio()
