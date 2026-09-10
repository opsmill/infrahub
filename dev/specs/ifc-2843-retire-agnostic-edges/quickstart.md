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

## The assertion that matters

Assert the **graph shape**, not the API response. The bug is a graph-shape bug that the API
hides: a leaked value is invisible through `NodeManager.get_one` and only surfaces later as a
uniqueness violation naming a UUID that resolves to nothing.

The canonical probe:

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

Every suite is component-tier — the predicate is Cypher, so there is nothing to test without a
database.

```bash
# Enforcement points: node delete, merge, rebase, branch delete
uv run pytest -x -v backend/tests/component/core/agnostic_retirement/

# The query's own graph shape
uv run pytest -x -v backend/tests/component/query/test_node_agnostic_retirement_query.py

# Schema field removal
uv run pytest -x -v backend/tests/component/core/migrations/schema/test_agnostic_field_removal.py

# The repair migration
uv run pytest -x -v backend/tests/component/core/migrations/graph/m078_retire_agnostic_property_edges/

# Everything for this feature
uv run pytest \
  backend/tests/component/core/agnostic_retirement/ \
  backend/tests/component/query/test_node_agnostic_retirement_query.py \
  backend/tests/component/core/migrations/schema/test_agnostic_field_removal.py \
  backend/tests/component/core/migrations/graph/m078_retire_agnostic_property_edges/ \
  backend/tests/component/core/node/test_branch_agnostic_edges.py
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
| 12 | Delete the holder of an allocated value, then allocate from the pool | Value is allocatable again, and retirement has not stood in the way of it (per the amended SC-007, deletion frees it regardless) |

Scenarios **4, 6, 9 and 10 are the negative cases** — they are what a naive implementation
breaks, in the opposite direction from the positive ones. Treat a run in which only the positive
cases pass as a failed run.

Four further checks exist to catch specific silent failures:

| Check | Expected |
|---|---|
| Allocate → delete → allocate again | The same value is returned. Guards a three-edge pool dependency no other test covers — though re-allocation turns out not to depend on retirement; see data-model.md §"Pool interaction" |
| Delete a truly branch-agnostic *node* | Edges closed exactly once; retirement is a no-op. Pins the out-of-scope boundary |
| Run `m078` twice | Second run reports zero; an interrupted upgrade is resumable |

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

⚠️ **`m078` is irreversible.** It hard-deletes `Attribute` / `Relationship` vertices that have no
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
| Node deletion | 3 | 35.1 ms | 28.7 ms | −18.2% | ✅ ≤ +10% |
| Node deletion | ~100 | 31.7 ms | 31.0 ms | −2.2% | ✅ ≤ +10% |
| Branch merge | 3 | 220.6 ms | 164.2 ms | −25.5% | ✅ ≤ +10% |
| Branch merge | ~100 | 253.9 ms | 155.4 ms | −38.8% | ✅ ≤ +10% |
| Branch rebase | 3 | 1856.9 ms | 1181.1 ms | −36.4% | ✅ ≤ +10% |
| Branch rebase | ~100 | 2027.0 ms | 1408.9 ms | −30.5% | ✅ ≤ +10% |
| Branch deletion | 3 | 34.9 ms | 27.9 ms | −19.8% | ✅ ≤ +10% |
| Branch deletion | ~100 | 35.2 ms | 48.5 ms | **+37.6%** | ❌ **breached** |

Measured 2026-08-23 with `backend/tests/query_benchmark/test_fr018_agnostic_retirement_operations.py`
(an uncommitted harness, per the "report numbers, do not add a committed suite" rule above). Dataset:
250 branch-aware nodes each carrying one branch-agnostic attribute; operations timed end to end;
before = pre-feature commit `bc7a578cfa` in a separate worktree, after = the slice 1–4 tree. Two full
runs per build, **interleaved** (after, before, after, before) to cancel machine drift, giving 14–18
samples per cell; the medians above combine both runs.

**Noise floor**: whole-run medians drifted up to ±2× between consecutive runs, on both builds
equally, so single-run comparisons of these operations are not evidence. An earlier non-interleaved
session measured branch deletion at ~100 branches at 364 ms; three later re-measurements (30, 48,
63 ms medians) never reproduced it, and stage-level profiling of the retirement query at 100 open
branches puts its warm cost at ~7 ms (candidate seed 4.2 ms, retention predicate ~2 ms; a cold plan
compile is ~260 ms, paid once per plan-cache eviction).

**The breach at ~100 branches (+37.6%, ~+13 ms absolute)**: given the noise floor above, the timing
table alone does not establish this cell — a single +37.6% delta is the same order as the drift the
unchanged operations show. What establishes it is the stage profiling: the retirement query is the
one addition to the operation, its warm cost is measured directly at ~7 ms at 100 open branches
plus closure writes, and ~+13 ms on the ~35 ms baseline predicts the observed delta almost exactly.
The table corroborates rather than establishes: this is the only cell whose delta is positive, and
it is positive in **both** interleaved epochs (30.1 vs 25.2 ms, 63.1 vs 44.7 ms) while every
unchanged operation came out negative under identical conditions.

The baseline itself (~35 ms) comes from deleting **empty** branches; any branch carrying real data
raises it and dissolves the relative breach. The spec's prescribed fallback (fork-point narrowing
via the existence edge's `from`/`to`) is already built into the query. Decision pending: accept
with an absolute floor added to the gate (e.g. ≤ +10% or ≤ +25 ms, whichever is greater) or
optimize further. Until decided, R05 stays open.

**Both rows are required.** The predicate's filter grows linearly in open-branch count (two
`(branch_set, timestamp)` pairs per branch), not in graph size, so a three-branch component
fixture is not evidence about a deployment with a hundred open branches. A gate passed only at the
low count has not been passed.

Branch deletion is the operation most at risk — it gains a query the other three do not. The
`EXPLAIN` plans for the delivered queries are recorded in `research.md` under "Query plans
(delivered queries, 2026-08-31)" (Principle V).

## Memory footprint (Principle V, T059)

The FR-018 harness reports wall clock only, over small datasets, deleting one node per sample. Two
dimensions grow with the size of a real rebase or merge and neither is bounded by the batch size:
the uuid list the enforcement point holds before slicing it, and the candidate collection the query
cross-joins against every branch. `test_t059_agnostic_retirement_memory.py` measures both by running
the same operation at two deletion counts 4x apart — a footprint tracking the batch size stays flat,
one tracking the total grows with it. Ten background branches fork between the population and the
deletions, so every candidate is retained and the predicate does full work without pruning anything.

```bash
INFRAHUB_USE_TEST_CONTAINERS=false uv run pytest -s \
    backend/tests/query_benchmark/test_t059_agnostic_retirement_memory.py
