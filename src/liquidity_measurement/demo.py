"""Deterministic artificial messages. None of these are live market results."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .analysis import replay, report
from .book import OrderBook
from .rules import calibrate
from .storage import Journal, write_json


def simulated_time(second):
    return datetime.fromtimestamp(1700000000 + second, timezone.utc).isoformat()


def make_book(shock=False):
    book = OrderBook("kraken")
    offset, size = (12, ".004") if shock else (1, ".02")
    for i in range(100):
        book.set_level("bid", 50000 - offset - i, size)
        book.set_level("ask", 50000 + offset + i, size)
    return book


def wire_message(venue, book, previous, second, corrupt=False):
    if venue == "kraken":
        data = {"symbol": "BTC/USD", "timestamp": simulated_time(second),
                "checksum": book.checksum() ^ int(corrupt)}
        for name, side in (("bids", "bid"), ("asks", "ask")):
            levels = dict(book.levels(side))
            earlier = dict(previous.levels(side)) if previous else {}
            data[name] = [{"price": str(p), "qty": str(levels.get(p, Decimal(0)))}
                          for p in sorted(set(levels) | set(earlier)) if previous is None or levels.get(p) != earlier.get(p)]
        return {"channel": "book", "type": "update" if previous else "snapshot", "data": [data]}
    if previous is None:
        return {"type": "snapshot", "product_id": "BTC-USD",
                "bids": [[str(p), str(q)] for p, q in book.levels("bid")],
                "asks": [[str(p), str(q)] for p, q in book.levels("ask")]}
    changes = []
    for side, wire in (("bid", "buy"), ("ask", "sell")):
        levels, earlier = dict(book.levels(side)), dict(previous.levels(side))
        changes.extend([[wire, str(p), str(levels.get(p, Decimal(0)))]
                        for p in sorted(set(levels) | set(earlier)) if levels.get(p) != earlier.get(p)])
    return {"type": "l2update", "product_id": "BTC-USD", "time": simulated_time(second), "changes": changes}


def generate_session(directory, phase, start, duration, rules=None):
    metadata = {"schema": 1, "session_id": "synthetic-" + phase, "phase": phase,
                "synthetic": True, "clock": "simulated", "started_at": simulated_time(start),
                "ended_at": simulated_time(start + duration), "venues": ["kraken", "coinbase"],
                "market": "BTC/USD", "depth_levels": 100, "sample_seconds": 1, "rules": rules}
    journal = Journal(directory, metadata)
    connections = {v: f"synthetic-{v}-1" for v in metadata["venues"]}
    previous = {v: None for v in connections}

    def append(second, venue, kind, **extra):
        journal.append({"venue": venue, "market": "BTC/USD", "connection_id": connections.get(venue),
                        "session_id": metadata["session_id"], "received_at": simulated_time(second),
                        "kind": kind, "processing_delay_ms": 0, **extra})

    for venue in connections:
        append(start, venue, "connected")
    for offset in range(duration):
        second = start + offset
        for venue in connections:
            if phase == "evaluation" and venue == "kraken" and 221 <= offset < 225:
                if offset == 221:
                    append(second, venue, "disconnected")
                continue
            if phase == "evaluation" and venue == "kraken" and offset == 225:
                connections[venue] = "synthetic-kraken-2"
                previous[venue] = None
                append(second, venue, "connected")
            shock = phase == "evaluation" and venue == "kraken" and 80 <= offset < 100
            book = make_book(shock)
            corrupt = phase == "evaluation" and venue == "kraken" and offset == 220
            append(second, venue, "message", raw=json.dumps(wire_message(venue, book, previous[venue], second, corrupt)))
            previous[venue] = book
        append(second, None, "sample")
    for venue in connections:
        append(start + duration, venue, "disconnected")
    append(start + duration, None, "sample", terminal=True)
    journal.close()
    return metadata


def demo(output):
    output = Path(output)
    if output.exists():
        raise ValueError("choose a new demo output directory")
    generate_session(output / "pilot", "pilot", 0, 80)
    replay(output / "pilot", output / "pilot-measures")
    rules = calibrate(output / "pilot", output / "pilot-measures")
    # use the simulated clock for this artificial research sequence.
    rules["created_at"] = simulated_time(81)
    rules["clock"] = "simulated"
    write_json(output / "rules.json", rules)
    generate_session(output / "evaluation", "evaluation", 100, 400, rules)
    summary = replay(output / "evaluation", output / "measures")
    report(output / "measures", output / "report")
    return summary
