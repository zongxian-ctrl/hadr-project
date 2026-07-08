# ADR-0004: One unified event view, joined by GLIDE then correlation

Status: accepted (2026-07-08, build-plan-product interview)

## Context

The three feeds have different ontologies: a USGS record is one rupture, a
GDACS event is an evolving multi-episode alert, a ReliefWeb disaster is a
humanitarian situation possibly spanning several ruptures. Records therefore
relate many-to-many; naive spatiotemporal deduplication both merges genuine
doublets (e.g. Venezuela's back-to-back M7.1/M7.5) and misses one-to-many
links. GDACS and ReliefWeb both carry GLIDE numbers when assigned.

## Decision

Maintain a single unified event view keyed on GDACS `eventid` (GDACS is the
trigger, ADR-0001). Linking, in order:

1. **GLIDE number** when present on both sides — exact join.
2. Fallback **type + space + time correlation** for USGS↔GDACS (same hazard
   type, epicentre distance and origin-time windows), tuned to *not* merge
   distinct events close in space/time.

USGS records store the full `ids` alias set (network IDs get merged upstream
and the preferred ID can change). Aftershocks cluster under their mainshock's
unified event as one report line.

## Consequences

- The report speaks in single events with sources attached — the reader never
  reconciles duplicates.
- GLIDE arriving late means links can form days after first report; linking
  must be re-runnable, not once-only.
- Magnitude disagreement between USGS and GDACS is expected (different
  solutions/magnitude types) and is never evidence of two events.
