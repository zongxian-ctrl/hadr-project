# GDACS fetch intermittently hangs from GitHub Actions

**Date:** 2026-07-08
**Symptom:** The first real dispatch of the `Morning sitrep` workflow failed at
the change-detection step: `FEED ERROR: could not fetch GDACS: <urlopen error
timed out>` after 30s. The exact same code fetched GDACS in ~1.7s from a local
machine.

## Investigation

1. **Not GDACS being down.** From a local IP the API returned 200 / 135 KB in
   1.7s; RSS in 4.9s.
2. **Suspected a datacenter-IP block.** `www.gdacs.org` is a single EU IP
   (`139.191.221.20`, European Commission / JRC), no IPv6. EU gov services often
   filter cloud traffic, and a 30s hang (vs a fast 403) looks like silent packet
   drops. **This turned out to be wrong.**
3. **Ground truth from the runner.** A throwaway diagnostic (curl, from the
   Actions runner at Azure IP `4.236.164.162`) reached the GDACS API in **1.07s**,
   RSS and USGS fine, ReliefWeb 403 (no appname). So gdacs.org is *not* blocked
   from CI.
4. **Not the User-Agent.** A Python `urllib` probe from the runner tried four
   User-Agents (current `hadr-monitor/0.1`, curl-like, browser-like, none) — all
   succeeded in ~1s.
5. **It is intermittent.** Across dispatches: run 1 timed out at 30s; run 2
   succeeded (committed a report); run 3's probes all succeeded. Same code, same
   IP, same UA — different outcome.

## Root cause

GDACS is a free public feed with no SLA and **occasionally hangs a connection**
(~30s) rather than responding. A retry moments later succeeds in ~1s. The
original `fetch_raw` made a single attempt with a 30s timeout, so one hang sank
the whole run.

## Fix

`scripts/hadr/gdacs.py` `fetch_raw`: modest per-attempt timeout (20s) + 3
retries with linear backoff; re-raise the last exception only if every attempt
fails. Tested with a fake `urlopen` (retry-then-succeed, exhaust-then-raise,
happy-path-no-retry) — never the network.

## If it recurs / worsens

- If hangs become frequent, add jitter and/or fall back to the GDACS **RSS**
  feed (`https://www.gdacs.org/xml/rss.xml`) — reachable from CI in this test.
- The workflow still fails loudly (non-zero) if *all* retries fail; that's the
  intended "feed down" signal until the render/skill layer can report it inline
  (D15).
