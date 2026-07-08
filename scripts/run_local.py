#!/usr/bin/env python3
"""Local end-to-end harness — the whole pipeline on your machine, via OpenCode.

Mirrors the CI workflow but runs locally and uses OpenCode (your Go key) as the
model instead of Claude:

    gate (deterministic) -> briefing.json -> if changed, OpenCode writes dashboard.html

  python scripts/run_local.py                         # live feed, default model
  python scripts/run_local.py --model opencode-go/qwen3.7-max
  python scripts/run_local.py --fixture tests/fixtures/gdacs_sample.json
  python scripts/run_local.py --force                 # run the model even if nothing changed

Like the real routine, the model runs ONLY when the reportable (Orange/Red) set
changed — `--force` overrides that for testing. The model never decides whether
to wake up; the gate does.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hadr.briefing import build_briefing  # noqa: E402
from hadr.gdacs import fetch_raw, parse_events  # noqa: E402
from hadr.state import detect_changes, load_state, save_state  # noqa: E402

DEFAULT_MODEL = "opencode-go/kimi-k2.7-code"
PROMPT = (
    "Read skills/sitrep/SKILL.md and follow it exactly: read briefing.json in "
    "this directory and write the morning situation report to dashboard.html. "
    "Modify only dashboard.html. Do not run git."
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Local OpenCode sitrep harness.")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="OpenCode model (provider/model).")
    ap.add_argument("--fixture", type=Path, help="Read GDACS JSON from a file instead of the network.")
    ap.add_argument("--state", type=Path, default=Path("state/seen-events.json"), help="State file path.")
    ap.add_argument("--force", action="store_true", help="Run the model even if nothing changed.")
    args = ap.parse_args(argv)

    raw = json.loads(args.fixture.read_text("utf-8")) if args.fixture else fetch_raw()
    events = parse_events(raw)
    prev = load_state(args.state)
    report = detect_changes(prev, events)
    print(("CHANGED: " if report.has_changes else "UNCHANGED: ") + report.summary())

    # Write the briefing the model reads, from prev_state (before it's overwritten).
    briefing = build_briefing(prev, events, report, datetime.now(timezone.utc))
    Path("briefing.json").write_text(json.dumps(briefing, indent=2), encoding="utf-8")

    if not report.has_changes and not args.force:
        print("No change — skipping the model step. Use --force to run it anyway.")
        return 0

    save_state(args.state, events, datetime.now(timezone.utc))

    opencode = shutil.which("opencode")
    if not opencode:
        print("ERROR: 'opencode' not found on PATH. Install OpenCode and sign in.", file=sys.stderr)
        return 1

    print(f"Running the model via OpenCode ({args.model}) …")
    result = subprocess.run([opencode, "run", "-m", args.model, "--auto", PROMPT])
    if result.returncode == 0:
        print("Wrote dashboard.html.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
