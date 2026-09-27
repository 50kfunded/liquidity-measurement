import json
import tempfile
import unittest
from pathlib import Path

from liquidity_measurement.analysis import replay
from liquidity_measurement.book import InvalidBook, OrderBook
from liquidity_measurement.demo import generate_session, make_book, wire_message
from liquidity_measurement.pipeline import Pipeline
from liquidity_measurement.rules import calibrate
from liquidity_measurement.storage import read_journal


class FaultTests(unittest.TestCase):
    def test_corrupted_checksum_requires_reset_and_snapshot(self):
        original = make_book()
        consumer = OrderBook("kraken")
        consumer.apply(json.dumps(wire_message("kraken", original, None, 0)))
        with self.assertRaises(InvalidBook):
            consumer.apply(json.dumps(wire_message("kraken", original, original, 1, corrupt=True)))
        with self.assertRaises(InvalidBook):
            consumer.apply(json.dumps(wire_message("kraken", original, None, 2)))
        consumer.reset()
        consumer.apply(json.dumps(wire_message("kraken", original, None, 3)))
        self.assertTrue(consumer.ready)

    def test_dropped_top_level_update_is_detected_on_next_checksum(self):
        consumer = OrderBook("kraken")
        before, after = make_book(), make_book(True)
        consumer.apply(json.dumps(wire_message("kraken", before, None, 0)))
        # drop the change, then send the next update with the exchange's new checksum.
        with self.assertRaises(InvalidBook):
            consumer.apply(json.dumps(wire_message("kraken", after, after, 2)))

    def test_replay_is_deterministic_and_separate_from_pilot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate_session(root / "pilot", "pilot", 0, 80)
            replay(root / "pilot", root / "pilot-measures")
            rules = calibrate(root / "pilot", root / "pilot-measures")
            rules["created_at"] = "2023-11-14T22:14:41+00:00"
            generate_session(root / "evaluation", "evaluation", 100, 400, rules)
            replay(root / "evaluation", root / "first")
            replay(root / "evaluation", root / "second")
            for name in ("observations.jsonl", "events.json", "summary.json"):
                self.assertEqual((root / "first" / name).read_bytes(), (root / "second" / name).read_bytes())
            events = json.loads((root / "first" / "events.json").read_text())
            self.assertEqual([e["classification"] for e in events], ["venue_specific_liquidity_change", "feed_problem"])
            self.assertEqual(events[0]["recovery"]["venues"]["kraken"]["spread_bps"]["seconds"], 20)

    def test_processing_backlog_requests_a_new_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate_session(root / "raw", "pilot", 0, 2)
            pipeline = Pipeline(root / "out", ("kraken", "coinbase"))
            try:
                for record in read_journal(root / "raw"):
                    if record["kind"] == "message" and record["venue"] == "kraken":
                        record["processing_delay_ms"] = 1500
                        self.assertEqual(pipeline.process(record), "kraken")
                        self.assertTrue(pipeline.feeds["kraken"].book.failed)
                        break
                    pipeline.process(record)
            finally:
                pipeline.close()
