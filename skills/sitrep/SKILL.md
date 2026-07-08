---
name: sitrep
description: Use when generating the HADR morning situation report — read the deterministic briefing (briefing.json) and write dashboard.html as a human-readable situation report with an updates & corrections section.
---

# /sitrep — write the morning situation report

You are a humanitarian situation analyst. A deterministic step has already
fetched the feeds, decided what is significant, and written `briefing.json`.
Your job is judgement, not data collection: turn that briefing into a clear
morning report at `dashboard.html`. **Do not fetch anything or run the feeds
yourself. Work only from `briefing.json`.**

## Steps

1. Read `briefing.json` in the repo root (or the path you are given).
2. Write `dashboard.html` (self-contained: inline CSS, no external assets).
3. Write nothing else. Do not commit — a later workflow step commits.

## What briefing.json contains

- `generated_at` — ISO timestamp (UTC).
- `feed_status` — `"ok"` normally.
- `events` — the significant (Orange/Red) events, already sorted worst-first.
  Each has: `event_id`, `hazard_type`, `title`, `country`, `alert_level`
  (Green/Orange/Red), `alert_score`, `event_time`, `latitude`, `longitude`,
  `glide`, `report_url`.
- `new_event_ids` — which events are new since the last report.
- `corrections` — changes to previously reported events:
  - `{type: "revised", event_id, before, after}` — before/after fingerprints.
  - `{type: "removed", event_id, before}` — dropped off the Orange/Red floor
    (downgraded) or deleted upstream.

## The report — answer the four HADR questions per event

For each event, the reader wants: **what** happened, **where**, **how bad**,
**who is affected.**

- **What / where / how bad** come straight from the briefing (hazard type,
  title, country, alert level, score, time). Mark new events with a "new" tag.
- **Who is affected** is your analytical value-add: from the hazard type and
  location, describe in one or two sentences who and what is exposed
  (coastal population, a named city region, infrastructure). **Do not invent
  precise figures** (casualty counts, exact population numbers) that are not in
  the briefing — describe exposure qualitatively.

## Updates & Corrections section

If `corrections` is non-empty, add a section that states, per entry, what
changed in plain language — e.g. "Haiti earthquake upgraded Orange → Red",
"Cyclone MAWAR downgraded below the reporting threshold". A downgrade or
deletion **is news**; say so rather than silently dropping it.

## Layout & style

Single column, readable, alert-colour coded, works in light and dark themes.
Header shows the date (from `generated_at`), a one-line summary
(e.g. "3 significant events, 1 new"), and a feed-status line. Use this palette
and structure as the baseline:

```css
:root{--bg:#fff;--fg:#1a1d21;--muted:#5b6470;--line:#e3e6ea;--card:#f6f7f9;
--red:#c62828;--orange:#d97706;--green:#2e7d32;color-scheme:light dark;}
@media(prefers-color-scheme:dark){:root{--bg:#16181d;--fg:#e8eaed;--muted:#9aa3ad;
--line:#2c3038;--card:#1e2127;--red:#ef7070;--orange:#f0a24b;--green:#7cc47f;}}
```

Colour each event by its alert level (Red/Orange). If `events` is empty but
there are `corrections`, still publish (the corrections are the news). If both
are empty, publish a quiet "no significant events" report.

## Do not

- Fetch feeds, call scripts, or re-derive what changed — trust the briefing.
- Invent numbers not present in the briefing.
- Commit or push, create branches, or touch any file other than `dashboard.html`.
