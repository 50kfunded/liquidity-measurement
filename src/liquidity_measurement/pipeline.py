import json
from pathlib import Path

from .book import InvalidBook, OrderBook
from .metrics import measure
from .storage import timestamp, write_json


class FeedState:
    def __init__(self, venue):
        self.book = OrderBook(venue)
        self.connected = False
        self.connection_id = None
        self.last_message = None
        self.last_book = None
        self.exchange_time = None
        self.delay_ms = 0

    def health(self, now):
        if not self.connected:
            return "disconnected", "connection is closed"
        if self.book.failed:
            return "failed_validation", self.book.reason
        if not self.book.ready:
            return "recovering", "waiting for snapshot"
        if self.last_message is None or now - self.last_message > 5:
            return "delayed", "no feed message for more than 5 seconds"
        if self.last_book is None or now - self.last_book > 10:
            return "delayed", "book has not changed for more than 10 seconds"
        if self.delay_ms > 1000:
            return "delayed", "local processing delay exceeds 1 second"
        if self.exchange_time and self.last_book - self.exchange_time > 5:
            return "delayed", "exchange update arrived more than 5 seconds late"
        if self.exchange_time and self.exchange_time - self.last_book > 2:
            return "delayed", "exchange time is ahead of the local clock"
        return "valid", self.book.reason


class Pipeline:
    def __init__(self, directory, venues=("kraken",), rules=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.feeds = {v: FeedState(v) for v in venues}
        self.stream = (self.directory / "observations.jsonl").open("w", encoding="utf-8")
        self.observations = []
        from .events import EventEngine
        self.events = EventEngine(rules) if rules else None
        self.counts = {"messages": 0, "checksum_failures": 0, "connections": 0,
                       "validation_failures": 0}

    def process(self, record):
        now = timestamp(record["received_at"])
        if record["kind"] == "sample":
            self.sample(record, now)
            return None
        state = self.feeds[record["venue"]]
        kind = record["kind"]
        if kind == "connected":
            state.book.reset()
            state.connected = True
            state.connection_id = record["connection_id"]
            state.last_message = state.last_book = state.exchange_time = None
            self.counts["connections"] += 1
        elif kind in ("disconnected", "error", "resync_requested"):
            state.connected = False
        elif kind == "message":
            self.counts["messages"] += 1
            if record["connection_id"] != state.connection_id or not state.connected:
                return None
            state.last_message = now
            state.delay_ms = record.get("processing_delay_ms", 0)
            try:
                raw_message = json.loads(record["raw"])
                is_book = raw_message.get("channel") == "book" or raw_message.get("type") in ("snapshot", "l2update")
                event_time = state.book.apply(record["raw"])
                if is_book:
                    if event_time and state.exchange_time and timestamp(event_time) < state.exchange_time:
                        state.book.invalidate("exchange book times arrived out of order")
                    state.last_book = now
                    state.exchange_time = timestamp(event_time) if event_time else None
                if state.delay_ms > 1000:
                    state.book.invalidate("processing backlog; fresh snapshot required")
            except (ValueError, KeyError, TypeError) as exc:
                state.book.ready = False
                state.book.failed = True
                state.book.reason = str(exc)
                self.counts["validation_failures"] += 1
                if "checksum" in str(exc):
                    self.counts["checksum_failures"] += 1
                return record["venue"]
        return None

    def sample(self, record, now):
        row = {"time": record["received_at"], "session_id": record["session_id"],
               "terminal": record.get("terminal", False), "venues": {}}
        for venue, state in self.feeds.items():
            status, reason = state.health(now)
            values = {"status": status, "reason": reason,
                      "connection_id": state.connection_id,
                      "book_age_ms": (now - state.last_book) * 1000 if state.last_book else None,
                      "processing_delay_ms": state.delay_ms,
                      "exchange_time": state.exchange_time,
                      "checksum_ok": state.book.checksum_ok if venue == "kraken" else None,
                      "validation": "top10_crc32" if venue == "kraken" else "connection_and_structure"}
            if status == "valid":
                try:
                    values.update(measure(state.book))
                except InvalidBook as exc:
                    values.update(status="failed_validation", reason=str(exc))
            row["venues"][venue] = values
        self.stream.write(json.dumps(row, allow_nan=False) + "\n")
        self.stream.flush()
        self.observations.append(row)
        if self.events:
            self.events.add(row)
            write_json(self.directory / "events.json", self.events.records())
        write_json(self.directory / "latest.json", row)

    def close(self):
        self.stream.close()
        write_json(self.directory / "feed_counts.json", self.counts)
        if self.events:
            write_json(self.directory / "events.json", self.events.records(final=True))
