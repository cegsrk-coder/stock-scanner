"""
Volume trend analysis and confidence scoring for support zone trades.
"""

import pandas as pd


def analyze_volume_trend(daily_df):
    """
    Compare recent volume (5-day avg) vs baseline (20-day avg).
    Near support: decreasing volume = bullish (selling exhaustion),
    increasing volume = caution (distribution).

    Returns dict with vol_ratio, vol_signal.
    """
    if daily_df is None or len(daily_df) < 20:
        return {"vol_ratio": None, "vol_signal": "—"}

    vol = daily_df["Volume"].values
    avg_5 = vol[-5:].mean()
    avg_20 = vol[-20:].mean()

    if avg_20 == 0:
        return {"vol_ratio": None, "vol_signal": "—"}

    ratio = round(avg_5 / avg_20, 2)

    # Near support: low volume = selling drying up (bullish)
    if ratio < 0.8:
        signal = "↓ Bullish"
    elif ratio > 1.2:
        signal = "↑ Caution"
    else:
        signal = "→ Neutral"

    return {"vol_ratio": ratio, "vol_signal": signal}


def fetch_delivery_pct(symbol):
    """
    Fetch delivery percentage from NSE bhavcopy.
    Returns float (e.g. 52.3) or None if unavailable.

    Degrades gracefully — returns None on any failure.
    """
    import urllib.request

    # Try up to 6 calendar days back, skipping weekends
    for days_back in range(6):
        date = pd.Timestamp.now() - pd.Timedelta(days=days_back)
        if date.weekday() >= 5:  # skip Saturday/Sunday
            continue
        date_str = date.strftime("%d%m%Y")
        url = (
            f"https://archives.nseindia.com/products/content/"
            f"sec_bhavdata_full_{date_str}.csv"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                import csv
                import io
                text = resp.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(text))
                for row in reader:
                    sym = row.get(" SYMBOL", row.get("SYMBOL", "")).strip()
                    if sym == symbol:
                        del_pct = row.get(" DELIV_PER", row.get("DELIV_PER", "")).strip()
                        if del_pct:
                            return round(float(del_pct), 1)
        except Exception:
            continue

    return None


def calc_confidence(zone_score, vol_signal, delivery_pct):
    """
    Calculate confidence level for a support zone trade.

    HIGH:   zone_score >= 3.5 AND bullish volume AND delivery > 50%
    MEDIUM: zone_score >= 2.5 AND (bullish volume OR delivery > 40%)
    LOW:    everything else

    Gracefully handles None delivery_pct by ignoring that factor.
    """
    is_bullish_vol = vol_signal == "↓ Bullish"
    has_delivery = delivery_pct is not None
    high_delivery = delivery_pct is not None and delivery_pct > 50
    med_delivery = delivery_pct is not None and delivery_pct > 40

    if zone_score >= 3.5:
        if is_bullish_vol and (high_delivery or not has_delivery):
            return "HIGH"
        if is_bullish_vol or high_delivery:
            return "HIGH"

    if zone_score >= 2.5:
        if is_bullish_vol or med_delivery or not has_delivery:
            return "MEDIUM"

    if zone_score >= 2.0 and (is_bullish_vol and high_delivery):
        return "MEDIUM"

    return "LOW"
