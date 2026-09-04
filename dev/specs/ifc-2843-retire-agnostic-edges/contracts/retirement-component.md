# Contracts: Retirement of branch-agnostic property edges

**Feature**: `specs/ifc-2843-retire-agnostic-edges` | **Date**: 2026-08-12 |
**Revised**: 2026-08-17

> **Revision note.** This document originally specified a single injected component
> (`AgnosticFieldRetirer`) behind a query `Protocol`, fed pre-built branch windows by an
> `AgnosticBranchWindowBuilder`, driving one query class parameterised by three candidate bounds and
> two anchor modes. That design was replaced mid-implementation by maintainer decision. The reasons
> are recorded in plan.md §"Design revision"; the contracts below describe what is actually being
> built. C1/C2 of the original are gone — there is no component, no protocol, no adapter and no
> window builder.

## External interface surface: none

This feature changes **no** externally-facing contract.

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
`schema/openapi.json`, or `frontend/app/src/shared/api/` is affected. The one hand-maintained
constant that changes is the graph version, and only when the repair migration lands.

The contracts below are therefore **internal**: the boundaries the tests assert against.

## C1 — The shared retention predicate

`UNRETAINED_AGNOSTIC_FIELD_PREDICATE` in `backend/infrahub/core/query/agnostic_retention.py`.

A Cypher fragment, not a class. It expects `field` in scope — one row per candidate vertex — plus
the `$global_branch_name` and `$at` parameters, and emits the candidates no branch retains, with
`field` as the only variable still in scope. Every enforcement point composes the same fragment, so
the judgement exists once.

**Guarantees**

- Retention is decided **per branch and per linked vertex**: under that branch's view, the vertex's
  existence edge and its edge to the field must both resolve to `active`. `branch_name` and `node`
  stay row keys from the first match through to the per-branch aggregation, which is what conjoins
  the two axes; the cross-branch reduction is a `max` applied afterwards, so retention is a
  disjunction of what each branch holds live on its own.
- Both axes matter. The field axis is not decoration: removing a field from a schema on one branch
  mirrors the attribute's edges onto that branch with `deleted` status while leaving the global edge
  untouched, so a branch can retain the *object* and not the *field*.
- Each edge is resolved by the repo-wide ordering — branch level, then latest write, then active
  over deleted — and the first is taken.
- A `:Relationship` requires **two live peers**, an attribute one. Peers are counted by **uuid**, so
  the copies a kind or inheritance change leaves behind count once between them.
- Branch isolation is always applied: a non-default branch reads its origin as of
  `min(branched_from, $at)`. There is no parameter to disable it (FR-012).
- The branch windows are derived **inside** the query from `(:Branch)`, not passed in. This reverses
  an explicit earlier decision (research R2, critique 2026-08-12) and is why there is no builder:
  marshalling the branches through Python meant a paginated read whose default limit silently turned
  the branches past it into branches that retain nothing.
- The fork window carries a lower bound only; a branch cannot have forked in the future.

**Assumption**

- Every branch forks from the default branch (`graphql/mutations/branch.py` rejects any other
  origin). The topology is a star. A branch-of-branch feature would invalidate this fragment rather
  than extend it.

**Known gap**

- No test separates counting peers by uuid from counting them by vertex. The kind-rename migration
  closes the superseded vertex's global edge and tombstones its existence on the migrating branch,
  so two same-uuid copies are never simultaneously live under one window, and no fixture built
  through the real migration produces the distinguishing shape. The uuid expresses the intent.

## C2 — Per-enforcement-point queries

Each enforcement point owns a query that composes C1. They differ only in how candidates are
selected, how the retirement timestamp is derived, and whether the writes are batched — never in how
retention is judged.

| Point | Candidate selection | Stamp | Batched |
|---|---|---|---|
| Node deletion | the node's uuid | the deletion's `at` | no |
| Branch merge | the merge diff's deleted nodes | the merge `at` | no |
| Branch rebase | the base-branch deletions | `rebase_at` | no |
| Branch deletion | fork-point bounded | the deletion time | its own query |
| Schema attribute removal | kind + attribute name | the removal `at` | folded into `AttributeRemoveQuery` |
| Schema relationship removal | kind + relationship identifier | the removal `at` | folded into the relationship equivalent |
| Repair migration | unbounded | derived per candidate | yes |

The schema removals fold the closure into the existing removal query rather than calling a separate
one: that query already matches the attribute vertices for the kind and already carries the branch
filter, and running afterwards would mean anchoring on an owning edge the previous statement just
closed.

