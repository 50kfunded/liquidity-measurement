import argparse
import asyncio
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="measure liquidity and check the feed")
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="record a public BTC/USD feed")
    record.add_argument("--output", required=True)
    record.add_argument("--seconds", type=int, default=60)
    record.add_argument("--phase", choices=["development", "pilot", "evaluation"], default="development")
    record.add_argument("--venues", nargs="+", choices=["kraken", "coinbase"], default=["kraken", "coinbase"])
    record.add_argument("--rules", help="frozen pilot thresholds; required for evaluation")
    chart = commands.add_parser("chart", help="plot saved spread, depth, and feed health")
    chart.add_argument("directory")
    chart.add_argument("--output", default="results/liquidity.png")
    pilot = commands.add_parser("calibrate", help="freeze rules from a pilot session")
    pilot.add_argument("session")
    pilot.add_argument("--measures")
    pilot.add_argument("--output", required=True)
    replay_parser = commands.add_parser("replay", help="rebuild measures and events from raw messages")
    replay_parser.add_argument("session")
    replay_parser.add_argument("--output", required=True)
    report_parser = commands.add_parser("report", help="reproduce the figures and research summary")
    report_parser.add_argument("directory")
    report_parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command in ("replay", "report"):
        from .analysis import replay, report
        if args.command == "replay":
            summary = replay(args.session, args.output)
        else:
            summary = report(args.directory, args.output)
        print(json.dumps(summary, indent=2))
        return
    if args.command == "chart":
        from .charts import plot_series, read_observations
        plot_series(read_observations(args.directory), args.output)
        print(f"saved chart to {args.output}")
        return
    if args.command == "calibrate":
        from .rules import calibrate
        from .storage import write_json
        measures = args.measures or str(Path(args.session).with_name(Path(args.session).name + "-measures"))
        if Path(args.output).exists():
            parser.error("choose a new rules file; frozen thresholds cannot be overwritten")
        write_json(args.output, calibrate(args.session, measures))
        print(f"saved fixed pilot rules to {args.output}")
        return
    if args.seconds <= 0:
        parser.error("seconds must be positive")
    rules = json.loads(Path(args.rules).read_text(encoding="utf-8")) if args.rules else None
    if args.phase == "evaluation" and rules is None:
        parser.error("evaluation requires --rules from a separate pilot")
    if rules and rules.get("synthetic"):
        parser.error("synthetic rules cannot be used for a live recording")
    from .collector import record_session
    from .pipeline import Pipeline
    if rules and set(args.venues) != set(rules["venues"]):
        parser.error("record the same venues used for pilot calibration")
    pipeline = Pipeline(Path(args.output).with_name(Path(args.output).name + "-measures"), args.venues, rules)
    try:
        metadata = asyncio.run(record_session(args.output, args.seconds, args.phase, args.venues,
                                              processor=pipeline.process, rules=rules))
    finally:
        pipeline.close()
    print(f"saved {metadata['phase']} session to {args.output}")


if __name__ == "__main__":
    main()
