"""
Export scan results as JSON for the dashboard.
"""

import json
import os
import numpy as np
from datetime import datetime


SCAN_JSON_DIR = "data/scans"


class _NumpyEncoder(json.JSONEncoder):
    """Handle numpy types in JSON serialization."""
    def default(self, obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super().default(obj)


def _serialize_zone(zone):
    """Convert a zone dict to JSON-safe format."""
    return {
        "low": zone["low"],
        "high": zone["high"],
        "score": zone["score"],
        "touches": zone["touches"],
        "last_touch": (
            zone["last_touch"].strftime("%Y-%m-%d")
            if hasattr(zone["last_touch"], "strftime")
            else str(zone["last_touch"])
        ),
        "distance_pct": zone.get("distance_pct"),
        "backtest": zone.get("backtest"),
    }


def _serialize_stock(stock):
    """Convert a stock result dict to the JSON structure the dashboard needs."""
    f = stock.get("fundamentals") or {}
    zones = stock.get("near_support") or stock.get("near_resistance") or []

    entry = {
        "symbol": stock["symbol"],
        "name": stock["name"],
        "sector": stock["sector"],
        "current_price": stock["current_price"],
        "day_change_pct": stock["day_change_pct"],
        "zone": _serialize_zone(zones[0]) if zones else None,
        "fundamentals": {
            "pe": f.get("pe"),
            "roe": f.get("roe"),
            "de": f.get("de"),
            "mcap_cr": f.get("mcap_cr"),
        },
        "fund_verdict": stock.get("fund_verdict", "—"),
        "week_52_high": stock.get("week_52_high"),
        "week_52_low": stock.get("week_52_low"),
        "dma_200": stock.get("dma_200"),
        "is_above_200dma": stock.get("is_above_200dma"),
    }

    # Risk/Reward
    if stock.get("risk_reward"):
        entry["risk_reward"] = stock["risk_reward"]

    # Volume / Delivery / Confidence
    if stock.get("vol_signal"):
        entry["vol_signal"] = stock["vol_signal"]
    if stock.get("delivery_pct") is not None:
        entry["delivery_pct"] = stock["delivery_pct"]
    if stock.get("confidence"):
        entry["confidence"] = stock["confidence"]

    # Extra fields for deep_value / falling_knife
    if stock.get("below_support_pct") is not None:
        entry["below_support_pct"] = stock["below_support_pct"]
    if stock.get("near_52w_low_pct") is not None:
        entry["near_52w_low_pct"] = stock["near_52w_low_pct"]

    return entry


def save_scan_json(scan_results, filename=None):
    """
    Save scan results as a JSON file in data/scans/.

    Args:
        scan_results: dict returned by run_full_scan()
        filename: optional override; defaults to scan_YYYY-MM-DD.json

    Returns:
        path to the saved file
    """
    os.makedirs(SCAN_JSON_DIR, exist_ok=True)

    if filename is None:
        filename = f"scan_{datetime.now().strftime('%Y-%m-%d')}.json"

    scan_date = scan_results["scan_time"]
    if hasattr(scan_date, "strftime"):
        scan_date_str = scan_date.strftime("%Y-%m-%d %H:%M")
    else:
        scan_date_str = str(scan_date)

    payload = {
        "scan_date": scan_date_str,
        "total_scanned": scan_results["total_scanned"],
        "near_support": [_serialize_stock(s) for s in scan_results["near_support"]],
        "near_resistance": [_serialize_stock(s) for s in scan_results["near_resistance"]],
        "deep_value": [_serialize_stock(s) for s in scan_results.get("deep_value", [])],
        "falling_knife": [_serialize_stock(s) for s in scan_results.get("falling_knife", [])],
        "sector_strength": scan_results.get("sector_strength", {}),
    }

    filepath = os.path.join(SCAN_JSON_DIR, filename)
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2, cls=_NumpyEncoder)

    print(f"  JSON saved to: {filepath}")
    return filepath


def save_tiered_scan_json(tier1_results, tier2_results, filename=None):
    """
    Merge Tier 1 and Tier 2 scan results into a single JSON file.

    Args:
        tier1_results: dict from run_full_scan() for Nifty 50 + Bank Nifty
        tier2_results: dict from run_full_scan() for remaining Nifty 500 (can be None)
        filename: optional override; defaults to scan_YYYY-MM-DD.json

    Returns:
        path to the saved file
    """
    os.makedirs(SCAN_JSON_DIR, exist_ok=True)

    if filename is None:
        filename = f"scan_{datetime.now().strftime('%Y-%m-%d')}.json"

    scan_date = tier1_results["scan_time"]
    if hasattr(scan_date, "strftime"):
        scan_date_str = scan_date.strftime("%Y-%m-%d %H:%M")
    else:
        scan_date_str = str(scan_date)

    def _merge_lists(key):
        items = list(tier1_results.get(key, []))
        if tier2_results:
            items.extend(tier2_results.get(key, []))
        return [_serialize_stock(s) for s in items]

    total = tier1_results["total_scanned"]
    if tier2_results:
        total += tier2_results["total_scanned"]

    # Use combined sector strength (already merged in run_tiered_scan)
    sector_strength = tier1_results.get("sector_strength", {})

    payload = {
        "scan_date": scan_date_str,
        "total_scanned": total,
        "near_support": _merge_lists("near_support"),
        "near_resistance": _merge_lists("near_resistance"),
        "deep_value": _merge_lists("deep_value"),
        "falling_knife": _merge_lists("falling_knife"),
        "sector_strength": sector_strength,
        "tier1_count": tier1_results["total_scanned"],
        "tier2_count": tier2_results["total_scanned"] if tier2_results else 0,
    }

    filepath = os.path.join(SCAN_JSON_DIR, filename)
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2, cls=_NumpyEncoder)

    print(f"  JSON saved to: {filepath}")
    return filepath
