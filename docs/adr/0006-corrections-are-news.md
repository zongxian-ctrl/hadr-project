# ADR-0006: Corrections are news — mutable feeds, explicit corrections section

Status: accepted (2026-07-08, build-plan-product interview)

## Context

Nothing in these feeds is immutable: USGS revises magnitude/location and
deletes events (and the summary feed's rolling window silently drops
revisions older than the window — the FDSN `updatedafter` query is the real
change feed); GDACS alert colours oscillate across episodes; ReliefWeb records
evolve. A reader who acted on yesterday's report must learn when it changed.

## Decision

Every sitrep carries an **Updates & Corrections** section listing, per
previously-reported event: magnitude/location revisions, alert upgrades and
downgrades, and upstream deletions. The event's own entry is simultaneously
updated in place to the latest state. Downgrades below the Orange floor and
deletions are still reported as corrections — that is the news — and then drop
from subsequent reports. Every sitrep also carries a per-feed status line so
a fetch failure is reported as "feed down", never mistaken for a quiet world.

## Consequences

- The deterministic change detector must diff on event *content and alert
  level*, not on feed bytes (USGS regenerates files every minute) and not
  just on new-event IDs.
- State (ADR-0003) must store enough per-event detail (magnitude, alert
  level, episode) to know *what* changed, not merely *that* something did.
- "Changed" for gating purposes includes: new Orange+ event, level change on
  a reported event, material revision, deletion, feed-liveness transition.
- First report of an under-scored event that GDACS later upgrades arrives via
  this mechanism (accepted miss class from ADR-0001).
