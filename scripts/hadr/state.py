"""Change detection and state persistence — the deterministic gate.

This is the step that decides whether the reporting step runs at all. It never
calls a model (ADR: the model never decides whether to wake up). It compares
the current *reportable* (Orange/Red) event set against the last committed
state and reports what changed.

Only reportable events are tracked. Green churn — the overwhelming majority of
feed traffic — must never wake the pipeline, so Green events never enter the
state file and never count as a change. A consequence, by design: on a morning
when only Green events change, the page is not rebuilt and shows the previous
day's events. That is the intended "don't wake for Green" behaviour.

State lives as committed JSON (ADR-0003) so git history is the audit log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .model import Event, is_reportable


def fingerprint(event: Event) -> dict:
    """The material facts about an event; a change in any of these is news."""
    return {
        "alert_level": event.alert_level,
        "alert_score": round(event.alert_score, 2),
        "hazard_type": event.hazard_type,
        "title": event.title,
        "event_time": event.event_time.isoformat() if event.event_time else None,
    }


@dataclass
class ChangeReport:
    added: list[str] = field(default_factory=list)      # new to the reportable set
    removed: list[str] = field(default_factory=list)    # gone (deleted or downgraded off floor)
    changed: list[str] = field(default_factory=list)    # material revision (level, score, ...)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        if not self.has_changes:
            return "no change"
        parts = []
        if self.added:
            parts.append(f"{len(self.added)} new ({', '.join(self.added)})")
        if self.changed:
            parts.append(f"{len(self.changed)} revised ({', '.join(self.changed)})")
        if self.removed:
            parts.append(f"{len(self.removed)} gone ({', '.join(self.removed)})")
        return "; ".join(parts)


def detect_changes(prev_state: dict, current_events: list[Event]) -> ChangeReport:
    """Diff the reportable set in `current_events` against `prev_state`.

    `current_events` may contain all events; only the reportable ones are
    considered, so a downgrade off the Orange/Red floor surfaces as a removal.
    """
    prev = prev_state.get("events", {})
    curr = {e.event_id: fingerprint(e) for e in current_events if is_reportable(e)}

    report = ChangeReport()
    for event_id, fp in curr.items():
        if event_id not in prev:
            report.added.append(event_id)
        elif prev[event_id] != fp:
            report.changed.append(event_id)
    for event_id in prev:
        if event_id not in curr:
            report.removed.append(event_id)

    report.added.sort()
    report.changed.sort()
    report.removed.sort()
    return report


def load_state(path: str | Path) -> dict:
    """Load the state file, or an empty state if it does not exist yet."""
    p = Path(path)
    if not p.exists():
        return {"events": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save_state(path: str | Path, events: list[Event], generated_at: datetime) -> None:
    """Persist the reportable events' fingerprints as the new state."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "generated_at": generated_at.isoformat(),
        "events": {
            e.event_id: fingerprint(e) for e in events if is_reportable(e)
        },
    }
    # Sorted keys keep the committed file diff-friendly.
    p.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
