"""Level 2 — standing orders (a system prompt).

Exactly Level 1, with ONE addition: before any user turn, we put a "system"
message at the front of the array, loaded from prompt.txt. That message is the
model's standing orders — it shapes every reply.

This is all CLAUDE.md is: a text file whose contents get prepended as the system
message. Nothing more magic than that.

Run:  python harness/level2_system.py
"""

from pathlib import Path

from llm import call_model

PROMPT_FILE = Path(__file__).parent / "prompt.txt"


def main():
    system_prompt = PROMPT_FILE.read_text(encoding="utf-8")
    messages = [{"role": "system", "content": system_prompt}]   # <-- the only new line
    print(f"Level 2 — standing orders loaded from {PROMPT_FILE.name}. ('quit' to exit)")
    while True:
        try:
            user = input("you> ").strip()
        except EOFError:
            break
        if user in ("quit", "exit", ""):
            break
        messages.append({"role": "user", "content": user})
        reply = call_model(messages)
        print("bot>", reply.get("content", ""))
        messages.append(reply)


if __name__ == "__main__":
    main()
