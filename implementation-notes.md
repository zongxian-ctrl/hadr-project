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

### 2026-07-08 — Slice 2: change-detection gate + scheduled workflow

Makes the pipeline run unattended: a deterministic gate decides whether to
rebuild, and the GitHub Actions workflow rebuilds + commits only on change.

- **`scripts/hadr/state.py`** — pure `detect_changes(prev, curr)` +
  `load_state`/`save_state`. State is committed JSON at
  `state/seen-events.json` (ADR-0003); git history is the audit log.
- **Gate tracks the reportable (Orange/Red) set only.** Green churn (the vast
  majority of feed traffic) never enters state and never wakes the pipeline.
  A downgrade off the floor (Orange→Green) surfaces as a *removal* — that is
  news (ADR-0006).
- **`scripts/check_changes.py`** — fetches GDACS once, detects change, writes
  `changed=true|false` to `$GITHUB_OUTPUT`, updates state on change, and saves
  the fetched feed (`--snapshot-out`) so the rebuild step renders from the same
  snapshot rather than fetching twice (avoids a fetch-vs-fetch race).
- **`.github/workflows/sitrep.yml`** — `workflow_dispatch` active; `schedule:`
  present but COMMENTED (correct cron `30 0 * * *` = 08:30 SGT). Commit-back
  guarded: `contents: write`, bot identity, empty-diff guard, `concurrency`
  group. Default `GITHUB_TOKEN` pushes do not retrigger the workflow.
- Tests: 10 new (`test_state.py`) incl. first-ever run, idempotence,
  Green-only no-op, upgrade, score revision, downgrade-as-removal, roundtrip.

## Open questions

- The reporting step is still deterministic (rebuilds the slice-1 page). The
  `/sitrep` model call (severity narrative, corrections section, feed-down
  line) replaces the "Rebuild" workflow step in a later slice.

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
  _(Slice 2: the workflow's first successful run overwrites this fixture-built
  page with live data and commits it — the intended product behaviour.)_

### Slice 2 deviations

- **Schedule shipped disabled.** The scaffold gates enabling the cron on both
  TODO steps existing, and step 2 here is a deterministic rebuild, not the
  eventual model call. Activating a daily job that auto-commits to the branch
  is also the user's call to make after watching a run. So `schedule:` is
  committed-but-commented; `workflow_dispatch` is the way in until then.
- **Report step is deterministic, not a model call.** The PRD architecture ends
  step 2 with headless `claude -p` running `/sitrep`. That skill doesn't exist
  yet, so this slice rebuilds the slice-1 page instead. The workflow's "Rebuild"
  step is the single seam the model call slots into later.
- **Feed-down handling is minimal.** On a fetch failure the gate exits non-zero
  (a failed Actions run is the "something's wrong" signal for now). The
  richer "report says the feed was down" behaviour (D15) waits on the render/
  skill layer that can express it.
