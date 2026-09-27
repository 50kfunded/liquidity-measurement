import unittest
from decimal import Decimal as D

from liquidity_measurement.book import OrderBook
from liquidity_measurement.metrics import displayed_cost, measure


class MetricsTests(unittest.TestCase):
    def test_walks_multiple_levels(self):
        value = displayed_cost([(D(101), D(5)), (D(102), D(5))], D(100), 1000, "buy")
        self.assertAlmostEqual(value["average_price"], 101.5)
        self.assertAlmostEqual(value["cost_bps"], 150)

    def test_insufficient_depth_has_no_invented_fill(self):
        value = displayed_cost([(D(101), D(1))], D(100), 1000, "buy")
        self.assertIsNone(value["cost_bps"])
        self.assertEqual(value["status"], "insufficient_depth")

    def test_incomplete_band_is_unavailable(self):
        book = OrderBook("coinbase")
        book.set_level("bid", 9999, 1)
        book.set_level("ask", 10001, 1)
        self.assertIsNone(measure(book)["depth_usd"])

    def test_sell_cost_is_positive_below_mid(self):
        value = displayed_cost([(D(99), D(10))], D(100), 1000, "sell")
        self.assertAlmostEqual(value["cost_bps"], 100)
