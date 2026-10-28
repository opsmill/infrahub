# Lift sheet, implementation and teardown

Read this in phase 5, when writing `05-implement.md`, and again when the design PR is approved.

The chosen revision is not a mockup. It is React, in this repo, built from `@infrahub/ui`
and the same tokens production uses. Implementation should start by **copying that file to
its real home and deleting what was scaffolding** — not by reading a document and building
it again. Rebuilding from a description throws away the only artifact everyone already
agreed on, and reintroduces every decision the review just settled.

So write a second file that makes the lift mechanical. Four lists, no prose:

- **Lift as-is** — the final `rev-NN.tsx` by path, and which parts transfer untouched:
  markup, component composition, the states, the copy. Name the real destination from
  `01-system.md`.
- **Replace at the seams** — each place the prototype fakes something, and what replaces
  it: mock rows → the actual GraphQL query, stub handlers → the real mutations, fake
  latency → real loading states.
- **Resolve, don't ship** — every knob, with the value that was chosen, written as a
  constant. Knobs are a design instrument; shipping a slider because nobody wrote the
  number down is the most embarrassing way for this to leak into production.
- **Do not lift** — the history panel, the annotation layer, the older `rev-*.tsx` files,
  and the duplication between them. All of it is scaffolding, and all of it is deleted with
  the prototype route.

Close with what still needs writing that a prototype never has: the tests, per the repo's
own testing guides.

## From approval to implementation

Implementation branches **from the design branch**, not from `develop`, so it starts with
`.design/<slug>/` and the approved revision already in place:

1. `git switch -c <your-prefix>-<slug> <your-prefix>-design/<slug>`
2. Follow `05-implement.md` — lift, seams, resolved knobs, tests — then run the teardown
   checklist below, all on this branch.
3. Open a normal feature PR against the same `base:`. `.design/<slug>/` lands with it, so
   the record and the code share one history.
4. Close the design PR as *superseded by #N*. Its thread stays readable; its branch can go.

Two PRs, deliberately. A four-revision prototype and a production implementation are
different things to review, and someone who approved the design should not have to re-read
it to approve the code.

## Teardown — the last item on the lift sheet

Write the teardown into `05-implement.md` as a checklist, to be run **when the
implementation merges**, not before. Until then the prototype is the only working
reference, and deleting it early leaves reviewers with a document and no way to check it.

- Delete the prototype route and every `rev-*.tsx`, the history panel, and the annotation
  layer.
- Keep `.design/<slug>/` in full, screenshots included. It costs nothing and it is the only
  answer to "why does it work this way" six months from now.
- Add one line to `05-handoff.md`: the PR that implemented it, and the date the prototype
  came down.

Grep for the marker before merging anything unrelated: every prototype-only file and every
line added to shared config carries a `PROTOTYPE design-jam <slug>` comment, so nothing
scaffolded is left behind by accident. Add that marker as you create them, not at teardown
— by then you will not remember which lines were yours.

**The final revision is the spec.** If the implementation has to diverge from it, that is a
design decision, and it goes back into `.design/<slug>/` as a new revision or a line in
`03-decisions.md` — never a silent drift discovered in review three weeks later.

Stop there. Implementation is a separate decision, made by people who have now seen this.
