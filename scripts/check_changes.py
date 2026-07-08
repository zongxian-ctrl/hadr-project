#!/usr/bin/env python3
"""Deterministic change-detection gate (slice 2).

Decides whether the reporting step should run. Fetches GDACS once, compares the
reportable (Orange/Red) set against the committed state, and reports the
verdict. Never calls a model.

  python scripts/check_changes.py                      # report verdict only
  python scripts/check_changes.py --update             # + persist new state on change
  python scripts/check_changes.py --fixture feed.json  # offline, from a file
  python scripts/check_changes.py --snapshot-out f.json # save the fetched feed
                                                          for the rebuild step

Signals, for a workflow to branch on:
  - writes `changed=true|false` to $GITHUB_OUTPUT when that env var is set;
  - prints `CHANGED` / `UNCHANGED` and a human summary to stdout;
  - exits 0 on success, non-zero if the feed could not be fetched (a failed
    run is itself the "feed down" signal for now — richer handling is a later
    slice).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hadr.briefing import build_briefing  # noqa: E402
from hadr.gdacs import fetch_raw, parse_events  # noqa: E402
from hadr.state import detect_changes, load_state, save_state  # noqa: E402

DEFAULT_STATE = Path("state/seen-events.json")


def _write_github_output(changed: bool) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HADR change-detection gate (slice 2).")
    parser.add_argument("--fixture", type=Path, help="Read GDACS JSON from a file instead of the network.")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="State file path.")
    parser.add_argument("--update", action="store_true", help="Persist new state when something changed.")
    parser.add_argument("--snapshot-out", type=Path, help="Write the fetched feed here for the rebuild step.")
    parser.add_argument("--briefing-out", type=Path, help="Write the briefing JSON here for the /sitrep model step.")
    args = parser.parse_args(argv)

    try:
        if args.fixture:
            raw = json.loads(args.fixture.read_text(encoding="utf-8"))
        else:
            raw = fetch_raw()
    except Exception as exc:  # network error, malformed feed, etc.
        print(f"FEED ERROR: could not fetch GDACS: {exc}", file=sys.stderr)
        _write_github_output(False)
        return 1

    if args.snapshot_out:
        args.snapshot_out.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot_out.write_text(json.dumps(raw), encoding="utf-8")

    events = parse_events(raw)
    prev_state = load_state(args.state)
    report = detect_changes(prev_state, events)

    verdict = "CHANGED" if report.has_changes else "UNCHANGED"
    print(f"{verdict}: {report.summary()}")

    # Briefing is built from prev_state (before it is overwritten) so the
    # corrections diff still has the previous fingerprints.
    if args.briefing_out:
        now = datetime.now(timezone.utc)
        briefing = build_briefing(prev_state, events, report, now)
        args.briefing_out.parent.mkdir(parents=True, exist_ok=True)
        args.briefing_out.write_text(json.dumps(briefing, indent=2), encoding="utf-8")

    if report.has_changes and args.update:
        save_state(args.state, events, datetime.now(timezone.utc))
        print(f"State updated: {args.state}")

    _write_github_output(report.has_changes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
