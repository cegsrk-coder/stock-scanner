#!/usr/bin/env python3
"""
Stock Level Scanner — Daily support/resistance scanner for Nifty 50 & Bank Nifty stocks.

Usage:
    python main.py                  # Full scan of Tier 1 (60 stocks)
    python main.py --nifty500       # Full scan of all Nifty 500 (Tier 1 + Tier 2)
    python main.py --stock MARUTI   # Scan a single stock in detail
    python main.py --sector Banking # Scan stocks in a sector
    python main.py --schedule       # Run daily at 4:00 PM
"""

import argparse
import schedule
import time

from config.stocks import ALL_STOCKS, SECTORS
from scanner import run_full_scan, run_tiered_scan, scan_stock
from report import generate_terminal_report, generate_tiered_report, generate_stock_detail, save_report
from data_fetcher import get_5paisa_client
from portfolio import analyze_portfolio
from allocator import suggest_allocation
from nifty500 import get_nifty500_list


def scan_all(send_telegram=False):
    """Run full scan across Tier 1 stocks and generate report."""
    client = get_5paisa_client()
    results = run_full_scan(client=client)
    report = generate_terminal_report(results)
    save_report(report, send_telegram=send_telegram)

    if results["near_support"]:
        print("\n\n  DETAILED VIEW — STOCKS NEAR SUPPORT:")
        for s in results["near_support"][:10]:
            generate_stock_detail(s)

    return results


def scan_nifty500(send_telegram=False):
    """Run tiered scan: Tier 1 (Nifty 50 + Bank Nifty) then Tier 2 (remaining Nifty 500)."""
    client = get_5paisa_client()
    tier1, tier2 = run_tiered_scan(client=client)
    generate_tiered_report(tier1, tier2, send_telegram=send_telegram)

    # Show top 10 support picks from each tier
    if tier1["near_support"]:
        print("\n\n  DETAILED VIEW — TIER 1 STOCKS NEAR SUPPORT:")
        for s in tier1["near_support"][:10]:
            generate_stock_detail(s)

    if tier2 and tier2["near_support"]:
        print("\n\n  DETAILED VIEW — TIER 2 STOCKS NEAR SUPPORT:")
        for s in tier2["near_support"][:10]:
            generate_stock_detail(s)

    return tier1, tier2


def scan_single(symbol):
    """Scan a single stock and show detailed levels."""
    symbol = symbol.upper()

    # Check Tier 1 first, then Nifty 500
    stock_info = ALL_STOCKS.get(symbol)
    if not stock_info:
        nifty500 = get_nifty500_list()
        stock_info = nifty500.get(symbol)

    if not stock_info:
        print(f"  Error: {symbol} not found in Nifty 50, Bank Nifty, or Nifty 500.")
        return None

    client = get_5paisa_client()
    print(f"\n  Scanning {symbol} ({stock_info['name']})...")
    result = scan_stock(symbol, stock_info, client)

    if result:
        generate_stock_detail(result)
    else:
        print(f"  Could not fetch data for {symbol}.")

    return result


def scan_sector(sector_name):
    """Scan all stocks in a specific sector."""
    matched = None
    for sector in SECTORS:
        if sector.lower() == sector_name.lower():
            matched = sector
            break

    if not matched:
        print(f"  Error: Sector '{sector_name}' not found.")
        print(f"  Available sectors: {', '.join(sorted(SECTORS.keys()))}")
        return None

    symbols = SECTORS[matched]
    stock_universe = {s: ALL_STOCKS[s] for s in symbols if s in ALL_STOCKS}

    client = get_5paisa_client()
    results = run_full_scan(stock_universe=stock_universe, client=client)
    generate_terminal_report(results)
    return results


def run_scheduled():
    """Run the scanner on a daily schedule at 4:00 PM. Always sends to Telegram."""
    print(f"\n  Scheduler started. Will scan daily at 4:00 PM.")
    print(f"  Press Ctrl+C to stop.\n")

    schedule.every().day.at("16:00").do(scan_all, send_telegram=True)

    # Also run once immediately
    scan_all(send_telegram=True)

    while True:
        schedule.run_pending()
        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(
        description="Stock Level Scanner — Find stocks near support/resistance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    Scan Tier 1 (Nifty 50 + Bank Nifty)
  python main.py --nifty500         Scan all Nifty 500 (Tier 1 + Tier 2)
  python main.py --stock MARUTI     Detailed scan of any stock
  python main.py --stock ABB        Works for Nifty 500 stocks too
  python main.py --sector Banking   Scan all banking stocks
  python main.py --portfolio        Analyze your holdings against levels
  python main.py --invest 10000     Suggest where to invest Rs.10,000
  python main.py --invest 50000 --nifty500  Invest suggestions from full 500
  python main.py --schedule         Auto-scan daily at 4 PM
  python main.py --telegram         Send report to Telegram after scan
        """,
    )
    parser.add_argument("--stock", "-s", type=str, help="Scan a single stock (symbol)")
    parser.add_argument("--sector", type=str, help="Scan a specific sector")
    parser.add_argument("--portfolio", "-p", action="store_true", help="Analyze your portfolio against levels")
    parser.add_argument("--invest", type=float, metavar="AMOUNT", help="Suggest where to invest (e.g. --invest 10000)")
    parser.add_argument("--nifty500", action="store_true", help="Include full Nifty 500 (Tier 1 + Tier 2)")
    parser.add_argument("--schedule", action="store_true", help="Run daily at 4:00 PM")
    parser.add_argument("--telegram", "-t", action="store_true", help="Send report to Telegram after scan")

    args = parser.parse_args()

    print(f"\n  Mode: ", end="")
    if args.stock:
        print(f"Single stock ({args.stock})")
        scan_single(args.stock)
    elif args.sector:
        print(f"Sector ({args.sector})")
        scan_sector(args.sector)
    elif args.portfolio:
        print("Portfolio analysis")
        analyze_portfolio()
    elif args.invest and args.nifty500:
        print(f"Nifty 500 + Investment allocation (Rs.{args.invest:,.0f})")
        tier1, tier2 = scan_nifty500(send_telegram=args.telegram)
        combined = {
            "scan_time": tier1["scan_time"],
            "total_scanned": tier1["total_scanned"] + (tier2["total_scanned"] if tier2 else 0),
            "near_support": tier1["near_support"] + (tier2["near_support"] if tier2 else []),
            "near_resistance": tier1["near_resistance"] + (tier2["near_resistance"] if tier2 else []),
            "no_signal": tier1["no_signal"] + (tier2["no_signal"] if tier2 else []),
            "sector_strength": tier1["sector_strength"],
            "all_results": tier1["all_results"] + (tier2["all_results"] if tier2 else []),
        }
        suggest_allocation(combined, args.invest)
    elif args.invest:
        print(f"Tier 1 + Investment allocation (Rs.{args.invest:,.0f})")
        results = scan_all(send_telegram=args.telegram)
        suggest_allocation(results, args.invest)
    elif args.nifty500:
        print("NIFTY 500 FULL SCAN (Tier 1 + Tier 2)")
        scan_nifty500(send_telegram=args.telegram)
    elif args.schedule:
        print("Scheduled mode (daily at 4 PM + Telegram)")
        run_scheduled()
    else:
        print("NIFTY 500 FULL SCAN (Tier 1 + Tier 2) — default")
        scan_nifty500(send_telegram=args.telegram)


if __name__ == "__main__":
    main()
