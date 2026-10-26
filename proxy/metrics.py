"""Turn Uptime Kuma's Prometheus /metrics output into the compact payload sent to the watch.

Paused monitors: Uptime Kuma calls `prometheus.remove()` when a monitor is stopped
(server/model/monitor.js, `stop()`), and only starts monitors with `active = 1` at boot,
so a paused monitor has no `monitor_status` series at all. Nothing needs filtering here;
values outside 0..3 are dropped defensively.
"""

import json
import math
import re
import unicodedata

DOWN, UP, PENDING, MAINTENANCE = 0, 1, 2, 3
NAME_MAX = 20

# Sort order on the watch: down, pending, maintenance, up.
_RANK = {DOWN: 0, PENDING: 1, MAINTENANCE: 2, UP: 3}

_SAMPLE_RE = re.compile(r"^monitor_status(?:\{(?P<labels>.*)\})?\s+(?P<value>\S+)(?:\s+-?\d+)?$")
_LABEL_RE = re.compile(r'\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*"((?:[^"\\]|\\.)*)"\s*(?:,|$)')
_ESCAPE_RE = re.compile(r"\\(.)")


def _unescape(value: str) -> str:
    return _ESCAPE_RE.sub(lambda m: "\n" if m.group(1) == "n" else m.group(1), value)


def _parse_labels(raw: str) -> dict[str, str]:
    labels = {}
    pos = 0
    while pos < len(raw):
        m = _LABEL_RE.match(raw, pos)
        if not m:
            raise ValueError(f"malformed labels: {raw!r}")
        labels[m.group(1)] = _unescape(m.group(2))
        pos = m.end()
    return labels


def parse_monitor_status(text: str) -> list[tuple[str, int]]:
    """Return (monitor_name, status) for every `monitor_status` sample.

    Raises ValueError if the text does not look like Uptime Kuma metrics (e.g. an HTML
    login page), so that a misconfiguration is not reported as "0 monitors, all good".
    """
    if "# TYPE monitor_status gauge" not in text:
        raise ValueError("monitor_status metric not found")

    monitors = []
    for line in text.splitlines():
        if not line.startswith("monitor_status"):
            continue
        m = _SAMPLE_RE.match(line.strip())
        if not m:
            continue
        try:
            value = float(m.group("value"))
        except ValueError:
            continue
        if math.isnan(value) or value not in (DOWN, UP, PENDING, MAINTENANCE):
            continue
        name = _parse_labels(m.group("labels") or "").get("monitor_name")
        if name is None:
            continue
        monitors.append((name, int(value)))
    return monitors


def _sort_name(name: str) -> str:
    # "Écluse" sorts with the E's, not after "Z".
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def build_payload(monitors: list[tuple[str, int]]) -> dict:
    ordered = sorted(monitors, key=lambda m: (_RANK[m[1]], _sort_name(m[0]), m[0]))
    return {
        "d": sum(1 for _, status in monitors if status == DOWN),
        "t": len(monitors),
        "h": [[name[:NAME_MAX], status] for name, status in ordered],
    }


def encode(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
