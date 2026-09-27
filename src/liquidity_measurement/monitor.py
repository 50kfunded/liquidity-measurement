"""A small local monitor. Bind only to localhost; no exchange credentials."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .charts import read_observations
from .storage import timestamp, utc_now


def serve(directory, port=8765):
    directory = Path(directory).resolve()
    assets = Path(__file__).with_name("web")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            try:
                if path == "/api/state":
                    latest_path = directory / "latest.json"
                    latest = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else None
                    events_path = directory / "events.json"
                    events = json.loads(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
                    session_path = directory / "session.json"
                    session = json.loads(session_path.read_text(encoding="utf-8")) if session_path.exists() else {}
                    age = max(0, timestamp(utc_now()) - timestamp(latest["time"])) if latest else None
                    body = json.dumps({"latest": latest, "age_seconds": age,
                                       "fresh": bool(latest and not latest.get("terminal") and age < 5),
                                       "synthetic": session.get("synthetic", False),
                                       "phase": session.get("phase"),
                                       "events": [{k: v for k, v in e.items() if k != "timeline"} for e in events]}).encode()
                    mime = "application/json"
                elif path == "/api/history":
                    body = json.dumps(read_observations(directory)[-600:]).encode()
                    mime = "application/json"
                elif path.startswith("/api/events/"):
                    identity = path.removeprefix("/api/events/")
                    events = json.loads((directory / "events.json").read_text(encoding="utf-8"))
                    event = next((e for e in events if e["id"] == identity), None)
                    if not event:
                        self.send_error(404)
                        return
                    body, mime = json.dumps(event).encode(), "application/json"
                elif path in ("/", "/app.js", "/style.css"):
                    name = "index.html" if path == "/" else path[1:]
                    body = (assets / name).read_bytes()
                    mime = {"index.html": "text/html", "app.js": "text/javascript", "style.css": "text/css"}[name]
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", mime + "; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (FileNotFoundError, json.JSONDecodeError):
                self.send_error(503, "recording is not ready yet")

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"monitor: http://127.0.0.1:{port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
