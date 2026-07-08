"""Tests for the briefing generator — the deterministic contract the /sitrep
model reads. The corrections diff (before -> after from prior state) is the
load-bearing part, so it's tested the same way as the change detector.
"""

from datetime import datetime, timezone

from hadr.briefing import build_briefing
from hadr.model import Event
from hadr.state import ChangeReport, fingerprint


def make_event(event_id, alert_level, alert_score=1.0, hazard="earthquake", title=None):
    return Event(
        source_feed="GDACS",
        event_id=event_id,
        hazard_type=hazard,
        title=title or f"{hazard} {event_id}",
        country="Testland",
        alert_level=alert_level,
        alert_score=alert_score,
        latitude=1.5,
        longitude=2.5,
        event_time=datetime(2026, 7, 8, 3, 0, tzinfo=timezone.utc),
        glide=None,
        report_url="https://example.test/e",
        description="",
    )


NOW = datetime(2026, 7, 8, 0, 30, tzinfo=timezone.utc)


def test_only_reportable_events_included_and_sorted_worst_first():
    events = [
        make_event("G", "Green"),
        make_event("O", "Orange", 1.2),
        make_event("R", "Red", 2.9),
    ]
    b = build_briefing({"events": {}}, events, ChangeReport(added=["O", "R"]), NOW)
    ids = [e["event_id"] for e in b["events"]]
    assert ids == ["R", "O"]           # Green excluded, Red before Orange


def test_new_event_ids_passed_through():
    events = [make_event("R", "Red")]
    b = build_briefing({"events": {}}, events, ChangeReport(added=["R"]), NOW)
    assert b["new_event_ids"] == ["R"]


def test_correction_for_revised_event_has_before_and_after():
    before = make_event("R", "Orange", 1.5)
    prev = {"events": {"R": fingerprint(before)}}
    after = make_event("R", "Red", 2.6)
    b = build_briefing(prev, [after], ChangeReport(changed=["R"]), NOW)
    corr = [c for c in b["corrections"] if c["event_id"] == "R"]
    assert len(corr) == 1
    assert corr[0]["type"] == "revised"
    assert corr[0]["before"]["alert_level"] == "Orange"
    assert corr[0]["after"]["alert_level"] == "Red"


def test_correction_for_removed_event_has_before_only():
    gone = make_event("X", "Orange")
    prev = {"events": {"X": fingerprint(gone)}}
    b = build_briefing(prev, [], ChangeReport(removed=["X"]), NOW)
    corr = [c for c in b["corrections"] if c["event_id"] == "X"]
    assert len(corr) == 1
    assert corr[0]["type"] == "removed"
    assert corr[0]["before"]["alert_level"] == "Orange"
    assert "after" not in corr[0]


def test_feed_status_and_generated_at_recorded():
    b = build_briefing({"events": {}}, [], ChangeReport(), NOW, feed_status="ok")
    assert b["feed_status"] == "ok"
    assert b["generated_at"] == NOW.isoformat()


def test_event_dict_carries_fields_the_report_needs():
    b = build_briefing({"events": {}}, [make_event("R", "Red")], ChangeReport(added=["R"]), NOW)
    e = b["events"][0]
    for key in ("event_id", "hazard_type", "title", "country", "alert_level",
                "alert_score", "event_time", "latitude", "longitude", "report_url"):
        assert key in e
