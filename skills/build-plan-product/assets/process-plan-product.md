<!-- Verbatim copy of https://raw.githubusercontent.com/bguiz/build-agent-skills/fb8c2eb7dfb32810e0c19ba964320c6ac0e54ab9/skills/build-1-plan-product/assets/process-plan-product.md (MIT) -->
# The product details planning process

Start from a high-level idea, and systematically turn that into a detailed product description.

This is achieved through a combination of these agent skills:
`/grill-with-docs` + `/to-prd` + `/shaping` + `/breadboarding`.

If you do not have them yet, install them using:

```shell
npx skills add -g mattpocock/skills --skill grill-with-docs --skill to-prd
npx skills add -g rjs/shaping-skills --skill shaping --skill breadboarding
```

## Documents

### Already exist

- REQS.md - Initial idea, created via handwritten capture of thoughts

### Will be produced

- QUESTIONS.md - Scratch file primarily used by `/grill-with-docs`
- CONTEXT.md - Contains shared language/terms/definitions, created via `/grill-with-docs`
- docs/adr/*.md - Architectural decision records, created via `/grill-with-docs`
- docs/PRD.md - User stories, problem statement, solution description, implementation decisions, testing decisions, out of scope, created via `/to-prd`
- FRAME.md - Succinct product definition, created via `/shaping`
- SHAPING.md - Requirements, shapes, RxS fit matrix, detailed selected shape, created via `/shaping`
- SPIKE-*.md - Used to ideate and decide on changes to requirements or shapes to achieve better RxS fit
- BREADBOARD.md - Affordances and how they are connected, created via `/shaping`

## Steps

### A - Grill with docs - Initial

(A1) Grill with docs, but modify the process to log all questions in a file upfront, so that you have the options to answer multiple in each turn, to speed up the process.

> Model hint: Medium, FRESH context
> Prompts:

```text
/grill-with-docs
context: build a product described in REQS.md
task:
- grill me and produce: CONTEXT.md + docs/adr/*.md
- add all questions up front + as you go in: QUESTIONS.md
```

```
(…answer questions asked, multiple times until all have been answered)
```

(A2) Inconsistencies check

> Model hint: Medium, reuse context
> Prompts:

```
review CONTEXT.md + docs/adr/*.md to do a final check for inconsistencies/problems, grill me on them
```

### B - To PRD - Write PRD

(B1) To PRD to write user stories.

> Model hint: High, FRESH context
> Prompts:

```text
/to-prd using CONTEXT.md and REQS.md
```

### C - Shaping - Frame to detailed shape

(C1) Frame - Capture the "why": Source (verbatim), Problem (what's broken), Outcome (what success looks like). Stored in a frame doc.

> Model hint: Medium, FRESH context
> Prompts:

```
/shaping analyse the contents of this dir and tell me which shaping steps have already been completed
```

```text
create the framing doc with REQS.md as the raw initial requirements and the docs/PRD.md and CONTEXT.md for detailed info/scaffolding
```

(C2) Build R (Requirements) - Collaboratively gather numbered requirements (R0, R1, R2…). Max 9 top-level; group into chunks with sub-requirements if needed. Track status: Core goal / Must-have / Undecided / Out.

> Model hint: Medium, reuse context
> Prompts:

```text
create SHAPING.md and do step "Build R" in it
```

```text
decompose requirement (…requirement ID) into 2 or more sub-requirements.
```

(C3) Sketch S (Shapes) - Propose mutually exclusive solution approaches (A, B, C…). Each is a table of parts - mechanisms describing what you build, not intentions.

> Model hint: Medium, reuse context
> Prompts:

```text
continue next step in SHAPING.md, "Sketch S (Shapes)" with 3 distinct shapes
```

(C4) Fit Check (R x S) - Decision matrix: requirements as rows, shapes as columns. Binary ✅/❌ only. Notes explain failures. Missing requirements surface here.

> Model hint: Medium, reuse context
> Prompts:

```text
continue next step in SHAPING.md, "Fit Check (R x S)"
```

(C5) If missing requirements are surfaced, and the decision is non-obvious, perform spikes in order to determine how best to address them.

> Model hint: Medium, reuse context ... but if there are many flags also consider a FRESH context window
> Prompts:

```text
/shaping
- go through the R x S table in SHAPING.md
- for each row that has at least 1 flag:
  - detail the reasons for that flag, and state why it passes or gets gets flagged for all 3 shapes
  - explain what was assumed when deciding on the OK vs flagged status for each shape.
  - explain what needs to change to go from flagged to OK
- note that there is an existing "notes" bullet point list
  - replace this with the more detailed explanation for flags from above
```

```text
I want to pick shape (…shape ID), as that seems the closest to achieving a R x S full fit (…or other reasons).

But first, address the flagged requirements (…list of flagged requirements for target shape)

Create a SPIKE-(…spike ID).md file, and do a spike for all the flagged requirements there?
```

```text
(…repeat above prompt for different shapes and different requirements, as desired)
```

```text
- I have made manual edits to SPIKE-(…spike ID).md
- use the recommendations in SPIKE-(…spike ID).md to update the appropriate parts of SHAPING.md
- however
  - do NOT modify the contents of the "## Fit Check" section, simply rename it to "## Fit Check v1"
  - instead create a new "## Fit Check v2" section, with a note linking to spike SPIKE-(…spike ID).md
```

(C6) Select a shape - Pick the shape that passes the fit check. If none pass, add missing R and iterate.

> Model hint: Medium, reuse context
> Prompts: None. 

```text
Pick shape (...shape ID)
```

> Note: You have already done the work in the previous step, so this step is mostly already done by the user.
> Simply tell it your decision. If unable to decide, consider backtracking and repeating previous steps.

(C7) Detail the selected shape - Break it into concrete components. Flag unknowns with ⚠️. Run further spikes to resolve flagged parts. A shape is ready only when all parts are understood (no ⚠️).

> Model hint: Medium, reuse context
> Prompts:

```text
select shape (…shape ID) and detail it in SHAPING.md
```

```text
trigger the shaping ripple hook check
```

### D - Shaping - Breadboarding

(D1) Breadboard - Translate the shape into affordance tables (UI affordances, Non-UI affordances) with wiring. Produces the concrete affordance map.

> Model hint: High, FRESH context
> Prompts:

```text
/shaping the shaping process has been completed up until shape detailing
see FRAME.md + SHAPING.md + (…list of spike files)

next create BREADBOARD.md and start breadboarding.
do NOT attempt to complete the full breadboard in a single pass, as you will exceed the max tokens per turn.
instead do this piecemeal, writing only 1 section to file at a time.
```

```text
add next breadboarding section (if not yet complete)
```

```text
(…repeat above prompt until you receives a response that it has completed the process)
```

```text
trigger the shaping ripple hook check
```

### E - Grill with docs - Extract ADRs and check problems

(E1) Ensure consistency and capture decisions.

> Model hint: Medium, FRESH context
> Prompts:

```text
/grill-with-docs
- review new files created from the shaping process: FRAME.md + SHAPING.md + BREADBOARD.md + (…list of spike files)
- assess if need to add/update existing files: CONTEXT.md + docs/PRD.md + ADRs in docs/adr/*.md
- make changes as needed
- check/clarify with me if unsure, adding all questions upfront and as you go to QUESTIONS.md
- identify any inconsistencies and other mistakes/ problems, similarly adding them to QUESTIONS.md
```
