# Phase 4: Review

Read this when phase 4 starts. The rules in `SKILL.md` still apply.

Run the passes on the running prototype, in this order. Tidy first, so the critique is
about the design and not the padding.

Preflight says which review this machine can run. The full review needs the four paid
review skills (`emil-ui-polish`, `emil-surfaces`, `emil-ui-review`, `emil-prep-for-prod`).
Without all four, run the reduced review, which uses public skills and the lists in
[`review-checklist.md`](review-checklist.md). Write the level, full or reduced, on the
first line of `04-review.md`.

| Pass | Full review | Reduced review |
|---|---|---|
| 1. Tidy | `emil-ui-polish`, then `emil-surfaces` | the *Tidy* list |
| 2. Stress | `break-ui` | `break-ui` |
| 3. Critique | `emil-ui-review` | `emil-design-eng`, then the *Critique* list |
| 4. Readiness | `emil-prep-for-prod`, without its marketing and SEO checks (say so) | the *Readiness* list |
| 5. By hand | the list below | the list below |

- **Tidy**: check repeated items (cards in a row, rows in a list) as one object: same
  padding, edges and baselines. In the full review, if the findings keep pointing at
  spacing or hierarchy across the screen, invoke `emil-design-foundations` once.
- **Stress**: `break-ui` adds a *Demo data / Worst case* toggle to the screen. Mark it with
  the `PROTOTYPE design-jam <slug>` comment like every other prototype-only line.
- **By hand**: no skill checks these.
  - Tab from the top: the order makes sense and the focus ring shows.
  - Look at dark mode.
  - In a narrow desktop window, there is no sideways scroll.
  - Every state from phase 3 still renders.

Fix each finding or accept it with a reason. Write `04-review.md`: the review level, then
the findings by pass, each fixed or accepted, with reasons.

**Gate**: phase 5 does not start while a finding is unresolved. "Accepted: the empty state
is out of scope, recorded as a gap" resolves one; silence does not. At the checkpoint, say
"the gate is clean" in those words. The code is copied into production next, and nobody
reviews again code that arrived approved.
