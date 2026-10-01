# Safe step patterns

Every step must leave `stable` releasable. These patterns are how a big change becomes a series of
small ones where each intermediate state is valid. Pick one per step; a step that needs two
patterns is two steps.

## Characterization tests first

The coverage gate in SKILL.md decides when this is required. Before moving code that has thin
coverage, pin its current behavior with tests — including the
weird edge cases, even ones that look like bugs. The tests pass on the current code and must keep
passing unchanged through every later step; that is the evidence behind "no behavior change".

- If a test reveals a real bug, **do not fix it in the refactor**. Record it in the test with a
  clear name, file a bug separately, and keep the behavior. A refactor PR that also changes
  behavior is no longer safe to ship on `stable` without scrutiny.
- Load `dev/guidelines/backend/testing.md` before writing backend tests; prefer the cheapest test
  tier that exercises the behavior.

## Expand → migrate → contract (parallel change)

1. **Expand:** add the new function/class/module next to the old one. Nothing calls it yet, or the
   old one delegates to it. Ship.
2. **Migrate:** move callers over in batches sized to the budget — one package or one call pattern
   per PR. Old and new coexist and both work. Ship each batch.
3. **Contract:** once the caller grep is empty, delete the old path. Ship.

Re-run the caller grep at every step: new callers of the old API appear on `stable` while the
refactor is in flight (reconciliation must catch them).

## Delegate, then inline

To replace an implementation, first make the old entry point a thin wrapper that calls the new
implementation (one PR, behavior identical, tests unchanged), then move callers, then delete the
wrapper.

## Extract without moving

Pure mechanical extractions — extract function, extract class, rename a private symbol — are
ideal steps: small, obviously safe, and reviewers can verify them by reading. Keep public import
paths working with a re-export until the last importer moves; Infrahub code imports deep paths and
the SDK/plugins may too.

## Things that are never a refactor step on `stable`

Stop and hand off instead (see *When to stop* in SKILL.md):

- graph migrations or changes to `GRAPH_VERSION`, schema definitions, or generated files' sources
  in a way that changes their output;
- GraphQL schema, REST/OpenAPI, event payloads, or message-bus contracts;
- new dependencies or version bumps;
- removing a public/importable symbol that external code (SDK, plugins, user transforms) could use
  without a deprecation decision by a human;
- performance changes that alter query shapes on hot paths without a benchmark — "same results"
  is not the same as "same behavior" for a production database.

## Sizing heuristics

- A reviewer should be able to say "yes, this is equivalent" from the diff alone. If they would
  need to run it in their head across several files, it is too big.
- Moves and renames can be larger in lines (they're mechanical), but keep them alone in their PR —
  never mix a move with a logic change.
- Generated-file churn doesn't count toward the budget, but the change that triggered it does.
