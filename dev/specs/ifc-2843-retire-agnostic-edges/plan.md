# Implementation Plan: Retirement of branch-agnostic property edges

**Branch**: `retire-agnostic-edges-ifc-2843` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/ifc-2843-retire-agnostic-edges/spec.md`

## Summary

A branch-agnostic attribute or relationship on a branch-aware node keeps all of its property
edges on the global branch. Only one path closes them today (branch deletion, and only for
nodes that existed on no other branch); every other path leaks, accumulating reserved pool
values with no owner until uniqueness validation fails on UUIDs that resolve to nothing.

The fix is one invariant enforced at six points, plus a repair migration for the existing
backlog. A single **retirement component** owns the invariant; two **candidate-set producers**
feed it (diff-derived for merge and rebase, fork-point-bounded query for branch deletion); one
**query** implements candidate traversal, the retaining-branch predicate and the time-close in
one pass, with an unbounded form the migration reuses. No new persisted state, no API surface,
no frontend surface.

Technical approach, in the order risk resolves: build the pure branch-window set builder and
the query first (they are testable at the cheapest tiers), wire the branch-deletion path next
because it is the only enforcement point that gains a query the others do not and therefore
carries the whole performance risk, then the remaining five enforcement points, then `m076`,
then documentation.

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

**Scale/Scope**: ~8 modules touched, 1 new migration, 2 new core components, 1 new query class.
Target branch `release-1.11`; reaches `develop` through the normal release merge.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Verdict |
|---|---|---|
| **I. Schema-Driven Integrity** | No schema-layer change. `m076` is a graph migration with no schema surface; no generated files affected. | ✅ Pass |
| **II. Branch-Safe by Default** | The feature *is* this principle. Cross-branch side effects on branch-agnostic data are the subject, explicitly documented (FR-019) and tested. Merge **and** rebase behaviour specified before completion (FR-006, FR-007). Every branch evaluated under its own filter with isolation intact (FR-012). Soft-delete governs all runtime paths — retirement is a time-close (FR-013). **One deviation**: `m076` hard-deletes vertices with no linked node. See Complexity Tracking. | ⚠️ Pass with justified deviation |
| **III. Type Safety & Explicit Contracts** | Frozen dataclasses for the branch-window pairs and the retirement result; query results exposed via `get_data()` returning a frozen dataclass, never raw Neo4j records. Collaborator injected behind a `Protocol`. No API contract change. | ✅ Pass |
| **IV. Test Discipline** | Component coverage per enforcement point, migration fixtures per orphan shape, pure predicate logic unit-tested. Graph migration with no schema surface → the integration-Docker requirement for schema migrations does not apply. No frontend surface → no Playwright requirement. Recording double behind a protocol, no mocks. | ✅ Pass |
| **V. Query Performance & Efficiency** | Candidate sets diff- and query-bounded rather than swept; predicate anchored on graph labels so indexes apply; migration batched; all Cypher parameterised; `EXPLAIN` required on the new query. Uniqueness validation — on the merge/schema-check hot path and the active target of separate perf work — deliberately untouched. | ✅ Pass |
| **VI. Security & Input Boundaries** | No user input reaches the new Cypher; every parameter is internally derived (branch names, timestamps, node ids) and bound via `$param`. No new error messages exposed to users. | ✅ Pass |
| **VII. Simplicity & Maintainability** | One invariant, two candidate producers, one retirement mechanism — versus six hand-written closure rules that drift apart. The uniqueness post-filter is declined specifically to keep the mechanism count down. Follows the established Query-class and injected-collaborator patterns. | ✅ Pass |

**Post-Phase-1 re-check**: unchanged. The design introduces no abstraction beyond the two
components the PRD names, and both have ≥2 callers on delivery (the retirement component has
six; the query has three parameterisations). The `Protocol` around the query satisfies the
"interface to keep an out-of-domain dependency out" case in the component-design rule, and its
second implementation is the recording double the unit tests require.

## Ask-First Gate

Per `AGENTS.md` **Boundaries → Ask First**, this feature crosses one gate that requires
maintainer sign-off before implementation begins:

- **Database schema or migration change** — `m076` plus a `GRAPH_VERSION` bump. It mutates
  existing customer data during upgrade, including **hard-deleting** `Attribute` and
  `Relationship` vertices that have no linked node vertex.

No other gate is crossed: no API/GraphQL/public-interface change, no new dependency, no CI/CD
workflow change, no auth change.

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
├── agnostic/                                                                          (new)
│   ├── __init__.py
│   ├── branch_windows.py                  # pure branch-window set builder
│   └── retirement.py                      # retirement component + query Protocol
├── query/
│   ├── agnostic_retirement.py             # RetireAgnosticPropertyEdgesQuery          (new)
│   └── branch.py                          # existing agnostic cleanup queries         (read)
├── node/__init__.py                        # Node.delete → invoke retirement          (edit)
├── branch/
│   ├── data_deleter.py                    # branch deletion → bounded form            (edit)
│   └── tasks.py                           # rebase_branch → base-branch deletions     (edit)
├── diff/merger/merger.py                  # merge → deleted-node candidates           (edit)
└── migrations/
    ├── graph/m076_retire_agnostic_property_edges.py                                   (new)
    ├── graph/__init__.py                  # register m076                             (edit)
    └── schema/
        ├── node_attribute_remove.py       # invoke retirement                         (edit)
        └── node_relationship_remove.py    # invoke retirement                         (edit)

backend/tests/
├── unit/core/agnostic/
│   ├── test_branch_windows.py                                                         (new)
│   └── test_retirement.py                 # recording double, no DB                   (new)
└── component/
    ├── core/
    │   ├── test_agnostic_attribute_fork_window.py   # ADOPT existing untracked file
    │   └── test_agnostic_retirement.py    # enforcement-point behaviour               (new)
    ├── query/test_agnostic_retirement_query.py      # graph shape, two-peer form      (new)
    └── migrations/test_m076_retire_agnostic_property_edges.py                         (new)

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
    reachable(V, B) ≡ ∃ peers p₁, p₂ :  live(p₁, B) ∧ live(p₂, B)
                                       ∧ active(IS_RELATED(p₁ → V), B)
                                       ∧ active(IS_RELATED(p₂ → V), B)

and  live(n, B) ≡ n has an active IS_PART_OF edge under B's own branch-and-time
                  filter, with isolation applied
```

