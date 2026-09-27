import unittest
from datetime import datetime, timezone

from liquidity_measurement.events import EventEngine


def rules():
    return {"venues": {v: {"spread_bps": 2, "depth_usd": 700} for v in ("kraken", "coinbase")},
            "persistence_seconds": 3, "merge_gap_seconds": 60, "comparison_seconds": 5,
            "baseline_seconds": 60, "minimum_baseline_samples": 20,
            "recovery_tolerance": .2, "recovery_seconds": 60}


def observation(second, kraken=1, coinbase=1, fault=None):
    values = {v: {"status": "valid", "reason": "checks passed", "spread_bps": spread,
                  "depth_usd": 1000, "displayed_cost": {}}
              for v, spread in (("kraken", kraken), ("coinbase", coinbase))}
    if fault:
        values[fault].update(status="failed_validation", reason="checksum mismatch")
    return {"time": datetime.fromtimestamp(1700000000 + second, timezone.utc).isoformat(),
            "session_id": "test", "venues": values}


class EventTests(unittest.TestCase):
    def scenario(self, second_venue=False, fault=None):
        engine = EventEngine(rules())
        for second in range(150):
            shock = 40 <= second < 50
            engine.add(observation(second, 4 if shock else 1,
                                   4 if shock and second_venue else 1, fault if shock else None))
        return engine.records(final=True)

    def test_healthy_single_venue_change(self):
        events = self.scenario()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["classification"], "venue_specific_liquidity_change")

    def test_both_venues_corroborate(self):
        self.assertEqual(self.scenario(True)[0]["classification"], "corroborated_liquidity_change")

    def test_fault_takes_priority_over_market_label(self):
        self.assertEqual(self.scenario(fault="kraken")[0]["classification"], "feed_problem")

    def test_short_sample_stays_uncertain(self):
        engine = EventEngine(rules())
        for second in range(10):
            engine.add(observation(second, 4, 1))
        self.assertEqual(engine.records(True)[0]["classification"], "uncertain")

    def test_session_ending_during_comparison_is_uncertain(self):
        engine = EventEngine(rules())
        for second in range(43):
            engine.add(observation(second, 4 if second >= 40 else 1))
        final = observation(43, fault="kraken")
        final["terminal"] = True
        engine.add(final)
        self.assertEqual(engine.records(True)[0]["classification"], "uncertain")

    def test_single_sample_on_other_venue_does_not_corroborate(self):
        engine = EventEngine(rules())
        for second in range(150):
            engine.add(observation(second, 4 if 40 <= second < 50 else 1, 4 if second == 42 else 1))
        self.assertEqual(engine.records(True)[0]["classification"], "venue_specific_liquidity_change")
