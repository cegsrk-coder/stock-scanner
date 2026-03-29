"""
Fetches historical OHLCV data from 5paisa API.
Falls back to Yahoo Finance (yfinance) if 5paisa is not configured.
Uses local parquet cache for fast repeat scans.
"""

import pandas as pd
from datetime import datetime, timedelta
from config.settings import FIVE_PAISA_CRED, CLIENT_CODE, LOOKBACK_YEARS
from cache import get_cached_data, save_to_cache, is_cache_fresh


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
            print("  No TOTP entered. Using Yahoo Finance fallback.")
            return None

        client.get_totp_session(CLIENT_CODE, totp, PIN)
        print("  5paisa: Authenticated successfully.")
        return client
    except Exception as e:
        print(f"  5paisa: Auth failed ({e}). Using Yahoo Finance fallback.")
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


def _fetch_yfinance(symbol, from_date, to_date):
    """Fetch from Yahoo Finance between dates. Used by cache system."""
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("Install yfinance: pip install yfinance")

    ticker = f"{symbol}.NS"
    df = yf.download(ticker, start=from_date, end=to_date, progress=False)

    if df is not None and not df.empty:
        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] if col[1] == "" else col[0] for col in df.columns]
        df = df.rename(columns={"Date": "Datetime"})
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        df = df.sort_values("Datetime").reset_index(drop=True)

    return df


def fetch_historical_data_yfinance(symbol, period_years=LOOKBACK_YEARS):
    """Fetch daily OHLCV data from Yahoo Finance as fallback."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=period_years * 365)
    return _fetch_yfinance(symbol, start_date, end_date)


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


def fetch_stock_data(symbol, scrip_code, client=None, period_years=LOOKBACK_YEARS, use_cache=True):
    """
    Fetch historical data for a stock.
    Uses cache first, then 5paisa, then yfinance.
    Returns both daily and weekly DataFrames.
    """
    daily_df = None

    # Step 1: Check cache
    if use_cache:
        cached_df, last_date = get_cached_data(symbol)
        if cached_df is not None and is_cache_fresh(symbol):
            daily_df = cached_df
        elif cached_df is not None and last_date is not None:
            # Cache exists but stale — fetch only new data and append
            from_date = last_date + timedelta(days=1)
            to_date = datetime.now()
            if from_date < to_date:
                new_df = None
                if client is not None:
                    try:
                        new_df = fetch_historical_data_5paisa(client, scrip_code)
                    except Exception:
                        pass
                if new_df is None or new_df.empty:
                    try:
                        new_df = _fetch_yfinance(symbol, from_date, to_date)
                    except Exception:
                        pass
                if new_df is not None and not new_df.empty:
                    new_df["Datetime"] = pd.to_datetime(new_df["Datetime"])
                    daily_df = pd.concat([cached_df, new_df]).drop_duplicates(
                        subset=["Datetime"], keep="last"
                    ).sort_values("Datetime").reset_index(drop=True)
                    save_to_cache(symbol, daily_df)
                else:
                    daily_df = cached_df  # Use stale cache if update fails
            else:
                daily_df = cached_df

    # Step 2: No cache — full download
    if daily_df is None:
        # Try 5paisa first
        if client is not None:
            try:
                daily_df = fetch_historical_data_5paisa(client, scrip_code, period_years)
            except Exception as e:
                pass

        # Fallback to yfinance
        if daily_df is None or daily_df.empty:
            try:
                daily_df = fetch_historical_data_yfinance(symbol, period_years)
            except Exception as e:
                return None, None

        # Save to cache
        if daily_df is not None and not daily_df.empty and use_cache:
            save_to_cache(symbol, daily_df)

    if daily_df is None or daily_df.empty:
        return None, None

    weekly_df = daily_to_weekly(daily_df)
    return daily_df, weekly_df
