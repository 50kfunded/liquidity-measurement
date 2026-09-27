"""Decimal books with sticky invalidation until the next connection snapshot."""

import json
import zlib
from decimal import Decimal, InvalidOperation


class InvalidBook(ValueError):
    pass


class OrderBook:
    def __init__(self, venue, depth=100):
        self.venue = venue
        self.depth = depth
        self.reset()

    def reset(self):
        self.bids = {}
        self.asks = {}
        self.ready = False
        self.failed = False
        self.reason = "waiting for snapshot"
        self.checksum_ok = None

    def invalidate(self, reason):
        self.ready = False
        self.failed = True
        self.reason = reason
        raise InvalidBook(reason)

    def levels(self, side, limit=None):
        values = self.bids if side == "bid" else self.asks
        return sorted(values.items(), reverse=side == "bid")[:limit]

    def set_level(self, side, price, quantity):
        try:
            price, quantity = Decimal(str(price)), Decimal(str(quantity))
        except InvalidOperation:
            self.invalidate("invalid numeric price/quantity")
        if not price.is_finite() or not quantity.is_finite() or price <= 0 or quantity < 0:
            self.invalidate("non-finite or invalid price/quantity")
        levels = self.bids if side == "bid" else self.asks
        if quantity == 0:
            levels.pop(price, None)
        else:
            levels[price] = quantity

    def checksum(self):
        def digits(value):
            return format(value, "f").replace(".", "").lstrip("0") or "0"
        text = "".join(digits(p) + digits(q) for side in ("ask", "bid")
                       for p, q in self.levels(side, 10))
        return zlib.crc32(text.encode()) & 0xffffffff

    def validate(self):
        if not self.bids or not self.asks:
            self.invalidate("empty side of book")
        if max(self.bids) >= min(self.asks):
            self.invalidate("locked or crossed book")

    def apply(self, raw):
        message = json.loads(raw, parse_float=Decimal)
        if self.venue == "coinbase":
            return self.apply_coinbase(message)
        if message.get("channel") != "book":
            if message.get("success") is False:
                self.invalidate(str(message.get("error", "subscription rejected")))
            return None
        if self.failed:
            raise InvalidBook(self.reason)
        data = message["data"][0]
        if data.get("symbol") != "BTC/USD":
            return None
        snapshot = message["type"] == "snapshot"
        if snapshot:
            self.bids.clear()
            self.asks.clear()
        elif not self.ready:
            self.invalidate("update arrived before snapshot")
        try:
            for wire, side in (("asks", "ask"), ("bids", "bid")):
                for level in data.get(wire, []):
                    self.set_level(side, level["price"], level["qty"])
            self.bids = dict(self.levels("bid", self.depth))
            self.asks = dict(self.levels("ask", self.depth))
            self.validate()
            self.checksum_ok = self.checksum() == int(data["checksum"])
            if not self.checksum_ok:
                self.invalidate("kraken checksum mismatch")
        except (KeyError, InvalidOperation, TypeError) as exc:
            self.invalidate(f"malformed book: {type(exc).__name__}")
        self.ready = True
        self.reason = "checksum passed"
        return data.get("timestamp")

    def apply_coinbase(self, message):
        if message.get("type") == "error":
            self.invalidate(str(message.get("message", "subscription rejected")))
        if message.get("type") not in ("snapshot", "l2update") or message.get("product_id") != "BTC-USD":
            return None
        if self.failed:
            raise InvalidBook(self.reason)
        if message["type"] == "snapshot":
            self.bids.clear()
            self.asks.clear()
            for wire, side in (("bids", "bid"), ("asks", "ask")):
                for price, size in message[wire]:
                    self.set_level(side, price, size)
        else:
            if not self.ready:
                self.invalidate("update arrived before snapshot")
            for side, price, size in message["changes"]:
                if side not in ("buy", "sell"):
                    self.invalidate("unknown coinbase book side")
                self.set_level("bid" if side == "buy" else "ask", price, size)
        # keep the full coinbase book; discarded deeper levels cannot be reconstructed later.
        self.validate()
        self.ready = True
        self.reason = "snapshot received; connection and book structure passed"
        return message.get("time")
