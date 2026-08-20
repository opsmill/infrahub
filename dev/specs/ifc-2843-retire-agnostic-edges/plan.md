# Implementation Plan: Retirement of branch-agnostic property edges

**Branch**: `retire-agnostic-edges-ifc-2843` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/ifc-2843-retire-agnostic-edges/spec.md`

## Summary

A branch-agnostic attribute or relationship on a branch-aware node keeps all of its property
edges on the global branch. Only one path closes them today (branch deletion, and only for
nodes that existed on no other branch); every other path leaks, accumulating reserved pool
values with no owner until uniqueness validation fails on UUIDs that resolve to nothing.

The fix is one invariant enforced at six points, plus a repair migration for the existing
backlog. One **shared Cypher predicate** owns the invariant; each enforcement point owns a query
that composes it and supplies only its own candidate selection, timestamp and batching. No new
persisted state, no API surface, no frontend surface.

Technical approach: deliver one enforcement point at a time, each with the tests that pin it,
starting with single-object deletion because it is the canonical case and settles the shared
predicate. Branch deletion carries the FR-018 timing risk and the repair migration is gated on
maintainer sign-off, so both come after the shape is proven.

## Design revision (2026-08-17)

The design this document originally described was replaced part-way through implementation, by
maintainer decision. Recorded here because much of what follows was written against the original and
the reasoning matters more than the diff.

**What changed.** A single query class served all six enforcement points and the migration, through
three swappable candidate bounds and two anchor modes, fed by pre-built branch windows from an
injected component behind a `Protocol`. It is now one shared retention fragment composed by a
separate query per enforcement point, with the branch windows derived inside Cypher.

**Why.**

1. *The migration and the runtime paths want different things.* The migration runs once and must
   cope with a wide set of broken states; the runtime paths can assume an attribute's owning and
   value edges are in sync, because they close both in one transaction. Serving both from one class
   meant three constructor guards whose only purpose was keeping the runtime path away from
   migration-only features, one dead predicate gate, and a triple-nested retention subquery.
2. *Marshalling branches through Python was a latent data-loss path.* The prescribed source,
   `Branch.get_list(db=db)`, paginates with a default limit of 1000; past that, missing windows turn
   retained fields into unretained ones with no signal. Deriving the windows in Cypher removes the
   failure mode rather than documenting it, and works when no registry has been populated. This
   reverses research R2 and a critique finding that had rejected the in-query read as unnecessary
   complexity — the complexity is real, and it is worth it.
3. *Retirement is not a best-effort side effect.* It runs inside the caller's still-open transaction,
   before the commit, so swallowing a failure commits the orphan shape this feature exists to
   eliminate. Failures propagate; the operation rolls back. See §"Retirement failure handling".
4. *Schema removals fold into the removal queries themselves* rather than calling a shared retirement
   afterwards, which also dissolves an ordering problem: after the removal query has closed the
   owning edge, an open-edge anchor can no longer see the candidate.

**What did not change.** The invariant, the enforcement points, the fork-window semantics, the
time-close-only rule, and the requirement that retention be judged per branch.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: Neo4j 2026.05 (driver 6.2), Pydantic 2.12 — no new dependencies

**Storage**: Neo4j graph. New graph migration `m076`; `GRAPH_VERSION` 75 → 76
(`backend/infrahub/core/graph/__init__.py:1`)

**Testing**: pytest 9.0 — unit (`backend/tests/unit/`), component
(`backend/tests/component/`, testcontainers), `pytest-benchmark` for the timing gate

**Target Platform**: Linux server (Infrahub backend)

**Project Type**: Backend-only change to an existing service. No frontend, no SDK.

**Performance Goals**: No median duration increase above 10% for node deletion, branch merge,
branch rebase, and branch deletion (FR-018 / SC-008)

**Constraints**: The predicate runs on the node-delete hot path, so it must be bounded by
candidate id or fork point — never an unbounded sweep outside the migration. Retirement is a
time-close (`SET e.to = ...`), never a `deleted`-status edge on the global branch (FR-013). The
predicate's filter grows linearly in the number of **open branches**, not in graph size, so
branch count is a first-class dimension of the FR-018 measurement.

**Scale/Scope**: ~8 modules touched, 1 new migration, 1 shared Cypher fragment, one query per
enforcement point.
Target branch `release-1.11`; reaches `develop` through the normal release merge.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Schema-Driven Integrity** | No schema-layer change. `m076` is a graph migration with no schema surface; no generated files affected. | ✅ Pass |
| **II. Branch-Safe by Default** | The feature *is* this principle. Cross-branch side effects on branch-agnostic data are the subject, explicitly documented (FR-019) and tested. Merge **and** rebase behaviour specified before completion (FR-006, FR-007). Every branch evaluated under its own filter with isolation intact (FR-012). Soft-delete governs all runtime paths — retirement is a time-close (FR-013). **One deviation**: `m076` hard-deletes vertices with no linked node. See Complexity Tracking. | ⚠️ Pass with justified deviation |
| **III. Type Safety & Explicit Contracts** | Query results exposed via `get_data()` returning a frozen dataclass, never raw Neo4j records. No API contract change. *(Revised: the branch-window dataclasses and the injected `Protocol` are gone — the windows are derived in Cypher and each query is self-sufficient.)* | ✅ Pass |
| **IV. Test Discipline** | Component coverage per enforcement point, migration fixtures per orphan shape, pure predicate logic unit-tested. Graph migration with no schema surface → the integration-Docker requirement for schema migrations does not apply. No frontend surface → no Playwright requirement. No mocks. *(Revised: with no injected collaborator there is no double to record; the predicate is exercised through component tests asserting graph shape, and each guarantee is mutation-checked.)* | ✅ Pass |
| **V. Query Performance & Efficiency** | Candidate sets diff- and query-bounded rather than swept; predicate anchored on graph labels so indexes apply; migration batched; all Cypher parameterised; `EXPLAIN` required on the new query. Uniqueness validation — on the merge/schema-check hot path and the active target of separate perf work — deliberately untouched. | ✅ Pass |
| **VI. Security & Input Boundaries** | No user input reaches the new Cypher; every parameter is internally derived (branch names, timestamps, node ids) and bound via `$param`. No new error messages exposed to users. | ✅ Pass |
| **VII. Simplicity & Maintainability** | One shared retention predicate — versus six hand-written closure rules that drift apart — composed by a query per enforcement point, so each call site reads on its own. The uniqueness post-filter is declined specifically to keep the mechanism count down. Follows the established Query-class pattern. | ✅ Pass |

**Post-implementation re-check (2026-08-17)**: the revised design introduces *fewer* abstractions
than the original — no component, no protocol, no adapter, no window types. The one shared artifact
is a Cypher fragment with a caller per enforcement point. Principle VII improves; Principle III is
narrower in scope but not weaker, since the typed boundary that mattered (`get_data()` returning a
frozen dataclass) is retained.

## Ask-First Gate

Per `AGENTS.md` **Boundaries → Ask First**, this feature crosses one gate that requires
maintainer sign-off before implementation begins:

- **Database schema or migration change** — `m076` plus a `GRAPH_VERSION` bump. It mutates
  existing customer data during upgrade, including **hard-deleting** `Attribute` and
  `Relationship` vertices that have no linked node vertex.

No other gate is crossed: no API/GraphQL/public-interface change, no new dependency, no CI/CD
workflow change, no auth change.

**Status (2026-08-17)**: sign-off requested; decision **deferred**, gate still open. The shared
predicate and the runtime enforcement points touch no migration and proceed. The repair migration
(`m076`, the `GRAPH_VERSION` bump, and the hard-delete) stays blocked until the gate is signed off.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2843-retire-agnostic-edges/
├── spec.md              # Phase 0 input (/speckit-specify output)
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output — internal component contracts
│   └── retirement-component.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/core/
├── graph/__init__.py                      # GRAPH_VERSION 75 → 76                    (edit)
├── query/
│   ├── agnostic_retention.py              # shared retention predicate fragment       (new)
│   ├── node_agnostic_retirement.py        # RetireNodeAgnosticFieldsQuery             (new)
│   └── branch.py                          # existing agnostic cleanup queries         (read)
├── node/__init__.py                        # Node.delete → invoke retirement          (edit)
├── branch/
│   ├── data_deleter.py                    # branch deletion → bounded form            (edit)
│   └── tasks.py                           # rebase_branch → base-branch deletions     (edit)
├── diff/merger/merger.py                  # merge → deleted-node candidates           (edit)
└── migrations/
    ├── graph/m076_retire_agnostic_property_edges.py                                   (new)
    ├── graph/__init__.py                  # register m076                             (edit)
    └── query/
        └── attribute_remove.py            # close the global edges in the same query  (edit)

backend/tests/component/
├── core/
│   └── test_agnostic_retirement.py        # enforcement-point behaviour               (new)
├── query/test_node_agnostic_retirement_query.py     # graph shape, per-query          (new)
└── migrations/test_m076_retire_agnostic_property_edges.py                             (new)

docs/docs/                                  # deletion semantics for agnostic fields   (edit)
changelog/                                  # towncrier fragment                       (new)
```