`live` is evaluated **per node vertex**, not per UUID — same-UUID copies produced by kind and
inheritance changes are distinct vertices and must be treated as such (see `data-model.md`).

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

Three units, each with a single reason to change:

1. **`AgnosticBranchWindowBuilder`** (`core/agnostic/branch_windows.py`) — pure. Takes the list
   of open branches plus a timestamp, returns the per-branch `(branch_names, timestamp)` pairs.
   Mirrors `Branch.get_branches_and_times_to_query_global` but for all branches at once. No
   database, no I/O. Unit-tested with hand-picked branch metadata.

   **The branch list is read from the database, never from `registry.branch`.** That registry is a
   per-worker dict filled lazily on `get_branch` and only ever pruned by
   `purge_inactive_branches`, so a branch created by another worker is simply absent from it.
   Using it as the predicate's source would omit a retaining branch and retire a live object's
   value — an FR-003 violation arriving as a distributed-worker race rather than a logic bug.
   Preferred shape: the retirement query matches `(:Branch)` vertices itself and computes the
   fork-window collapse in Cypher, which removes both the staleness window and a round-trip; the
   builder then serves the unit-testable pure form of that same collapse and the in-query path is
   verified against it. Fallback if the in-query join proves costly: `Branch.get_list(db=db)`
   under the enforcement point's existing transaction.

2. **`AgnosticFieldRetirer`** (`core/agnostic/retirement.py`) — the single entry point. Given a
   candidate bound and the retirement timestamp, evaluates the predicate and closes the global
   property edges of everything no branch retains. Takes its query collaborator through the
   constructor behind a `Protocol`, per the backend component-design rule; the recording double
   in the unit tests is its second implementation.

3. **`RetireAgnosticPropertyEdgesQuery`** (`core/query/agnostic_retirement.py`) — one Cypher
   body, three candidate bounds (node ids / fork point / unbounded) and two anchor modes
   (open-edge for runtime, widened for the migration). Candidate traversal, the retaining-branch
   predicate including the two-peer relationship form, and the time-close of both the owning edge
   and the property edges in a single pass.

The six enforcement points are the retirement component's only callers. They contribute a
candidate set and a timestamp; none of them contains predicate logic.

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

**Retirement is a best-effort side effect at every runtime enforcement point.** It runs after a
delete, merge, rebase or branch deletion has already committed. If it propagated, a graph hiccup
would fail user-facing deletes — a correctness regression FR-018 does not cover. If it were
swallowed bare, leaks would return silently and the feature's own failure would be undetectable.

