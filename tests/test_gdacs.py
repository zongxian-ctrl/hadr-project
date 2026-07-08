"""Tests for GDACS feed normalisation (slice 1).

These test the deterministic parsing layer against a fixture — never the live
feed (see the project's testing decisions: fixtures, not the live world).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from hadr.gdacs import parse_events
from hadr.model import is_reportable

FIXTURE = Path(__file__).parent / "fixtures" / "gdacs_sample.json"


def load_events():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return parse_events(raw)


def test_parses_all_features():
    events = load_events()
    assert len(events) == 3


def test_hazard_type_is_normalised():
    events = {e.event_id: e for e in load_events()}
    assert events["1550421"].hazard_type == "earthquake"
    assert events["1000999"].hazard_type == "cyclone"


def test_coordinates_are_lat_lon_not_swapped():
    # GDACS GeoJSON stores [lon, lat]; the normalised event must un-swap them.
    japan = next(e for e in load_events() if e.event_id == "1550421")
    assert japan.latitude == 40.4353
    assert japan.longitude == 141.845


def test_timestamps_are_parsed_as_utc():
    # GDACS timestamps carry no offset but are UTC — must be tz-aware UTC.
    japan = next(e for e in load_events() if e.event_id == "1550421")
    assert japan.event_time == datetime(2026, 7, 6, 11, 29, 36, tzinfo=timezone.utc)
    assert japan.event_time.tzinfo is not None


def test_alert_level_and_glide_captured():
    haiti = next(e for e in load_events() if e.event_id == "1234567")
    assert haiti.alert_level == "Red"
    assert haiti.glide == "EQ-2026-000200-HTI"

    japan = next(e for e in load_events() if e.event_id == "1550421")
    # Empty GLIDE in the feed becomes None, not "".
    assert japan.glide is None


def test_reportable_floor_is_orange_and_red():
    events = {e.event_id: e for e in load_events()}
    assert is_reportable(events["1234567"]) is True   # Red
    assert is_reportable(events["1000999"]) is True   # Orange
    assert is_reportable(events["1550421"]) is False  # Green
