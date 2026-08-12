# Phase 1 Data Model: Coalesce Python transform computed attributes on merge and rebase

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-11

**Revision**: second pass, after [critiques/critique-20260811.md](./critiques/critique-20260811.md). The first pass claimed no type changes were needed. That was wrong in one important place, corrected below.

No persisted entity changes. Nothing is added to the graph schema, nothing is migrated. Everything here is an in-memory value on the merge and rebase path.

## Existing types, and what changes

| Type | Change | Note |
|---|---|---|
| `RecomputeFamily` | Add a fourth member for Python transform computed attributes | Today a three-member literal, matched exhaustively when a submission becomes a workflow, so the compiler finds every place needing a new branch. |
| `MergeChange` | None | `node_id`, `kind`, `action`, `changed_fields`. Already carries what both axes need. |
| `ChangeSignature` | None | The dedup key. |
| `ReaderLookup` | None | Reused unchanged: a resolved set is a self-keyed lookup. |
| `AffectedTarget` | **Add an explicit whole-kind marker** | See below. This is the correction. |
| `CoalescedRecompute` | None | Both the input and the output of the new resolution step. |
| `CoalescedSubmission` | None | The chunked unit handed to a workflow. |
| `WrittenNode` | None | What the bulk writer reports, and what the chain turns back into changes. |

### The correction: a widened target must be representable

The first pass assumed FR-009's whole-kind widening could ride on the existing types. It cannot. `ReaderLookup` has no "all of kind" mode, and the planner chunks a node id set into submissions — so an empty set produces **zero** chunks, therefore zero submissions, and the widened target silently disappears. That is the exact opposite of what widening is for, and it would have shipped as a skip.

`AffectedTarget` therefore needs an explicit whole-kind marker, and the submission step needs a branch that routes such a target to the existing all-of-kind refresh rather than to the node-id-scoped one. FR-010 exists to pin this, and a unit test asserting that a widened target produces exactly one submission is the guard.

### Per-family self and cross derivation

The builder currently decides once per change whether to emit a self-target, and skips it on an update because the three existing families recompute inline when a node is saved. Python transforms do not: they need a repository, a GraphQL query and user code, none of which run on save. Slotting Python into the shared decision would drop the owner axis on every update.

The self and cross choice therefore becomes per family rather than per call.

## New types

### `PythonTargetResolver` (protocol) and its two implementations

Takes a coalesced recompute and returns a coalesced recompute, so nothing downstream changes shape. See [contracts/python-target-resolution.md](./contracts/python-target-resolution.md) for the guarantees and the failure table.

Two implementations from day one: client-backed for production, in-memory for tests. The second is what justifies the protocol under the project's design rule.

### Read-field index

Maps each Python computed attribute to the kinds and fields its transform's query reads. Derived once per pass from the stored query text, then used for both narrowings.

This is the piece that makes FR-004 possible, and its absence is what made the first draft slower than the behaviour it replaced. It is deliberately not cached: a stale cache would silently widen or, worse, miss a refresh, and the derivation is one pass amortised over the work it scopes.

### Schema-coverage pair set

The output of a pure function supporting FR-016: attribute-and-kind pairs a schema change is **expected** to refresh across the whole kind. Computed from the changed-elements payload alone, no I/O.

It implements only the two selection rules that need no read sets. Under-reporting shrinks the set of targets subtracted, which is the safe direction. Note the wording: *expected*, not *certain*. A pair whose transform exists in the schema but not in the database never becomes a candidate for the schema pass, so no set computed from the schema alone can be certain.

## State transitions

```text
merge or rebase change set
   |
   v
[build]                    pure, synchronous, no I/O
   |                       emits unfiltered Python targets for both axes
   v
CoalescedRecompute
   |
   v
[subtract schema-covered]  merge only, and only after a successful notification send
   |                       pure, no I/O
   v
CoalescedRecompute
   |
   v
[resolve python targets]   NEW. bounded lookups. narrows both axes. widens on failure.
   |                       never raises: the caller's guard would swallow everything.
   v
CoalescedRecompute         every target now has concrete node ids or a whole-kind marker
   |
   v
[plan] -> [submit]         chunked, dispatched per family
   |
   v
bulk write
   |
   +-- live origin      -> per-node automations chain the next level
   |
   +-- recompute origin -> the chain re-enters [build] at depth + 1
```

The chain re-entry is why resolution must sit on the shared path rather than beside a single caller. A chained level that skipped it would submit Python targets with no ids.

## Invariants

1. **A target never leaves the pipeline unresolved.** Concrete ids, or an explicit whole-kind marker that actually dispatches. An empty id set means nothing to do, never everything.
2. **Widening is bounded to one attribute-and-kind pair.**
3. **A resolution failure never removes work from another family.** The three existing families must still ship.
4. **Subtraction only removes work something else is certain to do.** The schema pass covers every node of the kind; the coalesced pass covers a subset. Removal in the other direction would leave untouched nodes stale.
5. **The origin stamped on a write decides who continues the chain**, and whether a write is coalesced is stated by its caller, never inferred from the shape of its arguments. Three different callers pass id lists and only one of them is coalesced.
6. **The depth bound counts every family.** Its guarantee is that it never truncates a real chain, which only holds if Python targets are included.
7. **The narrowed set never exceeds what the per-node path would have refreshed.** This is the invariant the first draft broke.
