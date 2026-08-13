# Quickstart: Validating branch-agnostic property edge retirement

**Feature**: `specs/ifc-2843-retire-agnostic-edges` | **Date**: 2026-08-12

How to run and validate this feature. Every check below maps to a numbered acceptance scenario
in [spec.md](./spec.md).

## Prerequisites

```bash
uv sync --all-groups
```

Component tests need a Docker daemon (testcontainers), or an already-running database with
`INFRAHUB_USE_TEST_CONTAINERS=false`. Per project memory, the local dev containers are the
faster path for iteration.

## The fixture this feature is validated against

A branch-aware kind carrying a branch-agnostic attribute under a uniqueness constraint. This is
the minimum shape that reproduces the bug — one create/delete cycle is enough, which is why no
large dataset and no E2E scenario are needed.

```text
TestWidget          branch: aware
  name    Text      unique: true
  serial  Number    branch: agnostic
```

This fixture already exists in
`backend/tests/component/core/test_agnostic_attribute_fork_window.py` (currently untracked in
this tree — adopt it, do not rewrite it).

## The assertion that matters

Assert the **graph shape**, not the API response. The bug is a graph-shape bug that the API
hides: a leaked value is invisible through `NodeManager.get_one` and only surfaces later as a
uniqueness violation naming a UUID that resolves to nothing.

The canonical probe, already written in the fork-window test file:

```cypher
MATCH (n:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attribute_name})
MATCH (a)-[e:HAS_VALUE {branch: $global_branch, status: "active"}]->()
WHERE e.to IS NULL
RETURN count(DISTINCT e) AS count
```

`count = 0` after an unretained delete is the pass condition for SC-004. `count = 1` is the
pre-fix behaviour and is what the existing test currently asserts as the documented leak.

**The owning edge counts too.** SC-004 covers every open global edge of the vertex, not only the
value edge, so the probe above is incomplete on its own — pair it with:

```cypher
MATCH (n:Node {uuid: $node_id})-[e:HAS_ATTRIBUTE {branch: $global_branch, status: "active"}]->
      (:Attribute {name: $attribute_name})
WHERE e.to IS NULL
RETURN count(DISTINCT e) AS count
```

Leaving `HAS_ATTRIBUTE` open would also keep the vertex a candidate on every future pass, so a
second retirement run reporting a non-zero count is the symptom of having missed it.

## Run the tests

```bash
# Unit — pure predicate logic, no database, runs in seconds
uv run pytest backend/tests/unit/core/agnostic/

# Component — query graph shape, enforcement points, migration fixtures
uv run pytest -x -v backend/tests/component/core/test_agnostic_retirement.py
uv run pytest -x -v backend/tests/component/core/test_agnostic_attribute_fork_window.py
uv run pytest -x -v backend/tests/component/query/test_agnostic_retirement_query.py
uv run pytest -x -v backend/tests/component/migrations/test_m076_retire_agnostic_property_edges.py

# Everything for this feature
uv run pytest backend/tests/unit/core/agnostic/ backend/tests/component -k agnostic
```

## Validation matrix

### Enforcement (User Story 1)

| # | Scenario | Expected |
|---|---|---|
| 1 | Delete on default branch, no branch forked during the object's lifetime | Every global property edge carries `to`; uniqueness check for `V` reports no violation |
| 2 | Delete on branch `B` an object that exists only on `B` | Global edges closed immediately |
| 3 | Delete on `B` an object live on `B` and default; then delete on default | Stays open after the first; closed after the second |
| 4 | `B` forked between creation and deletion; delete on default | Stays **open**; value stays reserved; object still readable on `B` |
| 5 | From #4, empty the retaining set by (a) deleting on `B`, (b) rebasing `B` past the deletion, (c) merging `B`, (d) deleting `B` | Closed in all four cases |
| 6 | From #4, rebase or merge `B` but the object is still live on `B` afterwards | Stays **open** |
| 7 | Delete one peer of a branch-agnostic relationship so no branch has both peers live | Closed, even though the other peer survives |
| 8 | Remove a branch-agnostic attribute from the schema; likewise a relationship | Closed |
| 9 | Schema removal with a branch that forked beforehand | Deferred; field still readable on that branch |
| 10 | Kind or inheritance change, then run every enforcement point and the migration | Surviving vertex **keeps** its value |
| 11 | Create and delete on `B`, then rebase `B` | Invariant holds; no vertex left with open global edges |
| 12 | Value freed by retirement, then allocate from the pool | Value is allocatable again |

