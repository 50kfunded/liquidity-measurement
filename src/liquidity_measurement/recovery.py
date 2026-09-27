"""Recovery requires an uninterrupted run of trustworthy observations."""

from .storage import timestamp


def recovery_time(timeline, venue, key, baseline, start, tolerance=.2, hold_seconds=60):
    if baseline is None or baseline <= 0:
        return {"status": "unavailable_baseline", "seconds": None}
    run = previous = None
    for row in timeline:
        now = timestamp(row["time"])
        if now < start or row.get("terminal"):
            continue
        value = row["venues"].get(venue, {})
        metric = value.get(key)
        valid = (value.get("status") == "valid" and metric is not None
                 and abs(metric - baseline) <= baseline * tolerance)
        if not valid:
            run = previous = None
            continue
        if run is None or previous is None or now - previous > 1.5:
            run = now
        previous = now
        if now - run >= hold_seconds - 1:
            return {"status": "recovered", "seconds": round(run - start, 3),
                    "confirmed_after_seconds": round(now - start, 3)}
    return {"status": "not_observed_to_recover", "seconds": None}


def summarize_recovery(event, rules):
    if event["classification"] not in ("corroborated_liquidity_change", "venue_specific_liquidity_change"):
        return {"status": "not_measured_for_untrustworthy_or_uncertain_event"}
    result = {"status": "measured", "tolerance": rules["recovery_tolerance"],
              "hold_seconds": rules["recovery_seconds"], "venues": {}}
    start = timestamp(event["start"])
    for venue in event["affected_venues"]:
        base = event["baseline"][venue]
        valid = [r["venues"][venue] for r in event["timeline"]
                 if timestamp(r["time"]) >= start and r["venues"][venue]["status"] == "valid"]
        summary = {}
        for key in ("spread_bps", "depth_usd"):
            summary[key] = recovery_time(event["timeline"], venue, key, base[key], start,
                                        rules["recovery_tolerance"], rules["recovery_seconds"])
        spreads = [v["spread_bps"] for v in valid if v.get("spread_bps") is not None]
        depths = [v["depth_usd"] for v in valid if v.get("depth_usd") is not None]
        summary["max_spread_increase_bps"] = max(0, max(spreads) - base["spread_bps"]) if spreads and base["spread_bps"] is not None else None
        summary["max_depth_reduction_fraction"] = max(0, 1 - min(depths) / base["depth_usd"]) if depths and base["depth_usd"] else None
        summary["peak_cost_increase_bps"] = {}
        for size in ("1000", "5000", "10000"):
            summary["peak_cost_increase_bps"][size] = {}
            for side in ("buy", "sell"):
                costs = [v.get("displayed_cost", {}).get(size, {}).get(side, {}).get("cost_bps") for v in valid]
                costs = [v for v in costs if v is not None]
                earlier = base["displayed_cost"][size][side]
                summary["peak_cost_increase_bps"][size][side] = max(0, max(costs) - earlier) if costs and earlier is not None else None
        summary["sensitivity"] = {
            str(tolerance): {key: recovery_time(event["timeline"], venue, key, base[key], start,
                                               tolerance, rules["recovery_seconds"])
                             for key in ("spread_bps", "depth_usd")}
            for tolerance in (.1, .2, .3)}
        result["venues"][venue] = summary
    return result
