"""The one shared piece: a single function that sends messages to the model and
returns its reply. Everything else in each level_N.py is the lesson.

Deliberately raw `urllib` (no SDK) so you can see the exact HTTP request and the
exact JSON that comes back. This is all an "LLM call" is: POST a messages array
to an endpoint, read the reply out of choices[0].message.
"""

import json
import os
import sys
import urllib.request

# Models love emoji; the Windows console defaults to cp1252 and crashes on them.
# Make stdout UTF-8 (replace anything unprintable) so every level prints safely.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# OpenCode Go gateway — OpenAI-compatible chat completions endpoint.
ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
MODEL = os.environ.get("HARNESS_MODEL", "qwen3.7-max")


def call_model(messages, tools=None, model_override=None):
    """POST the conversation to the model; return the assistant's message dict.

    `messages` is the whole conversation so far (the model is stateless — the
    array IS the memory). `tools` is an optional list of tool schemas; when
    given, the reply may contain `tool_calls` instead of (or with) content.
    """
    api_key = os.environ.get("OPENCODE_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set OPENCODE_API_KEY first. See harness/README.md for how to load "
            "it from your OpenCode auth without printing it."
        )

    payload = {"model": model_override or MODEL, "messages": messages}
    if tools:
        payload["tools"] = tools

    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Without a User-Agent, urllib sends "Python-urllib/x.y", which the
            # gateway's CDN (Cloudflare) blocks with a 403. Any normal UA passes.
            "User-Agent": "hadr-harness/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # choices[0].message is the assistant turn: {role, content, [tool_calls]}.
    return data["choices"][0]["message"]
