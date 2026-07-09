"""Tools = plain functions the model can ask you to run, plus a JSON-schema
description so the model knows they exist.

A "tool call" is not magic: the model replies with the name of a function and
some arguments; YOUR code runs the real function and feeds the result back. The
model never touches the network or the disk — you do.

Sources here mirror the HADR project's feeds, plus NASA EONET:
  - fetch_feed       GDACS   (multi-hazard, has alert levels)   — no arguments
  - fetch_usgs       USGS    (earthquakes)                      — args: magnitude, window
  - fetch_reliefweb  ReliefWeb RSS (curated humanitarian)       — arg: limit
  - fetch_eonet      NASA EONET (natural events, no severity)   — args: category, limit
and one writer: write_dashboard.
"""

import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

DASHBOARD_PATH = "harness-dashboard.html"   # distinct name; won't clobber the product page

GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson"
RELIEFWEB_RSS = "https://reliefweb.int/disasters/rss.xml"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
EONET_CATEGORIES = [
    "drought", "dustHaze", "earthquakes", "floods", "landslides", "manmade",
    "seaLakeIce", "severeStorms", "snow", "tempExtremes", "volcanoes",
    "waterColor", "wildfires",
]


def _get(url, tries=3, timeout=20):
    """GET a URL with a User-Agent (needed to pass CDNs) and simple retries.
    Returns the response body as text; raises on final failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "hadr-harness/1.0"})
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            last = e
            time.sleep(2)
    raise last


def _ms_to_iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


# ---- source 1: GDACS (multi-hazard, has alert levels) ------------------------

def fetch_feed():
    """Return current significant (Orange/Red) GDACS events as a JSON string."""
    try:
        data = json.loads(_get(GDACS_URL))
    except Exception as e:
        return json.dumps({"error": f"GDACS unreachable: {e}"})
    events = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        if p.get("alertlevel") in ("Orange", "Red"):
            events.append({
                "id": p.get("eventid"), "type": p.get("eventtype"),
                "title": p.get("name"), "country": p.get("country"),
                "alert": p.get("alertlevel"),
            })
    return json.dumps({"source": "GDACS", "count": len(events), "events": events})


# ---- source 2: USGS earthquakes (args: magnitude, window) --------------------

def fetch_usgs(min_magnitude=4.5, window="day"):
    """Return recent earthquakes at/above min_magnitude over the time window."""
    mag_tier = ("4.5" if min_magnitude >= 4.5 else "2.5" if min_magnitude >= 2.5
                else "1.0" if min_magnitude >= 1.0 else "all")
    window = window if window in ("hour", "day", "week") else "day"
    url = USGS_URL.format(feed=f"{mag_tier}_{window}")
    try:
        data = json.loads(_get(url))
    except Exception as e:
        return json.dumps({"error": f"USGS unreachable: {e}"})
    quakes = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        if (p.get("mag") or 0) >= min_magnitude:
            c = f.get("geometry", {}).get("coordinates", [None, None, None])
            quakes.append({
                "id": f.get("id"), "mag": p.get("mag"), "place": p.get("place"),
                "time": _ms_to_iso(p["time"]) if p.get("time") else None,
                "coords": c[:2],
            })
    return json.dumps({"source": "USGS", "window": window,
                       "min_magnitude": min_magnitude, "count": len(quakes),
                       "events": quakes})


# ---- source 3: ReliefWeb (curated humanitarian, RSS) -------------------------

def fetch_reliefweb(limit=10):
    """Return recent declared disasters from the ReliefWeb RSS feed."""
    try:
        root = ET.fromstring(_get(RELIEFWEB_RSS))
    except Exception as e:
        return json.dumps({"error": f"ReliefWeb unreachable: {e}"})
    items = []
    for item in root.findall(".//item")[:int(limit)]:
        items.append({
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "date": (item.findtext("pubDate") or "").strip(),
        })
    return json.dumps({"source": "ReliefWeb", "count": len(items), "events": items})


# ---- source 4: NASA EONET (natural events, no severity; args: category) ------

def fetch_eonet(category=None, limit=10):
    """Return current natural events from NASA EONET, optionally by category.
    NOTE: EONET has no severity/alert level — it is a catalog of what/where/when."""
    url = f"{EONET_URL}?status=open&limit={int(limit)}"
    if category:
        url += f"&category={category}"
    try:
        data = json.loads(_get(url))
    except Exception as e:
        return json.dumps({"error": f"EONET unreachable: {e}"})
    events = []
    for e in data.get("events", []):
        geo = (e.get("geometry") or [{}])[-1]
        cats = e.get("categories") or [{}]
        events.append({
            "id": e.get("id"), "title": e.get("title"),
            "category": cats[0].get("title"),
            "date": geo.get("date"), "coords": geo.get("coordinates"),
        })
    return json.dumps({"source": "EONET", "category": category or "all",
                       "count": len(events), "events": events})


# ---- writer: save the dashboard ---------------------------------------------

def write_dashboard(html):
    """Save a full HTML page (composed by the model) to disk. Returns a receipt."""
    Path(DASHBOARD_PATH).write_text(html, encoding="utf-8")
    return json.dumps({"saved": DASHBOARD_PATH, "bytes": len(html)})


# ---- the schemas the model sees ---------------------------------------------

FETCH_FEED_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_feed",
        "description": "Fetch current significant (Orange/Red) multi-hazard events "
                       "from GDACS. GDACS is the only source with alert levels. No arguments.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

FETCH_USGS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_usgs",
        "description": "Fetch recent earthquakes from USGS at or above a magnitude, "
                       "over a time window.",
        "parameters": {
            "type": "object",
            "properties": {
                "min_magnitude": {"type": "number", "description": "e.g. 4.5"},
                "window": {"type": "string", "enum": ["hour", "day", "week"]},
            },
            "required": [],
        },
    },
}

FETCH_RELIEFWEB_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_reliefweb",
        "description": "Fetch recently declared humanitarian disasters from ReliefWeb "
                       "(curated by UN OCHA; slower-moving, no severity score).",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "max items (default 10)"}},
            "required": [],
        },
    },
}

FETCH_EONET_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_eonet",
        "description": "List current natural events from NASA EONET, optionally "
                       "filtered by category. EONET has no severity level.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": EONET_CATEGORIES,
                             "description": "e.g. wildfires, floods, volcanoes, severeStorms"},
                "limit": {"type": "integer", "description": "max events (default 10)"},
            },
            "required": [],
        },
    },
}

WRITE_DASHBOARD_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_dashboard",
        "description": "Save the assessed events as an HTML dashboard page. Pass "
                       "the complete, self-contained HTML document.",
        "parameters": {
            "type": "object",
            "properties": {"html": {"type": "string", "description": "The full HTML document."}},
            "required": ["html"],
        },
    },
}
