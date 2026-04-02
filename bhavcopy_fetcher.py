"""
Fetches NSE CM Bhavcopy — official end-of-day data for ALL NSE stocks in one CSV.
Available by ~4:15-4:30 PM IST after market close.
"""

import io
import zipfile
import pandas as pd
import urllib.request
from datetime import datetime, timedelta

_BHAVCOPY_CACHE = {}


def fetch_bhavcopy(trade_date=None):
    """
    Download NSE CM bhavcopy for a given date.
    Returns dict: {symbol: {"Datetime": date, "Open": f, "High": f, "Low": f, "Close": f, "Volume": int}}
    Returns empty dict on failure (holiday, weekend, not yet published).
    """
    if trade_date is None:
        trade_date = datetime.now()

    date_str = trade_date.strftime("%Y%m%d")
    url = (
        f"https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "*/*",
        "Referer": "https://www.nseindia.com/",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            zip_bytes = resp.read()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_name = zf.namelist()[0]
            with zf.open(csv_name) as csv_file:
                df = pd.read_csv(csv_file)

        # Filter to equity series only
        series_col = None
        for col in df.columns:
            if "SctySrs" in col or "SERIES" in col.upper():
                series_col = col
                break
        if series_col:
            df = df[df[series_col].str.strip() == "EQ"]

        # Find column names (NSE uses various naming conventions)
        col_map = {}
        for col in df.columns:
            cl = col.strip().upper()
            if cl in ("TCKRSYMB", "SYMBOL", "TckrSymb"):
                col_map["symbol"] = col
            elif cl in ("OPNPRIC", "OPEN", "OpnPric"):
                col_map["Open"] = col
            elif cl in ("HGHPRIC", "HIGH", "HghPric"):
                col_map["High"] = col
            elif cl in ("LWPRIC", "LOW", "LwPric"):
                col_map["Low"] = col
            elif cl in ("CLSPRIC", "CLOSE", "ClsPric"):
                col_map["Close"] = col
            elif cl in ("TTLTRADGVOL", "VOLUME", "TtlTradgVol"):
                col_map["Volume"] = col
            elif cl in ("TRADDT", "DATE", "TradDt"):
                col_map["Datetime"] = col

        # Also try case-sensitive match
        for col in df.columns:
            stripped = col.strip()
            if stripped == "TckrSymb":
                col_map["symbol"] = col
            elif stripped == "OpnPric":
                col_map["Open"] = col
            elif stripped == "HghPric":
                col_map["High"] = col
            elif stripped == "LwPric":
                col_map["Low"] = col
            elif stripped == "ClsPric":
                col_map["Close"] = col
            elif stripped == "TtlTradgVol":
                col_map["Volume"] = col
            elif stripped == "TradDt":
                col_map["Datetime"] = col

        if "symbol" not in col_map:
            print(f"  Bhavcopy: could not find symbol column in {list(df.columns)[:10]}")
            return {}

        result = {}
        trade_dt = pd.Timestamp(trade_date.date())

        for _, row in df.iterrows():
            sym = str(row[col_map["symbol"]]).strip()
            try:
                result[sym] = {
                    "Datetime": trade_dt,
                    "Open": float(row[col_map.get("Open", "Open")]),
                    "High": float(row[col_map.get("High", "High")]),
                    "Low": float(row[col_map.get("Low", "Low")]),
                    "Close": float(row[col_map.get("Close", "Close")]),
                    "Volume": int(float(row[col_map.get("Volume", "Volume")])),
                }
            except (ValueError, KeyError):
                continue

        return result

    except Exception as e:
        print(f"  Bhavcopy: could not fetch for {date_str} ({e})")
        return {}


def get_today_bhavcopy():
    """
    Get today's bhavcopy. Cached at module level so it's fetched once per scan run.
    Tries today first, then yesterday (in case of holidays).
    """
    global _BHAVCOPY_CACHE

    today_str = datetime.now().strftime("%Y%m%d")
    if today_str in _BHAVCOPY_CACHE:
        return _BHAVCOPY_CACHE[today_str]

    # Try today
    data = fetch_bhavcopy()
    if data:
        _BHAVCOPY_CACHE[today_str] = data
        return data

    # Try yesterday (today might be a holiday)
    yesterday = datetime.now() - timedelta(days=1)
    data = fetch_bhavcopy(yesterday)
    if data:
        _BHAVCOPY_CACHE[today_str] = data
        return data

    _BHAVCOPY_CACHE[today_str] = {}
    return {}
