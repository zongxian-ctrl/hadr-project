# ADR-0001: GDACS-led triggering with an Orange/Red severity floor

Status: accepted (2026-07-08, build-plan-product interview)

## Context

Three feeds could decide when an event enters the report. Raw magnitude is a
poor severity proxy (a deep M7.5 can be harmless; a shallow M5.9 under a city
can be a disaster). GDACS alert colours already encode modeled human impact —
population exposure, not magnitude — and cover all rapid-onset hazards, not
just earthquakes. USGS's own impact model (PAGER) arrives ~20–30 minutes after
an event and only for significant quakes.

## Decision

GDACS is the sole trigger: an event enters the sitrep when its GDACS alert
level is Orange or Red. USGS enriches earthquake entries (detail, felt
reports, PAGER, revisions); ReliefWeb enriches with humanitarian context.
Green events are suppressed entirely. Scope is global; all GDACS rapid-onset
hazard types are in scope, with earthquakes as the first vertical slice.

## Consequences

- One threshold policy to design instead of three.
- Severity is impact-based by construction; no rebuilt magnitude heuristics.
- Known miss class: events GDACS under-scores early appear only when GDACS
  upgrades them (the corrections mechanism, ADR-0006, then surfaces them).
- ReliefWeb-only crises (slow-onset, conflict) never trigger in v1 — explicit
  out-of-scope.
- Orange+ events are rare; testing needs fixtures/replay and a `--min-alert`
  override rather than waiting on the live feed (see CONTEXT.md flagged
  tension).
