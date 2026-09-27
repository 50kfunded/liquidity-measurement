"""Only measure validated books, and never fill beyond recorded depth."""


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
            "recorded_band_depth_usd": depth, "comparable_levels": 100}
