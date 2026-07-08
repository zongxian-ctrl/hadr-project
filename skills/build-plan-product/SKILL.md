---
name: build-plan-product
description: Use when starting from a high-level idea (REQS.md) that needs to become a detailed product description, before any code or implementation planning exists.
license: MIT
metadata:
  author: bguiz, mattpocock, rjs (adapted for hadr-project)
  source: https://github.com/bguiz/build-agent-skills/tree/fb8c2eb7dfb32810e0c19ba964320c6ac0e54ab9/skills/build-1-plan-product
  version: "0.0.0-hadr.1"
---

# Plan Software Product Details

Role: You are an experienced software product owner, expert in applying Ryan
Singer's "Shape Up" process.

Goal: Turn a high-level idea into a detailed product description — via an
interview, never by assuming answers.

## Adaptation note

The upstream skill is a guide that dispatches to four other skills
(`/grill-with-docs`, `/to-prd`, `/shaping`, `/breadboarding`) which are not
installed in this project. This port is self-contained: the interview and PRD
steps are performed directly by this skill. The upstream process doc and its
prompt templates are preserved verbatim in
[assets/process-plan-product.md](assets/process-plan-product.md).

Second deviation: the PRD is produced as **`prd.html`** (a self-contained HTML
page, no external assets — it is a course artefact), not `docs/PRD.md`.

## When to apply

- "Help me turn my idea into a product design"
- REQS.md exists but no PRD does

## When not to apply

- A detailed PRD already exists → move on to shaping / spec planning

## Inputs (verify first)

- `REQS.md` must exist. If it does not, ask the user to capture their idea
  there first, then stop.

## Steps

### A — Interview (grill) · model: Medium

1. Read REQS.md and any feed/domain docs. Write **every** question you have
   upfront into `QUESTIONS.md` (grouped, numbered) so the user can answer many
   per turn. Add new questions to the file as answers raise them.
2. Interview the user in batches (use AskUserQuestion or plain text; offer a
   recommendation when you have one). Record answers in QUESTIONS.md.
3. When all load-bearing questions are answered, produce:
   - `CONTEXT.md` — shared language, terms, definitions, resolved decisions.
   - `docs/adr/*.md` — one ADR per architectural decision made during the
     interview.
4. Final pass: re-read CONTEXT.md + ADRs, check for inconsistencies, grill the
   user on any found.

**Do not generate the PRD until the interview is complete.**

### B — Write PRD · model: High, fresh context

Using REQS.md + CONTEXT.md + QUESTIONS.md answers, generate **`prd.html`**:
problem statement, user stories, solution description, implementation
decisions, testing decisions, explicit out-of-scope. Self-contained HTML,
readable in light and dark themes.

### C/D/E — Shaping, breadboarding, ADR extraction

Frame → requirements (R) → shapes (S) → R×S fit check → spikes → select and
detail a shape → breadboard affordances → consistency pass. Follow the prompt
templates in [assets/process-plan-product.md](assets/process-plan-product.md);
outputs are FRAME.md, SHAPING.md, SPIKE-*.md, BREADBOARD.md.

## Outputs

`QUESTIONS.md` · `CONTEXT.md` · `docs/adr/*.md` · `prd.html` · (later)
FRAME.md, SHAPING.md, BREADBOARD.md
