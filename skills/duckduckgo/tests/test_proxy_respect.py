"""Regression tests: network clients must honor HTTP_PROXY / HTTPS_PROXY.

This skill talks to the network through three transport engines — curl_cffi
(download.py's primary fetch), httpx (download.py's fallback fetch and
top_news.py's metadata fetch), and primp (ddgs's engine, used by search.py,
fact_check.py, monitor.py, trending.py, translate_search.py, top_news.py).
All three trust the environment by default and need no proxy wiring in this
skill's own code — these tests pin that behavior down so a future dependency
bump or an explicit `trust_env=False` / `proxy=...` override can't silently
break it in a corporate-proxy environment.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from download import TIMEOUT, _SSL_CTX  # noqa: E402


class _RecordingProxy:
    """A minimal TCP listener that records the first request line it receives.

    Good enough to prove a client routed a request through it — no actual
    proxying is needed since the test only cares whether the connection
    landed here instead of going straight to the destination host.
    """

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.received: bytes | None = None
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def _serve(self) -> None:
        self.sock.settimeout(5)
        try:
            conn, _addr = self.sock.accept()
        except OSError:
            return
        conn.settimeout(2)
        try:
            self.received = conn.recv(4096)
        except OSError:
            pass
        try:
            conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
        except OSError:
            pass
        conn.close()

    def __enter__(self) -> "_RecordingProxy":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._thread.join(timeout=3)
        self.sock.close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


@pytest.fixture
def proxy_env(monkeypatch: pytest.MonkeyPatch):
    with _RecordingProxy() as proxy:
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            monkeypatch.setenv(var, proxy.url)
        yield proxy


def test_curl_cffi_get_honors_http_proxy(proxy_env: _RecordingProxy) -> None:
    """Mirrors download.py's `_cffi_get` — curl_cffi's Chrome-impersonation path."""
    from curl_cffi import requests as cffi_requests

    try:
        cffi_requests.get(
            "http://example.com/", impersonate="chrome", timeout=TIMEOUT,
            allow_redirects=True,
        )
    except Exception:
        pass

    assert proxy_env.received is not None, "curl_cffi did not route through HTTP_PROXY"
    assert proxy_env.received.startswith(b"GET http://example.com/")


def test_httpx_client_honors_http_proxy(proxy_env: _RecordingProxy) -> None:
    """Mirrors download.py's `_httpx_get` fallback (Wayback/Google Cache)."""
    import httpx

    with httpx.Client(follow_redirects=True, timeout=TIMEOUT, verify=_SSL_CTX) as client:
        try:
            client.get("http://example.com/")
        except httpx.HTTPError:
            pass

    assert proxy_env.received is not None, "httpx.Client did not route through HTTP_PROXY"
    assert proxy_env.received.startswith(b"GET http://example.com/")


def test_primp_client_honors_http_proxy(proxy_env: _RecordingProxy) -> None:
    """Mirrors ddgs's internal HttpClient, used by search/fact_check/monitor/

    trending/translate_search/top_news via `DDGS()`, which constructs
    `primp.Client(proxy=None, ...)` when no proxy is passed explicitly.
    """
    import primp

    client = primp.Client(timeout=TIMEOUT)
    try:
        client.get("http://example.com/")
    except Exception:
        pass

    assert proxy_env.received is not None, "primp.Client did not route through HTTP_PROXY"
    assert proxy_env.received.startswith(b"GET http://example.com/")