**Structure Decision**: Backend-only, following the existing `core/` layout. The new
`core/agnostic/` package holds the two components the PRD names; the query goes in the existing
`core/query/` package alongside `branch.py`, whose agnostic cleanup queries are the direct
precedent. No new top-level directory, no frontend or SDK path touched.

## Design Overview

### The invariant, restated as an implementation contract

```text
open(all global edges of V, owning edge included)  ⟺  ∃ branch B :  reachable(V, B)

where, for V an Attribute vertex:
    reachable(V, B) ≡ ∃ node n :  live(n, B) ∧ active(HAS_ATTRIBUTE(n → V), B)

and, for V a Relationship vertex:
    reachable(V, B) ≡ ∃ peers p₁, p₂ with distinct uuids :
                                         live(p₁, B) ∧ live(p₂, B)
                                       ∧ active(IS_RELATED(p₁ → V), B)
                                       ∧ active(IS_RELATED(p₂ → V), B)

and  live(n, B) ≡ n has an active IS_PART_OF edge under B's own branch-and-time
                  filter, with isolation applied
```

The two halves of `reachable` are conjoined **per branch and per node vertex**: the same vertex must
be live *and* hold the active edge, under the same branch's view. Satisfying one half on one branch
or vertex and the other half elsewhere is not reachability, and reading it as such strands the value.

