# ADR-0003: Agent state lives as committed JSON in the repository

Status: accepted (2026-07-08, build-plan-product interview)

## Context

Change detection requires remembering what was already seen and reported.
GitHub Actions offers caches (evict after 7 days unused, branch-scoped) and
artifacts (awkward to chain between runs, expire), both of which can silently
lose state — and a state loss makes every event look new again, defeating the
"quiet when nothing changed" guarantee.

## Decision

State is JSON under `state/` (e.g. `state/seen-events.json`), committed by the
scheduled workflow in the same commit as `dashboard.html` (which the project
already force-commits as the product).

## Consequences

- State survives indefinitely and travels with the repo; git history is the
  audit log of every run's knowledge — invaluable for debugging revisions.
- Diffable in review: a wrong report can be traced to the exact state change.
- Repo accrues small daily commits (accepted; reports/ churn stays ignored).
- The workflow needs write permission and must handle the no-change case by
  not committing at all.
