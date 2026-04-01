"""
Data caching system: stores historical OHLCV data locally.
First run downloads full 2-year history. Subsequent runs only fetch new data.
"""

import os
import pandas as pd
from datetime import datetime, timedelta

CACHE_DIR = "data/cache"


def _cache_path(symbol):
    """Get cache file path for a symbol."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{symbol}.parquet")


def get_cached_data(symbol):
    """
    Load cached data for a symbol.
    Returns (DataFrame, last_date) or (None, None) if no cache.
    """
    path = _cache_path(symbol)
    if not os.path.exists(path):
        return None, None

    try:
        df = pd.read_parquet(path)
        if df.empty:
            return None, None
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        last_date = df["Datetime"].max()
        return df, last_date
    except Exception:
        return None, None


def save_to_cache(symbol, df):
    """Save DataFrame to cache."""
    if df is None or df.empty:
        return
    path = _cache_path(symbol)
    df.to_parquet(path, index=False)


def is_cache_fresh(symbol):
    """Check if cache has today's data (or last trading day if weekend/holiday)."""
    _, last_date = get_cached_data(symbol)
    if last_date is None:
        return False

    now = datetime.now()
    last_d = last_date.date() if hasattr(last_date, 'date') else last_date
    today = now.date()

    # Cache is fresh only if it contains data from the most recent trading day
    # Walk backwards from today to find the last expected trading day
    check = today
    # If before market close (3:30 PM IST), yesterday's data is OK
    if now.hour < 16:  # before 4 PM
        check = today - timedelta(days=1)
    # Skip weekends
    while check.weekday() >= 5:  # Saturday=5, Sunday=6
        check -= timedelta(days=1)

    return last_d >= check


def update_cache(symbol, fetch_func, full_period_years=2):
    """
    Smart cache update:
    - If no cache: full download
    - If cache exists but stale: fetch only missing days and append
    - If cache is fresh: return cached data

    fetch_func(symbol, from_date, to_date) -> DataFrame
    Returns the full DataFrame.
    """
    cached_df, last_date = get_cached_data(symbol)

    if cached_df is not None and is_cache_fresh(symbol):
        return cached_df

    if cached_df is not None and last_date is not None:
        # Incremental update: fetch from last cached date to today
        from_date = last_date + timedelta(days=1)
        to_date = datetime.now()

        if from_date >= to_date:
            return cached_df

        try:
            new_df = fetch_func(symbol, from_date, to_date)
            if new_df is not None and not new_df.empty:
                new_df["Datetime"] = pd.to_datetime(new_df["Datetime"])
                # Merge and deduplicate
                combined = pd.concat([cached_df, new_df]).drop_duplicates(
                    subset=["Datetime"], keep="last"
                ).sort_values("Datetime").reset_index(drop=True)
                save_to_cache(symbol, combined)
                return combined
        except Exception:
            pass

        return cached_df

    # Full download (no cache exists)
    from_date = datetime.now() - timedelta(days=full_period_years * 365)
    to_date = datetime.now()

    try:
        df = fetch_func(symbol, from_date, to_date)
        if df is not None and not df.empty:
            df["Datetime"] = pd.to_datetime(df["Datetime"])
            save_to_cache(symbol, df)
            return df
    except Exception:
        pass

    return None