`live` is evaluated **per node vertex**, since same-UUID copies produced by kind and inheritance
changes are distinct vertices carrying their own edges. Peers, however, are *counted* by uuid: two
copies of one object are one peer, so they cannot supply both ends of a relationship between them
(see `data-model.md`).

A relationship reaching one peer twice is not whole. Branch-agnostic self-referential relationships
are out of scope — the schema layer does not support them — and no accommodation is made for them.

### Prior art: the validated production remediation

The hand-written Cypher that unblocked the reported deployment (recorded on the ticket) is the
closest thing to a reference implementation, and this design deliberately reproduces its shape:

- closes the owning `HAS_ATTRIBUTE` edge **and** the property edges, each only where still open,
  using a subquery per group so a half-closed vertex is handled correctly;
- computes the owner's latest deletion time across every branch on which it was created or
  merged, and stamps that (matching FR-015);
- requires that **no** branch leaves the object still active before closing anything;
- batches with `IN TRANSACTIONS` explicitly to avoid exhausting the transaction memory pool.

It generalises that script in three ways: label-anchored rather than per-kind and
per-attribute-name, relationships as well as attributes, and the two-peer retention form.

### Component decomposition

> **Revised 2026-08-17.** This section previously described three units: a pure
> `AgnosticBranchWindowBuilder`, an injected `AgnosticFieldRetirer` behind a query `Protocol`, and one
> `RetireAgnosticPropertyEdgesQuery` parameterised by three candidate bounds and two anchor modes.
> None of them is being shipped. See §"Design revision" for why.

**One shared predicate, one query per enforcement point.**

1. **`UNRETAINED_AGNOSTIC_FIELD_PREDICATE`** (`core/query/agnostic_retention.py`) — a Cypher
   fragment, not a class. Given `field` rows in scope it emits the candidates no branch retains.
   Every enforcement point composes this same fragment, so the judgement exists in one place while
   the queries around it stay readable on their own.

   It derives the branch windows **inside Cypher** from `(:Branch)`. There is therefore no window
   builder and no branch list to marshal: `Branch.get_list(db=db)` paginates with a default limit,
   and a page limit quietly turns the branches past it into branches that retain nothing, which
   closes the very edges they were meant to keep. Reading `(:Branch)` removes that failure mode
   structurally and works in an upgrade process where no registry has been populated.

