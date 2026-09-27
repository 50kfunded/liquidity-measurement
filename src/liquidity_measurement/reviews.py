"""Manual review is a separate record; never overwrite the automatic label."""

import csv
from pathlib import Path

LABELS = {"feed_problem", "corroborated_liquidity_change", "venue_specific_liquidity_change", "uncertain"}


def write_template(events, output):
    with Path(output).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["event_id", "automatic_label", "reviewed_label", "reviewer", "reason"])
        writer.writeheader()
        for event in events:
            writer.writerow({"event_id": event["id"], "automatic_label": event["classification"]})


def read_reviews(events, path):
    lookup = {event["id"]: event for event in events}
    reviews = {}
    if path is None:
        return reviews
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if not row.get("reviewed_label"):
                continue
            identity = row["event_id"]
            if identity not in lookup or identity in reviews:
                raise ValueError("manual review has an unknown or repeated event ID")
            if row["reviewed_label"] not in LABELS or not row.get("reviewer") or not row.get("reason"):
                raise ValueError("manual review needs a valid label, reviewer, and reason")
            reviews[identity] = row
    return reviews
