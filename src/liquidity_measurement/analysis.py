import hashlib
import json
from collections import Counter
from pathlib import Path

from .charts import plot_series, read_observations
from .pipeline import Pipeline
from .storage import read_journal, timestamp, write_json


def replay(session, output):
    session, output = Path(session).resolve(), Path(output).resolve()
    if output == session or session in output.parents:
        raise ValueError("keep replay output outside the raw recording directory")
    metadata = json.loads((session / "session.json").read_text(encoding="utf-8"))
    rules = metadata.get("rules")
    if metadata["phase"] == "evaluation":
        if not rules or rules["pilot_session_id"] == metadata["session_id"]:
            raise ValueError("evaluation requires rules fixed on a separate pilot session")
        if timestamp(rules["created_at"]) > timestamp(metadata["started_at"]):
            raise ValueError("evaluation rules were chosen after recording started")
        if rules.get("pilot_ended_at") and timestamp(rules["pilot_ended_at"]) >= timestamp(metadata["started_at"]):
            raise ValueError("pilot overlaps evaluation")
        if rules.get("synthetic", False) != metadata.get("synthetic", False):
            raise ValueError("synthetic and live research periods cannot be mixed")
    pipeline = Pipeline(output, metadata["venues"], rules)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in session.glob("*.jsonl.gz")}
    try:
        for record in read_journal(session):
            pipeline.process(record)
    finally:
        pipeline.close()
    write_json(output / "session.json", metadata)
    write_json(output / "raw_hashes.json", hashes)
    return summarize(output)


def summarize(directory, reviews_path=None):
    directory = Path(directory)
    rows = read_observations(directory)
    metadata_path = directory / "session.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    events_path = directory / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
    from .reviews import read_reviews
    reviews = read_reviews(events, reviews_path)
    total = timestamp(rows[-1]["time"]) - timestamp(rows[0]["time"]) if len(rows) > 1 else 0
    coverage = {}
    for venue in metadata.get("venues", sorted({v for r in rows for v in r["venues"]})):
        valid_seconds = 0
        complete_depth_seconds = 0
        for first, second in zip(rows, rows[1:]):
            interval = timestamp(second["time"]) - timestamp(first["time"])
            value = first["venues"].get(venue, {})
            if 0 < interval <= 1.5 and value.get("status") == "valid":
                valid_seconds += interval
                if value.get("depth_complete"):
                    complete_depth_seconds += interval
        coverage[venue] = {"valid_seconds": round(valid_seconds, 3),
                           "valid_fraction": valid_seconds / total if total else None,
                           "complete_depth_seconds": round(complete_depth_seconds, 3),
                           "states": dict(Counter(r["venues"].get(venue, {}).get("status", "absent") for r in rows))}
    counts_path = directory / "feed_counts.json"
    counts = json.loads(counts_path.read_text(encoding="utf-8")) if counts_path.exists() else {}
    result = {"phase": metadata.get("phase"), "synthetic": metadata.get("synthetic", False),
              "recorded_seconds": round(total, 3), "recorded_hours": total / 3600,
              "coverage": coverage, "feed_counts": counts,
              "reconnections": max(0, counts.get("connections", 0) - len(coverage)),
              "events": len(events), "classifications": dict(Counter(e["classification"] for e in events)),
              "manual_reviews": len(reviews), "changed_on_review": sum(
                  review["reviewed_label"] != next(e["classification"] for e in events if e["id"] == identity)
                  for identity, review in reviews.items()) if reviews else None}
    write_json(directory / "summary.json", result)
    return result


def report(directory, output, reviews_path=None):
    directory, output = Path(directory), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    summary = summarize(directory, reviews_path)
    rows = read_observations(directory)
    synthetic = summary["synthetic"]
    title = "Synthetic fault demonstration" if synthetic else "Recorded BTC/USD observations"
    plot_series(rows, output / "liquidity.png", title)
    events_path = directory / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
    from .reviews import read_reviews, write_template
    reviews = read_reviews(events, reviews_path)
    write_template(events, output / "manual-review-template.csv")
    lines = ["# Liquidity Measurement and Market Data Quality", "",
             "did displayed liquidity change, or did the feed become unreliable?", "",
             "**synthetic demonstration — these are artificial events, not market findings.**" if synthetic else
             "this is a small live recording. it does not establish event frequencies across markets.", "",
             f"phase: {summary['phase']}. recorded time: {summary['recorded_hours']:.4f} hours.", "",
             "![spread, depth, and feed checks](liquidity.png)", "",
             "| venue | valid time | complete 10 bps depth |", "|---|---:|---:|"]
    for venue, value in summary["coverage"].items():
        fraction = value["valid_fraction"]
        lines.append(f"| {venue} | {fraction:.2%} | {value['complete_depth_seconds']:.1f} seconds |")
    lines += ["", f"events: {len(events)}. checksum failures: {summary['feed_counts'].get('checksum_failures', 0)}. "
              f"reconnections: {summary['reconnections']}.", "",
              "## event records", ""]
    for event in events:
        plot_series(event["timeline"], output / f"{event['id']}.png", f"{title} · {event['classification']}")
        lines += [f"### {event['id']}", "", f"start: {event['start']}. last trigger: {event['last_trigger']}.", "",
                  f"classification: **{event['classification']}**. confidence: {event['confidence']}.", "",
                  event["reason"] + ".", "", f"![event evidence]({event['id']}.png)", "",
                  "recovery and peak changes:", "", "```json", json.dumps(event["recovery"], indent=2), "```", ""]
    if not events:
        lines += ["no events were detected with these fixed rules in this recording. "
                  "there are insufficient events to compare spread and depth recovery.", ""]
    review_text = (f"{len(reviews)} events were reviewed; {summary['changed_on_review']} labels changed on review."
                   if reviews else "no manual classification reviews have been recorded in this output.")
    lines += ["## manual review", "", review_text + " automated fault tests are a software check and are reported separately.", ""]
    for identity, review in reviews.items():
        lines += [f"- {identity}: {review['reviewed_label']} ({review['reviewer']}). {review['reason']}"]
    lines += ["",
              "## method and limits", "",
              "measurements use the first 100 levels per side. depth within 10 bps is unavailable unless both "
              "recorded sides reach the band boundary. displayed costs walk these levels for $1,000, $5,000, "
              "and $10,000 converted to BTC at the current mid-price.", "",
              "pilot rules use the 99th spread percentile and 1st depth percentile with minimum-change guards. "
              "liquidity triggers persist for 3 sampled seconds; neighbouring alerts merge within 60 seconds. "
              "classification compares both feeds within 5 seconds of the event start. recovery requires 60 "
              "consecutive one-second samples within 20% of the baseline; gaps break that run. 10% and 30% "
              "tolerances are also saved in each event record.", "",
              "Kraken CRC32 verifies the top 10 levels, not every recorded level. Coinbase has no equivalent "
              "book checksum here. heartbeat sequence numbers are not used as level2 update sequence numbers. "
              "neither feed proves that silent loss of every deeper-level update can be detected.", "",
              "the book can change before an order arrives. no fees, hidden liquidity, queue position, or "
              "actual fills are modelled. two healthy venues can corroborate a change, but they cannot prove "
              "a market-wide cause. periods outside recorded sessions have unknown coverage.", "",
              "full trigger values, thresholds, feed reasons, baselines, and timelines are saved in events.json."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(output / "summary.json", summary)
    write_json(output / "manual-reviews.json", reviews)
    return summary
