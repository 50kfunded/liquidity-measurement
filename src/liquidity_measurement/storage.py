"""Keep wire messages unchanged inside a timed, ordered recording journal."""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


class Journal:
    def __init__(self, directory, metadata):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        write_json(self.directory / "session.json", metadata)
        self.stream = None
        self.day = None
        self.ordinal = 0

    def append(self, record):
        day = record["received_at"][:10]
        if day != self.day:
            if self.stream:
                self.stream.close()
            self.stream = gzip.open(self.directory / f"{day}.jsonl.gz", "at", encoding="utf-8")
            self.day = day
        self.ordinal += 1
        record = {**record, "ordinal": self.ordinal}
        self.stream.write(json.dumps(record, allow_nan=False) + "\n")
        self.stream.flush()
        return record

    def close(self):
        if self.stream:
            self.stream.close()


def read_journal(directory):
    previous = 0
    for path in sorted(Path(directory).glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                if record["ordinal"] != previous + 1:
                    raise ValueError("recording journal has a missing or reordered record")
                previous = record["ordinal"]
                yield record
