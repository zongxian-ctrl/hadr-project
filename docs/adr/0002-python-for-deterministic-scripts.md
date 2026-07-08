# ADR-0002: Python for the deterministic scripts

Status: accepted (2026-07-08, build-plan-product interview)

## Context

The two-stage architecture (deterministic change detection gating a model
call) needs a language for `scripts/` that runs on GitHub Actions runners with
minimal setup and handles JSON/XML feed parsing, date/timezone arithmetic and
simple geospatial math (haversine correlation windows).

## Decision

Python, using the runner's preinstalled interpreter. Dependencies kept
minimal and pinned.

## Consequences

- Zero-toolchain start on `ubuntu-latest`; fast workflow runs.
- stdlib covers most needs (`json`, `xml.etree`, `datetime`, `urllib`);
  `requests` and similar added only when justified.
- `dashboard.html` generation is also Python (templating), keeping the
  pipeline single-language.
