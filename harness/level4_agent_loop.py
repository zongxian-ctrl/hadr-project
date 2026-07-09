"""Level 4 — the agent loop.

Level 3 did one round. An *agent* just keeps doing rounds: call the model, and
as long as it asks for tools, run them and feed the results back. Stop only when
it stops asking and gives a plain answer.

That while-loop is the entire difference between "a model" and "an agent". It's
also the loop that /goal wraps a success-checker around (run until the goal is
met, not just until the model shrugs).

Run:  python harness/level4_agent_loop.py  ["your task"]
"""

import json
import sys

from llm import call_model
from tools import FETCH_FEED_SCHEMA, fetch_feed

# A tool registry: name -> real function. Dispatch by name so adding tools
# (Level 5) is just adding entries here + their schemas.
TOOLS = {"fetch_feed": fetch_feed}
SCHEMAS = [FETCH_FEED_SCHEMA]

TASK = "What significant disasters are happening right now? Assess them briefly."


def run_tool(tool_call):
    name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"].get("arguments") or "{}")
    fn = TOOLS.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    return fn(**args)


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else TASK
    messages = [{"role": "user", "content": task}]
    print(f"you> {task}")

    step = 0
    while True:                                        # <-- the agent loop
        reply = call_model(messages, tools=SCHEMAS)
        messages.append(reply)

        if not reply.get("tool_calls"):               # no more tools -> done
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