```

Measured 2026-08-31, dev database, after clearing the harness's own leftovers between cells (stale
branches inflate the predicate and would make the two counts incomparable). RSS is sampled from
`/proc/self/statm` on a polling thread, so the peak is in-window; growth is peak minus the reading
taken as the operation starts, because the absolute peak also carries the resident population.

| Operation | Deletions | Batches | Duration | RSS at start | Peak RSS | RSS growth |
|---|---|---|---|---|---|---|
| Branch rebase | 600 | 2 | 21.1 s | 366.8 MB | 441.4 MB | **74.6 MB** |
| Branch rebase | 2,100 | 5 | 70.5 s | 378.9 MB | 556.4 MB | **177.5 MB** |
| Branch merge | 600 | 2 | 1.5 s | 457.4 MB | 457.4 MB | **0.0 MB** |
| Branch merge | 2,100 | 5 | 4.2 s | 536.8 MB | 536.8 MB | **0.0 MB** |

**Merge is flat.** No measurable growth at either count, and 3.5x the deletions costs 2.9x the time.

**Rebase grows with the total deletion count**, 74.6 → 177.5 MB. That figure is the whole rebase,
so a separate run wrapped the retirement call in its own sampler to find out how much of it is this
feature:

| Slice of a 2,100-deletion rebase | Duration | RSS growth |
|---|---|---|
| Whole rebase | 63,662.9 ms | 188.4 MB |
| Retirement only (2,100 candidates, 5 batches) | 768.7 ms | **2.0 MB** |

Retirement is **1.2% of the time and 1.1% of the memory**. The growth is the rebase's own diff
machinery, not the uuid list: 2,100 uuids is roughly 76 KB of strings, and even a million deletions
would be about 36 MB. Streaming them out of the diff repository — the remedy T059 proposed if the
process side turned out to grow — would therefore target a percent of the footprint and is not
worth doing. The database side is bounded as designed: one 500-uuid batch costs 35,632 db hits
(see the query plans in `research.md`), and the collected candidate list never exceeds one batch.

The residual, recorded so a future large-scale report has the reference: the uuid list is still held
whole, so it is linear in the deletion count. At the measured 2 MB per 2,100 deletions it is not
worth bounding, but it is not constant either.

Heap readings are taken before and after rather than sampled, and are dominated by GC — one merge
cell read 879.7 MB before and 332.9 MB after. They are not reported above because they measure the
JVM's collection schedule, not this feature.

## Pre-push checks

```bash
uv run invoke format
uv run invoke lint
uv run invoke backend.test-unit
/pre-ci
```

`m078` bumps `GRAPH_VERSION`, so `uv run invoke docs.validate` must pass — CI fails on any stale
generated doc. A towncrier fragment under `changelog/` is required, and it should cite the
uniqueness-validation failures the upgrade clears — *not* pool re-allocation, which SC-007 records
as already working without this feature.

## Manual smoke check

The failure this fixes is reachable from a single create/delete cycle:

1. Define a branch-aware kind with a branch-agnostic attribute under a uniqueness constraint.
2. Create an object, note the allocated value, delete the object.
3. Create a second object requesting the same value.

**Before**: the second create fails with a uniqueness violation naming a node UUID that resolves
to nothing. **After**: it succeeds.

Note this smoke check passes on the *uniqueness* path, which is what the feature fixes. Pool
re-allocation on its own already worked before the feature — see data-model.md §"Pool interaction".
