"""Level 1 — a chat loop.

The whole idea of a "chat": keep a `messages` list, and each turn
  1. append the user's line,
  2. send the ENTIRE list to the model,
  3. print the reply and append it too.

The model is stateless. The growing `messages` array is the only memory there
is — that's why we send all of it every time.

Run (from the repo root):
    python harness/level1_chat.py
Type 'quit' or press Ctrl-D to exit.
"""

from llm import call_model


def main():
    messages = []
    print("Level 1 — chat loop. Type a message ('quit' to exit).")
    while True:
        try:
            user = input("you> ").strip()
        except EOFError:
            break
        if user in ("quit", "exit", ""):
            break

        messages.append({"role": "user", "content": user})   # 1. remember the user
        reply = call_model(messages)                          # 2. send the whole array
        print("bot>", reply.get("content", ""))               # 3. show + remember the reply
        messages.append(reply)


if __name__ == "__main__":
    main()
