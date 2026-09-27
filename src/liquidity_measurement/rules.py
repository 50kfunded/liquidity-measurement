"""Calibrate once on pilot data. Evaluation never changes these rules."""

import hashlib
import json
import statistics
from pathlib import Path

from .charts import read_observations
from .storage import utc_now


def quantile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def calibrate(session, measures):
    metadata = json.loads((Path(session) / "session.json").read_text(encoding="utf-8"))
    if metadata["phase"] != "pilot":
        raise ValueError("thresholds must come from a separate pilot recording")
    rows = read_observations(measures)
    venues = {}
    for venue in metadata["venues"]:
        valid = [r["venues"][venue] for r in rows if r["venues"][venue]["status"] == "valid"]
        spread = [v["spread_bps"] for v in valid]
        depth = [v["depth_usd"] for v in valid if v.get("depth_usd") is not None]
        if len(spread) < 60:
            raise ValueError(f"{venue} needs at least 60 valid pilot observations")
        venues[venue] = {
            "spread_bps": max(quantile(spread, .99), statistics.median(spread) * 1.5),
            "depth_usd": min(quantile(depth, .01), statistics.median(depth) * .7) if len(depth) >= 60 else None,
            "pilot_spread_median": statistics.median(spread),
            "pilot_depth_median": statistics.median(depth) if depth else None,
            "valid_spread_samples": len(spread), "complete_depth_samples": len(depth),
        }
    result = {"schema": 1, "created_at": utc_now(), "pilot_session_id": metadata["session_id"],
              "pilot_ended_at": metadata.get("ended_at"), "synthetic": metadata.get("synthetic", False),
              "pilot_observations_sha256": hashlib.sha256((Path(measures) / "observations.jsonl").read_bytes()).hexdigest(),
              "venues": venues, "persistence_seconds": 3, "merge_gap_seconds": 60,
              "comparison_seconds": 5, "baseline_seconds": 60, "minimum_baseline_samples": 20,
              "recovery_tolerance": .2, "recovery_seconds": 60,
              "method": "pilot 99th/1st percentiles with 1.5x spread and 0.7x depth guards"}
    return result


def triggers(value, threshold):
    if value.get("status") != "valid":
        return []
    found = []
    if value.get("spread_bps", 0) > threshold["spread_bps"]:
        found.append("spread_bps")
    if threshold.get("depth_usd") is not None and value.get("depth_usd") is not None:
        if value["depth_usd"] < threshold["depth_usd"]:
            found.append("depth_usd")
    return found
