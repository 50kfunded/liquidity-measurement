"""Public feeds only. Every reconnect starts a new connection and snapshot."""

import asyncio
import json
import time
import uuid
from pathlib import Path

from websockets.asyncio.client import connect

from .storage import Journal, utc_now, write_json

FEEDS = {
    "coinbase": (
        "wss://ws-feed.exchange.coinbase.com",
        {"type": "subscribe", "product_ids": ["BTC-USD"], "channels": ["level2_batch", "heartbeat"]},
    ),
    "kraken": (
        "wss://ws.kraken.com/v2",
        {"method": "subscribe", "params": {
            "channel": "book", "symbol": ["BTC/USD"], "depth": 100, "snapshot": True,
        }},
    ),
}


async def record_session(directory, seconds=60, phase="development", venues=("kraken",), processor=None, rules=None):
    session_id = uuid.uuid4().hex
    metadata = {
        "schema": 1, "session_id": session_id, "started_at": utc_now(),
        "phase": phase, "synthetic": False, "venues": list(venues),
        "market": "BTC/USD", "depth_levels": 100, "sample_seconds": 1,
        "rules": rules,
    }
    journal = Journal(directory, metadata)
    queue = asyncio.Queue(maxsize=4096)
    stop = asyncio.Event()
    rebuild = {venue: asyncio.Event() for venue in venues}

    def envelope(venue, connection, kind, **extra):
        return {"venue": venue, "market": "BTC/USD", "connection_id": connection,
                "session_id": session_id, "kind": kind, "received_at": utc_now(),
                "_received_mono": time.monotonic(), **extra}

    async def feed(venue):
        delay = 1
        while not stop.is_set():
            connection = uuid.uuid4().hex
            rebuild[venue].clear()
            try:
                url, subscription = FEEDS[venue]
                async with connect(url, open_timeout=10, max_size=16 * 1024 * 1024,
                                   max_queue=64, ping_interval=20, ping_timeout=20) as socket:
                    await queue.put(envelope(venue, connection, "connected"))
                    await socket.send(json.dumps(subscription))
                    delay = 1
                    while not stop.is_set() and not rebuild[venue].is_set():
                        try:
                            raw = await asyncio.wait_for(socket.recv(), timeout=1)
                        except asyncio.TimeoutError:
                            continue
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        queue.put_nowait(envelope(venue, connection, "message", raw=raw))
                    if rebuild[venue].is_set():
                        await queue.put(envelope(venue, connection, "resync_requested"))
            except Exception as exc:
                await queue.put(envelope(venue, connection, "error", reason=f"{type(exc).__name__}: {exc}"))
            finally:
                await queue.put(envelope(venue, connection, "disconnected"))
            if not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except asyncio.TimeoutError:
                    pass
                delay = min(delay * 2, 30)

    async def samples():
        while not stop.is_set():
            await queue.put(envelope(None, None, "sample"))
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except asyncio.TimeoutError:
                pass

    async def consume():
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            item["processing_delay_ms"] = round((time.monotonic() - item.pop("_received_mono")) * 1000, 3)
            item = journal.append(item)
            if processor:
                venue_to_rebuild = processor(item)
                if venue_to_rebuild in rebuild:
                    rebuild[venue_to_rebuild].set()
            queue.task_done()

    consumer = asyncio.create_task(consume())
    feeds = [asyncio.create_task(feed(v)) for v in venues]
    sampler = asyncio.create_task(samples())
    try:
        await asyncio.sleep(seconds)
    finally:
        stop.set()
        await asyncio.gather(*feeds, sampler)
        await queue.put(envelope(None, None, "sample", terminal=True))
        await queue.put(None)
        await consumer
        journal.close()
        metadata["ended_at"] = utc_now()
        write_json(Path(directory) / "session.json", metadata)
    return metadata
