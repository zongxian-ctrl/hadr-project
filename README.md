# HADR Monitor

An autonomous agent that watches live disaster feeds, works out what matters, and
publishes a daily humanitarian situation report — unattended, on a schedule, and
quiet on the mornings when nothing has changed.

## What is HADR?

**HADR** stands for **Humanitarian Assistance and Disaster Response** — the work of
responding to disasters, natural (earthquakes, cyclones, floods, volcanoes,
wildfires, drought) and man-made (conflict, displacement). The questions that
matter in this domain are always the same four:

- **What** happened?
- **Where** did it happen?
- **How bad** is it?
- **Who** is affected?

Responders drown in raw alerts. The signal — a magnitude-7 earthquake near a
populated coastline — is buried under hundreds of routine tremors and duplicate
notifications. HADR Monitor is a small agent that reads the same public feeds a
human analyst would, filters the noise, and answers those four questions once a
morning.

## What HADR Monitor does

By its intended end state, the agent:

- **Watches live disaster feeds** — GDACS, USGS and ReliefWeb (see [`feeds/`](feeds/)).
- **Filters out the noise and assesses what remains** — what happened, where, how
  bad, who is affected.
- **Publishes a morning situation report** to `dashboard.html` at **08:30
  Asia/Singapore**.
- **Runs on a schedule, unattended** — and stays quiet when nothing has changed.

## How it works

The scheduled run has two stages, and the split between them is the whole point
(see [`.github/workflows/sitrep.yml.disabled`](.github/workflows/sitrep.yml.disabled)):

1. **A deterministic change-detection step** decides whether anything changed. It
   lives in [`scripts/`](scripts/), exits with a status the workflow can branch on,
   and **never calls a model**.
2. **A model call runs only if something changed.** Headless Claude (`claude -p`)
   runs a `/sitrep` skill and rebuilds `dashboard.html`.

The guiding principle: **the model never decides whether to wake up.** Anything
that must give the same answer twice is deterministic code in `scripts/`;
judgement — assessing severity, writing the report — lives in a skill. A scheduled
job that fires a model every morning only to conclude "nothing happened" wastes
minutes, money, and trust.

## The data feeds

Three public feeds, three different shapes. Full specs and endpoints are in
[`feeds/`](feeds/).

- **GDACS** — the Global Disaster Alert and Coordination System (EU/UN).
  Multi-hazard (earthquakes, cyclones, floods, volcanoes, drought, wildfires),
  each event tagged with a colour-coded alert level. GeoJSON, with an RSS
  alternative.
- **USGS** — the United States Geological Survey real-time earthquake feed.
  GeoJSON, regenerated every minute and served as rolling time windows
  (`all_day`, `all_hour`, …). Events get revised — magnitude, location, or
  deleted outright — after they first appear.
- **ReliefWeb** — UN OCHA's curated humanitarian information service. Slower and
  human-vetted: a "disaster" appears here once people decide it matters. The API
  now requires a pre-approved `appname`, so the RSS feed is the no-approval
  fallback.

The hard part is not fetching any one feed — it is reconciling them. **The same
physical earthquake arrives from all three under different identifiers.** Deciding
when two records describe one event, and what to do when an event you already
reported on is later revised, is the real work.

## Repository layout

```
.
├── README.md                 you are here
├── CLAUDE.md                 conventions, test command, deviations policy — fill this in first
├── implementation-notes.md   decision log (an undocumented deviation is a bug)
├── feeds/                    specs for the three data feeds + their open questions
│   ├── gdacs.md
│   ├── usgs.md
│   └── reliefweb.md
├── scripts/                  deterministic checks — anything that must be repeatable
├── skills/                   reusable skills (e.g. /sitrep) — the judgement lives here
├── docs/solutions/           greppable archive of learnings (YYYY-MM-DD-slug.md)
└── .github/
    └── workflows/
        ├── claude.yml                 @claude responds on issues & PR comments
        ├── claude-code-review.yml     automated code review on PRs
        └── sitrep.yml.disabled        the 08:30 morning routine (enable when ready)
```

The product artefacts (`prd.html`, `system-view.html`, `dashboard.html`,
`goal.md`) do not exist yet — they are what you build. Note the rule in
[`.gitignore`](.gitignore): generated `reports/` and `*.sitrep.html` are ignored as
churn, but `dashboard.html` is force-committed **because it is the product.**

## Status

This repository is a **scaffold**, not a finished application. There is no source
code, and no language or toolchain has been chosen — `CLAUDE.md` is intentionally
blank until you fill it in. There are deliberately **no build, run, or test
commands yet**; defining them is part of the exercise. How the agent does any of
what is described above is not specified anywhere in this repository. That is the
course.

---

## For course participants

### The three days

1. **Plan** — interrogate the feeds, write the PRD, cut it into vertical slices.
2. **Autonomy** — build the first slice, write a skill, wire up the 08:30 routine,
   launch the overnight loop.
3. **Trust** — review code you didn't write, harden the pipeline, demo.

### Artefacts expected by the end

`prd.html` · `system-view.html` · `implementation-notes.md` · `dashboard.html` ·
`goal.md` · at least one skill.

### Day 1 setup

1. Sign in to Claude Code with your Team seat.
2. Create your own repository from this template, then clone it.
3. Run `/install-github-app` so @claude reviews your pull requests from Day 2.
4. Install OpenCode and sign in with your Go key.

Fill in `CLAUDE.md` before your first prompt. An empty conventions file is also a
decision — just not one you made.
