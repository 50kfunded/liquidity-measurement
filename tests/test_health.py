import unittest

from liquidity_measurement.pipeline import FeedState


class HealthTests(unittest.TestCase):
    def test_heartbeat_does_not_refresh_book(self):
        state = FeedState("coinbase")
        state.connected = state.book.ready = True
        state.last_message = 100
        state.last_book = 80
        self.assertEqual(state.health(100)[0], "delayed")

    def test_reconnect_waits_for_snapshot(self):
        state = FeedState("kraken")
        state.connected = True
        self.assertEqual(state.health(100)[0], "recovering")

    def test_checksum_failure_cannot_become_valid_from_heartbeat(self):
        state = FeedState("kraken")
        state.connected = True
        state.book.failed = True
        state.last_message = 100
        self.assertEqual(state.health(100)[0], "failed_validation")
