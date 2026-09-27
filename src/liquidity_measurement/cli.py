import argparse
import asyncio
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="measure liquidity and check the feed")
    commands = parser.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="record a public BTC/USD feed")
    record.add_argument("--output", required=True)
    record.add_argument("--seconds", type=int, default=60)
    record.add_argument("--phase", choices=["development", "pilot", "evaluation"], default="development")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")
    from .collector import record_session
    from .pipeline import Pipeline
    pipeline = Pipeline(Path(args.output).with_name(Path(args.output).name + "-measures"))
    try:
        metadata = asyncio.run(record_session(args.output, args.seconds, args.phase, processor=pipeline.process))
    finally:
        pipeline.close()
    print(f"saved {metadata['phase']} session to {args.output}")


if __name__ == "__main__":
    main()
