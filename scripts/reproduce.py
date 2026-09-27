"""Reproduce the live sample and both explicitly synthetic case studies."""

import argparse
from pathlib import Path

from liquidity_measurement.analysis import replay, report
from liquidity_measurement.demo import demo

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="results/reproduced")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = Path(args.output).resolve()
if output.exists():
    parser.error("choose a fresh output directory")
replay(root / "recordings" / "evaluation-01", output / "live-measures")
report(output / "live-measures", output / "live-report")
demo(output / "synthetic")
print(f"reports and figures saved to {output}")
