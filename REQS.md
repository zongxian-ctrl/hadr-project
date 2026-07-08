# REQS.md — HADR Monitoring Agent (initial idea capture)

> Status: DRAFT for you to edit. This is a raw capture of the idea to seed the
> `build-plan-product` process (Shape Up). It is intentionally rough. Rewrite it
> in your own words, resolve the `TO DECIDE` items, then run Step A.

## One-line idea

A monitoring agent that watches disaster/humanitarian feeds (GDACS, USGS,
ReliefWeb), correlates events across them, and surfaces relevant, severity-ranked
alerts.

## Why / motivation

Disaster-relevant signal is scattered across feeds that are different in kind:
sensor data, modeled multi-hazard alerts, and human-curated humanitarian
reporting. I want one agent that turns those raw feeds into timely, de-duplicated,
severity-aware situational awareness — instead of me watching three sites.

## Data sources (and what each really is)

- **USGS** — raw earthquake *sensor* data. Fast (seconds–minutes). Preliminary,
  gets revised; events can be deleted. Magnitude ≠ human impact.
- **GDACS** — multi-hazard *alert aggregator* (EQ, tsunami, cyclone, flood,
  volcano, drought). Modeled human-impact score (green/orange/red). Evolves via
  "episodes"; alert level can be upgraded. Re-reports USGS quakes.
- **ReliefWeb** — human-curated *humanitarian reporting* (OCHA). Slow (hours–days),
  editorial, authoritative. Rate-limited (1000 calls/day, 1000 results/call);
  from 1 Nov 2025 requires a pre-approved `appname`. Only window onto slow-onset
  crises (drought, displacement, conflict, epidemics).

## What the agent should do (rough)

- Ingest all three feeds on a schedule.
- Normalize to UTC; handle updates, revisions, and retractions (not append-only).
- Correlate the same real-world event across feeds (spatial + temporal + type).
- Rank/filter by severity and relevance (suppress low-level noise).
- Emit alerts / a view of current significant events.
- Self-monitor feed liveness (distinguish "feed down" from "world quiet").

## Open decisions (TO DECIDE — these shape everything)

1. **Trigger vs. context role** — which feed(s) drive alerts vs. only enrich?
2. **Scope** — rapid-onset only (EQ/cyclone/flood), or slow-onset/conflict too?
   (Decides whether ReliefWeb is central or supplementary.)
3. **Thresholds** — what geographic + severity level deserves an alert?
4. **Freshness** — near-real-time (seconds) or is minutes/hours acceptable?
5. **Correlation** — one unified cross-source event view, or three parallel streams?
6. **Stack & runtime** — language, where it runs, how state is stored.
7. **Output** — dashboard, notifications, API, LLM summaries, or combination?

## Known constraints / blindspots (context, not requirements)

- Entity resolution across feeds is the core hard problem, not ingestion.
- "What is an event?" differs per feed (rupture vs. multi-episode alert vs.
  declared disaster).
- Free public feeds: no SLA, silent failures, format drift, throttling.
- Coverage bias by region; absence of alert ≠ absence of event.

## Out of scope (tentative — TO DECIDE)

- Predicting/forecasting disasters.
- Feeds beyond GDACS / USGS / ReliefWeb (for v1).
- Acting on alerts (dispatch, tasking) — monitoring only for v1.
