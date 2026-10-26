import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from metrics import build_payload, encode, parse_monitor_status, summarize  # noqa: E402

# Trimmed /metrics output from Uptime Kuma 2.x (tags become labels, monitor_id present).
# "backup-nas" is paused: Kuma drops its series, it only shows up in the database.
KUMA_2_METRICS = """\
# HELP process_cpu_user_seconds_total Total user CPU time spent in seconds.
# TYPE process_cpu_user_seconds_total counter
process_cpu_user_seconds_total 152.31
# HELP monitor_cert_days_remaining The number of days remaining until the certificate expires
# TYPE monitor_cert_days_remaining gauge
monitor_cert_days_remaining{env="prod",monitor_id="2",monitor_name="nextcloud",monitor_type="http",monitor_url="https://cloud.example.org",monitor_hostname="null",monitor_port="null"} 61
# HELP monitor_response_time Monitor Response Time (ms)
# TYPE monitor_response_time gauge
monitor_response_time{env="",monitor_id="1",monitor_name="ovh-vm",monitor_type="ping",monitor_url="https://",monitor_hostname="203.0.113.10",monitor_port="null"} -1
monitor_response_time{env="prod",monitor_id="2",monitor_name="nextcloud",monitor_type="http",monitor_url="https://cloud.example.org",monitor_hostname="null",monitor_port="null"} 182
# HELP monitor_status Monitor Status (1 = UP, 0= DOWN, 2= PENDING, 3= MAINTENANCE)
# TYPE monitor_status gauge
monitor_status{env="",monitor_id="1",monitor_name="ovh-vm",monitor_type="ping",monitor_url="https://",monitor_hostname="203.0.113.10",monitor_port="null"} 0
monitor_status{env="prod",monitor_id="2",monitor_name="nextcloud",monitor_type="http",monitor_url="https://cloud.example.org",monitor_hostname="null",monitor_port="null"} 1
monitor_status{env="prod",monitor_id="3",monitor_name="Jellyfin",monitor_type="http",monitor_url="https://media.example.org",monitor_hostname="null",monitor_port="null"} 1
monitor_status{env="",monitor_id="4",monitor_name="mail-relay",monitor_type="port",monitor_url="https://",monitor_hostname="mx.example.org",monitor_port="25"} 2
monitor_status{env="",monitor_id="5",monitor_name="home-assistant-raspberry-pi",monitor_type="http",monitor_url="http://ha.lan:8123",monitor_hostname="null",monitor_port="null"} 3
monitor_status{env="",monitor_id="6",monitor_name="Aaa \\"quoted\\" \\\\ db",monitor_type="postgres",monitor_url="https://",monitor_hostname="null",monitor_port="null"} 0
# HELP monitor_uptime_ratio Uptime ratio calculated over sliding window specified by the 'window' label. (0.0 - 1.0)
# TYPE monitor_uptime_ratio gauge
monitor_uptime_ratio{env="prod",monitor_id="2",monitor_name="nextcloud",monitor_type="http",monitor_url="https://cloud.example.org",monitor_hostname="null",monitor_port="null",window="1d"} 1
"""

# Uptime Kuma 1.23 format: no monitor_id, no tag labels.
KUMA_1_METRICS = """\
# HELP monitor_status Monitor Status (1 = UP, 0= DOWN, 2= PENDING, 3= MAINTENANCE)
# TYPE monitor_status gauge
monitor_status{monitor_name="router",monitor_type="ping",monitor_url="https://",monitor_hostname="192.168.1.1",monitor_port="null"} 1
monitor_status{monitor_name="blog",monitor_type="keyword",monitor_url="https://blog.example.org",monitor_hostname="null",monitor_port="null"} 0
"""


class ParseMonitorStatusTest(unittest.TestCase):
    def test_kuma_2_format(self):
        self.assertEqual(
            parse_monitor_status(KUMA_2_METRICS),
            [
                ("ovh-vm", 0),
                ("nextcloud", 1),
                ("Jellyfin", 1),
                ("mail-relay", 2),
                ("home-assistant-raspberry-pi", 3),
                ('Aaa "quoted" \\ db', 0),
            ],
        )

    def test_kuma_1_format(self):
        self.assertEqual(parse_monitor_status(KUMA_1_METRICS), [("router", 1), ("blog", 0)])

    def test_ignores_other_metrics_with_monitor_name(self):
        names = [name for name, _ in parse_monitor_status(KUMA_2_METRICS)]
        self.assertEqual(names.count("nextcloud"), 1)

    def test_paused_monitor_absent(self):
        names = [name for name, _ in parse_monitor_status(KUMA_2_METRICS)]
        self.assertNotIn("backup-nas", names)

    def test_no_series_yet(self):
        text = "# HELP monitor_status x\n# TYPE monitor_status gauge\n"
        self.assertEqual(parse_monitor_status(text), [])

    def test_unknown_values_dropped(self):
        text = (
            "# TYPE monitor_status gauge\n"
            'monitor_status{monitor_name="a"} 7\n'
            'monitor_status{monitor_name="b"} NaN\n'
            'monitor_status{monitor_name="c"} 1.0 1729868400000\n'
        )
        self.assertEqual(parse_monitor_status(text), [("c", 1)])

    def test_not_kuma_metrics(self):
        with self.assertRaises(ValueError):
            parse_monitor_status("<!DOCTYPE html><html>login</html>")


class BuildPayloadTest(unittest.TestCase):
    def test_payload(self):
        payload = build_payload(parse_monitor_status(KUMA_2_METRICS))
        self.assertEqual(payload["d"], 2)
        self.assertEqual(payload["t"], 6)
        self.assertEqual(
            payload["h"],
            [
                ['Aaa "quoted" \\ db', 0],
                ["ovh-vm", 0],
                ["mail-relay", 2],
                ["home-assistant-raspb", 3],
                ["Jellyfin", 1],
                ["nextcloud", 1],
            ],
        )

    def test_accents_ignored_when_sorting(self):
        payload = build_payload([("zulip", 1), ("Écluse", 1), ("ebay", 1)])
        self.assertEqual([name for name, _ in payload["h"]], ["ebay", "Écluse", "zulip"])

    def test_names_truncated_to_20(self):
        payload = build_payload([("x" * 40, 1)])
        self.assertEqual(len(payload["h"][0][0]), 20)

    def test_summary_drops_the_list(self):
        payload = build_payload([("ovh-vm", 0), ("nextcloud", 1)])
        self.assertEqual(summarize(payload), {"d": 1, "t": 2})

    def test_encode_is_compact(self):
        body = encode(build_payload([("ovh-vm", 0), ("nextcloud", 1)]))
        self.assertEqual(body, b'{"d":1,"t":2,"h":[["ovh-vm",0],["nextcloud",1]]}')
        self.assertEqual(json.loads(body)["t"], 2)


if __name__ == "__main__":
    unittest.main()
