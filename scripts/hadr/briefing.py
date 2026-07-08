"""Build the briefing — the deterministic input the /sitrep model reads.

The gate (deterministic) fetches, detects change, and writes this. The model
(judgement) reads it and writes the report. Keeping the seam here means the
model never re-fetches or re-derives what changed: it is handed the current
reportable events and an explicit corrections diff, and only decides how to
say it.
"""

from __future__ import annotations

from datetime import datetime

from .model import Event, is_reportable
from .state import ChangeReport, fingerprint


def _event_dict(e: Event) -> dict:
    return {
        "event_id": e.event_id,
        "hazard_type": e.hazard_type,
        "title": e.title,
        "country": e.country,
        "alert_level": e.alert_level,
        "alert_score": e.alert_score,
        "event_time": e.event_time.isoformat() if e.event_time else None,
        "latitude": e.latitude,
        "longitude": e.longitude,
        "glide": e.glide,
        "report_url": e.report_url,
    }


def build_briefing(
    prev_state: dict,
    events: list[Event],
    change_report: ChangeReport,
    generated_at: datetime,
    feed_status: str = "ok",
) -> dict:
    """Assemble the briefing dict from current events and the change report.

    - `events` is the current reportable set (Green is dropped here).
    - `corrections` carries before/after for revised events and before-only for
      removed ones, so the model can write the Updates & Corrections section
      without touching feeds or prior state itself.
    """
    prev = prev_state.get("events", {})
    reportable = sorted(
        (e for e in events if is_reportable(e)),
        key=lambda e: (e.severity_rank, e.alert_score),
        reverse=True,
    )
    by_id = {e.event_id: e for e in reportable}

    corrections: list[dict] = []
    for eid in change_report.changed:
        entry = {"type": "revised", "event_id": eid, "before": prev.get(eid)}
        if eid in by_id:
            entry["after"] = fingerprint(by_id[eid])
        corrections.append(entry)
    for eid in change_report.removed:
        corrections.append({"type": "removed", "event_id": eid, "before": prev.get(eid)})

    return {
        "generated_at": generated_at.isoformat(),
        "feed_status": feed_status,
        "events": [_event_dict(e) for e in reportable],
        "new_event_ids": list(change_report.added),
        "corrections": corrections,
    }
