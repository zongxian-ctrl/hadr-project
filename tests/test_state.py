"""Tests for change detection and state persistence (slice 2).

The gate wakes the reporting step only when the *reportable* (Orange/Red) set
changes — Green churn must not wake it. These tests pin that behaviour, plus
the two easy-to-miss cases: the first-ever run, and running the same feed
twice (idempotence).
"""

from datetime import datetime, timezone

from hadr.model import Event
from hadr.state import detect_changes, fingerprint, load_state, save_state


def make_event(event_id, alert_level, alert_score=1.0, hazard="earthquake"):
    return Event(
        source_feed="GDACS",
        event_id=event_id,
        hazard_type=hazard,
        title=f"{hazard} {event_id}",
        country="Testland",
        alert_level=alert_level,
        alert_score=alert_score,
        latitude=0.0,
        longitude=0.0,
        event_time=datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc),
        glide=None,
        report_url="",
        description="",
    )


def state_of(events):
    """Build the on-disk state dict for a set of events (reportable filtered)."""
    return {"events": {e.event_id: fingerprint(e) for e in events if e.alert_level in ("Orange", "Red")}}


def test_first_ever_run_is_all_new():
    curr = [make_event("A", "Red"), make_event("B", "Orange")]
    report = detect_changes({"events": {}}, curr)
    assert set(report.added) == {"A", "B"}
    assert report.has_changes is True


def test_same_feed_twice_is_unchanged():
    curr = [make_event("A", "Red"), make_event("B", "Orange")]
    prev = state_of(curr)
    report = detect_changes(prev, curr)
    assert report.has_changes is False
    assert report.added == [] and report.removed == [] and report.changed == []


def test_green_only_change_does_not_wake():
    # A Green event appearing or changing must not count as a change.
    prev = state_of([make_event("A", "Red")])
    curr = [make_event("A", "Red"), make_event("G", "Green"), make_event("G2", "Green", 0.2)]
    report = detect_changes(prev, curr)
    assert report.has_changes is False


def test_new_reportable_event_is_added():
    prev = state_of([make_event("A", "Red")])
    curr = [make_event("A", "Red"), make_event("B", "Orange")]
    report = detect_changes(prev, curr)
    assert report.added == ["B"]


def test_deleted_event_is_removed():
    prev = state_of([make_event("A", "Red"), make_event("B", "Orange")])
    curr = [make_event("A", "Red")]
    report = detect_changes(prev, curr)
    assert report.removed == ["B"]


def test_downgrade_below_floor_is_a_removal():
    # Orange -> Green drops out of the reportable set: that is news (removal).
    prev = state_of([make_event("A", "Orange")])
    curr = [make_event("A", "Green")]
    report = detect_changes(prev, curr)
    assert report.removed == ["A"]
    assert report.has_changes is True


def test_alert_level_upgrade_is_a_change():
    prev = state_of([make_event("A", "Orange")])
    curr = [make_event("A", "Red")]
    report = detect_changes(prev, curr)
    assert report.changed == ["A"]


def test_score_revision_is_a_change():
    prev = state_of([make_event("A", "Red", alert_score=2.0)])
    curr = [make_event("A", "Red", alert_score=2.6)]
    report = detect_changes(prev, curr)
    assert report.changed == ["A"]


def test_state_roundtrip(tmp_path):
    path = tmp_path / "seen.json"
    events = [make_event("A", "Red"), make_event("B", "Orange"), make_event("G", "Green")]
    save_state(path, events, datetime(2026, 7, 8, 0, 30, tzinfo=timezone.utc))
    loaded = load_state(path)
    # Green is not persisted (not reportable); A and B are.
    assert set(loaded["events"]) == {"A", "B"}
    # Round-tripping through disk yields no spurious change.
    assert detect_changes(loaded, events).has_changes is False


def test_load_missing_state_is_empty():
    assert load_state("does-not-exist.json") == {"events": {}}
