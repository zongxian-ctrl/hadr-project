"""Fetch and normalise the GDACS event list.

GDACS is the trigger feed (ADR-0001). Two traps this module handles:
  - GeoJSON coordinates are [lon, lat] — the normalised event un-swaps them.
  - GDACS timestamps carry no timezone offset but are UTC — we attach it
    explicitly rather than letting a naive parse drift by local offset.

`EVENTS4APP` is an unversioned internal API, so parsing is defensive: unknown
hazard types pass through lower-cased, missing fields fall back to sane
defaults rather than raising.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone

from .model import Event

FEED_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"

# GDACS eventtype code -> human-readable hazard type.
_HAZARD_TYPES = {
    "EQ": "earthquake",
    "TC": "cyclone",
    "FL": "flood",
    "VO": "volcano",
    "DR": "drought",
    "WF": "wildfire",
    "TS": "tsunami",
}


def fetch_raw(url: str = FEED_URL, timeout: int = 30) -> dict:
    """Fetch the GDACS event list GeoJSON. Returns the parsed JSON dict."""
    req = urllib.request.Request(url, headers={"User-Agent": "hadr-monitor/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_utc(value: str | None) -> datetime | None:
    """Parse a GDACS timestamp (no offset, but UTC) into tz-aware UTC."""
    if not value:
        return None
    # Tolerate a trailing 'Z' if GDACS ever adds one.
    value = value.rstrip("Z")
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=timezone.utc)


def _feature_to_event(feature: dict) -> Event | None:
    props = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates") or [None, None]

    event_id = props.get("eventid")
    if event_id is None:
        return None  # nothing we can key on; skip defensively

    lon, lat = (coords + [None, None])[:2]
    code = (props.get("eventtype") or "").upper()
    glide = (props.get("glide") or "").strip() or None
    url = props.get("url") or {}

    return Event(
        source_feed="GDACS",
        event_id=str(event_id),
        hazard_type=_HAZARD_TYPES.get(code, code.lower() or "unknown"),
        title=props.get("name") or props.get("description") or "Untitled event",
        country=props.get("country") or "",
        alert_level=props.get("alertlevel") or "Unknown",
        alert_score=float(props.get("alertscore") or 0.0),
        latitude=float(lat) if lat is not None else 0.0,
        longitude=float(lon) if lon is not None else 0.0,
        event_time=_parse_utc(props.get("fromdate")),
        glide=glide,
        report_url=url.get("report") or "",
        description=props.get("htmldescription") or "",
    )


def parse_events(raw: dict) -> list[Event]:
    """Normalise a GDACS FeatureCollection dict into a list of Events."""
    features = raw.get("features") or []
    events = [_feature_to_event(f) for f in features]
    return [e for e in events if e is not None]


def fetch_events(url: str = FEED_URL, timeout: int = 30) -> list[Event]:
    """Fetch and normalise in one call."""
    return parse_events(fetch_raw(url, timeout=timeout))
