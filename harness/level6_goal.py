"""Level 6 — a real goal checker (what /goal does), done properly.

Levels 4-5 stop when the MODEL says DONE — untrustworthy. Level 6 makes an
INDEPENDENT verifier decide whether the goal is met, and sends the agent back
with specific feedback if not. Two lessons are baked in here:

1. ONE SHARED SNAPSHOT. The feed is fetched ONCE, up front, into a briefing.
   The agent writes the report from that briefing, and the checker judges the
   report against the SAME briefing. No second fetch, so no race, and the goal
   is a fixed target — exactly this project's gate -> briefing -> model shape.

2. A GOAL IS A PROXY — so verify in two tiers:
   - a STRONG DETERMINISTIC gate for what code can check for sure (every event
     present with its EXACT alert level, right count, no ungrounded casualty
     figures). Trustworthy but shallow.
   - an OPTIONAL SEPARATE-MODEL JUDGE (--judge) for the fuzzy part (is the prose
     accurate / sensible). Deeper but softer — and it must be a DIFFERENT model
     than the writer, or you're asking the fox to audit the henhouse.

Run:
    python harness/level6_goal.py --selftest      # prove the checker (no API key)
    python harness/level6_goal.py                 # full loop, deterministic gate
    python harness/level6_goal.py --judge         # also run the separate-model judge
Produces: harness-dashboard.html
"""

import json
import os
import re
import sys
from pathlib import Path

from llm import MODEL, call_model
from tools import DASHBOARD_PATH, WRITE_DASHBOARD_SCHEMA, fetch_feed, write_dashboard

TOOLS = {"write_dashboard": write_dashboard}
SCHEMAS = [WRITE_DASHBOARD_SCHEMA]
SYSTEM = (Path(__file__).parent / "prompt.txt").read_text(encoding="utf-8")
MAX_ATTEMPTS = 3
CASUALTY = re.compile(r"(\d[\d,]*)\s*(dead|killed|deaths?|casualties|fatalities|injured|missing)", re.I)


# ---- the goal, tier 1: a STRONG deterministic check against the snapshot -----

def check_dashboard(snapshot, html):
    """Return (ok, [problems]). Pure code, no model. Judges the page against the
    fixed snapshot — necessary conditions, checked strictly."""
    problems = []
    for e in snapshot:
        if e["title"] not in html:
            problems.append(f"missing event: {e['title']!r}")
        elif e["alert"] not in html:
            problems.append(f"event {e['title']!r} is present but its alert level {e['alert']!r} is not")
    # who-is-affected line per event (standing orders require it)
    if snapshot and html.lower().count("affected") < len(snapshot):
        problems.append("not every event has a 'who is affected' line")
    # groundedness: any casualty figure on the page must appear in the snapshot
    briefing_text = json.dumps(snapshot)
    for m in CASUALTY.finditer(html):
        if m.group(1) not in briefing_text:
            problems.append(f"ungrounded figure: {m.group(0).strip()!r} is not in the briefing")
    return (not problems), problems


# ---- the goal, tier 2: an OPTIONAL separate-model judge (the fuzzy part) -----

def judge_dashboard(snapshot, html, judge_model):
    """A DIFFERENT model, prompted adversarially, checks the prose the code can't.
    Returns (ok, [problems]). Softer guarantee than the deterministic gate."""
    prompt = (
        "You are a strict reviewer. Given the BRIEFING (ground truth) and the "
        "DASHBOARD HTML, find any event whose assessment is inaccurate, any "
        "invented fact not supported by the briefing, or any missing 'who is "
        "affected' detail. Reply with JSON only: "
        '{"ok": true|false, "problems": ["..."]}\n\n'
        f"BRIEFING:\n{json.dumps(snapshot)}\n\nDASHBOARD:\n{html}"
    )
    # Temporarily point call_model at the judge model via env (llm reads MODEL at import,
    # so pass the model through a fresh message with an override header instead).
    reply = call_model([{"role": "user", "content": prompt}], model_override=judge_model)
    text = reply.get("content", "") or ""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return True, []  # judge unparseable -> don't block on it
    try:
        verdict = json.loads(m.group(0))
        return bool(verdict.get("ok")), list(verdict.get("problems") or [])
    except Exception:
        return True, []


