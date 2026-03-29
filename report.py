"""
Report generator: creates readable terminal output and saves reports to file.
"""

import os
from datetime import datetime
from tabulate import tabulate
from config.settings import REPORT_DIR
from fundamentals import format_mcap
from telegram_bot import send_report_to_telegram, is_telegram_configured
from export_json import save_scan_json, save_tiered_scan_json


def format_zone_brief(zones, zone_type="support"):
    """Format zone info as a brief string for table display."""
    if not zones:
        return "—"

    z = zones[0]  # Show closest zone
    stars = "*" * int(z["score"])
    touches = z["touches"]
    last = z["last_touch"].strftime("%b %Y") if hasattr(z["last_touch"], "strftime") else str(z["last_touch"])[:7]
    dist = z.get("distance_pct", "?")

    return f"{z['low']:.0f}-{z['high']:.0f} | {stars} ({touches}x, last: {last}) | {dist}% away"


def generate_terminal_report(scan_results, title=None, print_output=True):
    """Print a formatted report to terminal."""
    r = scan_results
    scan_time = r["scan_time"].strftime("%d %b %Y, %I:%M %p")

    header = title or "DAILY LEVEL SCAN REPORT"

    output = []
    output.append("")
    output.append("=" * 80)
    output.append(f"  {header} — {scan_time}")
    output.append(f"  Stocks scanned: {r['total_scanned']}")
    output.append("=" * 80)

    # --- FUNDAMENTAL VERDICT LEGEND ---
    output.append("")
    output.append("  FUNDAMENTAL VERDICT:")
    output.append("    STRONG = Low P/E + High ROE + Low Debt (best to buy near support)")
    output.append("    OK     = Decent fundamentals, worth considering")
    output.append("    WEAK   = Expensive / low ROE / high debt (be cautious)")
    output.append("")

    # --- NEAR SUPPORT (BUY ZONE) ---
    output.append(f"  NEAR STRONG SUPPORT — BUY ZONE ({len(r['near_support'])} stocks)")
    output.append("  " + "-" * 76)

    if r["near_support"]:
        table_data = []
        for s in r["near_support"]:
            f = s.get("fundamentals") or {}
            pe = f"{f['pe']}" if f.get("pe") else "—"
            roe = f"{f['roe']}%" if f.get("roe") else "—"
            de = f"{f['de']}" if f.get("de") is not None else "—"
            mcap = format_mcap(f.get("mcap_cr"))
            verdict = s.get("fund_verdict", "—")
            # Risk/Reward
            rr = s.get("risk_reward") or {}
            sl = f"{rr['stop_loss']:,.0f}" if rr.get("stop_loss") else "—"
            tgt = f"{rr['target']:,.0f}" if rr.get("target") else "—"
            rr_str = f"{rr['rr_ratio']}:1" if rr.get("rr_ratio") else "—"

            # Volume / Delivery / Confidence
            vol = s.get("vol_signal") or "—"
            del_pct = f"{s['delivery_pct']}%" if s.get("delivery_pct") is not None else "—"
            conf = s.get("confidence") or "—"

            # Win rate from backtest
            bt = s["near_support"][0].get("backtest") if s.get("near_support") else None
            if bt and bt.get("total", 0) > 0:
                wr = f"{bt['win_rate']:.0f}% ({bt['wins']}/{bt['total']})"
            else:
                wr = "—"

            table_data.append([
                s["symbol"],
                f"Rs.{s['current_price']:,.2f}",
                f"{s['day_change_pct']:+.1f}%",
                s["sector"],
                format_zone_brief(s["near_support"], "support"),
                sl,
                tgt,
                rr_str,
                vol,
                del_pct,
                conf,
                verdict,
                wr,
            ])

        output.append(tabulate(
            table_data,
            headers=["Stock", "Price", "Day Chg", "Sector", "Support Zone", "SL", "Tgt", "R:R", "Vol", "Del%", "Conf", "Fund.", "WR"],
            tablefmt="simple",
            stralign="left",
        ))
    else:
        output.append("  No stocks near strong support today.")

    # --- NEAR RESISTANCE (PROFIT BOOKING ZONE) ---
    output.append("")
    output.append(f"  NEAR RESISTANCE — PROFIT BOOKING ZONE ({len(r['near_resistance'])} stocks)")
    output.append("  " + "-" * 76)

    if r["near_resistance"]:
        table_data = []
        for s in r["near_resistance"]:
            f = s.get("fundamentals") or {}
            pe = f"{f['pe']}" if f.get("pe") else "—"
            roe = f"{f['roe']}%" if f.get("roe") else "—"
            de = f"{f['de']}" if f.get("de") is not None else "—"
            mcap = format_mcap(f.get("mcap_cr"))
            verdict = s.get("fund_verdict", "—")
            table_data.append([
                s["symbol"],
                f"Rs.{s['current_price']:,.2f}",
                f"{s['day_change_pct']:+.1f}%",
                s["sector"],
                format_zone_brief(s["near_resistance"], "resistance"),
                pe,
                roe,
                de,
                mcap,
                verdict,
            ])

        output.append(tabulate(
            table_data,
            headers=["Stock", "Price", "Day Chg", "Sector", "Resistance Zone", "P/E", "ROE", "D/E", "MCap", "Fund."],
            tablefmt="simple",
            stralign="left",
        ))
    else:
        output.append("  No stocks near strong resistance today.")

    # --- DEEP VALUE WATCHLIST ---
    deep_value = r.get("deep_value", [])
    falling_knife = r.get("falling_knife", [])

    if deep_value:
        output.append("")
        output.append(f"  DEEP VALUE WATCHLIST — BROKEN BELOW SUPPORT, GOOD FUNDAMENTALS ({len(deep_value)} stocks)")
        output.append("  (Price below all support zones — wait for base formation before buying)")
        output.append("  " + "-" * 76)

        table_data = []
        for s in deep_value:
            f = s.get("fundamentals") or {}
            pe = f"{f['pe']}" if f.get("pe") else "—"
            roe = f"{f['roe']}%" if f.get("roe") else "—"
            de = f"{f['de']}" if f.get("de") is not None else "—"
            mcap = format_mcap(f.get("mcap_cr"))
            verdict = s.get("fund_verdict", "—")
            low_dist = f"{s['near_52w_low_pct']:.1f}%" if s.get("near_52w_low_pct") is not None else "—"
            below = f"{s['below_support_pct']}%" if s.get("below_support_pct") else "—"
            table_data.append([
                s["symbol"],
                f"Rs.{s['current_price']:,.2f}",
                f"{s['day_change_pct']:+.1f}%",
                s["sector"],
                below,
                low_dist,
                pe,
                roe,
                de,
                mcap,
                verdict,
            ])

        output.append(tabulate(
            table_data,
            headers=["Stock", "Price", "Day Chg", "Sector", "Below Sup.", "From 52W Low", "P/E", "ROE", "D/E", "MCap", "Fund."],
            tablefmt="simple",
            stralign="left",
        ))

    if falling_knife:
        output.append("")
        output.append(f"  FALLING KNIFE — AVOID ({len(falling_knife)} stocks)")
        output.append("  (Broken all support + weak fundamentals — stay away)")
        output.append("  " + "-" * 76)

        table_data = []
        for s in falling_knife:
            f = s.get("fundamentals") or {}
            pe = f"{f['pe']}" if f.get("pe") else "—"
            roe = f"{f['roe']}%" if f.get("roe") else "—"
            de = f"{f['de']}" if f.get("de") is not None else "—"
            mcap = format_mcap(f.get("mcap_cr"))
            verdict = s.get("fund_verdict", "—")
            below = f"{s['below_support_pct']}%" if s.get("below_support_pct") else "—"
            table_data.append([
                s["symbol"],
                f"Rs.{s['current_price']:,.2f}",
                f"{s['day_change_pct']:+.1f}%",
                s["sector"],
                below,
                pe,
                roe,
                de,
                verdict,
            ])

        output.append(tabulate(
            table_data,
            headers=["Stock", "Price", "Day Chg", "Sector", "Below Sup.", "P/E", "ROE", "D/E", "Fund."],
            tablefmt="simple",
            stralign="left",
        ))

    # --- SECTOR STRENGTH ---
    output.append("")
    output.append("  SECTOR STRENGTH (% stocks above 200 DMA)")
    output.append("  " + "-" * 76)

    if r["sector_strength"]:
        sector_table = []
        for sector, strength in r["sector_strength"].items():
            bar = "#" * int(strength / 5)
            label = "STRONG" if strength >= 70 else "NEUTRAL" if strength >= 40 else "WEAK"
            sector_table.append([sector, f"{strength}%", bar, label])

        output.append(tabulate(
            sector_table,
            headers=["Sector", "Strength", "", "Verdict"],
            tablefmt="simple",
            stralign="left",
        ))

    # --- SUMMARY ---
    output.append("")
    output.append("  " + "=" * 76)
    output.append(f"  SUMMARY: {len(r['near_support'])} stocks in buy zone | "
                  f"{len(r['near_resistance'])} stocks in profit zone | "
                  f"{len(deep_value)} deep value | {len(falling_knife)} falling knife | "
                  f"{len(r['no_signal'])} no signal")
    output.append("  " + "=" * 76)
    output.append("")

    report_text = "\n".join(output)
    if print_output:
        print(report_text)
    return report_text


