"""
Daily scanner: scans all stocks in the universe and identifies
stocks near support/resistance zones.
"""

import pandas as pd
from datetime import datetime
from config.stocks import ALL_STOCKS
from config.settings import PROXIMITY_PCT, LOOKBACK_YEARS
from data_fetcher import fetch_stock_data, get_5paisa_client
from level_detector import detect_levels, check_proximity, backtest_zone_bounces
from fundamentals import get_fundamentals, fundamental_verdict
from allocator import calc_risk_reward
from volume_analysis import analyze_volume_trend, fetch_delivery_pct, calc_confidence
from nifty500 import get_tier2_stocks


def scan_stock(symbol, stock_info, client=None, bhavcopy_data=None):
    """
    Scan a single stock: fetch data, detect levels, check proximity.
    Returns a result dict or None if no actionable signal.
    """
    scrip_code = stock_info["scrip_code"]

    # Fetch data
    daily_df, weekly_df = fetch_stock_data(symbol, scrip_code, client, LOOKBACK_YEARS,
                                           bhavcopy_data=bhavcopy_data)

    if daily_df is None or weekly_df is None:
        return None

    # Detect levels
    levels = detect_levels(daily_df, weekly_df)

    # Backtest each support zone
    for zone in levels["support_zones"]:
        zone["backtest"] = backtest_zone_bounces(daily_df, zone)

    # Current price
    current_price = daily_df["Close"].iloc[-1]
    prev_close = daily_df["Close"].iloc[-2] if len(daily_df) > 1 else current_price
    day_change_pct = round((current_price - prev_close) / prev_close * 100, 2)

    # 52-week high/low
    one_year_data = daily_df[daily_df["Datetime"] >= (pd.Timestamp.now() - pd.Timedelta(days=365))]
    week_52_high = one_year_data["High"].max() if not one_year_data.empty else daily_df["High"].max()
    week_52_low = one_year_data["Low"].min() if not one_year_data.empty else daily_df["Low"].min()

    # 200 DMA
    dma_200 = None
    if len(daily_df) >= 200:
        dma_200 = round(daily_df["Close"].tail(200).mean(), 2)

    # Check proximity to support/resistance
    near_support = check_proximity(current_price, levels["support_zones"], PROXIMITY_PCT, direction="support")
    near_resistance = check_proximity(current_price, levels["resistance_zones"], PROXIMITY_PCT, direction="resistance")

    # Check if price has broken below all support zones
    broken_below_support = False
    below_support_pct = None
    if levels["support_zones"] and not near_support:
        lowest_support = min(z["low"] for z in levels["support_zones"])
        if current_price < lowest_support:
            broken_below_support = True
            below_support_pct = round((lowest_support - current_price) / lowest_support * 100, 1)

    # Risk/Reward for stocks near support
    risk_reward = None
    vol_data = None
    delivery_pct = None
    confidence = None
    if near_support:
        risk_reward = calc_risk_reward(current_price, near_support[0], levels["resistance_zones"])
        vol_data = analyze_volume_trend(daily_df)
        delivery_pct = fetch_delivery_pct(symbol)
        best_zone_score = near_support[0].get("score", 0)
        confidence = calc_confidence(best_zone_score, vol_data["vol_signal"], delivery_pct)
    elif near_resistance or broken_below_support:
        # Fetch volume/delivery for profit zone and deep value stocks too
        vol_data = analyze_volume_trend(daily_df)
        delivery_pct = fetch_delivery_pct(symbol)

    # Fetch fundamentals for actionable stocks (near zone or broken below support)
    fund = None
    fund_verdict = "—"
    if near_support or near_resistance or broken_below_support:
        fund = get_fundamentals(symbol)
        fund_verdict = fundamental_verdict(fund)

    # 52W low proximity
    near_52w_low_pct = round((current_price - week_52_low) / week_52_low * 100, 1) if week_52_low > 0 else None

    return {
        "symbol": symbol,
        "name": stock_info["name"],
        "sector": stock_info["sector"],
        "current_price": round(current_price, 2),
        "day_change_pct": day_change_pct,
        "week_52_high": round(week_52_high, 2),
        "week_52_low": round(week_52_low, 2),
        "dma_200": dma_200,
        "all_support_zones": levels["support_zones"],
        "all_resistance_zones": levels["resistance_zones"],
        "near_support": near_support,
        "near_resistance": near_resistance,
        "is_near_support": len(near_support) > 0,
        "is_near_resistance": len(near_resistance) > 0,
        "is_above_200dma": current_price > dma_200 if dma_200 else None,
        "broken_below_support": broken_below_support,
        "below_support_pct": below_support_pct,
        "near_52w_low_pct": near_52w_low_pct,
        "fundamentals": fund,
        "fund_verdict": fund_verdict,
        "risk_reward": risk_reward,
        "vol_signal": vol_data["vol_signal"] if vol_data else None,
        "delivery_pct": delivery_pct,
        "confidence": confidence,
    }


