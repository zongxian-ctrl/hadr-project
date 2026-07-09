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

import base64
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

DASHBOARD_PATH = "harness-dashboard.html"   # distinct name; won't clobber the product page

GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"
USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson"
RELIEFWEB_RSS = "https://reliefweb.int/disasters/rss.xml"
NWS_ALERTS = "https://api.weather.gov/alerts/active"
EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
# NASA WorldView Snapshot API — wraps GIBS; returns one JPEG for a bbox+date.
WORLDVIEW_URL = "https://wvs.earthdata.nasa.gov/api/v1/snapshot"
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
                "coords": (f.get("geometry") or {}).get("coordinates"),  # [lon, lat]
                "date": p.get("fromdate"),
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


# ---- source 4b: NWS severe-weather alerts (US; keyless, HAS severity) --------

_NWS_ORDER = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}


def _centroid(geometry):
    """Rough centroid (lon, lat) of any GeoJSON geometry, or (None, None)."""
    if not geometry:
        return None, None
    pts = []

    def walk(x):
        if isinstance(x, list) and x and isinstance(x[0], (int, float)) and len(x) >= 2:
            pts.append((x[0], x[1]))
        elif isinstance(x, list):
            for y in x:
                walk(y)

    walk(geometry.get("coordinates"))
    if not pts:
        return None, None
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def fetch_nws(min_severity="Severe", limit=10):
    """Return active US NWS weather alerts at/above a severity (Extreme/Severe/...)."""
    floor = _NWS_ORDER.get(min_severity, 3)
    try:
        data = json.loads(_get(NWS_ALERTS))
    except Exception as e:
        return json.dumps({"error": f"NWS unreachable: {e}"})
    out = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        if _NWS_ORDER.get(p.get("severity"), 0) < floor:
            continue
        lon, lat = _centroid(f.get("geometry"))
        out.append({
            "event": p.get("event"), "severity": p.get("severity"),
            "area": (p.get("areaDesc") or "").split(";")[0].strip(),
            "headline": p.get("headline"), "lon": lon, "lat": lat,
            "date": p.get("onset") or p.get("effective"),
        })
        if len(out) >= int(limit):
            break
    return json.dumps({"source": "NWS", "count": len(out), "events": out})


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


# ---- satellite imagery: NASA GIBS via the WorldView snapshot API -------------
# EONET/GDACS/USGS give WHERE + WHEN; GIBS gives the picture. Resolution is
# ~250m-1km (MODIS/VIIRS): good for smoke plumes, flood extent, burn scars —
# NOT building-level damage.
#
# Default is TRUE COLOR — the raw daily image the satellite saw, no overlays.
# FIRE_LAYER (thermal-anomaly "red dots") is available but OFF by default; pass
# it explicitly via `layers=` only if you want that overlay.

TRUECOLOR = "VIIRS_SNPP_CorrectedReflectance_TrueColor"   # natural color, daily
FALSECOLOR_BURN = "VIIRS_SNPP_CorrectedReflectance_BandsM11-I2-I1"  # real bands; burn scars/smoke pop
FIRE_LAYER = "VIIRS_SNPP_Thermal_Anomalies_375m_All"     # optional overlay (the red dots)


def snapshot_url(lat, lon, date, span=1.0, layers=None, width=512, height=512):
    """Build a WorldView/GIBS snapshot image URL for a place + date (no download).
    Defaults to true color (no overlays) — what the satellite actually saw."""
    layers = layers or TRUECOLOR
    bbox = f"{lat - span},{lon - span},{lat + span},{lon + span}"  # EPSG:4326 = lat,lon
    q = urlencode({
        "REQUEST": "GetSnapshot", "LAYERS": layers, "CRS": "EPSG:4326",
        "TIME": str(date)[:10], "BBOX": bbox, "FORMAT": "image/jpeg",
        "WIDTH": width, "HEIGHT": height,
    })
    return f"{WORLDVIEW_URL}?{q}"


def snapshot_data_uri(lat, lon, date, span=1.0, layers=None):
    """Download the snapshot and return it as a base64 data: URI (self-contained
    for embedding in HTML), or None if the fetch fails."""
    url = snapshot_url(lat, lon, date, span=span, layers=layers)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hadr-harness/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    except Exception:
        return None


def fetch_imagery(lat, lon, date, span=1.0):
    """Tool form: return a satellite-image URL for a place + date (aftermath)."""
    return json.dumps({"image_url": snapshot_url(lat, lon, date, span=span)})


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

FETCH_NWS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_nws",
        "description": "Fetch active US National Weather Service alerts at or above "
                       "a severity (Extreme, Severe, Moderate, Minor). US-only.",
        "parameters": {
            "type": "object",
            "properties": {
                "min_severity": {"type": "string",
                                 "enum": ["Extreme", "Severe", "Moderate", "Minor"]},
                "limit": {"type": "integer"},
            },
            "required": [],
        },
    },
}

FETCH_IMAGERY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_imagery",
        "description": "Get a NASA satellite image URL (true-color + fire hotspots) "
                       "for a location and date — the aftermath view of an event. "
                       "~250m resolution: smoke/flood/burn-scar scale, not buildings.",
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number"}, "lon": {"type": "number"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "span": {"type": "number", "description": "half-width in degrees (default 1.0)"},
            },
            "required": ["lat", "lon", "date"],
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
