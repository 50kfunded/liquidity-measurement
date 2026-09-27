"""Persisted triggers and inspectable evidence, including uncertain cases."""

import statistics

from .rules import triggers
from .storage import timestamp


class EventEngine:
    def __init__(self, rules):
        self.rules = rules
        self.rows = []
        self.candidates = {}
        self.seen_valid = set()
        self.events = []
        self.active = None

    def add(self, row):
        self.rows.append(row)
        if row.get("terminal"):
            return
        now = timestamp(row["time"])
        if self.active and now - self.active["last_trigger_seconds"] > self.rules["merge_gap_seconds"]:
            self.active["closed"] = True
            self.active = None
        for venue, value in row["venues"].items():
            if value["status"] == "valid":
                self.seen_valid.add(venue)
            found = triggers(value, self.rules["venues"][venue]) if venue in self.rules["venues"] else []
            fault = value["status"] != "valid" and venue in self.seen_valid
            if fault:
                self.candidates.pop(venue, None)
                self.trigger(row, venue, ["feed_health"], row["time"])
            elif found:
                candidate = self.candidates.get(venue)
                common = set(found) & set(candidate["measures"]) if candidate else set()
                if not candidate or now - candidate["last"] > 1.5 or not common:
                    candidate = {"first": row["time"], "started": now, "count": 0, "measures": found}
                else:
                    candidate["measures"] = sorted(common)
                candidate["count"] += 1
                candidate["last"] = now
                self.candidates[venue] = candidate
                if candidate["count"] >= self.rules["persistence_seconds"] and now - candidate["started"] >= self.rules["persistence_seconds"] - 1:
                    self.trigger(row, venue, candidate["measures"], candidate["first"])
            else:
                self.candidates.pop(venue, None)

    def trigger(self, row, venue, measures, first):
        if self.active is None:
            self.active = {"id": f"{row['session_id'][:8]}-{len(self.events) + 1:03d}",
                           "start": first, "detected_at": row["time"], "closed": False, "triggers": []}
            self.events.append(self.active)
        self.active["last_trigger"] = row["time"]
        self.active["last_trigger_seconds"] = timestamp(row["time"])
        value = row["venues"][venue]
        self.active["triggers"].append({"time": row["time"], "venue": venue,
                                         "measures": measures, "status": value["status"],
                                         "reason": value["reason"],
                                         "spread_bps": value.get("spread_bps"),
                                         "depth_usd": value.get("depth_usd"),
                                         "threshold": self.rules["venues"].get(venue)})

    def records(self, final=False):
        from .recovery import summarize_recovery
        records = [investigate(event, self.rows, self.rules, final) for event in self.events]
        for record in records:
            record["recovery"] = summarize_recovery(record, self.rules)
        return records


def baseline(rows, venue, start, rules):
    valid = [r["venues"].get(venue, {}) for r in rows
             if start - rules["baseline_seconds"] <= timestamp(r["time"]) < start
             and r["venues"].get(venue, {}).get("status") == "valid"]
    result = {"valid_samples": len(valid)}
    for key in ("spread_bps", "depth_usd"):
        values = [v[key] for v in valid if v.get(key) is not None]
        result[key] = statistics.median(values) if len(values) >= rules["minimum_baseline_samples"] else None
    result["displayed_cost"] = {}
    for size in ("1000", "5000", "10000"):
        result["displayed_cost"][size] = {}
        for side in ("buy", "sell"):
            values = [v.get("displayed_cost", {}).get(size, {}).get(side, {}).get("cost_bps") for v in valid]
            values = [v for v in values if v is not None]
            result["displayed_cost"][size][side] = statistics.median(values) if len(values) >= rules["minimum_baseline_samples"] else None
    return result


def investigate(event, rows, rules, final):
    start = timestamp(event["start"])
    end = timestamp(event["last_trigger"])
    window = rules["comparison_seconds"]
    evidence = [r for r in rows if start - window <= timestamp(r["time"]) <= start + window]
    affected = sorted({t["venue"] for t in event["triggers"]})
    bases = {v: baseline(rows, v, start, rules) for v in rules["venues"]}
    label, reason, confidence = "uncertain", "not enough healthy comparison coverage", "low"
    explicit_fault = any("feed_health" in t["measures"] for t in event["triggers"])
    if explicit_fault:
        label = "feed_problem"
        reason = "; ".join(sorted({t["reason"] for t in event["triggers"] if "feed_health" in t["measures"]}))
        confidence = "high_for_unusable_data"
    elif evidence:
        healthy = all(r["venues"].get(v, {}).get("status") == "valid" for r in evidence for v in ("kraken", "coinbase"))
        coverage = (timestamp(evidence[0]["time"]) <= start - window + 1.5
                    and timestamp(evidence[-1]["time"]) >= start + window - 1.5)
        own_invalid = any(r["venues"].get(v, {}).get("status") != "valid" for r in evidence for v in affected)
        if own_invalid:
            label, reason, confidence = "feed_problem", "triggering venue has unusable data in the comparison window", "high_for_unusable_data"
        elif healthy and coverage and all(bases[v]["valid_samples"] >= rules["minimum_baseline_samples"] for v in affected):
            breaches = {v: set(m for r in evidence for m in triggers(r["venues"][v], rules["venues"][v]))
                        for v in ("kraken", "coinbase")}
            comparable = breaches["kraken"] & breaches["coinbase"]
            if comparable:
                label = "corroborated_liquidity_change"
                reason = "both healthy venues breached fixed " + ", ".join(sorted(comparable)) + " rules within the comparison window"
            elif len(affected) == 1:
                label = "venue_specific_liquidity_change"
                reason = f"both feeds passed checks; only {affected[0]} showed a comparable threshold breach"
            else:
                reason = "venues triggered different measures; the changes are not directly corroborated"
            confidence = "moderate" if label != "uncertain" else "low"
    timeline = [r for r in rows if start - rules["baseline_seconds"] <= timestamp(r["time"]) <= end + 120]
    return {**{k: v for k, v in event.items() if k != "last_trigger_seconds"},
            "status": "closed" if event["closed"] else ("session_ended" if final else "open"),
            "classification": label, "confidence": confidence, "reason": reason,
            "affected_venues": affected, "comparison_seconds": window, "baseline": bases,
            "timeline": timeline, "limits": "two public venues; checks do not prove cause or executable prices"}
