"""
Smart allocation engine: given a budget, suggests where to invest
based on scanner results using expert positional trading principles.

Rules (how a veteran allocates):
1. Only buy near strong support — never chase
2. Prefer stocks in strong/neutral sectors over weak sectors
3. Higher zone score + more touches = higher conviction = more allocation
4. Max 30% of capital in a single stock
5. Prefer 3-5 concentrated positions over 10 tiny ones
6. Skip stocks where you can't buy at least 1 share
7. If nothing is near strong support — stay in cash. Don't force trades.
"""

from datetime import datetime
from tabulate import tabulate


SECTOR_WEIGHT = {
    "STRONG": 1.5,
    "NEUTRAL": 1.0,
    "WEAK": 0.5,
}


def get_sector_verdict(strength_pct):
    if strength_pct >= 70:
        return "STRONG"
    elif strength_pct >= 40:
        return "NEUTRAL"
    return "WEAK"


def score_candidate(stock, sector_strength):
    """
    Score a stock for allocation priority.
    Higher score = more capital allocated.
    """
    if not stock["near_support"]:
        return 0

    best_zone = stock["near_support"][0]
    zone_score = best_zone["score"]
    touches = best_zone["touches"]
    distance = best_zone.get("distance_pct", 99)

    # Base score from zone quality
    score = zone_score * 10  # 0-50

    # Bonus for more touches (institutional memory)
    score += min(touches, 10) * 2  # 0-20

    # Closer to support = better entry
    if distance < 0.5:
        score += 20
    elif distance < 1.0:
        score += 15
    elif distance < 2.0:
        score += 10
    elif distance < 3.0:
        score += 5

    # Sector strength multiplier
    sector = stock["sector"]
    sector_pct = sector_strength.get(sector, 0)
    verdict = get_sector_verdict(sector_pct)
    score *= SECTOR_WEIGHT[verdict]

    # Bonus if above 200 DMA (trend is friend)
    if stock.get("is_above_200dma"):
        score += 15

    # Penalty if too far below 200 DMA (catching falling knife)
    if stock.get("dma_200") and stock["current_price"] < stock["dma_200"] * 0.85:
        score *= 0.6

    return round(score, 1)


def _build_allocation_entry(c):
    """Build a single allocation entry dict for a candidate."""
    best_zone = c["near_support"][0]
    stop_loss = best_zone["low"] * 0.97  # 3% below support
    target = c["all_resistance_zones"][0]["center"] if c["all_resistance_zones"] else c["current_price"] * 1.15
    risk_pct = round((c["current_price"] - stop_loss) / c["current_price"] * 100, 1)
    reward_pct = round((target - c["current_price"]) / c["current_price"] * 100, 1)

    return {
        "symbol": c["symbol"],
        "name": c["name"],
        "sector": c["sector"],
        "price": c["current_price"],
        "score": c["alloc_score"],
        "support_zone": f"{best_zone['low']:.0f}-{best_zone['high']:.0f}",
        "zone_touches": best_zone["touches"],
        "zone_score": best_zone["score"],
        "distance_pct": best_zone.get("distance_pct", 0),
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "risk_pct": risk_pct,
        "reward_pct": reward_pct,
    }


