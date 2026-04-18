"""
Support/Resistance level detection engine.
Finds swing highs/lows, clusters them into zones, scores each zone.
"""

import numpy as np
import pandas as pd
from config.settings import ZONE_CLUSTER_PCT, MIN_TOUCHES


def find_swing_lows(df, window=5):
    """
    Find swing lows (local minima) in price data.
    A swing low is a point where the Low is lower than 'window' bars on each side.
    """
    lows = df["Low"].values
    swing_lows = []

    for i in range(window, len(lows) - window):
        is_swing = True
        for j in range(1, window + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing = False
                break
        if is_swing:
            swing_lows.append({
                "index": i,
                "date": df["Datetime"].iloc[i],
                "price": lows[i],
                "volume": df["Volume"].iloc[i],
            })

    return swing_lows


def find_swing_highs(df, window=5):
    """
    Find swing highs (local maxima) in price data.
    A swing high is a point where the High is higher than 'window' bars on each side.
    """
    highs = df["High"].values
    swing_highs = []

    for i in range(window, len(highs) - window):
        is_swing = True
        for j in range(1, window + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing = False
                break
        if is_swing:
            swing_highs.append({
                "index": i,
                "date": df["Datetime"].iloc[i],
                "price": highs[i],
                "volume": df["Volume"].iloc[i],
            })

    return swing_highs


def cluster_levels(swing_points, cluster_pct=ZONE_CLUSTER_PCT):
    """
    Cluster nearby swing points into zones.
    Points within cluster_pct% of each other are grouped together.
    Returns list of zones with: center price, touch count, dates, volumes.
    """
    if not swing_points:
        return []

    # Sort by price
    sorted_points = sorted(swing_points, key=lambda x: x["price"])
    zones = []
    used = set()

    for i, point in enumerate(sorted_points):
        if i in used:
            continue

        # Start a new cluster
        cluster = [point]
        used.add(i)

        for j in range(i + 1, len(sorted_points)):
            if j in used:
                continue
            cluster_max = max(p["price"] for p in cluster)
            pct_diff = abs(sorted_points[j]["price"] - cluster_max) / cluster_max * 100
            if pct_diff <= cluster_pct:
                cluster.append(sorted_points[j])
                used.add(j)

        prices = [p["price"] for p in cluster]
        zones.append({
            "low": min(prices),
            "high": max(prices),
            "center": np.mean(prices),
            "touches": len(cluster),
            "dates": [p["date"] for p in cluster],
            "volumes": [p["volume"] for p in cluster],
            "last_touch": max(p["date"] for p in cluster),
        })

    return zones


def score_zone(zone, current_price, avg_volume, total_weeks):
    """
    Score a support/resistance zone on a 1-5 scale.

    Factors:
    - Touch count: more touches = stronger
    - Recency: recent touches score higher
    - Volume: high volume on touches = institutional interest
    - Confluence: near round number bonus
    - Weekly close held: zone respected on closing basis
    """
    score = 0

    # Touch count (max 2 points)
    if zone["touches"] >= 4:
        score += 2
    elif zone["touches"] >= 3:
        score += 1.5
    elif zone["touches"] >= 2:
        score += 1

    # Recency — was there a touch in the last 6 months? (max 1 point)
    six_months_ago = pd.Timestamp.now() - pd.Timedelta(days=180)
    recent_touches = [d for d in zone["dates"] if d >= six_months_ago]
    if recent_touches:
        score += 1

    # Volume — were touches on above-average volume? (max 1 point)
    if avg_volume > 0:
        high_vol_touches = sum(1 for v in zone["volumes"] if v > avg_volume)
        if high_vol_touches >= len(zone["volumes"]) * 0.5:
            score += 1

    # Round number confluence (max 0.5 points)
    center = zone["center"]
    # Check if near a round number (multiples of 100 for stocks < 5000, 500 for > 5000)
    round_unit = 500 if center > 5000 else 100
    nearest_round = round(center / round_unit) * round_unit
    if abs(center - nearest_round) / center * 100 < 1:
        score += 0.5

    return min(round(score, 1), 5)


def detect_levels(daily_df, weekly_df):
    """
    Main function: detect support and resistance zones for a stock.

    Uses weekly data for swing detection (cleaner signals for positional trading)
    and daily data for volume confirmation.

    Returns dict with support_zones and resistance_zones, sorted by score.
    """
    if weekly_df is None or weekly_df.empty or len(weekly_df) < 20:
        return {"support_zones": [], "resistance_zones": []}

    # Use window=3 for weekly data (3 weeks on each side = ~6 week swing)
    swing_lows = find_swing_lows(weekly_df, window=3)
    swing_highs = find_swing_highs(weekly_df, window=3)

    # Also detect on daily with larger window for more granularity
    daily_swing_lows = []
    daily_swing_highs = []
    if daily_df is not None and len(daily_df) > 50:
        daily_swing_lows = find_swing_lows(daily_df, window=10)
        daily_swing_highs = find_swing_highs(daily_df, window=10)

    # Combine weekly and daily swing points
    all_lows = swing_lows + daily_swing_lows
    all_highs = swing_highs + daily_swing_highs

    # Cluster into zones
    support_zones = cluster_levels(all_lows)
    resistance_zones = cluster_levels(all_highs)

    # Filter: minimum touches
    support_zones = [z for z in support_zones if z["touches"] >= MIN_TOUCHES]
    resistance_zones = [z for z in resistance_zones if z["touches"] >= MIN_TOUCHES]

    # Get current price and average volume for scoring
    current_price = daily_df["Close"].iloc[-1] if daily_df is not None else weekly_df["Close"].iloc[-1]
    avg_volume = daily_df["Volume"].mean() if daily_df is not None else weekly_df["Volume"].mean()
    total_weeks = len(weekly_df)

    # Score each zone
    for zone in support_zones:
        zone["score"] = score_zone(zone, current_price, avg_volume, total_weeks)

    for zone in resistance_zones:
        zone["score"] = score_zone(zone, current_price, avg_volume, total_weeks)

    # Sort by score (highest first)
    support_zones.sort(key=lambda z: z["score"], reverse=True)
    resistance_zones.sort(key=lambda z: z["score"], reverse=True)

    # Keep top 5 zones each
    return {
        "support_zones": support_zones[:5],
        "resistance_zones": resistance_zones[:5],
    }


def backtest_zone_bounces(daily_df, zone, lookahead_days=10, bounce_pct=3.0):
    """
    For a support zone, check each historical touch to see if price
    bounced up by bounce_pct% within lookahead_days trading days.
    Returns {"wins": N, "total": N, "win_rate": float}.
    """
    if daily_df is None or daily_df.empty or not zone.get("dates"):
        return {"wins": 0, "total": 0, "win_rate": 0.0}

    dt_index = daily_df["Datetime"].values
    highs = daily_df["High"].values
    closes = daily_df["Close"].values

    wins = 0
    total = 0

    for touch_date in zone["dates"]:
        # Find nearest daily bar on or after the touch date
        touch_ts = pd.Timestamp(touch_date)
        matches = np.where(dt_index >= touch_ts.to_numpy())[0]
        if len(matches) == 0:
            continue

        idx = matches[0]
        # Need enough future bars to check
        if idx + lookahead_days >= len(daily_df):
            continue

        total += 1
        entry_close = closes[idx]
        future_high = highs[idx + 1 : idx + 1 + lookahead_days].max()

        if future_high >= entry_close * (1 + bounce_pct / 100):
            wins += 1

    win_rate = round(wins / total * 100, 1) if total > 0 else 0.0
    return {"wins": wins, "total": total, "win_rate": win_rate}


def check_proximity(current_price, zones, proximity_pct, direction=None):
    """
    Check if current price is within proximity_pct% of any zone.
    direction='support': price must be at or above zone low (not broken below).
    direction='resistance': price must be at or below zone high (not broken above).
    Returns list of zones that are 'active' (price is near them).
    """
    active = []
    for zone in zones:
        dist_to_low = abs(current_price - zone["low"]) / current_price * 100
        dist_to_high = abs(current_price - zone["high"]) / current_price * 100
        dist_to_center = abs(current_price - zone["center"]) / current_price * 100
        min_dist = min(dist_to_low, dist_to_high, dist_to_center)

        if min_dist <= proximity_pct:
            if direction == "support" and current_price < zone["low"]:
                continue
            if direction == "resistance" and current_price > zone["high"]:
                continue
            zone_copy = zone.copy()
            zone_copy["distance_pct"] = round(min_dist, 2)
            active.append(zone_copy)

    return active