### C2.1 — `RetireNodeAgnosticFieldsQuery` (delivered)

`backend/infrahub/core/query/node_agnostic_retirement.py`.

```text
init(db, node_uuid: str, at: Timestamp) -> Query
get_data() -> NodeAgnosticRetirementResult
```

**Guarantees**

- Anchors on the node's open, active global `HAS_ATTRIBUTE` / `IS_RELATED` edges. Anchors on the
  `:Node`, `:Attribute`, `:Relationship` labels, never on schema kinds, so profiles and templates are
  covered without being enumerated.
- Closes **every** open, active global edge incident to each unretained field vertex, whatever its
  type — one undirected match, no enumeration. An enumerated list drifts out of step with
  `DatabaseEdgeType` and silently leaks whatever it omits; a sweep cannot. The consequence is that a new
  edge type hung off an `:Attribute` or `:Relationship` vertex is closed automatically, so a type that
  must outlive its field has to sit on a vertex the field does not touch. `IS_RESERVED` already does:
  every one runs pool-to-value or pool-to-address, never through a field vertex. See data-model.md
  §"Pool interaction".
- Never writes a `deleted`-status edge. Retirement is a time-close (FR-013).
- Never deletes a vertex or an `AttributeValue` (FR-017).
- Idempotent: a second run closes nothing and reports zero.
- Runs as a participant in its caller's transaction and therefore never batches — Neo4j forbids
  `CALL { … } IN TRANSACTIONS` inside an explicit transaction.
- Returns a frozen dataclass from `get_data()`, never raw records (Principle III).

**Caller obligations**

- Supply `at`. The query does not read the clock.
- Sequence the call after the operation's own writes and **before its commit**.

**Failure behaviour**

- A failure propagates. At a runtime enforcement point the query runs inside the caller's still-open
  transaction — the GraphQL delete calls `NodeManager.delete` inside `db.start_transaction()` under
  `@retry_db_transaction` — so it is before the commit, not after it, and
  `dev/guidelines/backend/python.md` §"Best-effort side effects degrade to a safe fallback" does not
  apply: its third condition forbids straddling the point of no return and its preamble scopes it to
  an operation that has already succeeded. Raising rolls the tombstone back and the caller retries;
  swallowing would commit the orphan shape this feature exists to eliminate, with no
  operator-invocable repair.

## C3 — Enforcement-point contract

Every enforcement point owes three things and nothing more: a candidate selection, a timestamp, and
correct sequencing relative to its own writes. No enforcement point contains retention logic, and
none treats its own occurrence as a release trigger (FR-009).

| Point | Sequencing obligation |
|---|---|
| Node deletion | after the existence tombstone is written |
| Branch merge | after the bulk merge queries complete |
| Branch rebase | inside the existing `global_graph_lock`, before `user_branch.rebase` is applied |
| Branch deletion | before the branch's `IS_PART_OF` edges are removed — retention reads them |
| Schema removals | in the same statement as the removal itself |

## C4 — Repair migration

```text
minimum_version  = 77
GRAPH_VERSION    : 77 -> 78
```

**Guarantees**

- Closes the global edges of vertices no branch retains, including pre-existing half-closed shapes,
  and hard-deletes `Attribute` / `Relationship` vertices with no linked node vertex at all.
- Derives its stamp **per candidate** rather than using the run time: the owner's latest effective
  deletion time where one is derivable, otherwise the latest `to` among the vertex's closed owning
  edges — the moment the field stopped being reachable. Only where neither is derivable does it fall
  back to the upgrade's own time, and FR-014 still holds there: a candidate with no owner departure
  and no closed owning edge on record is one no branch resolves as live, so the close shifts no
  branch's view. Stamping everything with upgrade time *by default* would land the close inside the
  window of every branch forked before the upgrade, which FR-014 forbids.
- Batches its writes.
- Reports both counts to the upgrade log.
- Returns `MigrationResult(errors=[...])` on unrepairable state; never raises, never fails the
  upgrade (FR-016).
- Safe to re-run; a second run reports zero.
- Announces the irreversibility of the hard-delete before it begins.

**Non-guarantee**

- Does not delete `AttributeValue` vertices left with zero references.

**Blocked on**

- Nothing. The Ask-First migration gate (tasks T001) was signed off 2026-08-25 and the migration
  shipped as `m078_retire_agnostic_property_edges`.
