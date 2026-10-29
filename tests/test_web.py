from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from urllib.parse import quote

import pytest

from whowrote.web.server import make_server


@pytest.fixture
def base() -> Iterator[str]:
    srv = make_server("127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_serves_page_and_health(base: str) -> None:
    status, body = get(base + "/")
    assert status == 200 and b"who wrote" in body
    assert get(base + "/healthz")[0] == 200
    assert get(base + "/nope")[0] == 404


@pytest.mark.parametrize("target", ["/etc", ".", "file:///etc/passwd", "https://gitlab.com/a/b",
                                    "https://github.com/a", ""])
def test_rejects_non_github_targets(base: str, target: str) -> None:
    status, body = get(f"{base}/api/analyze?url={quote(target)}")
    assert status == 400 and "GitHub repo URL" in json.loads(body)["error"]