def generate_stock_detail(result):
    """Generate detailed level report for a single stock."""
    output = []
    s = result
    output.append(f"\n{'='*60}")
    output.append(f"  {s['symbol']} — {s['name']} ({s['sector']})")
    output.append(f"  Price: Rs.{s['current_price']:,.2f} | Day: {s['day_change_pct']:+.1f}%")
    output.append(f"  52W High: Rs.{s['week_52_high']:,.2f} | 52W Low: Rs.{s['week_52_low']:,.2f}")
    if s["dma_200"]:
        pos = "ABOVE" if s["is_above_200dma"] else "BELOW"
        output.append(f"  200 DMA: Rs.{s['dma_200']:,.2f} ({pos})")
    f = s.get("fundamentals") or {}
    if f:
        pe = f"{f['pe']}" if f.get("pe") else "—"
        roe = f"{f['roe']}%" if f.get("roe") else "—"
        de = f"{f['de']}" if f.get("de") is not None else "—"
        mcap = format_mcap(f.get("mcap_cr"))
        verdict = s.get("fund_verdict", "—")
        output.append(f"  P/E: {pe} | ROE: {roe} | D/E: {de} | MCap: {mcap} | Verdict: {verdict}")
    output.append(f"{'='*60}")

    output.append("\n  SUPPORT ZONES (2 Year History):")
    if s["all_support_zones"]:
        for z in s["all_support_zones"]:
            stars = "*" * int(z["score"])
            last = z["last_touch"].strftime("%b %Y") if hasattr(z["last_touch"], "strftime") else str(z["last_touch"])[:7]
            output.append(f"    Rs.{z['low']:,.0f} - {z['high']:,.0f}  "
                          f"{stars:6s}  Touched {z['touches']}x | Last: {last}")
    else:
        output.append("    No significant support zones found.")

    output.append("\n  RESISTANCE ZONES:")
    if s["all_resistance_zones"]:
        for z in s["all_resistance_zones"]:
            stars = "*" * int(z["score"])
            last = z["last_touch"].strftime("%b %Y") if hasattr(z["last_touch"], "strftime") else str(z["last_touch"])[:7]
            output.append(f"    Rs.{z['low']:,.0f} - {z['high']:,.0f}  "
                          f"{stars:6s}  Touched {z['touches']}x | Last: {last}")
    else:
        output.append("    No significant resistance zones found.")

    report_text = "\n".join(output)
    print(report_text)
    return report_text


