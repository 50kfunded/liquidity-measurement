import json
import unittest
from decimal import Decimal

from liquidity_measurement.book import InvalidBook, OrderBook


class CoinbaseTests(unittest.TestCase):
    def test_updates_replace_absolute_size(self):
        book = OrderBook("coinbase")
        book.apply(json.dumps({"type": "snapshot", "product_id": "BTC-USD",
                               "bids": [["100", "2"], ["99", "1"]], "asks": [["101", "2"]]}))
        book.apply(json.dumps({"type": "l2update", "product_id": "BTC-USD",
                               "changes": [["buy", "100", "3"], ["buy", "99", "0"]]}))
        self.assertEqual(book.bids, {Decimal("100"): Decimal("3")})
        self.assertIsNone(book.checksum_ok)

    def test_crossed_book_is_invalid(self):
        with self.assertRaises(InvalidBook):
            OrderBook("coinbase").apply(json.dumps({"type": "snapshot", "product_id": "BTC-USD",
                                                    "bids": [["101", "1"]], "asks": [["100", "1"]]}))
