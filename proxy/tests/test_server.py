import json
import logging
import pathlib
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from server import StatusCache, make_handler  # noqa: E402

TOKEN = "test-token"
METRICS = """\
# TYPE monitor_status gauge
monitor_status{monitor_name="nextcloud"} 1
monitor_status{monitor_name="ovh-vm"} 0
"""


# The 502 tests log a warning on purpose.
logging.getLogger("kuma-proxy").setLevel(logging.ERROR)


class FakeCache(StatusCache):
    """StatusCache with /metrics served from memory instead of Uptime Kuma."""

    def __init__(self, ttl=30):
        super().__init__("http://kuma.invalid", "key", ttl)
        self.response = METRICS
        self.fetches = 0

    def _fetch(self):
        self.fetches += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.cache = FakeCache()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.cache, TOKEN, timeout=0.5))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def get(self, path, token=TOKEN):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.base + path, headers=headers)) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read()

    def test_healthz_needs_no_auth(self):
        self.assertEqual(self.get("/healthz", token=None), (200, b"ok"))

    def test_status_requires_token(self):
        self.assertEqual(self.get("/status", token=None), (401, b'{"e":"auth"}'))
        self.assertEqual(self.get("/status", token="wrong"), (401, b'{"e":"auth"}'))

    def test_status(self):
        code, body = self.get("/status")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body), {"d": 1, "t": 2, "h": [["ovh-vm", 0], ["nextcloud", 1]]})

    def test_summary_has_counts_only(self):
        code, body = self.get("/status?summary=1")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body), {"d": 1, "t": 2})

    def test_full_and_summary_share_one_fetch(self):
        self.get("/status")
        self.get("/status?summary=1")
        self.assertEqual(self.cache.fetches, 1)

    def test_kuma_unreachable(self):
        self.cache.response = OSError("connection refused")
        self.assertEqual(self.get("/status"), (502, b'{"e":"kuma"}'))

    def test_not_kuma_metrics(self):
        self.cache.response = "<html>login</html>"
        self.assertEqual(self.get("/status"), (502, b'{"e":"kuma"}'))

    def test_idle_connection_closed(self):
        with socket.create_connection(self.server.server_address, timeout=5) as sock:
            sock.sendall(b"GET /status HTTP/1.1\r\n")  # never finishes the request
            self.assertEqual(sock.recv(1024), b"")

    def test_unknown_path(self):
        self.assertEqual(self.get("/metrics")[0], 404)


if __name__ == "__main__":
    unittest.main()
