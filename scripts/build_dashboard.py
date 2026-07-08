#!/usr/bin/env python3
"""Slice 1 end-to-end: fetch GDACS -> normalise -> render dashboard.html.

  python scripts/build_dashboard.py                 # live GDACS feed
  python scripts/build_dashboard.py --fixture F.json # offline, from a file
  python scripts/build_dashboard.py -o out.html      # choose output path

Deterministic and model-free: this is the kind of step that must give the same
answer twice, so it lives here in scripts/ rather than in a skill.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the `hadr` package importable whether run from the repo root or elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hadr.gdacs import fetch_raw, parse_events  # noqa: E402
from hadr.render import render_page  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the HADR events page (slice 1).")
    parser.add_argument(
        "--fixture", type=Path, help="Read GDACS JSON from a file instead of the network."
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("dashboard.html"),
        help="Where to write the HTML (default: dashboard.html).",
    )
    args = parser.parse_args(argv)

    if args.fixture:
        raw = json.loads(args.fixture.read_text(encoding="utf-8"))
        source = str(args.fixture)
    else:
        raw = fetch_raw()
        source = "live GDACS feed"

    events = parse_events(raw)
    args.output.write_text(render_page(events), encoding="utf-8")

    reportable = sum(1 for e in events if e.alert_level in ("Orange", "Red"))
    print(
        f"Read {len(events)} events from {source}; "
        f"{reportable} clear the Orange/Red floor. Wrote {args.output}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