def run_full_scan(stock_universe=None, client=None):
    """
    Run the scanner across all stocks.
    Returns categorized results.
    """
    if stock_universe is None:
        stock_universe = ALL_STOCKS

    if client is None:
        client = get_5paisa_client()

    # Fetch bhavcopy once for all stocks (instant today-price patch)
    from bhavcopy_fetcher import get_today_bhavcopy
    bhavcopy_data = get_today_bhavcopy()
    if bhavcopy_data:
        print(f"  Bhavcopy: {len(bhavcopy_data)} stocks loaded for today")
    else:
        print(f"  Bhavcopy: not available (will use jugaad-data)")

    results = []
    total = len(stock_universe)

    print(f"\n{'='*60}")
    print(f"  STOCK LEVEL SCANNER — {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    print(f"  Scanning {total} stocks...")
    print(f"{'='*60}\n")

    for i, (symbol, info) in enumerate(stock_universe.items(), 1):
        print(f"  [{i}/{total}] Scanning {symbol}...", end=" ")
        try:
            result = scan_stock(symbol, info, client, bhavcopy_data=bhavcopy_data)
            if result:
                results.append(result)
                status = []
                if result["is_near_support"]:
                    status.append("NEAR SUPPORT")
                if result["is_near_resistance"]:
                    status.append("NEAR RESISTANCE")
                print(" | ".join(status) if status else "—")
            else:
                print("no data")
        except Exception as e:
            print(f"ERROR: {e}")

    # Categorize results
    near_support = [r for r in results if r["is_near_support"]]
    near_resistance = [r for r in results if r["is_near_resistance"]]
    broken_below = [r for r in results if r.get("broken_below_support")]
    no_signal = [r for r in results if not r["is_near_support"] and not r["is_near_resistance"] and not r.get("broken_below_support")]

    # Sort buy zone by confidence first, then distance
    conf_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, None: 3}
    near_support.sort(key=lambda r: (
        conf_order.get(r.get("confidence"), 3),
        r["near_support"][0]["distance_pct"] if r["near_support"] else 99,
    ))
    near_resistance.sort(key=lambda r: r["near_resistance"][0]["distance_pct"] if r["near_resistance"] else 99)

    # Split broken-below into deep value vs falling knife
    deep_value = [r for r in broken_below if r.get("fund_verdict") in ("STRONG", "OK")]
    falling_knife = [r for r in broken_below if r.get("fund_verdict") not in ("STRONG", "OK")]

    # Sort by how close to 52W low (most beaten down first)
    deep_value.sort(key=lambda r: r.get("near_52w_low_pct", 99))
    falling_knife.sort(key=lambda r: r.get("near_52w_low_pct", 99))

    # Sector strength (% of stocks above 200 DMA per sector)
    sector_strength = _calc_sector_strength(results)

    return {
        "scan_time": datetime.now(),
        "total_scanned": len(results),
        "near_support": near_support,
        "near_resistance": near_resistance,
        "deep_value": deep_value,
        "falling_knife": falling_knife,
        "no_signal": no_signal,
        "sector_strength": sector_strength,
        "all_results": results,
    }


def _calc_sector_strength(results):
    """Calculate sector strength from scan results."""
    sectors = {}
    for r in results:
        sec = r["sector"]
        if sec not in sectors:
            sectors[sec] = {"total": 0, "above": 0}
        if r["is_above_200dma"] is not None:
            sectors[sec]["total"] += 1
            if r["is_above_200dma"]:
                sectors[sec]["above"] += 1

    sector_strength = {}
    for sec, data in sectors.items():
        if data["total"] > 0:
            sector_strength[sec] = round(data["above"] / data["total"] * 100, 1)

    return dict(sorted(sector_strength.items(), key=lambda x: x[1], reverse=True))


def run_tiered_scan(client=None):
    """
    Run Tier 1 (Nifty 50 + Bank Nifty) then Tier 2 (remaining Nifty 500).
    Returns both results separately.
    """
    if client is None:
        client = get_5paisa_client()

    # --- TIER 1 ---
    print(f"\n{'='*60}")
    print(f"  TIER 1: NIFTY 50 + BANK NIFTY")
    print(f"{'='*60}")
    tier1_results = run_full_scan(stock_universe=ALL_STOCKS, client=client)

    # --- TIER 2 ---
    tier1_symbols = set(ALL_STOCKS.keys())
    tier2_universe = get_tier2_stocks(tier1_symbols)

    if not tier2_universe:
        print("  Could not fetch Nifty 500 list. Skipping Tier 2.")
        return tier1_results, None

    tier2_results = run_full_scan(stock_universe=tier2_universe, client=client)

    # Merge sector strength from both tiers for a complete picture
    all_results = tier1_results["all_results"] + tier2_results["all_results"]
    combined_sector_strength = _calc_sector_strength(all_results)
    tier1_results["sector_strength"] = combined_sector_strength
    tier2_results["sector_strength"] = combined_sector_strength

    return tier1_results, tier2_results
