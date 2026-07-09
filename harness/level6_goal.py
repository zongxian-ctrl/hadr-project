"""Level 6 — a goal checker.

Levels 4-5 stop when the MODEL says it's done. That's not trustworthy — a model
will happily declare success on incomplete work. So here a DETERMINISTIC checker
(plain code, no model) decides whether the goal is actually met, and if not, it
sends the agent back to work with specific feedback.

The decider is separate from the doer. That is the whole idea behind /goal, and
it's the same rule this project already lives by: the model never gets to decide
the thing that must be reliable — deterministic code does.

  inner loop (Level 5): model + tools, until the model stops asking
  outer loop (new):      run inner loop -> check goal -> if not met, feed back and retry

Run:  python harness/level6_goal.py            # normal
      python harness/level6_goal.py --demo-retry   # force one rejection to watch the retry
Produces: harness-dashboard.html
"""

import json
import sys
from pathlib import Path

from llm import call_model
from tools import (
    DASHBOARD_PATH,
    FETCH_FEED_SCHEMA,
    WRITE_DASHBOARD_SCHEMA,
    fetch_feed,
    write_dashboard,
)

TOOLS = {"fetch_feed": fetch_feed, "write_dashboard": write_dashboard}
SCHEMAS = [FETCH_FEED_SCHEMA, WRITE_DASHBOARD_SCHEMA]
SYSTEM = (Path(__file__).parent / "prompt.txt").read_text(encoding="utf-8")
TASK = (
    "Fetch the current significant disasters, assess each (what/where/how bad/"
    "who is affected), then save an HTML dashboard with write_dashboard. Every "
    "event must appear with a 'who is affected' line. Reply DONE when saved."
)
MAX_ATTEMPTS = 3


def run_tool(tool_call):
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"].get("arguments") or "{}")
    fn = TOOLS.get(name)
    return fn(**args) if fn else json.dumps({"error": f"unknown tool: {name}"})


def run_agent(messages):
    """The inner agent loop (Level 5): run tools until the model stops asking."""
    while True:
        reply = call_model(messages, tools=SCHEMAS)
        messages.append(reply)
        if not reply.get("tool_calls"):
            return reply.get("content", "")
        for tc in reply["tool_calls"]:
            print(f"    [tool] {tc['function']['name']}()")
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": run_tool(tc),
            })


def check_goal(expected_titles):
    """Deterministic goal check — no model involved. Returns (ok, reason)."""
    page = Path(DASHBOARD_PATH)
    if not page.exists():
        return False, f"{DASHBOARD_PATH} was not created."
    html = page.read_text(encoding="utf-8")
    missing = [t for t in expected_titles if t not in html]
    if missing:
        return False, f"these events are missing from the page: {missing}"
    if expected_titles and "affected" not in html.lower():
        return False, "no 'who is affected' information is present."
    return True, f"all {len(expected_titles)} events present, with impact info."


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    demo_retry = "--demo-retry" in argv

    # Ground truth for the checker: fetch the feed ONCE up front.
    expected = [e["title"] for e in json.loads(fetch_feed()).get("events", [])]
    print(f"[goal] dashboard must contain these {len(expected)} events: {expected}")

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TASK}]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n=== attempt {attempt} ===")
        final = run_agent(messages)
        print("  agent:", (final or "").splitlines()[0][:120] if final else "(no text)")

        ok, reason = check_goal(expected)
        # --demo-retry forces a single rejection on attempt 1 so you can see the loop.
        if demo_retry and attempt == 1:
            ok, reason = False, "(demo) forcing one retry to show the feedback loop"
        print(f"  [checker] {'PASS' if ok else 'FAIL'} — {reason}")

        if ok:
            print(f"\nGoal met on attempt {attempt}. → {DASHBOARD_PATH}")
            return 0

        messages.append({
            "role": "user",
            "content": f"The goal is NOT met: {reason} "
                       f"Fix {DASHBOARD_PATH} so every listed event appears with a "
                       f"'who is affected' line, then reply DONE.",
        })

    print(f"\nGave up after {MAX_ATTEMPTS} attempts.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