2. **One query per enforcement point**, each composing the fragment and differing only in candidate
   selection, stamp derivation and batching. Delivered so far:
   `RetireNodeAgnosticFieldsQuery` (`core/query/node_agnostic_retirement.py`) for node deletion —
   node-uuid anchored, one static Cypher body, caller-supplied `at`, no batching, no anchor
   parameter.

   The schema removals do not get a query of their own: their closure folds into the existing
   `AttributeRemoveQuery` and its relationship equivalent, which already match the right vertices
   for the kind and already carry the branch filter.

There is no retirement component and no protocol. The queries are self-sufficient, and each
enforcement point constructs the one it needs.

### Enforcement points and their candidate sets

| # | Point | Module | Candidate set | Timestamp | FR |
|---|---|---|---|---|---|
| 1 | Node deletion | `core/node/__init__.py` — after `NodeDeleteQuery` | the deleted node | `delete_at` | FR-005 |
| 2 | Branch merge | `core/diff/merger/merger.py` — after bulk merges | deleted nodes from the merge diff | merge `at` | FR-006 |
| 3 | Branch rebase | `core/branch/tasks.py` — inside `global_graph_lock`, before `user_branch.rebase` | deleted nodes from the **base-branch** diff | `rebase_at` | FR-007 |
| 4 | Branch deletion | `core/branch/data_deleter.py` — beside `_delete_agnostic_peers`, before `_delete_edges` | fork-point-bounded query | delete time | FR-008 |
| 5 | Attribute removal | `migrations/schema/node_attribute_remove.py` | the removed field | migration time | FR-010 |
| 6 | Relationship removal | `migrations/schema/node_relationship_remove.py` | the removed field | migration time | FR-010 |
| — | Repair migration | `migrations/graph/m076_*.py` | unbounded, batched | migration run time | FR-016 |

Points 2, 3 and 4 are **re-evaluation points, not release triggers** (FR-009). Each runs the
same predicate and acts only on its result; none of them may assume its own occurrence releases
anything.

Point 4 inherits the ordering constraint recorded in `data_deleter.py`: it must complete before
`_delete_edges` starts removing the branch's `IS_PART_OF` edges, because the reachability
determination reads them.

### Two decisions that are correctness dependencies, not preferences

**Candidate traversal starts from open, active global `HAS_ATTRIBUTE` / `IS_RELATED` edges at the
runtime enforcement points** (FR-011). Kind and inheritance migrations leave several node vertices
sharing one UUID, each with its own global edge to the *same* field vertex, the superseded one
closed as it is duplicated. Anchoring on open edges excludes superseded copies for free.
Traversing by reachability instead, while evaluating retention only from the node you arrived
from, would close a shared vertex's value edges and strip a live object's value — and the failure
would only surface after pre-migration branches were cleaned up, i.e. long after the change
shipped. This is why kind/inheritance migrations are deliberately *not* enforcement points.

**The repair migration widens that anchor, and moves the protection into the predicate**
(FR-011a). Pre-existing *half-closed* vertices — owning edge closed, property edges still open, or
the reverse — are unreachable from an open-edge anchor, and they exist in the reported data. The
migration therefore anchors on `status: "active"` regardless of `to`, and recovers same-UUID
protection from the predicate: a vertex is retained when **any** linked node vertex is live with an
active owning edge, which is what the invariant literally says. Safe there, and only there,
because the migration is batched and off every hot path.

**Retirement closes the owning edge too, not only the four property edges.** Two independent
reasons: the owning edge is part of what keeps the value looking live, and it is also the
candidate anchor — leaving it open would keep the vertex a candidate on every future pass
forever. The owning edge and the property edges are closed **independently**, each only where
still open (FR-002a), because existing data contains both mismatched states.

**A retirement failure propagates at every runtime enforcement point** (maintainer decision,
2026-08-17). An earlier revision of this plan called retirement a best-effort side effect governed by
`dev/guidelines/backend/python.md` §"Best-effort side effects degrade to a safe fallback", logged its
failures and swallowed them. That was implemented, and then removed, because the premise does not
survive contact with the call sites.