Follow `dev/guidelines/backend/python.md` §"Best-effort side effects degrade to a safe fallback",
whose three conditions map directly:

- **Log the failure** — required anyway by the observability decision below.
- **Fall back safely** — the fallback is *leaving the global edges open*. That over-reserves,
  which is today's behaviour: a value stays reserved when it could have been freed. The opposite
  fallback — closing on partial information — is data loss. This is the "must over-execute, not
  under-execute" rule applied to a reservation.
- **Position it after the point of no return** — retirement runs fully after the primary
  operation's own writes, never straddling them.

`m076` keeps its own non-fatal reporting (FR-016): same principle, different mechanism, because a
migration reports through `MigrationResult` rather than through a log-and-continue.

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
hedge against predicate bugs, not a correctness requirement, and the existing fork-window test
file already encodes the degraded-read behaviour it buys.

### Implementation sequencing (risk-first)

1. Branch-window builder + query + component — cheapest tiers, and everything else depends on
   them.
2. **Branch deletion (point 4) and its timing measurement.** It is the only point that gains a
   query the others do not, so it carries the entire FR-018 risk. Measuring here first means a
   failed gate surfaces before five other integrations are built on the assumption it passes.
   Measure at **two open-branch counts** (a low one and a realistic-high one, e.g. 3 and 100),
   because the predicate's filter grows with branch count and a three-branch fixture is not
   evidence about a real deployment.
3. Node deletion, merge, rebase (points 1–3).
4. Schema-removal migrations (points 5–6).
5. `m076` + `GRAPH_VERSION` bump.
6. Documentation + changelog.

`m076` is deliberately late despite being P1: it is the unbounded form of a query that must
already be proven correct, and it is the one step that mutates customer data.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Principle II** — `m076` hard-deletes `Attribute` / `Relationship` vertices with no linked node vertex, where the constitution permits hard-delete only for branch deletion itself | A vertex with no linked node cannot be reached, diffed, or time-travelled to. A time-close would leave permanent garbage with no reader, and would not remove it from any future scan. | Time-closing them instead: leaves unreachable vertices in the graph forever with no path to ever remove them. Mitigating factor: these vertices were *produced by* branch deletions predating the existing agnostic-peer cleanup, and `BranchDataDeleter._delete_agnostic_peers` already `DETACH DELETE`s exactly this shape at branch-deletion time. The migration completes an operation the system already performs — late rather than newly — so this is arguably inside the existing exemption rather than a new one. |
| **New `core/agnostic/` package** for two components, where Principle VII asks that shared abstractions serve ≥2 callers before extraction | The retirement component has six callers on delivery (five enforcement points plus the migration); the query has three parameterisations. Both clear the bar at the moment they are introduced. | Inlining the predicate at each enforcement point: this is precisely the "six hand-written closure rules that drift apart" outcome the single-invariant design exists to avoid, and the leak being fixed was caused by exactly that drift. |

## Test plan additions

Beyond the tiers assigned in research R10, four tests exist because a reviewer asked what would
catch a specific silent failure:

- **Pool re-allocation** (component) — allocate, delete, retire, allocate again, assert the same
  value comes back. SC-007 and acceptance scenario 12 are otherwise unowned by any module in this
  plan. Verified as satisfiable: `NumberPoolGetUsed` requires `IS_RESERVED`, `HAS_VALUE` and
  `HAS_ATTRIBUTE` to *all* pass the branch filter, so closing `HAS_VALUE` drops the value from
  the used set — but by a three-edge interaction with the pool-side `IS_RESERVED` edge left
  untouched, which is subtle enough to break under an unrelated pool change with nothing to catch
  it.
- **Branch created late** (component) — create a branch after candidate selection and assert the
  object stays readable on it. Bounds the race window that survives even with the branch list
  read from the database, and locks in the degraded-read property that makes the time-close choice
  load-bearing rather than stylistic. Without it, a future switch to a status tombstone would pass
  every other test while silently removing the hedge.
- **Branch-agnostic node no-op** (component) — deleting a truly branch-agnostic node closes its
  edges exactly once and retirement is a no-op. `Node.delete` resolves `branch` to the global
  branch for such nodes, so the enforcement point *will* run against them; this pins the
  out-of-scope boundary the spec asserts must not regress.
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
