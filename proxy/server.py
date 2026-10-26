"""Uptime Kuma -> Garmin proxy.

GET /status   Bearer-protected, compact JSON summary of monitor states (cached CACHE_TTL s)
              ?summary=1 returns the counts only, without the monitor list
GET /healthz  liveness probe, no auth
"""

import base64
import hmac
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from metrics import build_payload, encode, parse_monitor_status, summarize

log = logging.getLogger("kuma-proxy")

KUMA_TIMEOUT = 10
# Closes idle or trickling client connections (slowloris); a normal request takes milliseconds.
CLIENT_TIMEOUT = 10
USER_AGENT = "kuma-watch-proxy/1.0"
ERR_KUMA = b'{"e":"kuma"}'
ERR_AUTH = b'{"e":"auth"}'
ERR_NOT_FOUND = b'{"e":"404"}'


class StatusCache:
    """Fetches /metrics from Uptime Kuma, at most once per `ttl` seconds."""

    def __init__(self, kuma_url: str, api_key: str, ttl: float):
        self.url = kuma_url.rstrip("/") + "/metrics"
        # Uptime Kuma API keys: empty username, key as password.
        token = base64.b64encode(f":{api_key}".encode()).decode()
        self.auth_header = f"Basic {token}"
        self.ttl = ttl
        self._lock = threading.Lock()
        self._full: bytes | None = None
        self._summary: bytes | None = None
        self._fetched_at = 0.0

    def get(self, summary: bool = False) -> bytes:
        """Return the encoded payload; raises on any Uptime Kuma failure."""
        with self._lock:
            if self._full is None or time.monotonic() - self._fetched_at >= self.ttl:
                payload = build_payload(parse_monitor_status(self._fetch()))
                self._full, self._summary = encode(payload), encode(summarize(payload))
                self._fetched_at = time.monotonic()
            return self._summary if summary else self._full

    def _fetch(self) -> str:
        # Cloudflare's bot protection rejects the default "Python-urllib/x.y" User-Agent with a 403.
        req = urllib.request.Request(
            self.url,
            headers={"Authorization": self.auth_header, "User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=KUMA_TIMEOUT) as resp:
            return resp.read().decode("utf-8")


def make_handler(cache: StatusCache, proxy_token: str, timeout: float = CLIENT_TIMEOUT):
    expected = f"Bearer {proxy_token}".encode()
    client_timeout = timeout

    class Handler(BaseHTTPRequestHandler):
        server_version = "kuma-proxy"
        # Read by StreamRequestHandler: socket timeout for each connection.
        timeout = client_timeout
        sys_version = ""

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/healthz":
                self._send(200, b"ok", "text/plain")
            elif path == "/status":
                self._status(parse_qs(query).get("summary") == ["1"])
            else:
                self._send(404, ERR_NOT_FOUND)

        def _status(self, summary: bool):
            given = self.headers.get("Authorization", "").encode()
            if not hmac.compare_digest(given, expected):
                self._send(401, ERR_AUTH)
                return
            try:
                body = cache.get(summary)
            except (OSError, urllib.error.URLError, ValueError) as e:
                log.warning("Uptime Kuma unavailable: %s", e)
                self._send(502, ERR_KUMA)
                return
            self._send(200, body)

        def _send(self, code: int, body: bytes, content_type: str = "application/json"):
            self.send_response(code)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            log.info("%s %s", self.address_string(), fmt % args)

    return Handler


def healthcheck(port: int) -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3):
            return 0
    except OSError:
        return 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    port = int(os.environ.get("PORT", "8080"))
    if "--healthcheck" in sys.argv:
        return healthcheck(port)

    missing = [k for k in ("KUMA_URL", "KUMA_API_KEY", "PROXY_TOKEN") if not os.environ.get(k)]
    if missing:
        log.error("missing environment variables: %s", ", ".join(missing))
        return 1

    cache = StatusCache(
        os.environ["KUMA_URL"],
        os.environ["KUMA_API_KEY"],
        float(os.environ.get("CACHE_TTL", "30")),
    )
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(cache, os.environ["PROXY_TOKEN"]))
    log.info("listening on :%d, upstream %s", port, cache.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
