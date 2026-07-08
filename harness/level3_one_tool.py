"""Level 3 — one tool, one round.

We hand the model a tool (fetch_feed) by passing its schema. Now a reply can
come back two ways:
  - plain content  -> the model just answered, or
  - tool_calls     -> the model is asking US to run a function.

When it asks, we: run the function, append the result as a "tool" message, and
call the model again so it can answer using that result. That round-trip —
model asks, your code runs, result goes back — is the whole idea of a tool.

This level does exactly ONE round (ask -> run -> answer). Level 4 turns it into
a loop.

Run:  python harness/level3_one_tool.py  ["your question"]
"""

import sys

from llm import call_model
from tools import FETCH_FEED_SCHEMA, fetch_feed

QUESTION = "What significant disasters are happening right now? Use the feed."


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    tools = [FETCH_FEED_SCHEMA]
    messages = [{"role": "user", "content": question}]

    print(f"you> {question}")
    reply = call_model(messages, tools=tools)

    if reply.get("tool_calls"):
        messages.append(reply)                       # the model's request
        for tc in reply["tool_calls"]:
            name = tc["function"]["name"]
            print(f"[model asked to run: {name}()]")
            result = fetch_feed()                     # your code runs the real thing
            print(f"[fetch_feed returned {len(result)} chars]")
            messages.append({                         # feed the result back
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })
        reply = call_model(messages, tools=tools)     # model answers using the data

    print("bot>", reply.get("content", ""))


if __name__ == "__main__":
    main()
