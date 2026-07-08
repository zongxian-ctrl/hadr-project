# CONTEXT.md — shared language and resolved decisions

> Produced by the `build-plan-product` Step A interview on 2026-07-08.
> Decisions below are recorded as ADRs in `docs/adr/`; the interview log is
> `QUESTIONS.md`.

## Terms

- **Event (physical)** — one real-world occurrence as a sensor sees it: one
  USGS earthquake record. Mutable: magnitude/location revised, occasionally
  deleted.
- **Alert** — GDACS's evolving, colour-coded (Green/Orange/Red) assessment of
  a hazard's modeled *human impact*. One alert spans **episodes** and can
  change colour over its life. Identified by GDACS `eventid`.
- **Situation** — ReliefWeb's human-curated disaster record: a humanitarian
  consequence, possibly spanning several physical events (e.g. one record for
  two Venezuela quakes).
- **Unified event** — this project's canonical record, keyed on GDACS
  `eventid`, holding the alert plus linked physical events (USGS) and
  situations (ReliefWeb). The hierarchy is physical event → alert → situation;
  linking is many-to-many, not deduplication.
- **GLIDE** — the humanitarian sector's shared disaster identifier
  (glidenumber.net), present in both GDACS and ReliefWeb records when
  assigned. Primary join key when present; assigned late and only for
  significant disasters, so never the only mechanism.
- **Sitrep** — the daily situation report published to `dashboard.html` at
  08:30 Asia/Singapore. Answers: what happened, where, how bad, who affected.
- **Correction** — an explicit sitrep entry stating that something previously
  reported has changed (magnitude revision, alert downgrade/upgrade, upstream
  deletion). A downgrade is itself news, never silently applied.
- **Knowledge time** — when *this agent* first learned a fact. "New in
  today's report" means new to the agent's knowledge, not new by event time:
  a ReliefWeb situation declared today about last week's quake is news today.
- **Feed status line** — per-feed liveness note carried by every sitrep, so
  "feed down" is never mistaken for "world quiet".

## Product decisions (summary)

| # | Decision | Detail |
|---|----------|--------|
| A1 | Audience | The user personally; terse 2-minute daily brief |
| A2 | Cadence | Daily 08:30 SGT only; deterministic change gate; quiet when unchanged |
| A3 | Success | Trustworthy unattended pipeline first; report quality is the stretch goal |
| B4 | Scope | All GDACS rapid-onset hazards; first vertical slice = earthquakes |
| B5 | Trigger | GDACS-led: alert colour triggers; USGS & ReliefWeb enrich |
| B6 | Severity floor | Orange + Red only; Green suppressed |
| B7 | Geography | Global |
| C8 | Revisions | Corrections section + entry updated in place |
| C9 | Aftershocks | Clustered under mainshock as one line |
| C10 | Event model | One unified event view keyed on GDACS eventid |
| C11 | Join key | GLIDE when present; else type + space + time correlation |
| D12 | Language | Python (GitHub Actions runner) |
| D13 | State | Committed JSON (`state/`), git history as audit log |
| D14 | ReliefWeb | RSS now; API behind same interface once appname approved |
| D15 | Liveness | Per-feed status line in every sitrep |
| E16 | Dashboard | Latest sitrep + 7-day history |
| E17 | Style | Single column, alert-colour coded, light/dark |

## Flagged tension (from the Step A consistency check)

**Orange/Red-only + earthquakes-first is rare in live data.** GDACS Orange+
earthquakes occur perhaps a few times a month globally; a live demo during a
3-day course may see zero qualifying events. Proposed resolution (to confirm
during slice planning): a `--min-alert` override for testing, plus recorded
feed fixtures (replay mode) so change detection and report generation are
testable deterministically regardless of what the world does that week. This
also serves the test strategy: the deterministic step should be tested against
fixtures, never against the live feeds.

## Feed roles

- **GDACS** — trigger + severity authority. Poll the GeoJSON event list; treat
  it as a current-state snapshot (events vanish when over, not retracted).
  `EVENTS4APP` is unversioned/internal — parse defensively.
- **USGS** — enrichment for earthquakes: detail, felt reports, PAGER, and
  revision tracking. The summary feed is a rolling window, not a changelog;
  revision tracking uses the FDSN query API (`updatedafter`). Store the full
  `ids` alias set, not just `id`. Conditional GET (ETag) always.
- **ReliefWeb** — humanitarian context. RSS announces creation only and never
  republishes updates; the API (post-approval) exposes the evolving record.
