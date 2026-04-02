"""
Fetches Nifty 500 constituents dynamically from NSE.
Caches the list locally and refreshes weekly.
"""

import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

CACHE_FILE = "data/nifty500_list.json"
NSE_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
CACHE_EXPIRY_DAYS = 7  # Refresh list weekly (index rebalances quarterly)


def fetch_nifty500_from_nse():
    """Download Nifty 500 constituent list from NSE website."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "text/html,application/xhtml+xml",
    }
    r = requests.get(NSE_URL, headers=headers, timeout=15)
    r.raise_for_status()

    lines = r.text.strip().split("\n")
    stocks = {}

    for line in lines[1:]:  # Skip header
        parts = line.strip().split(",")
        if len(parts) >= 4:
            name = parts[0].strip()
            sector = parts[1].strip()
            symbol = parts[2].strip()
            stocks[symbol] = {
                "scrip_code": 0,  # Not used for jugaad-data/bhavcopy
                "name": name,
                "sector": sector,
            }

    return stocks


def get_nifty500_list(force_refresh=False):
    """
    Get Nifty 500 stock list. Uses cache if available and fresh.
    Returns dict of {symbol: {name, sector, scrip_code}}.
    """
    os.makedirs("data", exist_ok=True)

    # Check cache
    if not force_refresh and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)

        cached_date = datetime.fromisoformat(cache["fetched_on"])
        if datetime.now() - cached_date < timedelta(days=CACHE_EXPIRY_DAYS):
            print(f"  Nifty 500 list: loaded from cache ({len(cache['stocks'])} stocks, "
                  f"fetched {cached_date.strftime('%d %b %Y')})")
            return cache["stocks"]

    # Fetch fresh
    print("  Fetching Nifty 500 list from NSE...")
    try:
        stocks = fetch_nifty500_from_nse()
    except Exception as e:
        print(f"  Failed to fetch from NSE: {e}")
        # Try loading stale cache
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                cache = json.load(f)
            print(f"  Using stale cache ({len(cache['stocks'])} stocks)")
            return cache["stocks"]
        return {}

    # Save cache
    cache = {
        "fetched_on": datetime.now().isoformat(),
        "count": len(stocks),
        "stocks": stocks,
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"  Nifty 500 list: fetched {len(stocks)} stocks from NSE.")
    return stocks


def get_tier2_stocks(tier1_symbols):
    """
    Get Tier 2 stocks = Nifty 500 minus Tier 1 (Nifty 50 + Bank Nifty).
    """
    all_500 = get_nifty500_list()
    tier2 = {sym: info for sym, info in all_500.items() if sym not in tier1_symbols}
    print(f"  Tier 2 universe: {len(tier2)} stocks (Nifty 500 minus {len(tier1_symbols)} Tier 1)")
    return tier2


if __name__ == "__main__":
    stocks = get_nifty500_list(force_refresh=True)
    print(f"\nTotal: {len(stocks)} stocks")
    # Show sector distribution
    sectors = {}
    for s in stocks.values():
        sec = s["sector"]
        sectors[sec] = sectors.get(sec, 0) + 1
    for sec, count in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
        print(f"  {sec}: {count}")
