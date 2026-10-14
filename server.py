import json
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler

import paths
from adapters.common import london_now, london_today, parse_ts
from main import latest, offline_banner, refresh

PORT = 8000
# Live mode: the last good refresh is reused until it's this old. A failed refresh isn't retried
# sooner either, so a failing chain can't turn every page load into a slow refresh attempt.
REFRESH_SECONDS = 30 * 60

_last_attempt = 0.0


def is_fresh(data):
    return bool(data) and data.get("start") == london_today() and (
        london_now() - parse_ts(data["refreshed_at"])
    ).total_seconds() <= REFRESH_SECONDS


def sessions():
    """Payload for /api/sessions. mode is "live" only when the data is a fresh live refresh;
    "offline" when OFFLINE=1 or the last refresh failed (serving the last good data)."""
    global _last_attempt
    data = latest()
    if not paths.OFFLINE and not is_fresh(data) and time.time() - _last_attempt > REFRESH_SECONDS:
        _last_attempt = time.time()
        data = refresh() or data
    if not data:
        raise RuntimeError("no data yet: run once with OFFLINE=0")
    return {**data, "mode": "live" if not paths.OFFLINE and is_fresh(data) else "offline"}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=paths.WEB_DIST, **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] != "/api/sessions":
            return super().do_GET()
        try:
            body, status = sessions(), 200
        except Exception as e:
            body, status = {"error": str(e)}, 502
        out = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    # Single-threaded on purpose: concurrent page loads queue up and reuse the saved results
    # instead of triggering duplicate upstream requests.
    if paths.OFFLINE:
        data = latest()
        offline_banner(data) if data else print("OFFLINE and no snapshot yet: run once with OFFLINE=0")
    print(f"http://localhost:{PORT}", flush=True)
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
