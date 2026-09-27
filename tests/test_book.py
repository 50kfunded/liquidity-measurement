import json
import unittest

from liquidity_measurement.book import InvalidBook, OrderBook


class KrakenBookTests(unittest.TestCase):
    def test_published_checksum_vector(self):
        # this is the example from kraken's checksum guide.
        bids = [("45283.5", "0.10000000"), ("45283.4", "1.54582015"),
                ("45282.1", "0.10000000"), ("45281.0", "0.10000000"),
                ("45280.3", "1.54592586"), ("45279.0", "0.07990000"),
                ("45277.6", "0.03310103"), ("45277.5", "0.30000000"),
                ("45277.3", "1.54602737"), ("45276.6", "0.15445238")]
        asks = [("45285.2", "0.00100000"), ("45286.4", "1.54571953"),
                ("45286.6", "1.54571109"), ("45289.6", "1.54560911"),
                ("45290.2", "0.15890660"), ("45291.8", "1.54553491"),
                ("45294.7", "0.04454749"), ("45296.1", "0.35380000"),
                ("45297.5", "0.09945542"), ("45299.5", "0.18772827")]
        book = OrderBook("kraken")
        for side, values in (("bid", bids), ("ask", asks)):
            for p, q in values:
                book.set_level(side, p, q)
        self.assertEqual(book.checksum(), 3310070434)

    def test_update_before_snapshot_and_sticky_failure(self):
        book = OrderBook("kraken")
        with self.assertRaises(InvalidBook):
            book.apply(json.dumps({"channel": "book", "type": "update", "data": [{"symbol": "BTC/USD"}]}))
        self.assertTrue(book.failed)
        with self.assertRaises(InvalidBook):
            book.apply(json.dumps({"channel": "book", "type": "snapshot", "data": [{}]}))
        book.reset()
        self.assertFalse(book.failed)

    def test_zero_removes_and_quantity_replaces(self):
        book = OrderBook("kraken")
        book.set_level("bid", "100", "2")
        book.set_level("bid", "100", "3")
        self.assertEqual(float(book.levels("bid")[0][1]), 3)
        book.set_level("bid", "100", "0")
        self.assertFalse(book.bids)

    def test_bad_numeric_quantity_invalidates_book(self):
        book = OrderBook("coinbase")
        with self.assertRaises(InvalidBook):
            book.set_level("bid", "100", "broken")
        self.assertTrue(book.failed)