**Retirement runs before the commit, not after it.** The GraphQL delete runs `NodeManager.delete`
inside `async with db.start_transaction()`, under a mutation decorated `@retry_db_transaction`.
Retirement sits inside `Node.delete` — inside that still-open transaction, after the existence
tombstone is written but before anything is committed. So it does not run after an operation that
"has already committed"; it straddles the point of no return, which is exactly what the guideline's
third condition forbids: *do the best-effort work either fully before the point of no return or
fully after it, never straddling it.* The guideline's preamble narrows it further to a side effect
whose failure must not abort a primary operation **that has already succeeded**, and offers a cache
write and an observability emit as its examples. Retirement is not an optimization layered on the
delete; it is the invariant the delete exists to maintain.

**Leaving the global edges open is not a safe fallback at the delete point.** What each choice
actually commits:

- **Propagating** aborts the transaction, so the tombstone is never written either. The retry
  decorator absorbs the transient case; a persistent failure surfaces as a retryable, visible delete
  failure. The graph is never committed in the illegal shape.
- **Swallowing** commits a node that is gone still holding a live branch-agnostic value — precisely
  the orphan shape this feature exists to eliminate — and nothing a user or an operator can invoke
  repairs it, because `m076` runs only at upgrade. That is not "today's behaviour preserved"; it is
  today's bug re-introduced by the code written to fix it.

The runtime path can only work this way, which is worth stating because it looks like an
implementation detail. Neo4j forbids `CALL { … } IN TRANSACTIONS` inside an explicit transaction, so
the runtime adapter's `batch_size=None` is a requirement rather than a preference: retirement runs as
a participant in the caller's transaction, and that participation is what makes the rollback
available at all.

**One thing does still degrade rather than fail: an empty branch list defers retirement** and leaves
the global edges open, logged. That is a refusal to act on a degenerate input, not failure handling —
with no branch to read retention under there is no retention picture to judge, and over-reserving is
the safe direction, while closing on partial information is data loss. This is the "must
over-execute, not under-execute" rule applied to a reservation, and it is the only place it applies.

`m076` keeps its own non-fatal reporting (FR-016), and that is *not* the same principle applied
through a different mechanism: the migration has no caller transaction to roll back and no user
operation to abort, so accumulating into `MigrationResult` is simply the correct shape there.

**Every enforcement point logs what it did** — edges closed, and how many branches retain the
field when retirement is deferred. Without this, an operator cannot distinguish a correct
deferral from a fresh leak (they present identically: a value that will not free), and a future
refactor that breaks retirement would be invisible until a customer is stuck again — the same
blind spot that let this bug reach production. `BranchDataDeleter._delete_agnostic_peers` already
logs its edge count and is in one of the files being edited, so the shape is established.

**Retirement is a time-close, never a global status tombstone** (FR-013). Both are equally
correct when the predicate is right and fail in opposite directions when it is wrong. A missed
retaining branch under a time-close leaves that branch reading through its fork window —
degraded, no data loss, self-correcting on its next rebase. The same miss under a global status
tombstone strips the field from a live object immediately and everywhere. This is a deliberate
hedge against predicate bugs, not a correctness requirement. The degraded read it buys is worth a
test where it is actually reachable: only the repair migration closes edges a branch can still read,
since the runtime paths close only once no branch retains the field.

### Implementation sequencing (risk-first)

Revised 2026-08-17: one enforcement point at a time, each landing with the tests that pin it,
rather than a shared substrate followed by six integrations.

1. **Node deletion (point 1)** — the canonical two-axis case, one call site, transaction semantics
   already settled. It establishes the shared predicate, which the rest reuse unchanged.
2. Schema removals (points 5–6) — the analogue that proves the predicate generalises to the field
   axis, and self-contained because the closure folds into the existing removal queries.
3. Merge and rebase (points 2–3).
4. **Branch deletion (point 4) and its timing measurement.** It carries the entire FR-018 risk.
   Measure at **two open-branch counts** (a low one and a realistic-high one, e.g. 3 and 100),
   because the predicate's filter grows with branch count and a three-branch fixture is not
   evidence about a real deployment.
5. `m076` + `GRAPH_VERSION` bump, once the Ask-First gate is signed off.
6. Documentation + changelog.