# ---- the inner agent loop (Level 5) -----------------------------------------

def run_agent(messages):
    while True:
        reply = call_model(messages, tools=SCHEMAS)
        messages.append(reply)
        if not reply.get("tool_calls"):
            return reply.get("content", "")
        for tc in reply["tool_calls"]:
            args = json.loads(tc["function"].get("arguments") or "{}")
            fn = TOOLS.get(tc["function"]["name"])
            result = fn(**args) if fn else json.dumps({"error": "unknown tool"})
            print(f"    [tool] {tc['function']['name']}()")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})


# ---- the outer goal loop -----------------------------------------------------

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    use_judge = "--judge" in argv
    judge_model = os.environ.get("HARNESS_JUDGE_MODEL", "kimi-k2.7-code")

    # ONE fetch. This snapshot is the single source of truth for BOTH the agent
    # and the checker — the whole point.
    snapshot = json.loads(fetch_feed()).get("events", [])
    print(f"[briefing] {len(snapshot)} significant events fetched once (shared):")
    for e in snapshot:
        print(f"    - {e['alert']:6} {e['title']}")

    task = (
        "Write an HTML situation report to dashboard.html using write_dashboard. "
        "Use ONLY the events in this briefing; include every one with its exact "
        "alert level and a 'who is affected' line; invent no figures. Reply DONE.\n\n"
        f"BRIEFING:\n{json.dumps(snapshot, indent=2)}"
    )
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n=== attempt {attempt} ===")
        run_agent(messages)
        html = Path(DASHBOARD_PATH).read_text(encoding="utf-8") if Path(DASHBOARD_PATH).exists() else ""

        ok, problems = check_dashboard(snapshot, html)      # tier 1: hard gate
        print(f"  [deterministic] {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {problems}"))

        if ok and use_judge:                                # tier 2: soft gate
            jok, jproblems = judge_dashboard(snapshot, html, judge_model)
            print(f"  [judge:{judge_model}] {'PASS' if jok else 'FAIL'}" + ("" if jok else f" — {jproblems}"))
            ok, problems = jok, jproblems

        if ok:
            print(f"\nGoal met on attempt {attempt}. → {DASHBOARD_PATH}")
            return 0

        messages.append({"role": "user", "content":
                         f"The report is not acceptable. Fix these and reply DONE: {problems}"})

    print(f"\nGave up after {MAX_ATTEMPTS} attempts.")
    return 1


# ---- prove the checker with zero API calls -----------------------------------

def selftest():
    snap = [{"title": "Flood in China", "alert": "Orange", "country": "China"},
            {"title": "Quake in Peru", "alert": "Red", "country": "Peru"}]
    good = ("<h1>Sitrep</h1>"
            "<div>Flood in China — Orange. Who is affected: riverine communities.</div>"
            "<div>Quake in Peru — Red. Who is affected: Andean towns.</div>")
    cases = {
        "complete & grounded": (good, True),
        "missing an event": (good.replace("Quake in Peru — Red. ", ""), False),
        "wrong alert level": (good.replace("Quake in Peru — Red", "Quake in Peru — Orange"), False),
        "invented casualties": (good + "<p>1200 killed.</p>", False),
    }
    print("Deterministic checker self-test (no model calls):")
    all_ok = True
    for name, (html, expect_pass) in cases.items():
        ok, problems = check_dashboard(snap, html)
        verdict = "PASS" if ok else "FAIL"
        correct = (ok == expect_pass)
        all_ok &= correct
        print(f"  [{'ok ' if correct else 'BUG'}] {name:22} -> checker says {verdict}"
              + ("" if ok else f" {problems}"))
    print("self-test", "PASSED" if all_ok else "FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
