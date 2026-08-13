# Contracts: Retirement of branch-agnostic property edges

**Feature**: `specs/ifc-2843-retire-agnostic-edges` | **Date**: 2026-08-12

## External interface surface: none

This feature changes **no** externally-facing contract. Specifically:

| Surface | Change |
|---|---|
| GraphQL schema | none |
| REST API / OpenAPI | none |
| Python SDK | none |
| CLI | none |
| Frontend | none |
| Events / message bus | none |
| Configuration | none |

No generated file under `backend/infrahub/core/schema/generated/`, `schema/schema.graphql`,
`schema/openapi.json`, or `frontend/app/src/shared/api/` is affected, so no regeneration step is
required for the API surface. The one generated artifact that *does* change is the graph version
constant, which is hand-maintained rather than generated.

The contracts below are therefore **internal component contracts** — the boundaries the tests
assert against and the enforcement points code to.

## C1 — `AgnosticBranchWindowBuilder` (pure)

The only part of the predicate testable without a database.

```text
build(branches: Sequence[Branch], at: Timestamp) -> BranchWindowSet
```

**Guarantees**

- Pure: no I/O, no database, no clock read. `at` is always supplied by the caller.
- For the default branch, emits a single pair `({global, name}, at)`.
- For a non-default branch, emits two pairs:
  `({global, origin_branch}, min(at, branched_from))` and `({global, name}, at)`.
- Isolation is **always** applied. There is deliberately no parameter to disable it (FR-012) —
  the escape hatches that exist on `Branch.get_query_filter_path` (`is_isolated=False`,
  `branch_agnostic=True`) are not reproduced here, so no future caller can reach for one.

**Rejects**

- An empty branch list is valid input and yields an empty set; it is not an error.

**Unit-testable properties**

- A branch that forked between two timestamps collapses its origin read to `branched_from`.
- A branch that forked after `at` does not collapse (`min` picks `at`).
- The default branch never collapses.

## C2 — `AgnosticFieldRetirerInterface` (Protocol)

The single entry point. Six callers on delivery.

```text
retire(candidates: RetirementCandidates, at: Timestamp) -> RetirementResult
```

**Guarantees**

- Evaluates the predicate against **all** open branches, each under its own filter with
  isolation applied.
- Closes the global property edges (`HAS_VALUE`, `IS_PROTECTED`, `HAS_SOURCE`, `HAS_OWNER`) of
  every candidate field vertex no branch retains.
- Closes **nothing** while any branch retains the vertex.
- Never creates a `deleted`-status edge on the global branch (FR-013).
- Never deletes an `AttributeValue` still referenced by another attribute (FR-017).
- Idempotent: a second call with the same candidates and a later `at` closes nothing further,
  because the edges it would close are no longer open.

**Caller obligations**

- Supply `at`: the owner's deletion time where one survives, the migration run time only where
  none does (FR-015). The component does not read the clock.
- Supply candidates bounded by id or fork point at every runtime enforcement point. The
  unbounded bound is reserved for the migration; using it on a hot path violates FR-018.

**Constructor dependencies** (all required, per the backend component-design rule)

- `db`
- the query collaborator, behind a `Protocol` — its second implementation is the recording
  double the unit tests use, satisfying the no-mock testing rule

## C3 — `RetireAgnosticPropertyEdgesQuery`

One Cypher body, three candidate bounds.

```text
init(db, candidates: RetirementCandidates, windows: BranchWindowSet,
     at: Timestamp, batch_size: int | None) -> Query
get_data() -> RetirementResult
```

**Guarantees**

- Candidate traversal starts from **open, active** global `HAS_ATTRIBUTE` / `IS_RELATED` edges
  (FR-011) — never from node reachability.
- Anchors on the `:Node`, `:Attribute`, `:Relationship` labels; never enumerates schema kinds
  (so profiles and templates are covered without being listed).
- Evaluates the relationship two-peer form: both peers live **and** both `IS_RELATED` edges
  active on the *same* branch (FR-002).
- Every value is bound as `$param`; no string interpolation of any value. The single
  interpolated element permitted is the batch size in `IN TRANSACTIONS OF n ROWS`, which cannot
  be parameterised in Cypher — matching the existing precedent in
  `DeleteBranchAgnosticAttributesQuery`.
- Returns results through `get_data()` as a frozen dataclass, never raw Neo4j records
  (Principle III).
- Batches when a batch size is supplied (required for the unbounded form).

**Verification obligation**

`EXPLAIN` must be run against the candidate traversal for all three bounds and the plans
recorded before the branch-deletion path is signed off (Principle V, research R5).

## C4 — Enforcement-point contract

Every enforcement point owes the same three things and nothing more:

1. A candidate set — **bounded** at runtime points.
2. A timestamp, per FR-015.
3. Correct sequencing relative to its own writes.

Sequencing obligations, which are not interchangeable:

| Point | Obligation |
|---|---|
| Node deletion | After the existence tombstone is written |
| Branch merge | After the bulk merge queries complete |
| Branch rebase | Inside the existing `global_graph_lock`, **before** `user_branch.rebase` is applied, at `rebase_at` |
| Branch deletion | **Before** `_delete_edges` removes the branch's `IS_PART_OF` edges — the reachability determination reads them |
| Schema removals | After the existing removal query runs |

No enforcement point contains predicate logic. No enforcement point treats its own occurrence as
a release trigger (FR-009).

## C5 — `Migration076` contract

```text
name             = "076_retire_agnostic_property_edges"
minimum_version  = 75
GRAPH_VERSION    : 75 -> 76
```

**Guarantees**

- Closes global property edges of vertices no branch retains; hard-deletes `Attribute` /
  `Relationship` vertices with no linked node vertex at all.
- Batches its writes.
- Reports **both** counts (edges closed, vertices removed) to the upgrade log via
  `get_migration_console()`.
- Returns `MigrationResult(errors=[...])` on unrepairable state. **Never raises**, never fails
  the upgrade (FR-016) — the pattern `m075_finish_deleting_branches` already establishes.

**Non-guarantee**

- Does not delete `AttributeValue` vertices left with zero references. Permitted, not required,
  explicitly not a deliverable.
