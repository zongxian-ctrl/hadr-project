# QUESTIONS.md — interview log for build-plan-product

> Scratch file for the Step A interview (see `skills/build-plan-product/`).
> All questions logged upfront; answers recorded inline as `**A:**`. New
> questions raised by answers get appended to the relevant group.

## A. Product intent & audience

- **A1.** Who reads the morning report — you personally, a notional team of
  responders, or is it primarily a course demo artefact? (Shapes tone, detail
  level, and how much explanation each entry needs.)
  **A:** The user personally, as a daily brief — terse, 2-minute morning scan.
- **A2.** Is the 08:30 daily sitrep the only product surface for v1, or do you
  also want intra-day alerts (e.g. a Red-level event shouldn't wait until
  tomorrow morning)?
  **A:** Daily 08:30 only. Deterministic change check gates the model; quiet
  when nothing changed. Red events wait until morning (v1).
- **A3.** What does success look like at the end of the course week — a
  demoable end-to-end pipeline, or a report you'd genuinely keep reading after
  the course?
  **A:** Both, pipeline first: trustworthy unattended pipeline is the bar;
  genuinely-useful daily reading is the stretch goal.

## B. Scope & severity

- **B4.** Hazard scope: earthquakes only for v1, all GDACS rapid-onset hazards
  (EQ, cyclone, flood, volcano, wildfire), or also slow-onset/conflict crises
  (which makes ReliefWeb central rather than supplementary)?
  **A:** All GDACS rapid-onset hazards in the PRD; first vertical slice is
  earthquakes-only. ReliefWeb supplementary, not a trigger.
- **B5.** Trigger role (REQS open decision 1): which feed(s) can cause an event
  to enter the report? GDACS-led (alert colours trigger; USGS enriches;
  ReliefWeb adds context) vs any-feed-triggers vs USGS-led.
  **A:** GDACS-led. Alert colours (modeled impact) trigger; USGS enriches EQ
  detail/revisions; ReliefWeb enriches humanitarian context.
- **B6.** Severity floor: GDACS Orange/Red only? Include Green events when
  modeled exposure or PAGER says otherwise? Where is the noise floor?
  **A:** Orange + Red only. Green suppressed entirely (v1).
- **B7.** Geographic scope: global, or a priority region (e.g. Asia-Pacific,
  given the 08:30 Asia/Singapore cadence)?
  **A:** Global. Orange/Red rarity makes geography unnecessary as a filter.

## C. Correlation & mutation policy

- **C8.** Revision policy: when an event you already reported is revised,
  downgraded, or deleted upstream, does the next report carry an explicit
  "corrections" section, silently update, or both?
  **A:** Explicit "updates & corrections" section + entry updated in place.
  A downgrade/deletion is itself news.
- **C9.** Aftershock/sequence handling: cluster aftershocks under their
  mainshock as one line, or list individually above the severity floor?
  **A:** Cluster under mainshock as one line (default accepted).
- **C10.** One unified cross-source event view, or three parallel streams
  presented side by side (REQS open decision 5)?
  **A:** One unified event view, keyed on GDACS eventid (default accepted).
- **C11.** Use GLIDE numbers as the primary cross-feed join key when present,
  falling back to type+space+time correlation?
  **A:** Yes — GLIDE when present, else type+space+time (default accepted).

## D. Architecture & stack

- **D12.** Language/runtime for `scripts/` (must run in GitHub Actions):
  Python, Node/TypeScript, or something else you're fluent in?
  **A:** Python.
- **D13.** Where does state ("what did I already report") live — a committed
  JSON file in the repo, or Actions cache/artifacts?
  **A:** Committed JSON (e.g. `state/seen-events.json`), committed by the
  workflow alongside dashboard.html; git history as audit log.
- **D14.** ReliefWeb: build against RSS now and slot the API in when the
  appname is approved — request the appname today?
  **A:** Request appname now (user action); v1 builds on RSS behind an
  interface the API can replace later.
- **D15.** Feed-down behaviour: what does the 08:30 report say on a morning a
  feed is unreachable (distinguish "feed down" from "world quiet")?
  **A:** Every report carries a per-feed status line; "feed down" is reported
  explicitly, never conflated with "no events" (default accepted).

## E. Output

- **E16.** `dashboard.html`: latest sitrep only, or latest plus a short
  history/trend of recent days?
  **A:** Latest sitrep + 7-day history (default accepted).
- **E17.** Any layout/style preferences for `prd.html` and `dashboard.html`
  (they render in light and dark themes)?
  **A:** Clean single column, alert-colour coded, light/dark support
  (default accepted).
