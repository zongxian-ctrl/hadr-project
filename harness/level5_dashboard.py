"""Level 5 — a second tool: write_dashboard.

Nothing about the loop changes from Level 4. We just register a SECOND tool.
Now the model can chain them on its own: fetch_feed to get the events, then
write_dashboard to save an assessed HTML page — and the same while-loop drives
both, one after another, until it's done.

That's the whole harness: a system prompt, a messages array, a set of tools,
and a loop. Everything fancier (Claude Code, OpenCode) is this plus polish.

Run:  python harness/level5_dashboard.py  ["your task"]
Produces: harness-dashboard.html
"""

import json
import sys
from pathlib import Path

from llm import call_model
from tools import (
    FETCH_FEED_SCHEMA,
    WRITE_DASHBOARD_SCHEMA,
    fetch_feed,
    write_dashboard,
)

# Two tools now. Adding a tool = one entry here + its schema. The loop is unchanged.
TOOLS = {"fetch_feed": fetch_feed, "write_dashboard": write_dashboard}
SCHEMAS = [FETCH_FEED_SCHEMA, WRITE_DASHBOARD_SCHEMA]

SYSTEM = (Path(__file__).parent / "prompt.txt").read_text(encoding="utf-8")
TASK = (
    "Fetch the current significant disasters, assess each (what/where/how bad/"
    "who is affected), then save a clean HTML dashboard of them with "
    "write_dashboard. Then reply DONE."
)


def run_tool(tool_call):
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"].get("arguments") or "{}")
    fn = TOOLS.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    return fn(**args)


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else TASK
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task},
    ]
    print(f"you> {task}")

    step = 0
    while True:                                        # same loop as Level 4
        reply = call_model(messages, tools=SCHEMAS)
        messages.append(reply)

        if not reply.get("tool_calls"):
            print("bot>", reply.get("content", ""))
            return

        for tc in reply["tool_calls"]:
            step += 1
            print(f"[step {step}] model runs {tc['function']['name']}()")
            result = run_tool(tc)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })


if __name__ == "__main__":
    main()
