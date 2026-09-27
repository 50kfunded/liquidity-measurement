"""Only measure validated books, and never fill beyond recorded depth."""

from decimal import Decimal


def displayed_cost(levels, mid, notional, side):
    target = Decimal(str(notional)) / mid
    remaining = target
    value = Decimal(0)
    for price, quantity in levels:
        fill = min(remaining, quantity)
        value += price * fill
        remaining -= fill
        if remaining == 0:
            average = value / target
            cost = (average - mid) / mid * 10000
            if side == "sell":
                cost = -cost
            return {"status": "available", "quantity_btc": float(target),
                    "average_price": float(average), "cost_bps": float(cost)}
    return {"status": "insufficient_depth", "quantity_btc": float(target),
            "average_price": None, "cost_bps": None}


def measure(book, band_bps=10):
    book.validate()
    bids, asks = book.levels("bid", 100), book.levels("ask", 100)
    bid, ask = bids[0][0], asks[0][0]
    mid = (bid + ask) / 2
    band = mid * type(mid)(str(band_bps)) / 10000
    lower, upper = mid - band, mid + band
    complete = bids[-1][0] <= lower and asks[-1][0] >= upper
    depth = sum(float(p * q) for p, q in bids if p >= lower)
    depth += sum(float(p * q) for p, q in asks if p <= upper)
    return {"mid_price": float(mid), "best_bid": float(bid), "best_ask": float(ask),
            "spread_bps": float((ask - bid) / mid * 10000), "band_bps": band_bps,
            "depth_usd": depth if complete else None, "depth_complete": complete,
            "recorded_band_depth_usd": depth, "comparable_levels": 100,
            "displayed_cost": {str(size): {
                "buy": displayed_cost(asks, mid, size, "buy"),
                "sell": displayed_cost(bids, mid, size, "sell"),
            } for size in (1000, 5000, 10000)}}
