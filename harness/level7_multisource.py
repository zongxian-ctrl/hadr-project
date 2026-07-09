"""Level 7 — many sources, and tools with arguments.

Levels 3-6 used one no-argument tool. A real agent has several tools, some
taking arguments, and must decide WHICH to call and WITH WHAT. Here the agent
gets four data sources — GDACS, USGS, ReliefWeb, NASA EONET — plus
write_dashboard, and picks based on the task:

  "significant quakes"  -> fetch_usgs(min_magnitude=5, window="day")
  "active wildfires"    -> fetch_eonet(category="wildfires")
  "declared disasters"  -> fetch_reliefweb()
  "alert-level events"  -> fetch_feed()   (GDACS, the only source with severity)

The loop is unchanged from Level 4 — only the toolbox grew. That's the point:
capability comes from adding tools, not from changing the loop.

Run:  python harness/level7_multisource.py  ["your task"]
"""

import json
import sys

from llm import call_model
from tools import (
    FETCH_EONET_SCHEMA,
    FETCH_FEED_SCHEMA,
    FETCH_RELIEFWEB_SCHEMA,
    FETCH_USGS_SCHEMA,
    WRITE_DASHBOARD_SCHEMA,
    fetch_eonet,
    fetch_feed,
    fetch_reliefweb,
    fetch_usgs,
    write_dashboard,
)

TOOLS = {
    "fetch_feed": fetch_feed,
    "fetch_usgs": fetch_usgs,
    "fetch_reliefweb": fetch_reliefweb,
    "fetch_eonet": fetch_eonet,
    "write_dashboard": write_dashboard,
}
SCHEMAS = [FETCH_FEED_SCHEMA, FETCH_USGS_SCHEMA, FETCH_RELIEFWEB_SCHEMA,
           FETCH_EONET_SCHEMA, WRITE_DASHBOARD_SCHEMA]

TASK = (
    "Give me a natural-hazard brief for right now: significant earthquakes "
    "(USGS, magnitude 5+), active wildfires (EONET), and any GDACS alert-level "
    "events. Pull from each relevant source, then summarize the picture."
)


def run_tool(tool_call):
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"].get("arguments") or "{}")
    print(f"    [tool] {name}({args if args else ''})")   # show the ARGUMENTS
    fn = TOOLS.get(name)
    return fn(**args) if fn else json.dumps({"error": f"unknown tool: {name}"})


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else TASK
    messages = [{"role": "user", "content": task}]
    print(f"you> {task}")

    while True:                                        # same loop as Level 4
        reply = call_model(messages, tools=SCHEMAS)
        messages.append(reply)
        if not reply.get("tool_calls"):
            print("\nbot>", reply.get("content", ""))
            return
        for tc in reply["tool_calls"]:
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": run_tool(tc),
            })


if __name__ == "__main__":
    main()