def generate_tiered_report(tier1_results, tier2_results, send_telegram=False):
    """Generate combined report with Tier 1 and Tier 2 sections."""
    output_parts = []

    # Tier 1 — always print
    report1 = generate_terminal_report(tier1_results, title="TIER 1: NIFTY 50 + BANK NIFTY", print_output=True)
    output_parts.append(report1)

    if tier2_results:
        # Tier 2 — print
        report2 = generate_terminal_report(tier2_results, title="TIER 2: NIFTY 500 (REMAINING)", print_output=True)
        output_parts.append(report2)

        # Combined summary
        t1_sup = len(tier1_results["near_support"])
        t2_sup = len(tier2_results["near_support"])
        t1_res = len(tier1_results["near_resistance"])
        t2_res = len(tier2_results["near_resistance"])
        total_scanned = tier1_results["total_scanned"] + tier2_results["total_scanned"]

        summary = []
        summary.append("")
        summary.append("=" * 80)
        summary.append(f"  COMBINED SUMMARY — {total_scanned} stocks scanned")
        summary.append("=" * 80)
        summary.append(f"  Tier 1 (Nifty 50 + Bank Nifty): {t1_sup} buy zone | {t1_res} profit zone")
        summary.append(f"  Tier 2 (Nifty 500 remaining):   {t2_sup} buy zone | {t2_res} profit zone")
        summary.append(f"  Total:                          {t1_sup + t2_sup} buy zone | {t1_res + t2_res} profit zone")
        summary.append("=" * 80)
        summary.append("")
        combined_summary = "\n".join(summary)
        output_parts.append(combined_summary)
        print(combined_summary)
    else:
        print("\n  Tier 2 scan was skipped (no data). Only Tier 1 shown above.")

    full_report = "\n".join(output_parts)
    save_report(full_report, send_telegram=send_telegram)

    # Save JSON for dashboard
    save_tiered_scan_json(tier1_results, tier2_results)

    return full_report


def save_report(report_text, filename=None, send_telegram=True, scan_results=None):
    """Save report to a text file and send to Telegram if configured.

    Args:
        scan_results: optional dict from run_full_scan(); if provided, also saves JSON for dashboard.
    """
    os.makedirs(REPORT_DIR, exist_ok=True)
    if filename is None:
        filename = f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    filepath = os.path.join(REPORT_DIR, filename)

    with open(filepath, "w") as f:
        f.write(report_text)

    print(f"  Report saved to: {filepath}")

    # Save JSON for dashboard (standalone, non-tiered scans)
    if scan_results is not None:
        save_scan_json(scan_results)

    # Send to Telegram if configured
    if send_telegram and is_telegram_configured():
        send_report_to_telegram(report_text, filepath)

    return filepath
