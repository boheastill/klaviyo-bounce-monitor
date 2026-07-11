#!/usr/bin/env python3
"""Klaviyo bounce monitor — pulls campaigns from the last N days, checks
hard / soft / total bounce rates against configurable thresholds, and posts
a summary to Slack.

Zero dependencies (Python stdlib only).

Usage:
    python3 bounce_monitor.py --mock              # demo against mock_klaviyo_server.py
    python3 bounce_monitor.py                     # real Klaviyo (needs env vars below)
    python3 bounce_monitor.py --mock --preview    # also write slack_preview.html

Environment (real mode):
    KLAVIYO_API_KEY     private key, read scope for campaigns + metrics
    SLACK_WEBHOOK_URL   incoming-webhook URL; if unset, the Slack payload is
                        printed to stdout instead of posted (dry run)

The same three API calls, the same threshold logic, and the same Slack Block
Kit payload are what the n8n workflow (n8n_workflow.json) implements node-by-
node — this script is the fast way to see the pipeline end to end.
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
KLAVIYO_REVISION = "2025-04-15"
MOCK_BASE = "http://localhost:8778"
REAL_BASE = "https://a.klaviyo.com"


# ---------------------------------------------------------------- http
def call(base, path, api_key=None, payload=None):
    url = base + path
    headers = {"Accept": "application/vnd.api+json", "revision": KLAVIYO_REVISION}
    if api_key:
        headers["Authorization"] = f"Klaviyo-API-Key {api_key}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/vnd.api+json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------- pipeline
def fetch_campaigns(base, api_key, lookback_days):
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    flt = f'and(equals(messages.channel,"email"),greater-than(scheduled_at,{since}))'
    path = "/api/campaigns?filter=" + urllib.request.quote(flt)
    doc = call(base, path, api_key)
    return [
        {
            "id": c["id"],
            "name": c["attributes"]["name"],
            "send_time": c["attributes"].get("send_time"),
        }
        for c in doc.get("data", [])
    ]


def fetch_delivery_stats(base, api_key, campaign_ids):
    payload = {
        "data": {
            "type": "campaign-values-report",
            "attributes": {
                "timeframe": {"key": "last_7_days"},
                "statistics": ["recipients", "delivered", "delivery_rate",
                               "bounced", "bounce_rate"],
                "filter": "any(campaign_id,[" + ",".join(f'"{i}"' for i in campaign_ids) + "])",
            },
        }
    }
    doc = call(base, "/api/campaign-values-reports", api_key, payload)
    out = {}
    for row in doc["data"]["attributes"]["results"]:
        out[row["groupings"]["campaign_id"]] = row["statistics"]
    return out


def fetch_bounce_split(base, api_key, campaign_ids):
    """Hard vs soft split from the 'Bounced Email' metric, grouped by
    attributed campaign + bounce type."""
    payload = {
        "data": {
            "type": "metric-aggregate",
            "attributes": {
                "measurements": ["count"],
                "by": ["$attributed_message", "bounce_type"],
                "filter": ["any($attributed_message,["
                           + ",".join(f'"{i}"' for i in campaign_ids) + "])"],
            },
        }
    }
    doc = call(base, "/api/metric-aggregates", api_key, payload)
    split = {cid: {"hard": 0, "soft": 0} for cid in campaign_ids}
    for row in doc["data"]["attributes"]["results"]:
        cid, btype = row["dimensions"][0], row["dimensions"][1]
        count = row["measurements"]["count"][0]
        if cid in split:
            split[cid]["hard" if "hard" in btype.lower() else "soft"] += count
    return split


def evaluate(campaigns, stats, split, thresholds):
    results = []
    for c in campaigns:
        st = stats.get(c["id"], {})
        sp = split.get(c["id"], {"hard": 0, "soft": 0})
        recipients = st.get("recipients", 0) or 1
        hard_rate = sp["hard"] / recipients
        soft_rate = sp["soft"] / recipients
        total_rate = st.get("bounce_rate", (sp["hard"] + sp["soft"]) / recipients)
        breaches = []
        if hard_rate > thresholds["hard_bounce_rate"]:
            breaches.append(("hard", hard_rate, thresholds["hard_bounce_rate"]))
        if soft_rate > thresholds["soft_bounce_rate"]:
            breaches.append(("soft", soft_rate, thresholds["soft_bounce_rate"]))
        if total_rate > thresholds["total_bounce_rate"]:
            breaches.append(("total", total_rate, thresholds["total_bounce_rate"]))
        results.append(
            {
                **c,
                "recipients": st.get("recipients", 0),
                "delivered": st.get("delivered", 0),
                "hard_rate": hard_rate,
                "soft_rate": soft_rate,
                "total_rate": total_rate,
                "breaches": breaches,
                "flagged": bool(breaches),
                # hard bounces are the reputation killer -> red; soft/total -> orange
                "severity": "red" if any(b[0] == "hard" for b in breaches)
                            else ("orange" if breaches else "ok"),
            }
        )
    return results


# ---------------------------------------------------------------- slack
def pct(x):
    return f"{x * 100:.2f}%"


COLORS = {"red": "#E01E5A", "orange": "#ECB22E", "green": "#2EB67D"}


def build_slack_blocks(results, thresholds, lookback_days):
    flagged = [r for r in results if r["flagged"]]
    healthy = [r for r in results if not r["flagged"]]
    icon = "🚨" if any(r["severity"] == "red" for r in flagged) else (
        "⚠️" if flagged else "✅")

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": f"{icon} Klaviyo Bounce Monitor"}},
        {"type": "context",
         "elements": [{"type": "mrkdwn",
                       "text": f"Last {lookback_days} days · "
                               f"*{len(results)}* campaigns checked · "
                               f"*{len(flagged)}* flagged · {len(healthy)} healthy"}]},
    ]

    def metric_field(label, rate, breached, limit):
        mark = "⚠️ " if breached else ""
        return {"type": "mrkdwn",
                "text": f"*{label}*\n{mark}{pct(rate)} · limit {pct(limit)}"}

    attachments = []
    for r in flagged:
        breached = {kind for kind, _, _ in r["breaches"]}
        headline = ("hard bounces elevated" if r["severity"] == "red"
                    else "soft/total bounces elevated")
        attachments.append({
            "color": COLORS[r["severity"]],
            "blocks": [
                {"type": "section",
                 "text": {"type": "mrkdwn",
                          "text": f"*{r['name']}* — {headline}\n"
                                  f"Sent {r['send_time'][:16].replace('T', ' ')} UTC"},
                 "fields": [
                     metric_field("Hard bounce", r["hard_rate"],
                                  "hard" in breached, thresholds["hard_bounce_rate"]),
                     metric_field("Soft bounce", r["soft_rate"],
                                  "soft" in breached, thresholds["soft_bounce_rate"]),
                     metric_field("Total bounce", r["total_rate"],
                                  "total" in breached, thresholds["total_bounce_rate"]),
                     {"type": "mrkdwn",
                      "text": f"*Delivered*\n{r['delivered']:,} / {r['recipients']:,}"},
                 ]},
            ],
        })

    if healthy:
        attachments.append({
            "color": COLORS["green"],
            "blocks": [
                {"type": "section",
                 "text": {"type": "mrkdwn",
                          "text": f"*{len(healthy)} healthy* · " + " · ".join(
                              f"{r['name']} ({pct(r['total_rate'])})" for r in healthy)}},
            ],
        })

    return {"blocks": blocks, "attachments": attachments}


def post_to_slack(payload, webhook_url):
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


# ---------------------------------------------------------------- preview
def write_preview(payload, results, path):
    """Render the Block Kit message as a Slack-look-alike HTML file."""
    import re as _re

    def mrkdwn(txt):
        txt = txt.replace("\n", "<br>")
        txt = _re.sub(r"\*(.+?)\*", r"<b>\1</b>", txt)
        txt = _re.sub(r"_(.+?)_", r"<i>\1</i>", txt)
        return txt

    def render_blocks(blocks):
        rows = []
        for block in blocks:
            if block["type"] == "header":
                rows.append(f'<div class="bk-header">{block["text"]["text"]}</div>')
            elif block["type"] == "section":
                rows.append(f'<div class="bk-section">{mrkdwn(block["text"]["text"])}</div>')
                if block.get("fields"):
                    cells = "".join(f'<div class="bk-field">{mrkdwn(f["text"])}</div>'
                                    for f in block["fields"])
                    rows.append(f'<div class="bk-fields">{cells}</div>')
            elif block["type"] == "divider":
                rows.append('<div class="bk-divider"></div>')
            elif block["type"] == "context":
                rows.append(f'<div class="bk-context">{mrkdwn(block["elements"][0]["text"])}</div>')
        return rows

    rows = render_blocks(payload.get("blocks", []))
    for att in payload.get("attachments", []):
        inner = "\n".join(render_blocks(att.get("blocks", [])))
        rows.append(f'<div class="bk-card" style="border-left-color:{att["color"]}">{inner}</div>')
    body = "\n".join(rows)
    flagged = sum(1 for r in results if r["flagged"])
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Slack preview — Klaviyo Bounce Monitor</title>
<style>
  body {{ background:#1a1d21; color:#d1d2d3; font:15px/1.45 -apple-system,'Segoe UI',sans-serif;
         display:flex; justify-content:center; padding:40px 16px; }}
  .msg {{ max-width:640px; width:100%; background:#222529; border:1px solid #35383c;
          border-radius:12px; padding:20px 24px; }}
  .meta {{ display:flex; align-items:center; gap:10px; margin-bottom:12px; }}
  .avatar {{ width:36px;height:36px;border-radius:6px;background:#4a154b;display:flex;
             align-items:center;justify-content:center;font-size:20px; }}
  .botname {{ font-weight:700; color:#fff; }} .bottag {{ font-size:11px;background:#35383c;
             border-radius:3px;padding:1px 4px;color:#9a9b9c; }}
  .ts {{ color:#9a9b9c; font-size:12px; }}
  .bk-header {{ font-size:19px; font-weight:800; color:#fff; margin:6px 0 10px; }}
  .bk-section {{ margin:10px 0; }}
  .bk-divider {{ border-top:1px solid #35383c; margin:14px 0; }}
  .bk-context {{ color:#9a9b9c; font-size:13px; }}
  .bk-card {{ border-left:4px solid #666; border-radius:4px; background:#1e2124;
              padding:10px 14px; margin:10px 0; }}
  .bk-fields {{ display:grid; grid-template-columns:1fr 1fr; gap:8px 16px; margin-top:10px; }}
  .bk-field {{ font-size:14px; }}
  b {{ color:#fff; }} i {{ color:#9a9b9c; }}
</style></head><body>
<div class="msg">
  <div class="meta"><div class="avatar">📬</div>
    <div><span class="botname">Bounce Monitor</span> <span class="bottag">APP</span><br>
    <span class="ts">today · {flagged} campaign(s) flagged</span></div></div>
  {body}
</div></body></html>"""
    Path(path).write_text(html)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mock", action="store_true",
                    help="use local mock_klaviyo_server.py instead of the real API")
    ap.add_argument("--preview", action="store_true",
                    help="write slack_preview.html next to this script")
    ap.add_argument("--config", default=str(HERE / "config.json"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    thresholds = cfg["thresholds"]
    lookback = cfg["lookback_days"]

    base = MOCK_BASE if args.mock else REAL_BASE
    api_key = None if args.mock else os.environ.get("KLAVIYO_API_KEY")
    if not args.mock and not api_key:
        sys.exit("Set KLAVIYO_API_KEY for real mode, or run with --mock for the demo.")

    print(f"→ Fetching campaigns from the last {lookback} days ({base}) …")
    campaigns = fetch_campaigns(base, api_key, lookback)
    print(f"  {len(campaigns)} campaigns found")
    if not campaigns:
        print("Nothing sent in the window — no alert needed.")
        return

    ids = [c["id"] for c in campaigns]
    print("→ Pulling delivery stats and hard/soft bounce split …")
    stats = fetch_delivery_stats(base, api_key, ids)
    split = fetch_bounce_split(base, api_key, ids)

    results = evaluate(campaigns, stats, split, thresholds)
    for r in results:
        mark = {"red": "🔴", "orange": "🟠", "ok": "✅"}[r["severity"]]
        print(f"  {mark} {r['name']:<32} hard {pct(r['hard_rate'])}  "
              f"soft {pct(r['soft_rate'])}  total {pct(r['total_rate'])}")

    payload = build_slack_blocks(results, thresholds, lookback)

    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook:
        status = post_to_slack(payload, webhook)
        print(f"→ Posted to Slack (HTTP {status})")
    else:
        print("→ SLACK_WEBHOOK_URL not set — dry run, Block Kit payload below:\n")
        print(json.dumps(payload, indent=2))

    if args.preview:
        out = HERE / "slack_preview.html"
        write_preview(payload, results, out)
        print(f"→ Preview written to {out}")


if __name__ == "__main__":
    main()
