"""
Fetches historical OHLCV data for NSE stocks.
Fallback chain: cache (with bhavcopy patch) → jugaad-data → stale cache.
5paisa available for local runs with TOTP auth.
"""

import time
import pandas as pd
from datetime import datetime, timedelta
from config.settings import FIVE_PAISA_CRED, CLIENT_CODE, LOOKBACK_YEARS
from cache import get_cached_data, save_to_cache, is_cache_fresh


# ---------------------------------------------------------------------------
# 5paisa (optional, local only)
# ---------------------------------------------------------------------------

def get_5paisa_client():
    """Initialize and authenticate 5paisa client."""
    if not FIVE_PAISA_CRED["APP_SOURCE"] or not CLIENT_CODE:
        return None

    try:
        from py5paisa import FivePaisaClient
        client = FivePaisaClient(cred=FIVE_PAISA_CRED)

        from config.settings import PIN
        totp = input("  Enter your TOTP code: ").strip()
        if not totp:
            print("  No TOTP entered. Using jugaad-data fallback.")
            return None

        client.get_totp_session(CLIENT_CODE, totp, PIN)
        print("  5paisa: Authenticated successfully.")
        return client
    except Exception as e:
        print(f"  5paisa: Auth failed ({e}). Using jugaad-data fallback.")
        return None


def fetch_historical_data_5paisa(client, scrip_code, period_years=LOOKBACK_YEARS):
    """Fetch daily OHLCV data from 5paisa for the given scrip code."""
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=period_years * 365)).strftime("%Y-%m-%d")

    df = client.historical_data(
        Exch="N",
        ExchangeSegment="C",
        ScripCode=scrip_code,
        time="1d",
        From=from_date,
        To=to_date,
    )

    if df is not None and not df.empty:
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        df = df.sort_values("Datetime").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# jugaad-data (primary source, scrapes NSE directly)
# ---------------------------------------------------------------------------

def _fetch_jugaad_data(symbol, from_date, to_date):
    """
    Fetch historical data from jugaad-data (NSE scraper).
    Same-day data available after market close (~3:45 PM IST).
    """
    try:
        from jugaad_data.nse import stock_df
    except ImportError:
        raise ImportError("Install jugaad-data: pip install jugaad-data")

    # jugaad-data expects datetime.date objects
    fd = from_date.date() if hasattr(from_date, "date") else from_date
    td = to_date.date() if hasattr(to_date, "date") else to_date

    df = stock_df(symbol=symbol, from_date=fd, to_date=td, series="EQ")

    if df is not None and not df.empty:
        # jugaad-data columns: DATE, OPEN, HIGH, LOW, CLOSE, VOLUME, etc.
        df = df.rename(columns={
            "DATE": "Datetime",
            "OPEN": "Open",
            "HIGH": "High",
            "LOW": "Low",
            "CLOSE": "Close",
            "VOLUME": "Volume",
        })

        standard_cols = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        for col in standard_cols:
            if col not in df.columns:
                if col == "Volume":
                    df["Volume"] = 0
                else:
                    return None

        df = df[standard_cols].copy()
        df["Datetime"] = pd.to_datetime(df["Datetime"]).dt.tz_localize(None)
        df = df.sort_values("Datetime").reset_index(drop=True)

    # Rate limit to avoid NSE blocking
    from config.settings import JUGAAD_DELAY_SECONDS
    time.sleep(JUGAAD_DELAY_SECONDS)

    return df


# ---------------------------------------------------------------------------
# Weekly conversion
# ---------------------------------------------------------------------------

def daily_to_weekly(df):
    """Convert daily OHLCV data to weekly candles."""
    df = df.copy()
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df.set_index("Datetime")

    weekly = df.resample("W").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()

    weekly = weekly.reset_index()
    return weekly


# ---------------------------------------------------------------------------
# Main fetch function
# ---------------------------------------------------------------------------

def fetch_stock_data(symbol, scrip_code, client=None, period_years=LOOKBACK_YEARS,
                     use_cache=True, bhavcopy_data=None):
    """
    Fetch historical data for a stock.
    Fallback chain: cache + bhavcopy patch → jugaad-data → stale cache.
    Returns (daily_df, weekly_df).
    """
    daily_df = None

    # Step 1: Check cache
    if use_cache:
        cached_df, last_date = get_cached_data(symbol)

        if cached_df is not None and is_cache_fresh(symbol):
            daily_df = cached_df

        elif cached_df is not None and last_date is not None:
            # Cache exists but stale — try to update

            # 1a. Try bhavcopy first (instant, no network per stock)
            if bhavcopy_data and symbol in bhavcopy_data:
                today_row = bhavcopy_data[symbol]
                today_dt = today_row["Datetime"]
                if today_dt > last_date:
                    new_row = pd.DataFrame([today_row])
                    daily_df = pd.concat([cached_df, new_row]).drop_duplicates(
                        subset=["Datetime"], keep="last"
                    ).sort_values("Datetime").reset_index(drop=True)
                    save_to_cache(symbol, daily_df)
                else:
                    daily_df = cached_df
            else:
                daily_df = cached_df  # Will try jugaad-data below

            # 1b. If still stale after bhavcopy, try jugaad-data incremental
            if daily_df is not None and not is_cache_fresh(symbol):
                from_date = last_date + timedelta(days=1)
                to_date = datetime.now()
                if from_date < to_date:
                    try:
                        new_df = _fetch_jugaad_data(symbol, from_date, to_date)
                        if new_df is not None and not new_df.empty:
                            daily_df = pd.concat([cached_df, new_df]).drop_duplicates(
                                subset=["Datetime"], keep="last"
                            ).sort_values("Datetime").reset_index(drop=True)
                            save_to_cache(symbol, daily_df)
                    except Exception:
                        pass  # Keep stale cache

    # Step 2: No cache — full download
    if daily_df is None:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_years * 365)

        # 2a. Try 5paisa (local runs with TOTP)
        if client is not None:
            try:
                daily_df = fetch_historical_data_5paisa(client, scrip_code, period_years)
            except Exception:
                pass

        # 2b. Try jugaad-data for full history
        if daily_df is None or daily_df.empty:
            try:
                daily_df = _fetch_jugaad_data(symbol, start_date, end_date)
            except Exception:
                pass

        # 2c. Patch with bhavcopy if today is missing
        if daily_df is not None and not daily_df.empty and bhavcopy_data and symbol in bhavcopy_data:
            today_row = bhavcopy_data[symbol]
            last_dt = daily_df["Datetime"].max()
            if today_row["Datetime"] > last_dt:
                new_row = pd.DataFrame([today_row])
                daily_df = pd.concat([daily_df, new_row]).drop_duplicates(
                    subset=["Datetime"], keep="last"
                ).sort_values("Datetime").reset_index(drop=True)

        # Save to cache
        if daily_df is not None and not daily_df.empty and use_cache:
            save_to_cache(symbol, daily_df)

    if daily_df is None or daily_df.empty:
        return None, None

    weekly_df = daily_to_weekly(daily_df)
    return daily_df, weekly_df