Scenarios **4, 6, 9 and 10 are the negative cases** — they are what a naive implementation
breaks, in the opposite direction from the positive ones. Treat a run in which only the positive
cases pass as a failed run.

Four further checks exist to catch specific silent failures:

| Check | Expected |
|---|---|
| Allocate → delete → retire → allocate again | The same value is returned (SC-007). Guards a three-edge pool dependency that no other test covers. |
| Create a branch *after* candidate selection | Object stays readable on the late branch — the bounded race window, and the property that makes the time-close choice load-bearing |
| Delete a truly branch-agnostic *node* | Edges closed exactly once; retirement is a no-op. Pins the out-of-scope boundary |
| Run `m076` twice | Second run reports zero; an interrupted upgrade is resumable |

### Repair migration (User Story 2)

| # | Fixture | Expected |
|---|---|---|
| 1 | Node with open global `HAS_VALUE` edges and no active existence edge on any branch | Edges carry `to`; count reported; a subsequent data-only proposed change validates clean |
| 2 | `Attribute` / `Relationship` vertex with no linked node vertex at all | Vertex hard-deleted; count reported |
| 3 | Two attributes sharing one `AttributeValue`, one orphaned | Orphan detached; surviving attribute keeps its value |
| 4 | State the migration cannot repair | Reported; **upgrade completes** |
| 5 | Half-closed: owning edge closed, property edges open (and the reverse) | Each fully closed and counted — reachable only via the widened anchor |
| 6 | Kind renamed, then the migration run with the widened anchor | Surviving vertex keeps its value — same-UUID protection now comes from the predicate, not the anchor |

Run the migration directly against hand-built fixtures rather than through a full upgrade — the
orphan shapes cannot be produced by the current code paths (that is the point of the migration),
so they must be built with raw Cypher.

⚠️ **`m076` is irreversible.** It hard-deletes `Attribute` / `Relationship` vertices that have no
linked node vertex, and for those vertices there is nothing to roll back *to*. The migration
announces this before it begins; operators need a pre-upgrade backup, and that must be an informed
decision rather than an assumed one.

## Performance gate (FR-018 / SC-008)

Required before the branch-deletion path is signed off. Report numbers, do not add a committed
suite.

```bash
uv run pytest backend/tests/query_benchmark -k "delete or merge or rebase"
```

Measure the pre-change build and the post-change build on the **same dataset**, at **two
open-branch counts**, and report median durations for all four operations:

| Operation | Branches | Before | After | Δ | Gate |
|---|---|---|---|---|---|
| Node deletion | 3 | | | | ≤ +10% |
| Node deletion | ~100 | | | | ≤ +10% |
| Branch merge | 3 | | | | ≤ +10% |
| Branch merge | ~100 | | | | ≤ +10% |
| Branch rebase | 3 | | | | ≤ +10% |
| Branch rebase | ~100 | | | | ≤ +10% |
| Branch deletion | 3 | | | | ≤ +10% |
| Branch deletion | ~100 | | | | ≤ +10% |

**Both rows are required.** The predicate's filter grows linearly in open-branch count (two
`(branch_set, timestamp)` pairs per branch), not in graph size, so a three-branch component
fixture is not evidence about a deployment with a hundred open branches. A gate passed only at the
low count has not been passed.

Branch deletion is the operation most at risk — it gains a query the other three do not. Also
record the `EXPLAIN` plan for the candidate traversal under each of its three bounds
(Principle V).

## Pre-push checks

```bash
uv run invoke format
uv run invoke lint
uv run invoke backend.test-unit
/pre-ci
```

`m076` bumps `GRAPH_VERSION`, so `uv run invoke docs.validate` must pass — CI fails on any stale
generated doc. A towncrier fragment under `changelog/` is required: freed pool values becoming
allocatable again is user-visible behaviour.

## Manual smoke check

The failure this fixes is reachable from a single create/delete cycle:

1. Define a branch-aware kind with a branch-agnostic attribute under a uniqueness constraint.
2. Create an object, note the allocated value, delete the object.
3. Create a second object requesting the same value.

**Before**: the second create fails with a uniqueness violation naming a node UUID that resolves
to nothing. **After**: it succeeds (SC-007).
