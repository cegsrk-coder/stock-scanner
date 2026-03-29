"""
Fetches fundamental data for stocks: P/E, ROE, Debt/Equity, Promoter Holding.
Caches fundamentals locally (refreshed weekly — fundamentals don't change daily).
"""

import os
import json
from datetime import datetime, timedelta

FUND_CACHE_FILE = "data/fundamentals_cache.json"
FUND_CACHE_EXPIRY_DAYS = 7  # Refresh weekly


def _load_fund_cache():
    if os.path.exists(FUND_CACHE_FILE):
        with open(FUND_CACHE_FILE, "r") as f:
            return json.load(f)
    return {"fetched_on": None, "data": {}}


def _save_fund_cache(cache):
    os.makedirs("data", exist_ok=True)
    with open(FUND_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def fetch_fundamentals_yfinance(symbol):
    """Fetch fundamental data from Yahoo Finance."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info

        pe = info.get("trailingPE") or info.get("forwardPE")
        roe = info.get("returnOnEquity")
        de = info.get("debtToEquity")
        mcap = info.get("marketCap")
        promoter = info.get("heldPercentInsiders")
        dividend_yield = info.get("dividendYield")
        book_value = info.get("bookValue")
        eps = info.get("trailingEps")
        pb = info.get("priceToBook")

        return {
            "pe": round(pe, 1) if pe else None,
            "roe": round(roe * 100, 1) if roe else None,
            "de": round(de, 2) if de else None,
            "mcap_cr": round(mcap / 1e7, 0) if mcap else None,  # Convert to crores
            "promoter_pct": round(promoter * 100, 1) if promoter else None,
            "div_yield": round(dividend_yield, 2) if dividend_yield else None,
            "book_value": round(book_value, 2) if book_value else None,
            "eps": round(eps, 2) if eps else None,
            "pb": round(pb, 2) if pb else None,
        }
    except Exception:
        return None


def get_fundamentals(symbol, force_refresh=False):
    """Get fundamentals for a stock, using cache when possible."""
    cache = _load_fund_cache()

    # Check if cache is fresh for this symbol
    if not force_refresh and symbol in cache["data"]:
        entry = cache["data"][symbol]
        cached_date = entry.get("cached_on")
        if cached_date:
            cached_dt = datetime.fromisoformat(cached_date)
            if datetime.now() - cached_dt < timedelta(days=FUND_CACHE_EXPIRY_DAYS):
                return entry["fundamentals"]

    # Fetch fresh
    fund = fetch_fundamentals_yfinance(symbol)
    if fund:
        cache["data"][symbol] = {
            "cached_on": datetime.now().isoformat(),
            "fundamentals": fund,
        }
        _save_fund_cache(cache)

    return fund


def get_fundamentals_batch(symbols):
    """Get fundamentals for multiple symbols. Returns dict {symbol: fundamentals}."""
    results = {}
    cache = _load_fund_cache()
    to_fetch = []

    # Check cache first
    for sym in symbols:
        if sym in cache["data"]:
            entry = cache["data"][sym]
            cached_date = entry.get("cached_on")
            if cached_date:
                cached_dt = datetime.fromisoformat(cached_date)
                if datetime.now() - cached_dt < timedelta(days=FUND_CACHE_EXPIRY_DAYS):
                    results[sym] = entry["fundamentals"]
                    continue
        to_fetch.append(sym)

    # Fetch missing ones
    for sym in to_fetch:
        fund = fetch_fundamentals_yfinance(sym)
        if fund:
            results[sym] = fund
            cache["data"][sym] = {
                "cached_on": datetime.now().isoformat(),
                "fundamentals": fund,
            }

    if to_fetch:
        _save_fund_cache(cache)

    return results


def format_mcap(mcap_cr):
    """Format market cap in crores to readable string."""
    if mcap_cr is None:
        return "—"
    if mcap_cr >= 100000:
        return f"{mcap_cr/100000:.1f}L Cr"
    elif mcap_cr >= 1000:
        return f"{mcap_cr/1000:.0f}K Cr"
    else:
        return f"{mcap_cr:.0f} Cr"


def fundamental_verdict(fund):
    """
    Quick verdict on fundamentals: STRONG / OK / WEAK.
    Used to add conviction to technical setups.
    """
    if not fund:
        return "—"

    score = 0
    reasons = []

    # P/E: < 15 cheap, 15-25 fair, > 25 expensive
    pe = fund.get("pe")
    if pe:
        if pe < 15:
            score += 2
            reasons.append("cheap P/E")
        elif pe < 25:
            score += 1
        elif pe > 40:
            score -= 1
            reasons.append("expensive")

    # ROE: > 15% good, > 20% great
    roe = fund.get("roe")
    if roe:
        if roe > 20:
            score += 2
            reasons.append("high ROE")
        elif roe > 15:
            score += 1
        elif roe < 10:
            score -= 1

    # D/E: < 0.5 low debt, > 1.5 high debt
    de = fund.get("de")
    if de is not None:
        if de < 0.5:
            score += 1
            reasons.append("low debt")
        elif de > 1.5:
            score -= 1
            reasons.append("high debt")

    # Dividend yield bonus
    div = fund.get("div_yield")
    if div and div > 1.5:
        score += 1

    if score >= 3:
        return "STRONG"
    elif score >= 1:
        return "OK"
    else:
        return "WEAK"
