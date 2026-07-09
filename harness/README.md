# Build an agent harness in 5 levels

A from-scratch agent harness, one concept per file, so you can stop at any level
and still have something that runs. Standard-library Python only (`urllib`) — no
SDK — so every part is visible. It talks to the **OpenCode Go** gateway
(OpenAI-compatible), so it uses your Go key, not Claude.

Everything a big tool (Claude Code, OpenCode) does is these five ideas plus
polish: a system prompt, a `messages` array, some tools, and a loop.

## Setup

**None, if you've signed in to OpenCode** (`opencode auth login`). The harness
auto-reads your key from OpenCode's stored config, so it just runs.

To override the key or use it elsewhere, set `OPENCODE_API_KEY` yourself.
Optional: pick a different model with `HARNESS_MODEL` (default `qwen3.7-max`);
any tool-capable `opencode-go/*` model works, e.g. `kimi-k2.7-code`, `glm-5.2`.

Run every level from the **repo root**.

## The eight levels

| Level | File | The one new idea |
|-------|------|------------------|
| 1 | `level1_chat.py` | **Chat loop.** Keep a `messages` array; send all of it each turn. The array is the memory. |
| 2 | `level2_system.py` | **Standing orders.** Prepend a system message from `prompt.txt`. This is all `CLAUDE.md` is. |
| 3 | `level3_one_tool.py` | **One tool.** The model asks for `fetch_feed`, your code runs it, the result goes back as a `tool` message. |
| 4 | `level4_agent_loop.py` | **The agent loop.** Keep running tools while the model keeps asking. The loop `/goal` wraps a checker around. |
| 5 | `level5_dashboard.py` | **A second tool.** Add `write_dashboard`; the same loop now chains fetch → assess → write on its own. |
| 6 | `level6_goal.py` | **A goal checker.** A deterministic check — not the model — decides if the goal is met; if not, it feeds back and retries. This is what `/goal` does. |
| 7 | `level7_multisource.py` | **Many tools, with arguments.** Four data sources (GDACS, USGS, ReliefWeb, EONET); the model chooses *which* to call and *with what arguments*. Same loop — a bigger toolbox. |
| 8 | `level8_capstone.py` | **The capstone.** Gather 4 feeds (GDACS/USGS/EONET/NWS) → **resolve duplicates** (the same event from >1 feed merged by hazard+space+time) → NASA aftermath image per event → model assesses each → render a polished UI: **KPI tiles, a world map with severity-coded, hoverable event dots, a legend, source filters, feed-status, and a fire-detection toggle**. Deterministic gather+resolve+render, model only for judgement. |

### The sources (`tools.py`)

| Tool | Source | Arguments | Note |
|------|--------|-----------|------|
| `fetch_feed` | GDACS | — | The only source with alert levels (Orange/Red). |
| `fetch_usgs` | USGS earthquakes | `min_magnitude`, `window` | Magnitude + time window. |
| `fetch_reliefweb` | ReliefWeb RSS | `limit` | Curated, slower, no severity. |
| `fetch_eonet` | NASA EONET | `category`, `limit` | Natural-events catalog; no severity. |
| `fetch_nws` | US NWS weather alerts | `min_severity`, `limit` | US-only; carries a severity (Extreme/Severe/…). |
| `fetch_imagery` | NASA GIBS / WorldView | `lat`, `lon`, `date` | Satellite image (aftermath) for a place+date. ~250m: smoke/flood/burn-scar scale, not buildings. |

Shared plumbing (not the lesson): `llm.py` (the raw HTTP call) and `tools.py`
(the tool functions + their JSON schemas).

## Run them

```bash
python harness/level1_chat.py                 # type messages; 'quit' to exit
python harness/level2_system.py               # same, but follows prompt.txt
python harness/level3_one_tool.py             # one fetch_feed round
python harness/level4_agent_loop.py           # loops until the model stops asking
python harness/level5_dashboard.py            # fetch -> assess -> write; makes harness-dashboard.html
python harness/level6_goal.py --selftest      # prove the checker itself (no API key needed)
python harness/level6_goal.py                 # full loop: shared snapshot + deterministic gate
python harness/level6_goal.py --judge         # also run a SEPARATE-model judge for the prose
python harness/level7_multisource.py          # agent picks among GDACS/USGS/ReliefWeb/EONET
python harness/level7_multisource.py "strongest quakes today and any active volcanoes"
python harness/level8_capstone.py             # auto: gather all + aftermath imagery -> nice UI
```

## How this maps to the real tools

- **`prompt.txt` → `CLAUDE.md`**: a text file prepended as the system message.
- **`fetch_feed` / `write_dashboard` → any tool** (Read, Bash, web fetch…): a
  function the model can request; your code runs it and returns the result.
- **The Level 4 loop → the agent**: "keep going while it asks for tools" is the
  core.
- **The Level 6 checker → `/goal`**: an independent verifier decides "done", not
  the model. Two lessons in it:
  - **One shared snapshot.** The feed is fetched once; the agent writes from that
    briefing and the checker judges against the *same* briefing — no second
    fetch, no race, a fixed target. This mirrors the project's
    gate → `briefing.json` → model flow.
  - **A goal is a proxy, so verify in two tiers.** A *strong deterministic* gate
    for what code can check for sure (every event present with its exact alert
    level, no ungrounded casualty figures) — trustworthy but shallow; plus an
    *optional separate-model judge* (`--judge`) for the fuzzy prose — deeper but
    softer, and deliberately a **different** model than the writer. An agent is
    only as good as its verifier, and any single proxy can be gamed.
- This project's real pipeline is the same shape: the deterministic gate writes
  a briefing, then a model (via a tool-running harness) writes the report.
