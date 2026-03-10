#!/usr/bin/env python3
"""Minimal Flask-based kanban dashboard for SpecKitty work packages."""

import argparse
import os
import re
import signal
import sys
from pathlib import Path

try:
    from flask import Flask, Response
except ImportError:
    print("Flask is required: pip install flask")
    sys.exit(1)

app = Flask(__name__)
FEATURE = ""
WP_DIR = Path()

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>SpecKitty Dashboard - {feature}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
  h1 {{ text-align: center; margin-bottom: 20px; color: #e94560; }}
  .board {{ display: flex; gap: 16px; justify-content: center; }}
  .lane {{ flex: 1; max-width: 280px; background: #16213e; border-radius: 8px; padding: 12px; min-height: 300px; }}
  .lane h2 {{ text-align: center; padding: 8px; border-radius: 4px; margin-bottom: 12px; font-size: 14px; text-transform: uppercase; }}
  .lane.planned h2 {{ background: #555; }}
  .lane.doing h2 {{ background: #1a56db; }}
  .lane.for_review h2 {{ background: #c27803; }}
  .lane.done h2 {{ background: #057a55; }}
  .card {{ background: #0f3460; border-radius: 6px; padding: 10px; margin-bottom: 8px; }}
  .card .id {{ font-weight: bold; color: #e94560; }}
  .card .title {{ font-size: 13px; margin-top: 4px; }}
  .card .agent {{ font-size: 11px; color: #888; margin-top: 4px; }}
  .progress {{ text-align: center; margin-top: 20px; font-size: 18px; }}
  .bar {{ width: 60%; margin: 10px auto; background: #16213e; border-radius: 8px; height: 24px; overflow: hidden; }}
  .bar .fill {{ height: 100%; background: #057a55; transition: width 0.3s; }}
</style>
</head>
<body>
<h1>SpecKitty: {feature}</h1>
<div class="board">{lanes}</div>
<div class="progress">
  Progress: {done}/{total} done ({pct}%)
  <div class="bar"><div class="fill" style="width:{pct}%"></div></div>
</div>
</body>
</html>"""


def parse_wp_frontmatter(filepath: Path) -> dict:
    """Parse YAML frontmatter from a WP file."""
    text = filepath.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    data = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip().strip('"')
    # Extract title from heading
    title_match = re.search(r"^# Work Package WP\d+: (.+)$", text, re.MULTILINE)
    data["title"] = title_match.group(1) if title_match else ""
    return data


def build_board() -> str:
    """Build the HTML kanban board."""
    lanes = {"planned": [], "doing": [], "for_review": [], "done": []}
    wp_path = WP_DIR / FEATURE

    if wp_path.is_dir():
        for f in sorted(wp_path.glob("WP*.md")):
            wp = parse_wp_frontmatter(f)
            lane = wp.get("lane", "planned")
            if lane in lanes:
                lanes[lane].append(wp)

    total = sum(len(v) for v in lanes.values())
    done = len(lanes["done"])
    pct = (done * 100 // total) if total > 0 else 0

    lanes_html = ""
    for lane_name, label in [
        ("planned", "Planned"),
        ("doing", "Doing"),
        ("for_review", "For Review"),
        ("done", "Done"),
    ]:
        cards = ""
        for wp in lanes[lane_name]:
            agent_line = f'<div class="agent">{wp.get("agent", "")}</div>' if wp.get("agent") else ""
            cards += f'<div class="card"><span class="id">{wp.get("id", "?")}</span><div class="title">{wp.get("title", "")}</div>{agent_line}</div>'
        lanes_html += f'<div class="lane {lane_name}"><h2>{label}</h2>{cards}</div>'

    return HTML_TEMPLATE.format(feature=FEATURE, lanes=lanes_html, done=done, total=total, pct=pct)


@app.route("/")
def index():
    return Response(build_board(), content_type="text/html")


def main():
    global FEATURE, WP_DIR

    parser = argparse.ArgumentParser(description="SpecKitty Dashboard")
    parser.add_argument("--feature", required=True, help="Feature branch name")
    parser.add_argument("--port", type=int, default=5050, help="Port (default: 5050)")
    parser.add_argument("--kill", action="store_true", help="Kill running dashboard")
    args = parser.parse_args()

    if args.kill:
        os.system("pkill -f 'dashboard.py.*--feature'")
        print("Dashboard stopped.")
        return

    FEATURE = args.feature
    WP_DIR = Path(__file__).resolve().parent.parent.parent / "work-packages"

    print(f"SpecKitty Dashboard: http://localhost:{args.port}")
    print(f"Feature: {FEATURE}")
    print("Press Ctrl+C to stop.")

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
