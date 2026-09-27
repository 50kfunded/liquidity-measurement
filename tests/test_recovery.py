import unittest

from liquidity_measurement.recovery import recovery_time
from liquidity_measurement.storage import timestamp
from test_events import observation


class RecoveryTests(unittest.TestCase):
    def test_spread_recovers_after_ten_seconds(self):
        rows = [observation(t, 4 if t < 10 else 1) for t in range(100)]
        result = recovery_time(rows, "kraken", "spread_bps", 1, timestamp(rows[0]["time"]))
        self.assertEqual(result["seconds"], 10)
        self.assertEqual(result["confirmed_after_seconds"], 69)

    def test_gap_breaks_the_recovery_run(self):
        rows = [observation(t) for t in list(range(30)) + list(range(40, 80))]
        result = recovery_time(rows, "kraken", "spread_bps", 1, timestamp(rows[0]["time"]))
        self.assertEqual(result["status"], "not_observed_to_recover")
