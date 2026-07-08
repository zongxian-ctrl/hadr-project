# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

### 2026-07-08 — Slice 1: GDACS → events → page (walking skeleton)

First vertical slice: fetch one feed, normalise, render a page — end to end.

- **Feed = GDACS** (not USGS), because it is the trigger feed (ADR-0001) and
  carries the alert level the whole product is built around.
- **`scripts/hadr/`** Python package: `model.Event` (the normalised shape the
  rest of the pipeline will speak), `gdacs.py` (fetch + parse), `render.py`
  (events → HTML). `scripts/build_dashboard.py` wires them end to end.
- **Normalisation traps handled now** so later slices inherit them: GeoJSON
  `[lon, lat]` un-swapped; GDACS's offset-less timestamps parsed as tz-aware
  UTC; empty GLIDE → `None`; unknown hazard codes pass through rather than
  raising (`EVENTS4APP` is an unversioned internal API).
- **Tests are fixture-based**, never against the live feed (project testing
  decision). `tests/fixtures/gdacs_sample.json` covers Green/Orange/Red and
  EQ + cyclone.

## Open questions

- Where does the deterministic change-detection step (the model gate) sit
  relative to this code — a `changed()` returning an exit code, consuming the
  committed state file? (Next slice.)

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

- **Page shows all events, not only the Orange/Red floor.** The PRD's product
  is Orange/Red-only, but Orange+ is rare and a floor-only page is usually
  empty — useless for a first end-to-end slice. Compromise: render everything,
  colour-coded and worst-first, and tag which rows clear the floor
  (`is_reportable`, which *is* tested against the PRD floor). Applying the
  filter for real is a later slice.
- **Committed `dashboard.html` is built from the fixture, not the live feed.**
  The convention force-commits `dashboard.html`, but a live snapshot is stale
  churn in a code PR. The fixture build is small, deterministic, and
  reproducible; the live page is one command away.