def suggest_allocation(scan_results, budget):
    """
    Given scan results and a budget, suggest stock allocation.
    Splits into primary picks (strong/neutral sectors) and
    weak sector opportunities (shown with warnings).
    """
    near_support = scan_results["near_support"]
    sector_strength = scan_results["sector_strength"]

    if not near_support:
        return _no_opportunity_report(budget)

    # Score all candidates and split by sector strength
    primary_candidates = []
    weak_candidates = []

    for stock in near_support:
        score = score_candidate(stock, sector_strength)
        if score <= 0:
            continue
        if stock["current_price"] > budget:
            continue

        sector_pct = sector_strength.get(stock["sector"], 0)
        verdict = get_sector_verdict(sector_pct)
        entry = {**stock, "alloc_score": score, "sector_verdict": verdict}

        if verdict == "WEAK":
            weak_candidates.append(entry)
        else:
            primary_candidates.append(entry)

    if not primary_candidates and not weak_candidates:
        return _no_opportunity_report(budget)

    # Sort by score
    primary_candidates.sort(key=lambda x: x["alloc_score"], reverse=True)
    weak_candidates.sort(key=lambda x: x["alloc_score"], reverse=True)

    # --- Allocate primary picks (top 5) ---
    top = primary_candidates[:5]
    allocations = []
    remaining = budget

    if top:
        total_score = sum(c["alloc_score"] for c in top)
        max_per_stock = budget * 0.30

        for c in top:
            raw_alloc = (c["alloc_score"] / total_score) * budget
            alloc = min(raw_alloc, max_per_stock)

            shares = int(alloc // c["current_price"])
            if shares < 1:
                continue

            actual_cost = shares * c["current_price"]
            if actual_cost > remaining:
                shares = int(remaining // c["current_price"])
                if shares < 1:
                    continue
                actual_cost = shares * c["current_price"]

            remaining -= actual_cost
            entry = _build_allocation_entry(c)
            entry["shares"] = shares
            entry["cost"] = round(actual_cost, 2)
            entry["alloc_pct"] = round(actual_cost / budget * 100, 1)
            allocations.append(entry)

    # --- Build weak sector watchlist (no allocation, just flagged) ---
    weak_watchlist = []
    for c in weak_candidates[:10]:
        entry = _build_allocation_entry(c)
        # Determine warning reason
        sector_pct = sector_strength.get(c["sector"], 0)
        warnings = []
        if sector_pct == 0:
            warnings.append(f"Sector {c['sector']}: 0% stocks above 200 DMA — entire sector under pressure")
        else:
            warnings.append(f"Sector {c['sector']}: only {sector_pct}% above 200 DMA — weak momentum")
        if not c.get("is_above_200dma"):
            warnings.append("Stock below 200 DMA — counter-trend trade")
        if entry["risk_pct"] > 5:
            warnings.append(f"Wide stop loss ({entry['risk_pct']}%) — size smaller")
        entry["warnings"] = warnings
        weak_watchlist.append(entry)

    # Print report
    _print_allocation_report(budget, allocations, remaining, sector_strength, weak_watchlist)
    return allocations


def _no_opportunity_report(budget):
    print(f"\n{'='*70}")
    print(f"  INVESTMENT ALLOCATION — Rs.{budget:,.0f}")
    print(f"{'='*70}")
    print(f"\n  VERDICT: STAY IN CASH")
    print(f"  No stocks are near strong support right now.")
    print(f"  A veteran waits for the right setup. Patience IS the edge.")
    print(f"\n{'='*70}\n")
    return []


def _print_allocation_report(budget, allocations, remaining, sector_strength, weak_watchlist=None):
    print(f"\n{'='*70}")
    print(f"  INVESTMENT ALLOCATION — Budget: Rs.{budget:,.0f}")
    print(f"  {datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    print(f"{'='*70}")

    if not allocations and not weak_watchlist:
        print(f"\n  No suitable stocks found within budget.")
        print(f"  Keep the cash ready for better opportunities.\n")
        return

    # --- PRIMARY PICKS (strong/neutral sectors) ---
    if allocations:
        print(f"\n  RECOMMENDED BUYS (Strong/Neutral Sectors):")
        print(f"  {'-'*66}")

        table_data = []
        for a in allocations:
            stars = "*" * int(a["zone_score"])
            table_data.append([
                a["symbol"],
                f"Rs.{a['price']:,.0f}",
                a["shares"],
                f"Rs.{a['cost']:,.0f}",
                f"{a['alloc_pct']}%",
                f"{a['support_zone']} {stars} ({a['zone_touches']}x)",
                f"{a['distance_pct']}%",
            ])

        print(tabulate(
            table_data,
            headers=["Stock", "CMP", "Qty", "Cost", "Alloc", "Support Zone", "Dist"],
            tablefmt="simple",
            stralign="left",
        ))

        # Risk/Reward table
        print(f"\n  RISK / REWARD:")
        print(f"  {'-'*66}")

        rr_data = []
        for a in allocations:
            rr_ratio = round(a["reward_pct"] / a["risk_pct"], 1) if a["risk_pct"] > 0 else 0
            rr_label = "GOOD" if rr_ratio >= 2 else "OK" if rr_ratio >= 1.5 else "LOW"
            rr_data.append([
                a["symbol"],
                f"Rs.{a['price']:,.0f}",
                f"Rs.{a['stop_loss']:,.0f}",
                f"Rs.{a['target']:,.0f}",
                f"-{a['risk_pct']}%",
                f"+{a['reward_pct']}%",
                f"{rr_ratio}:1 ({rr_label})",
            ])

        print(tabulate(
            rr_data,
            headers=["Stock", "Entry", "Stop Loss", "Target", "Risk", "Reward", "R:R"],
            tablefmt="simple",
            stralign="left",
        ))
    else:
        print(f"\n  No picks from strong/neutral sectors today.")

    # --- WEAK SECTOR WATCHLIST ---
    if weak_watchlist:
        print(f"\n  {'='*66}")
        print(f"  WEAK SECTOR OPPORTUNITIES — HANDLE WITH CARE ({len(weak_watchlist)} stocks)")
        print(f"  These stocks are near strong support BUT their sector is weak.")
        print(f"  Higher risk, but can be big winners if sector turns around.")
        print(f"  {'='*66}")

        weak_table = []
        for w in weak_watchlist:
            stars = "*" * int(w["zone_score"])
            rr_ratio = round(w["reward_pct"] / w["risk_pct"], 1) if w["risk_pct"] > 0 else 0
            weak_table.append([
                w["symbol"],
                f"Rs.{w['price']:,.0f}",
                w["sector"],
                f"{w['support_zone']} {stars} ({w['zone_touches']}x)",
                f"{w['distance_pct']}%",
                f"{rr_ratio}:1",
            ])

        print(tabulate(
            weak_table,
            headers=["Stock", "CMP", "Sector", "Support Zone", "Dist", "R:R"],
            tablefmt="simple",
            stralign="left",
        ))

        # Print warnings per stock
        print(f"\n  WARNINGS:")
        for w in weak_watchlist:
            print(f"    {w['symbol']}:")
            for warning in w["warnings"]:
                print(f"      ! {warning}")

        print(f"\n  EXPERT ADVICE ON WEAK SECTOR PICKS:")
        print(f"    - Only buy if support zone has 4+ touches (proven level)")
        print(f"    - Use HALF position size compared to strong sector picks")
        print(f"    - Keep tighter stop loss (2% below support instead of 3%)")
        print(f"    - Best when: stock is at support AND sector shows early reversal signs")
        print(f"    - Worst when: sector is in freefall — even strong support can break")

    # --- SUMMARY ---
    total_invested = sum(a["cost"] for a in allocations) if allocations else 0
    total_risk = sum(a["cost"] * a["risk_pct"] / 100 for a in allocations) if allocations else 0

    print(f"\n  {'-'*66}")
    print(f"  Budget:         Rs.{budget:,.0f}")
    print(f"  Allocated:      Rs.{total_invested:,.0f} ({round(total_invested/budget*100, 1)}%)")
    print(f"  Cash Reserve:   Rs.{remaining:,.0f} ({round(remaining/budget*100, 1)}%)")
    print(f"  Max Risk:       Rs.{total_risk:,.0f} (if all stop losses hit)")
    weak_count = len(weak_watchlist) if weak_watchlist else 0
    print(f"  Watchlist:      {weak_count} weak-sector stocks to monitor")
    print(f"  {'-'*66}")

    # Expert notes
    print(f"\n  EXPERT NOTES:")
    if remaining > budget * 0.1:
        print(f"    - Rs.{remaining:,.0f} kept as cash reserve — good for averaging down if support is tested again")
    if allocations and any(a["risk_pct"] > 5 for a in allocations):
        risky = [a["symbol"] for a in allocations if a["risk_pct"] > 5]
        print(f"    - {', '.join(risky)}: wider stop loss — consider smaller position or wait for closer entry")
    strong_sectors = [s for s, v in sector_strength.items() if v >= 70]
    if strong_sectors:
        in_strong = [a["symbol"] for a in allocations if a["sector"] in strong_sectors]
        if in_strong:
            print(f"    - {', '.join(in_strong)}: in strong sector — higher conviction")
    if weak_watchlist:
        best_weak = weak_watchlist[0]
        print(f"    - Best weak-sector pick: {best_weak['symbol']} ({best_weak['sector']}) — "
              f"support at {best_weak['support_zone']} ({best_weak['zone_touches']}x touched)")
    print(f"    - Review positions weekly. Exit if weekly close breaks below stop loss.")
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import argparse
    from scanner import run_full_scan

    parser = argparse.ArgumentParser()
    parser.add_argument("budget", type=float, help="Amount to invest (in Rs.)")
    args = parser.parse_args()

    print(f"\n  Running scan first...")
    results = run_full_scan()
    suggest_allocation(results, args.budget)
