# Lift sheet, implementation and teardown

Read this in phase 5, when writing `05-implement.md`, and again when the design PR is
approved.

The approved revision is React in this repo, built from `@infrahub/ui` and the production
tokens. Implementation starts by copying it to its real place and deleting the prototype
code, not by rebuilding it from a description: a rebuild reopens decisions the review
already settled.

## `05-implement.md`

Four lists, no prose:

- **Lift as is**: the path of the final `rev-NN.tsx`, the parts that move unchanged
  (markup, component structure, states, copy), and the destination from `01-system.md`.
- **Replace**: each thing the prototype fakes and what replaces it, for example mock rows
  with the GraphQL query, stub handlers with the mutations, fake delays with real loading
  states.
- **Resolve**: every knob and its chosen value, written as a constant. No knob ships.
- **Do not lift**: the history panel, the pin layer and the older `rev-*.tsx` files.

End with the tests that still need writing, following the repo's testing guides. Add the
teardown checklist below.

## From approval to implementation

1. Branch from the design branch, not `develop`, so `.design/<slug>/` and the approved
   revision come with it:
   `git switch -c <your-prefix>-<slug> <your-prefix>-design/<slug>`.
2. Follow `05-implement.md` on that branch.
3. Open a normal feature PR against `base:` from `STATE.md`. `.design/<slug>/` merges with
   the code.
4. Close the design PR as "superseded by #N".

The design and the implementation get separate PRs because they are reviewed differently,
and the people who approved the design should not have to review it again.

## Teardown

Run this when the implementation merges, not before: until then the prototype is the only
working reference.

- Delete the prototype route, every `rev-*.tsx`, the history panel and the pin layer.
- Keep `.design/<slug>/`, screenshots included.
- Add a line to `05-handoff.md` with the implementation PR and the date the prototype was
  removed.

Every prototype-only file, and every line added to shared config, carries a
`PROTOTYPE design-jam <slug>` comment from the moment it is created. Search for it before
merging, so nothing is left behind.

The final revision is the spec. If the implementation has to differ from it, record that
in `.design/<slug>/` as a new revision or a line in `03-decisions.md`.
