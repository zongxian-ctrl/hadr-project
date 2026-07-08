# ADR-0005: ReliefWeb via RSS now, API behind the same interface later

Status: accepted (2026-07-08, build-plan-product interview)

## Context

Since 1 Nov 2025 the ReliefWeb API requires a pre-approved `appname`
(form + email confirmation) — an approval delay outside our control, during a
one-week build. The disasters RSS feed needs no approval but only announces a
disaster's creation: status changes and content updates are never republished.

## Decision

Request the appname immediately (user action, already in flight). Build v1
against the RSS feed behind a small fetcher interface; swap in the API
implementation when approval lands. ReliefWeb remains enrichment-only
(ADR-0001), so its update blindness degrades context freshness, not
triggering.

## Consequences

- ReliefWeb is in the product from day one; no external approval on the
  critical path.
- Until the API lands, a situation's evolving status (alert → ongoing → past)
  is invisible; entries link to the ReliefWeb page for the live record.
- The fetcher interface must expose a superset shape (GLIDE, country, status,
  URL) that both implementations can fill, so the swap is config, not rework.
- API usage is monitored/rate-limited per app (~1000 calls/day) — the daily
  cadence stays far below it.