`m076` is deliberately late despite being P1: it is the unbounded form of a query that must
already be proven correct, and it is the one step that mutates customer data.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Principle II** — `m076` hard-deletes `Attribute` / `Relationship` vertices with no linked node vertex, where the constitution permits hard-delete only for branch deletion itself | A vertex with no linked node cannot be reached, diffed, or time-travelled to. A time-close would leave permanent garbage with no reader, and would not remove it from any future scan. | Time-closing them instead: leaves unreachable vertices in the graph forever with no path to ever remove them. Mitigating factor: these vertices were *produced by* branch deletions predating the existing agnostic-peer cleanup, and `BranchDataDeleter._delete_agnostic_peers` already `DETACH DELETE`s exactly this shape at branch-deletion time. The migration completes an operation the system already performs — late rather than newly — so this is arguably inside the existing exemption rather than a new one. |

The original plan also tracked a `core/agnostic/` package holding a retirement component and a
window builder as a Principle VII deviation. That package is not part of the revised design and the
deviation no longer exists.

## Test plan additions

Beyond the tiers assigned in research R10, these tests exist because a reviewer asked what would
catch a specific silent failure:

- **Pool re-allocation** (component) — allocate, delete, allocate again, assert the same value comes
  back. Written, and it disproved the assumption behind it: re-allocation does not depend on
  retirement, because the ordinary delete already writes branch-scoped `deleted` edges that the pool's
  `branch_agnostic=True` filter honours. The test earns its place through its graph assertions rather
  than through SC-007. See data-model.md §"Pool interaction". Original reasoning follows:
  `NumberPoolGetUsed` requires `IS_RESERVED`, `HAS_VALUE` and
  `HAS_ATTRIBUTE` to *all* pass the branch filter, so closing `HAS_VALUE` drops the value from
  the used set — but by a three-edge interaction with the pool-side `IS_RESERVED` edge left
  untouched, which is subtle enough to break under an unrelated pool change with nothing to catch
  it.
- ~~**Branch created late**~~ — withdrawn 2026-08-18. It bounded the race between candidate selection
  and closure; those are now one Cypher statement in one transaction, so the window it guarded does not
  exist. The degraded-read property it also claimed to lock in is only reachable through the repair
  migration, which closes edges a branch can still read.
- **Branch-agnostic node no-op** (component, written) — deleting a truly branch-agnostic node is a
  retirement no-op, and for a reason the plan had wrong: the ordinary agnostic delete already both
  tombstones the global edges and stamps `to` on the superseded active ones, so nothing is left to
  close. The enforcement point does run against such nodes; it simply finds nothing.
- **`m076` re-run** (component) — running the migration twice is safe and the second run reports
  zero. An interrupted upgrade must be resumable, as `m075` is.

## Deferred decisions

- **Branch-deletion candidate selectivity number** — design is fixed (research R5); the measured
  number on a customer-sized graph is produced during implementation and judged against the
  FR-018 gate at both branch counts. Fallback if the gate fails: narrow the bound with the
  existence edge's `from` timestamp against the fork point.

### Resolved during critique

- **How the base-branch diff is obtained at rebase**: a second `DiffRepository` read under the
  existing tracking id. Widening `DiffCoordinator.update_branch_diff`'s return type to expose both
  diffs is the larger change and that method has other callers, so the read wins. No longer open —
  the rebase task is fully specified.
- **`m076` batching**: adopt the existing `MAX_AGNOSTIC_PEER_BATCH_SIZE = 500` cap. Each row can
  drag an unbounded number of peer vertices into the transaction, which is precisely why that cap
  exists in `data_deleter.py`. The migration must be safe to re-run.
- **`m076` irreversibility**: it hard-deletes vertices, and for those vertices there is nothing to
  roll back *to* — no rollback will be built. Instead, state the irreversibility in the upgrade
  documentation and in the migration's own console output before it begins, so the operator's
  pre-upgrade backup is an informed decision rather than an assumed one.

## Phase 1 artifacts

- [data-model.md](./data-model.md) — graph entities, edge states, the predicate's evaluation
  rules, and the orphan shapes `m076` repairs
- [contracts/retirement-component.md](./contracts/retirement-component.md) — internal component
  contracts (no external API surface exists for this feature)
- [quickstart.md](./quickstart.md) — runnable validation of every acceptance scenario
