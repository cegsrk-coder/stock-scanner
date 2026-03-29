from __future__ import annotations

import streamlit as st
import json
import os
import glob
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stock Level Scanner",
    page_icon="\U0001F4C8",
    layout="wide",
)

SCANS_DIR = Path(__file__).parent / "data" / "scans"


def _tradingview_link(symbol: str) -> str:
    """Return TradingView URL for an NSE stock."""
    return f"https://www.tradingview.com/chart/?symbol=NSE%3A{symbol}"


def _stock_detail_card(stock: dict):
    """Show stock details + TradingView link when a row is selected."""
    sym = stock.get("symbol", "")
    zone = stock.get("zone") or {}
    fund = stock.get("fundamentals") or {}

    tv_url = _tradingview_link(sym)

    col1, col2, col3 = st.columns([3, 3, 2])
    with col1:
        st.markdown(f"### {sym}")
        st.markdown(f"**{stock.get('name', '')}** | {stock.get('sector', '')}")
        price = stock.get("current_price", 0)
        chg = stock.get("day_change_pct", 0)
        chg_color = "#2ecc71" if chg >= 0 else "#e74c3c"
        st.markdown(
            f"Price: **\u20B9{price:,.1f}** "
            f'<span style="color:{chg_color}">({chg:+.1f}%)</span>',
            unsafe_allow_html=True,
        )

    with col2:
        if zone:
            st.markdown(f"**Zone:** \u20B9{zone.get('low', 0):,.0f} - \u20B9{zone.get('high', 0):,.0f}")
            st.markdown(f"**Touches:** {zone.get('touches', 0)}x | **Distance:** {zone.get('distance_pct', 0):.1f}%")
            bt = zone.get("backtest") or {}
            if bt.get("total", 0) > 0:
                st.markdown(f"**Win Rate:** {bt['win_rate']:.0f}% ({bt['wins']}/{bt['total']})")
        rr = stock.get("risk_reward") or {}
        if rr:
            st.markdown(f"**SL:** \u20B9{rr.get('stop_loss', 0):,.0f} | **Tgt:** \u20B9{rr.get('target', 0):,.0f} | **R:R:** {rr.get('rr_ratio', 0)}:1")
        pe = fund.get("pe", "-")
        roe = fund.get("roe", "-")
        de = fund.get("de", "-")
        st.markdown(f"**P/E:** {pe} | **ROE:** {roe} | **D/E:** {de}")
        vol_sig = stock.get("vol_signal")
        del_pct = stock.get("delivery_pct")
        conf = stock.get("confidence")
        if vol_sig or del_pct or conf:
            parts = []
            if vol_sig:
                parts.append(f"**Vol:** {vol_sig}")
            if del_pct is not None:
                parts.append(f"**Del%:** {del_pct}%")
            if conf:
                cc = {"HIGH": "#2ecc71", "MEDIUM": "#f39c12", "LOW": "#e74c3c"}.get(conf, "#aaa")
                parts.append(f'**Conf:** <span style="color:{cc}">{conf}</span>')
            st.markdown(" | ".join(parts), unsafe_allow_html=True)

    with col3:
        verdict = stock.get("fund_verdict", "")
        vc = {"STRONG": "#2ecc71", "OK": "#f39c12", "WEAK": "#e74c3c"}.get(verdict, "#aaa")
        st.markdown(f'<span style="color:{vc}; font-size:1.5em; font-weight:bold">{verdict}</span>', unsafe_allow_html=True)
        st.markdown(f"[Open TradingView Chart \u2197]({tv_url})")
        st.markdown(f"52W: \u20B9{stock.get('week_52_low', 0):,.0f} - \u20B9{stock.get('week_52_high', 0):,.0f}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _available_dates() -> list[str]:
    """Return scan dates sorted most-recent-first."""
    files = sorted(SCANS_DIR.glob("scan_*.json"), reverse=True)
    dates = []
    for f in files:
        stem = f.stem  # scan_2026-03-29
        date_str = stem.replace("scan_", "")
        dates.append(date_str)
    return dates


def _load_scan(date_str: str) -> dict | None:
    path = SCANS_DIR / f"scan_{date_str}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _fmt_mcap(val) -> str:
    """Format market cap in crores: 389513 -> '3.9L Cr', 45000 -> '45K Cr'."""
    if val is None or pd.isna(val):
        return "-"
    val = float(val)
    if val >= 100000:
        return f"{val / 100000:.1f}L Cr"
    elif val >= 1000:
        return f"{val / 1000:.0f}K Cr"
    else:
        return f"{val:.0f} Cr"


def _fmt_val(val, decimals=1, suffix="") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "-"
    return f"{val:.{decimals}f}{suffix}"


def _color_verdict(v: str) -> str:
    colors = {"STRONG": "#2ecc71", "OK": "#f39c12", "WEAK": "#e74c3c"}
    c = colors.get(v, "#aaa")
    return f"color: {c}; font-weight: bold"


def _color_change(v) -> str:
    if v is None or pd.isna(v):
        return ""
    return "color: #2ecc71" if v >= 0 else "color: #e74c3c"


def _build_df(stocks: list, extra_cols: list[str] | None = None, mode: str = "buy") -> pd.DataFrame:
    """Build a display DataFrame from a list of stock dicts.

    mode: 'buy' = buy zone columns, 'profit' = profit zone, 'broken' = deep value/falling knife.
    """
    if not stocks:
        return pd.DataFrame()

    rows = []
    for s in stocks:
        zone = s.get("zone") or {}
        zone_str = f"{int(zone['low'])}-{int(zone['high'])}" if zone.get("low") else "-"
        sym = s.get("symbol", "")
        tv_url = _tradingview_link(sym)

        row = {
            "Symbol": tv_url,
            "Price": s.get("current_price"),
            "Day Chg%": s.get("day_change_pct"),
            "Sector": s.get("sector", ""),
        }

        if mode == "buy":
            # Buy zone columns — full trading signals
            bt = zone.get("backtest") or {}
            wr_val = bt.get("win_rate") if bt.get("total", 0) > 0 else None
            rr = s.get("risk_reward") or {}
            row["Zone"] = zone_str
            row["Dist%"] = zone.get("distance_pct")
            row["SL"] = rr.get("stop_loss")
            row["Tgt"] = rr.get("target")
            row["R:R"] = rr.get("rr_ratio")
            row["Vol"] = s.get("vol_signal", "")
            row["Del%"] = s.get("delivery_pct")
            row["Conf"] = s.get("confidence", "")
            row["WR%"] = wr_val
            row["Verdict"] = s.get("fund_verdict", "")
        elif mode == "profit":
            # Profit zone — no R:R/SL/Tgt, just zone + vol/del
            row["Zone"] = zone_str
            row["Dist%"] = zone.get("distance_pct")
            row["Vol"] = s.get("vol_signal", "")
            row["Del%"] = s.get("delivery_pct")
            row["Verdict"] = s.get("fund_verdict", "")
        else:
            # Deep value / Falling knife columns
            if extra_cols and "Below Support%" in extra_cols:
                row["Below Sup%"] = s.get("below_support_pct")
            if extra_cols and "From 52W Low%" in extra_cols:
                row["From 52W Low%"] = s.get("near_52w_low_pct")
            row["Vol"] = s.get("vol_signal", "")
            row["Del%"] = s.get("delivery_pct")
            row["Verdict"] = s.get("fund_verdict", "")

        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def _style_table(df: pd.DataFrame):
    """Apply conditional styling to the dataframe."""
    if df.empty:
        return df.style

    def _style_row(row):
        styles = [""] * len(row)
        idx = row.index.tolist()

        if "Day Chg%" in idx:
            pos = idx.index("Day Chg%")
            v = row["Day Chg%"]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                styles[pos] = "color: #2ecc71" if v >= 0 else "color: #e74c3c"

        if "Conf" in idx:
            pos = idx.index("Conf")
            v = row["Conf"]
            colors = {"HIGH": "#2ecc71", "MEDIUM": "#f39c12", "LOW": "#e74c3c"}
            c = colors.get(v, "")
            if c:
                styles[pos] = f"color: {c}; font-weight: bold"

        if "R:R" in idx:
            pos = idx.index("R:R")
            v = row["R:R"]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                if v >= 2:
                    styles[pos] = "color: #2ecc71; font-weight: bold"
                elif v >= 1.5:
                    styles[pos] = "color: #f39c12"
                else:
                    styles[pos] = "color: #e74c3c"

        if "WR%" in idx:
            pos = idx.index("WR%")
            v = row["WR%"]
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                if v >= 60:
                    styles[pos] = "color: #2ecc71; font-weight: bold"
                elif v >= 40:
                    styles[pos] = "color: #f39c12"
                else:
                    styles[pos] = "color: #e74c3c"

        if "Verdict" in idx:
            pos = idx.index("Verdict")
            v = row["Verdict"]
            colors = {"STRONG": "#2ecc71", "OK": "#f39c12", "WEAK": "#e74c3c"}
            c = colors.get(v, "")
            if c:
                styles[pos] = f"color: {c}; font-weight: bold"

        return styles

    styled = df.style.apply(_style_row, axis=1)

    # Format numeric columns
    fmt = {}
    if "Price" in df.columns:
        fmt["Price"] = "{:.1f}"
    if "Day Chg%" in df.columns:
        fmt["Day Chg%"] = "{:+.2f}%"
    if "Dist%" in df.columns:
        fmt["Dist%"] = "{:.2f}%"
    if "P/E" in df.columns:
        fmt["P/E"] = "{:.1f}"
    if "ROE" in df.columns:
        fmt["ROE"] = "{:.1f}"
    if "D/E" in df.columns:
        fmt["D/E"] = "{:.1f}"
    if "SL" in df.columns:
        fmt["SL"] = "{:.0f}"
    if "Tgt" in df.columns:
        fmt["Tgt"] = "{:.0f}"
    if "R:R" in df.columns:
        fmt["R:R"] = "{:.1f}"
    if "Del%" in df.columns:
        fmt["Del%"] = "{:.1f}%"
    if "WR%" in df.columns:
        fmt["WR%"] = "{:.0f}%"
    if "Below Sup%" in df.columns:
        fmt["Below Sup%"] = "{:.1f}%"
    if "From 52W Low%" in df.columns:
        fmt["From 52W Low%"] = "{:.1f}%"

    styled = styled.format(fmt, na_rep="-")
    return styled


def _render_table(stocks: list, extra_cols: list[str] | None = None, key: str = "", mode: str = "buy"):
    """Render a styled, sortable stock table with clickable symbols."""
    df = _build_df(stocks, extra_cols, mode=mode)
    if df.empty:
        st.info("No stocks in this category.")
        return

    # Table with row selection and clickable Symbol links
    event = st.dataframe(
        _style_table(df),
        width="stretch",
        hide_index=True,
        height=min(35 * len(df) + 50, 600),
        on_select="rerun",
        selection_mode="single-row",
        key=f"df_{key}",
        column_config={
            "Symbol": st.column_config.LinkColumn(
                "Symbol",
                display_text=r"NSE%3A(.+?)$",
            ),
        },
    )

    # Show stock detail card when a row is clicked
    selected_rows = event.selection.rows if event.selection else []
    if selected_rows:
        idx = selected_rows[0]
        # Symbol column has the URL — match by index
        stock = stocks[idx] if idx < len(stocks) else None
        if stock:
            st.divider()
            _stock_detail_card(stock)


def _filter_stocks(stocks: list, sectors: list[str], verdicts: list[str]) -> list:
    """Filter stocks by sector and verdict selections."""
    filtered = stocks
    if sectors:
        filtered = [s for s in filtered if s.get("sector", "") in sectors]
    if verdicts:
        filtered = [s for s in filtered if s.get("fund_verdict", "") in verdicts]
    return filtered


def _compute_history(dates: list[str], max_lookback: int = 10) -> dict[str, int]:
    """
    Find stocks appearing in Buy Zone on consecutive recent days.
    Returns {symbol: consecutive_day_count}.
    """
    if not dates:
        return {}

    # Look at the most recent N dates
    recent = dates[:max_lookback]
    # Track per-symbol: list of dates it appeared in buy zone (ordered recent-first)
    symbol_dates: dict[str, list[str]] = {}
    for d in recent:
        scan = _load_scan(d)
        if scan is None:
            continue
        for s in scan.get("near_support", []):
            sym = s.get("symbol", "")
            if sym:
                symbol_dates.setdefault(sym, []).append(d)

    # Count consecutive days starting from the most recent date
    result = {}
    latest = recent[0]
    for sym, ds in symbol_dates.items():
        ds_set = set(ds)
        count = 0
        # Walk backwards from latest date
        check_date = datetime.strptime(latest, "%Y-%m-%d")
        for _ in range(max_lookback):
            if check_date.strftime("%Y-%m-%d") in ds_set:
                count += 1
                check_date -= timedelta(days=1)
            else:
                break
        if count >= 2:
            result[sym] = count

    # Sort by count descending
    return dict(sorted(result.items(), key=lambda x: -x[1]))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

dates = _available_dates()

if not dates:
    st.warning("No scan files found in `data/scans/`. Run the scanner first.")
    st.stop()

with st.sidebar:
    st.header("Filters")

    selected_date = st.selectbox("Scan Date", dates, index=0)

    scan = _load_scan(selected_date)
    if scan is None:
        st.error(f"Could not load scan for {selected_date}")
        st.stop()

    # Collect all sectors across all categories
    all_stocks = (
        scan.get("near_support", [])
        + scan.get("near_resistance", [])
        + scan.get("deep_value", [])
        + scan.get("falling_knife", [])
    )
    all_sectors = sorted(set(s.get("sector", "") for s in all_stocks if s.get("sector")))
    all_verdicts = sorted(set(s.get("fund_verdict", "") for s in all_stocks if s.get("fund_verdict")))

    sector_filter = st.multiselect("Sector", all_sectors)
    verdict_filter = st.multiselect("Verdict", all_verdicts if all_verdicts else ["STRONG", "OK", "WEAK"])

    st.divider()
    st.caption(f"Scan: {scan.get('scan_date', selected_date)}")
    st.caption(f"Stocks scanned: {scan.get('total_scanned', '-')}")


# ---------------------------------------------------------------------------
# Filtered data
# ---------------------------------------------------------------------------

buy_zone = _filter_stocks(scan.get("near_support", []), sector_filter, verdict_filter)
profit_zone = _filter_stocks(scan.get("near_resistance", []), sector_filter, verdict_filter)
deep_value = _filter_stocks(scan.get("deep_value", []), sector_filter, verdict_filter)
falling_knife = _filter_stocks(scan.get("falling_knife", []), sector_filter, verdict_filter)
sector_strength = scan.get("sector_strength", {})

# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("\U0001F4C8 Stock Level Scanner")
st.caption(f"Daily Scan Report \u2014 {scan.get('scan_date', selected_date)}")

# --- Header metrics ---
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Scanned", scan.get("total_scanned", 0))
m2.metric("Buy Zone", len(buy_zone))
m3.metric("Profit Zone", len(profit_zone))
m4.metric("Deep Value", len(deep_value))
m5.metric("Falling Knife", len(falling_knife))

st.divider()

# --- Tabs ---
tab_buy, tab_profit, tab_deep, tab_knife = st.tabs([
    f"\U0001F7E2 Buy Zone ({len(buy_zone)})",
    f"\U0001F7E1 Profit Zone ({len(profit_zone)})",
    f"\U0001F4A1 Deep Value ({len(deep_value)})",
    f"\U0001F534 Falling Knife ({len(falling_knife)})",
])

with tab_buy:
    st.subheader("Stocks Near Support")
    st.caption("These stocks are approaching strong demand zones where buyers have historically stepped in.")
    _render_table(buy_zone, key="buy")

with tab_profit:
    st.subheader("Stocks Near Resistance")
    st.caption("These stocks are approaching supply zones. Consider booking partial profits.")
    _render_table(profit_zone, key="profit", mode="profit")

with tab_deep:
    st.subheader("Deep Value Watchlist")
    st.caption("Stocks trading well below support with strong fundamentals. Potential deep value picks.")
    _render_table(deep_value, extra_cols=["Below Support%", "From 52W Low%"], key="deep", mode="broken")

with tab_knife:
    st.markdown(
        '<h3 style="color: #e74c3c;">Falling Knife - Avoid</h3>',
        unsafe_allow_html=True,
    )
    st.caption("Stocks in freefall with weak fundamentals. High risk of further downside.")
    _render_table(falling_knife, extra_cols=["Below Support%"], key="knife", mode="broken")

# --- Sector Strength ---
st.divider()
st.subheader("Sector Strength")

if sector_strength:
    # Prepare data
    sectors_sorted = sorted(sector_strength.items(), key=lambda x: x[1], reverse=True)
    sector_names = [s[0] for s in sectors_sorted]
    sector_vals = [s[1] for s in sectors_sorted]

    def _strength_label(v: float) -> str:
        if v >= 70:
            return "STRONG"
        elif v >= 40:
            return "NEUTRAL"
        return "WEAK"

    def _strength_color(v: float) -> str:
        if v >= 70:
            return "#2ecc71"
        elif v >= 40:
            return "#f1c40f"
        return "#e74c3c"

    # Build a horizontal bar chart using native streamlit column layout
    for name, val in sectors_sorted:
        label = _strength_label(val)
        color = _strength_color(val)
        col_label, col_bar, col_val = st.columns([2, 6, 2])
        with col_label:
            st.markdown(f"**{name}**")
        with col_bar:
            st.markdown(
                f'<div style="background: #1a1f2c; border-radius: 4px; height: 24px; width: 100%;">'
                f'<div style="background: {color}; width: {max(val, 2)}%; height: 24px; '
                f'border-radius: 4px;"></div></div>',
                unsafe_allow_html=True,
            )
        with col_val:
            st.markdown(
                f'<span style="color: {color}; font-weight: bold;">{val:.0f}% {label}</span>',
                unsafe_allow_html=True,
            )
else:
    st.info("No sector strength data available.")

# --- History Tracker ---
st.divider()
st.subheader("History Tracker")
st.caption("Stocks appearing in the Buy Zone on consecutive days (persistent opportunities).")

history = _compute_history(dates)
if history:
    for sym, count in history.items():
        # Find the stock details from current buy zone or any category
        detail = None
        for s in scan.get("near_support", []):
            if s.get("symbol") == sym:
                detail = s
                break

        trend_arrows = "\U0001F525" * min(count, 5)
        sector_tag = f" | {detail['sector']}" if detail and detail.get("sector") else ""
        price_tag = f" | \u20B9{detail['current_price']:.1f}" if detail and detail.get("current_price") else ""
        verdict_tag = ""
        if detail and detail.get("fund_verdict"):
            v = detail["fund_verdict"]
            vc = {"STRONG": "#2ecc71", "OK": "#f39c12", "WEAK": "#e74c3c"}.get(v, "#aaa")
            verdict_tag = f' | <span style="color:{vc}">{v}</span>'

        st.markdown(
            f"**{sym}** \u2014 in buy zone for **{count} days** {trend_arrows}"
            f"<span style='color:#888; font-size:0.85em;'>{sector_tag}{price_tag}{verdict_tag}</span>",
            unsafe_allow_html=True,
        )
else:
    st.info("Need at least 2 consecutive scan days to track history. Keep running daily scans!")
