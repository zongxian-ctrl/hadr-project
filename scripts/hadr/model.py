"""The normalised event — the one shape the rest of the pipeline speaks.

Slice 1 populates this from GDACS only. Later slices link USGS physical
events and ReliefWeb situations into the same record (keyed on the GDACS
event id), so the fields here are the cross-feed common ground, not GDACS
trivia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# GDACS alert levels that clear the reporting floor (ADR-0001).
REPORTABLE_LEVELS = frozenset({"Orange", "Red"})

# Severity order for sorting; higher is worse.
_LEVEL_RANK = {"Red": 3, "Orange": 2, "Green": 1}


@dataclass(frozen=True)
class Event:
    source_feed: str          # "GDACS" in slice 1
    event_id: str             # GDACS eventid, as a string
    hazard_type: str          # normalised: "earthquake", "cyclone", ...
    title: str
    country: str
    alert_level: str          # "Green" | "Orange" | "Red"
    alert_score: float
    latitude: float
    longitude: float
    event_time: datetime      # tz-aware UTC
    glide: str | None         # GLIDE number when present, else None
    report_url: str
    description: str

    @property
    def severity_rank(self) -> int:
        return _LEVEL_RANK.get(self.alert_level, 0)


def is_reportable(event: Event) -> bool:
    """True when the event clears the Orange/Red reporting floor (ADR-0001)."""
    return event.alert_level in REPORTABLE_LEVELS
