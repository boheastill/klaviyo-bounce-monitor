#!/usr/bin/env python3
"""Mock Klaviyo API server — zero dependencies, Python stdlib only.

Mirrors the shape of the real Klaviyo endpoints the bounce monitor uses:

  GET  /api/campaigns                    -> campaigns sent in the last 3 days (JSON:API)
  POST /api/campaign-values-reports     -> per-campaign delivery/bounce statistics
  POST /api/metric-aggregates           -> hard vs soft bounce split ("Bounced Email" metric)
  POST /slack                            -> stand-in Slack incoming webhook (logs the message)

Run:  python3 mock_klaviyo_server.py   (listens on http://localhost:8778)

The dataset is deterministic: 5 campaigns over the last 3 days, of which
  - "Flash Sale - Last Chance"  has an elevated HARD bounce rate (list decay scenario)
  - "Weekly Digest #142"        has an elevated SOFT bounce rate (inbox-full/deferral scenario)
  - the other 3 are healthy
so the monitor always has something to flag in a demo.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8778
NOW = datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ---------------------------------------------------------------- dataset
# recipients, delivered, hard_bounced, soft_bounced
CAMPAIGNS = [
    {
        "id": "01HZCAMPA1GN0001",
        "name": "Flash Sale - Last Chance",
        "send_time": iso(NOW - timedelta(hours=14)),
        "recipients": 18500,
        "hard": 610,   # 3.30% hard  -> RED flag
        "soft": 148,   # 0.80% soft
    },
    {
        "id": "01HZCAMPA1GN0002",
        "name": "Weekly Digest #142",
        "send_time": iso(NOW - timedelta(hours=30)),
        "recipients": 42200,
        "hard": 84,    # 0.20% hard
        "soft": 971,   # 2.30% soft  -> ORANGE flag
    },
    {
        "id": "01HZCAMPA1GN0003",
        "name": "New Arrivals - Summer Drop",
        "send_time": iso(NOW - timedelta(hours=42)),
        "recipients": 31000,
        "hard": 47,    # 0.15%
        "soft": 155,   # 0.50%
    },
    {
        "id": "01HZCAMPA1GN0004",
        "name": "VIP Early Access",
        "send_time": iso(NOW - timedelta(hours=55)),
        "recipients": 5400,
        "hard": 5,     # 0.09%
        "soft": 22,    # 0.41%
    },
    {
        "id": "01HZCAMPA1GN0005",
        "name": "Post-Purchase Cross-sell",
        "send_time": iso(NOW - timedelta(hours=68)),
        "recipients": 12800,
        "hard": 26,    # 0.20%
        "soft": 77,    # 0.60%
    },
]


def campaigns_payload():
    return {
        "data": [
            {
                "type": "campaign",
                "id": c["id"],
                "attributes": {
                    "name": c["name"],
                    "status": "Sent",
                    "send_time": c["send_time"],
                    "audiences": {"included": ["mock-list-id"]},
                },
            }
            for c in CAMPAIGNS
        ],
        "links": {"next": None},
    }


def values_report_payload(campaign_ids):
    rows = []
    for c in CAMPAIGNS:
        if campaign_ids and c["id"] not in campaign_ids:
            continue
        bounced = c["hard"] + c["soft"]
        delivered = c["recipients"] - bounced
        rows.append(
            {
                "groupings": {"campaign_id": c["id"]},
                "statistics": {
                    "recipients": c["recipients"],
                    "delivered": delivered,
                    "delivery_rate": round(delivered / c["recipients"], 4),
                    "bounced": bounced,
                    "bounce_rate": round(bounced / c["recipients"], 4),
                },
            }
        )
    return {
        "data": {
            "type": "campaign-values-report",
            "attributes": {"results": rows},
        }
    }


def metric_aggregates_payload(campaign_ids):
    """Hard/soft split, shaped like a metric-aggregates query on the
    'Bounced Email' metric grouped by $attributed_message + bounce_type."""
    results = []
    for c in CAMPAIGNS:
        if campaign_ids and c["id"] not in campaign_ids:
            continue
        results.append(
            {
                "dimensions": [c["id"], "HardBounce"],
                "measurements": {"count": [c["hard"]]},
            }
        )
        results.append(
            {
                "dimensions": [c["id"], "SoftBounce"],
                "measurements": {"count": [c["soft"]]},
            }
        )
    return {
        "data": {
            "type": "metric-aggregate",
            "attributes": {"results": results},
        }
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MockKlaviyo/1.0"

    def _send(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/vnd.api+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        if self.path.startswith("/api/campaigns"):
            self._send(campaigns_payload())
        elif self.path == "/health":
            self._send({"status": "ok", "campaigns": len(CAMPAIGNS)})
        else:
            self._send({"errors": [{"detail": f"Unknown path {self.path}"}]}, 404)

    def do_POST(self):
        body = self._read_body()
        # accept a Klaviyo-style filter and pull campaign ids out of it if present
        raw_filter = json.dumps(body)
        ids = set(re.findall(r"01HZCAMPA1GN\d{4}", raw_filter))
        if self.path.rstrip("/") == "/api/campaign-values-reports":
            self._send(values_report_payload(ids))
        elif self.path.rstrip("/") == "/api/metric-aggregates":
            self._send(metric_aggregates_payload(ids))
        elif self.path.rstrip("/") == "/slack":
            header = ""
            for block in body.get("blocks", []):
                if block.get("type") == "header":
                    header = block["text"]["text"]
            print(f"[mock-slack] received message: {header!r} "
                  f"({len(body.get('blocks', []))} blocks)")
            self._send({"ok": True, "note": "mock Slack webhook — message accepted"})
        else:
            self._send({"errors": [{"detail": f"Unknown path {self.path}"}]}, 404)

    def log_message(self, fmt, *args):
        print(f"[mock-klaviyo] {self.address_string()} {fmt % args}")


if __name__ == "__main__":
    print(f"Mock Klaviyo API listening on http://localhost:{PORT}")
    print(f"  {len(CAMPAIGNS)} campaigns in the last 3 days "
          f"(1 hard-bounce spike, 1 soft-bounce spike, 3 healthy)")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
