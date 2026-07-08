"""Tools = plain functions the model can ask you to run, plus a JSON-schema
description so the model knows they exist.

A "tool call" is not magic: the model replies with the name of a function and
some arguments; YOUR code runs the real function and feeds the result back. The
model never touches the network or the disk — you do.
"""

import json
import time
import urllib.request
from pathlib import Path

GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"
DASHBOARD_PATH = "harness-dashboard.html"   # distinct name; won't clobber the product page


# ---- the actual function -----------------------------------------------------

def fetch_feed():
    """Return current significant (Orange/Red) GDACS events as a JSON string."""
    req = urllib.request.Request(GDACS_URL, headers={"User-Agent": "hadr-harness/1.0"})
    last = None
    for _ in range(3):                     # GDACS occasionally hangs; retry
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except Exception as e:
            last = e
            time.sleep(2)
    else:
        return json.dumps({"error": f"feed unreachable: {last}"})

    events = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        if p.get("alertlevel") in ("Orange", "Red"):
            events.append({
                "id": p.get("eventid"),
                "type": p.get("eventtype"),
                "title": p.get("name"),
                "country": p.get("country"),
                "alert": p.get("alertlevel"),
            })
    return json.dumps({"count": len(events), "events": events})


# ---- the schema the model sees -----------------------------------------------

FETCH_FEED_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_feed",
        "description": "Fetch current significant (Orange/Red) disaster events "
                       "from the GDACS feed. Takes no arguments.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}


# ---- second tool: write the dashboard ----------------------------------------

def write_dashboard(html):
    """Save a full HTML page (composed by the model) to disk. Returns a receipt."""
    Path(DASHBOARD_PATH).write_text(html, encoding="utf-8")
    return json.dumps({"saved": DASHBOARD_PATH, "bytes": len(html)})


WRITE_DASHBOARD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_dashboard",
        "description": "Save the assessed events as an HTML dashboard page. Pass "
                       "the complete, self-contained HTML document.",
        "parameters": {
            "type": "object",
            "properties": {
                "html": {
                    "type": "string",
                    "description": "The full HTML document to save.",
                },
            },
            "required": ["html"],
        },
    },
}
