"""Web UI: `whowrote-web` serves index.html and GET /api/analyze?url=<github url>.

Public-facing, so: GitHub URLs only (never local paths), a cap on concurrent clones, git
timeouts (ingest.repo), and GITHUB_TOKEN dropped so visitors can't analyze private repos.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import parse_qs, urlparse

from whowrote.cli import analyze
from whowrote.ingest.repo import GITHUB_URL
from whowrote.report.json_out import to_json

INDEX = files("whowrote.web").joinpath("index.html").read_bytes()
HISTORY = 300
MAX_URL = 300
# ponytail: process-wide job cap + in-memory result cache; use a queue/shared cache to scale out.
_slots = threading.BoundedSemaphore(int(os.environ.get("WHOWROTE_MAX_JOBS", "2")))
_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; script-src 'unsafe-inline'; "
                               "style-src 'unsafe-inline'; img-src data:; connect-src 'self'",
}


@lru_cache(maxsize=256)
def _analyze(url: str) -> str:
    result, meta = analyze(url, HISTORY)
    return to_json(result, meta)


class Handler(BaseHTTPRequestHandler):
    server_version = "whowrote"

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in _HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: str | dict[str, str]) -> None:
        body = payload if isinstance(payload, str) else json.dumps(payload)
        self._send(status, body.encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, INDEX, "text/html; charset=utf-8")
        if u.path == "/healthz":
            return self._json(200, {"ok": "true"})
        if u.path != "/api/analyze":
            return self._json(404, {"error": "Not found."})

        url = parse_qs(u.query).get("url", [""])[0].strip()
        m = GITHUB_URL.match(url) if len(url) <= MAX_URL else None
        if not m:
            return self._json(400, {"error": "Paste a GitHub repo URL, like "
                                             "https://github.com/owner/repo"})
        owner, name, branch = m.groups()
        canonical = f"https://github.com/{owner}/{name}" + (f"/tree/{branch}" if branch else "")
        if not _slots.acquire(blocking=False):
            return self._json(429, {"error": "Busy analyzing other repos. Try again in a moment."})
        try:
            self._json(200, _analyze(canonical))
        except subprocess.TimeoutExpired:
            self._json(504, {"error": "That repo took too long to clone."})
        except subprocess.CalledProcessError:
            self._json(422, {"error": "Couldn't clone that repo. Is it public and spelled right?"})
        except Exception as e:  # never leak internals to visitors
            print(f"analyze {canonical} failed: {e!r}", file=sys.stderr)
            self._json(500, {"error": "Something went wrong analyzing that repo."})
        finally:
            _slots.release()


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    os.environ.pop("GITHUB_TOKEN", None)
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    print(f"whowrote web on http://{host}:{port}", file=sys.stderr)
    make_server(host, port).serve_forever()


if __name__ == "__main__":
    main()
