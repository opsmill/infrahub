# Phase 0 Research: Retirement of branch-agnostic property edges

**Feature**: `specs/ifc-2843-retire-agnostic-edges` | **Date**: 2026-08-12

All findings below are grounded in the `release-1.11` tree at `bc7a578cfa`. Line references
are indicative, not load-bearing.

## R1 — Where the existing agnostic cleanup lives, and what it proves

**Decision**: Model the new retirement component on `BranchDataDeleter._delete_agnostic_peers`,
and extend that same method rather than replacing it.

**Findings**: `backend/infrahub/core/branch/data_deleter.py` already performs a narrow version
of this feature. `DeleteBranchAgnosticRelationshipsQuery` and
`DeleteBranchAgnosticAttributesQuery` (`backend/infrahub/core/query/branch.py`) locate Nodes
whose only active `IS_PART_OF` edge is on the branch being deleted, then `DETACH DELETE` the
`Relationship` / `Attribute` vertices reached over a `{branch: $global_branch_name}` edge.

Three things this establishes for the plan:

1. **Hard-delete of agnostic peers at branch deletion is already the shipped behaviour.** The
   migration's hard-delete of vertices with no linked node is therefore not a new exception to
   the constitution's soft-delete rule (Principle II) — it completes an operation the system
   already performs, late rather than newly. This is the argument recorded in Complexity
   Tracking.
2. **The cleanup only covers branch-only Nodes** (`NOT EXISTS { ... ipo.branch <> $branch_name }`).
   Every other leak path is untouched, which is exactly the bug.
3. **Ordering constraint**: the agnostic cleanup must run *before* `_delete_edges` removes the
   branch's `IS_PART_OF` edges, because the branch-only determination reads them. The new
   fork-point-bounded predicate has the same dependency and must be sequenced identically.

**Alternatives considered**: A standalone sweeper task decoupled from branch deletion —
rejected, it would need persisted state (explicitly out of scope) and would leave a window in
which uniqueness validation still sees the orphans.

## R2 — The branch-window set builder already exists in prototype form

> **Superseded 2026-08-17.** No builder ships. The windows are derived inside the retention
> query from `(:Branch)`, because marshalling the branch list through Python meant a paginated
> read whose default limit silently turns the branches past it into branches that retain nothing.
> The `min(at, branched_from)` collapse this section identified is still exactly what the Cypher
> does — only its home changed. See plan.md §"Design revision".

**Decision (original)**: Extract a pure function that produces, for every open branch, the
`(frozenset[branch_names], timestamp)` pairs the predicate needs — mirroring
`Branch.get_branches_and_times_to_query_global`, but for *all* branches at once rather than
for the one branch being queried.

**Findings**: `Branch.get_branches_and_times_to_query_global(at, is_isolated=True)`
(`backend/infrahub/core/branch/models.py:280`) is exactly the per-branch shape needed:

```text
{frozenset((global, origin_branch)): min(at, branched_from),
 frozenset((global, self.name)): at}
```

The `min(at, branched_from)` collapse *is* the fork window. `is_isolated` defaults to `True`
and `Branch.is_isolated` is a field defaulting to `True`; `get_query_filter_path` exposes an
`is_isolated: bool = True` override and a `branch_agnostic: bool = False` bypass. FR-012
forbids using either escape hatch here.

The builder is a pure function of branch metadata (`name`, `origin_branch`, `branched_from`,
`is_isolated`, `is_default`) and a timestamp, with no database access — so it is the one piece
of the predicate unit-testable at the cheapest tier, satisfying the "pick the cheapest test
tier" rule.

**Alternatives considered**: Calling `get_branches_and_times_to_query_global` per branch inside
a loop and issuing one query per branch — rejected on Principle V (N+1 across every open
branch, on the node-delete hot path). The builder produces one parameter list consumed by a
single query.

## R3 — Two candidate-set producers, one query

> **Superseded 2026-08-17.** One query class serving every bound was replaced by one query per
> enforcement point, each composing a shared retention *fragment*. The finding below — that merge
> and rebase already name the affected nodes while branch deletion does not — survives intact and
> is why branch deletion still gets a query of its own shape.

**Decision (original)**: One query class parameterised by a discriminated candidate bound — either an
explicit list of node vertex ids / uuids, or a fork-point timestamp bound, or unbounded (the
migration). All three share the predicate and the closure clause.

**Findings**: The two producers exist for a structural reason, not a stylistic one:

- **Merge and rebase already compute the diffs** that name exactly the affected nodes.
  `DiffMerger.merge_graph` calls `diff_repository.get_affected_node_uuids(...)`
  (`repository.py:570`) before running the bulk merges. That is the merge candidate set.
- **Branch deletion has no diff.** Its candidate set is every node the discarded branch could
  reach, which is a fork-point-bounded query rather than an enumeration.
- **The migration is the same query with the bound removed.**

This is why FR-016 says the migration is "the unbounded form" — it is one Cypher body with a
swappable `MATCH` prefix, not three queries that must be kept in sync.

**Alternatives considered**: A single always-unbounded sweep invoked at every enforcement point
— rejected outright on Principle V; it would make every node delete scan the graph.

## R4 — Rebase has the base-branch diff it needs (resolves an FR-007 assumption)

**Decision**: FR-007 is implementable as specified. Retrieve the base-branch diff inside the
existing `lock.registry.global_graph_lock()` block in `rebase_branch`, before
`user_branch.rebase(...)` is applied, and pass `rebase_at` as the retirement timestamp.

**Findings**: `DiffCoordinator._update_diffs` returns an `enriched_diffs` pair carrying **both**
`diff_branch_diff` and `base_branch_diff` (`coordinator.py:291-292` shows both being written),
and both are persisted by `diff_repo.save(...)`. `rebase_branch`
(`backend/infrahub/core/branch/tasks.py:136`) only keeps the returned `diff_branch_diff`, but
the base-branch diff is retrievable from the repository under the same tracking id.

`rebase_at = enriched_diff_metadata.to_time` is already computed before the lock is taken and is
the timestamp the rebase itself uses — so FR-007's "the same timestamp the rebase uses" needs no
new plumbing.

**Risk**: the base-branch diff is retrieved by a second repository read rather than being handed
down from `update_branch_diff`. If that read proves awkward, the fallback is to widen
`update_branch_diff`'s return type to expose both diffs. Flagged as the one interface change
this feature may need.

**Alternatives considered**: Recomputing the base-branch deletions with a fresh query at rebase
time — rejected, it duplicates work already done and risks a different window than the rebase
actually closes.

## R5 — Branch-deletion selectivity (resolves the PRD's first open question)

**Decision**: Bound the branch-deletion candidate query by anchoring on **open, active global
`HAS_ATTRIBUTE` / `IS_RELATED` edges** (required anyway by FR-011) and intersecting with nodes
the discarded branch could reach via its `IS_PART_OF` edges, which the existing cleanup already
matches on. Do **not** scan every node carrying a branch-agnostic field.

**Findings**: The anchor is not merely a filter — FR-011 makes it a correctness requirement, and
it is also the most selective starting point available, because global `HAS_ATTRIBUTE` /
`IS_RELATED` edges exist *only* for branch-agnostic fields. A deployment with no branch-agnostic
fields matches zero rows.

The existing agnostic cleanup already traverses `(:Root)<-[e:IS_PART_OF {status:"active"}]-(n:Node)
WHERE e.branch = $branch_name`, and `DeleteBranchEdgesQuery`'s docstring records that naming the
edge type is what lets the `branch` **range index** be used. The same index serves here.

**Open measurement, deferred to implementation**: whether this is selective enough on a
customer-sized graph is an empirical question. It is *not* a design blocker — the design is
fixed; only the acceptance number is outstanding. The FR-018 gate (≤10% median) decides it, and
the documented fallback is to narrow further using the existence edge's `from` timestamp against
the fork point. `EXPLAIN` on the candidate query is a required step (Principle V) before the
branch-deletion path is signed off.

## R6 — Retirement timestamp (FR-015)

**Decision**: Stamp `to` with the owner's latest deletion time when one survives; use the
migration run time only when no deletion edge exists.

**Findings**: `NodeDeleteQuery` (`backend/infrahub/core/query/node.py:601`) writes the existence
tombstone at `$at`, so the deletion time is available at every runtime enforcement point without
a lookup. For the migration, the orphan shapes are precisely those with *no* surviving deletion
edge (branch-deletion orphans hard-deleted their `IS_PART_OF`), so migration run time is the only
available stamp — which is why FR-015 is worded as it is rather than as a preference.

Consequence for FR-014: stamping the deletion time (not "now") is what keeps retirement from
registering as a change on a branch that forked *before* the deletion, since the close falls
outside that branch's window.

**Correction (maintainer decision, 2026-08-17)**: the paragraph above is wrong about the
migration, and the query implements the corrected rule. The dominant orphan shape is a node
deleted on the default branch: its `IS_PART_OF` tombstone survives, so a deletion time *is*
derivable from the graph — per branch, `status: "deleted"` gives the edge's `from` and a set `to`
gives that `to`, and the latest of those across every branch and every linked node vertex is the
moment the field stopped being reachable anywhere. Only branch-deletion orphans have no existence
edge at all, and those have no linked node vertex either, so the migration hard-deletes the vertex
and the stamp is moot — which is why no run-time fallback is needed, and why a candidate whose
stamp cannot be derived is left open (over-reserving) instead. Deriving the stamp per candidate is
what keeps FR-014 intact on upgrade: stamping run time would land every close inside the window of
every branch forked before the upgrade, which is exactly what FR-014 forbids.

## R7 — Migration `m076` shape

**Decision**: `ArbitraryMigration` with `minimum_version: int = 75`, batching via
`IN TRANSACTIONS OF n ROWS`, reporting both counts through `get_migration_console()`, and
returning `MigrationResult(errors=[...])` **without raising** for unrepairable state.

**Findings**: `m075_finish_deleting_branches.py` is the direct template and is already the
"batched repair with graph-shape assertion" precedent the PRD names. It demonstrates every
required element: a read query to find work, per-item `try`/`except` so one failure does not
hide the rest, `console.log` progress reporting, and accumulating `errors` into the
`MigrationResult` rather than raising — exactly FR-016's "MUST NOT fail the upgrade".

`GRAPH_VERSION = 75` lives at `backend/infrahub/core/graph/__init__.py:1`; bumping it to 76 is a
one-line change. `MAX_AGNOSTIC_PEER_BATCH_SIZE = 500` in `data_deleter.py` is the precedent for
capping a batch whose rows each drag unbounded peers into the transaction — the same cap applies
here.

## R8 — Schema-removal migrations are already shaped for this

**Decision**: Invoke retirement from `NodeAttributeRemoveMigration` and
`NodeRelationshipRemoveMigration` after their existing queries run.

**Findings**: `NodeRelationshipRemoveMigrationQuery`'s docstring states the behaviour the PRD
predicted verbatim: *"An active edge created on the branch the migration runs on is closed in
place; an active edge inherited from a parent/global branch is left intact and shadowed by a new
`deleted` edge on the migration branch."* That inherited-and-shadowed global edge **is** the
leak. Retirement complements this rather than replacing it, confirming the spec's assumption.

`node_attribute_remove.py` is a thin 30-line wrapper over a shared `AttributeRemoveQuery`; the
relationship one is 13KB with a `RelationshipRemoveQueryParams` frozen dataclass. The attribute
side is the cheaper of the two to extend.

## R9 — Performance measurement (FR-018 / SC-008)

**Decision**: Measure with the existing `tests/query_benchmark/` harness (pytest-benchmark +
CodSpeed, per the constitution's Performance Standards), reporting before/after medians for the
four operations as numbers in the PR description — not as a new committed suite.

**Findings**: The spec pinned the threshold at ≤10% median increase. Node deletion, merge and
rebase all have existing exercised paths; branch deletion is the one carrying real risk, because
it gains a query that the other three do not (R5). Sequencing consequence: the branch-deletion
path (FR-008) should be implemented and measured **before** the remaining enforcement points are
polished, so a failed gate is discovered early rather than at the end.

## R10 — Test tier assignment

**Decision**: Follow the PRD's Testing Decisions exactly.

| Subject | Tier | Rationale |
|---|---|---|
| Branch-window set builder | Unit, no DB | Pure function of branch metadata (R2) |
| Retirement component | Unit, recording double behind a `Protocol` | Testing rule forbids mocks; `BranchDataDeleterInterface` is the in-repo precedent for the protocol shape |
| Retirement query (incl. two-peer form) | Component | Graph-shape assertions need a database |
| `m076` fixtures | Component | Hand-built orphan shapes |
| Enforcement points | Component (behaviour) | No separate unit suites per the PRD |

**Existing asset**: `backend/tests/component/core/test_agnostic_attribute_fork_window.py` is an
uncommitted working file in this tree that already builds the exact schema fixture (a
branch-aware `TestWidget` with an agnostic `serial` attribute), asserts the pre-fix leak
(`"deleting on the default branch is expected to leave the global value edge open today"`), and
stubs retirement with a `_close_global_property_edges` helper whose docstring says to replace it
once the real path exists. Its two fork-window tests cover the spec's fork-window edge case and
FR-013's degraded-but-no-data-loss argument. **Adopt this file**: swap the stub for the real
delete path and the assertions should hold unchanged. It is currently untracked and must be
committed as part of this feature.

## Query plans

> **Stale 2026-08-17.** The plans below were measured against the superseded single query class,
> before the retention predicate was flattened, the branch read moved into Cypher, the stamp
> derivation added and peer counting changed. They are kept as the record of the anchor-split
> analysis; they do not describe any query that currently exists. Principle V's `EXPLAIN`
> obligation is unmet for the current queries and is carried as an open task.


Principle V requires the candidate traversal to be planned, not assumed. All six combinations of the
three candidate bounds and the two anchor modes were planned against a live Neo4j
2026.05.0-enterprise instance (`bolt://localhost:7687`) in a throwaway database carrying the
production relationship and node indexes.

**Dataset**: 160,001 vertices, 160,000 edges, of which 65,000 are `HAS_ATTRIBUTE`. 25,000 of those
are global owning edges with `status: "active"` — 5,000 open (both anchors see them) and 20,000
closed (only the widened anchor sees them). The 4:1 closed-to-open ratio is the steady state a
deployment reaches once retirement has been running for a while, because every retirement moves one
edge from the open population to the closed one. The remaining 60,000 `HAS_ATTRIBUTE` edges are
branch-aware, so they exercise the anchor's ability to ignore non-agnostic traffic. Four branches are
in the window set. No `IS_RELATED` edges, so the relationship half of every plan reports one db hit.

**Method**: `EXPLAIN` on the full write form of each combination — `EXPLAIN` does not execute, so no
edge was closed — and `PROFILE` on a read-only truncation of the same query (everything above the
closing subquery: the candidate bound, the retention predicate and the stamp derivation, ending in
`RETURN count(field)`) to obtain real rows and db hits rather than estimates. Estimates alone would
not have supported a conclusion: Neo4j keeps no per-value statistics for relationship-property
indexes, so the seek on `anchor.branch` is estimated at the whole index (65,000) in every combination
regardless of anchor mode.

**The two unbounded combinations were re-measured on 2026-08-17**, after the unbounded form gained
its per-candidate stamp derivation and stopped matching the Cypher first recorded here. The dataset
was rebuilt from the same generator and reproduced identically (160,001 vertices, 65,000
`HAS_ATTRIBUTE` edges, 25,000 global owning edges of which 5,000 open), and all four bounded
combinations re-measured to the same seed rows, candidate counts and db-hit totals, so the two
unbounded rows are the only ones that moved. Nothing may be recorded until index statistics have
settled — the last finding below is why, and it invalidated a first attempt at this re-measurement.

| Bound | Anchor | Seed operator | Seed rows / db hits | Candidates | Unretained | Total db hits |
|---|---|---|---|---|---|---|
| Node ids | Open-edge | `NodeIndexSeek` `Node(uuid) WHERE uuid IN $node_uuids` | 2 / 4 | 1 | 0 | 121 |
| Node ids | Widened | `NodeIndexSeek` `Node(uuid) WHERE uuid IN $node_uuids` | 2 / 4 | 2 | 1 | 157 |
| Fork point | Open-edge | `UndirectedRelationshipIndexSeek` `HAS_ATTRIBUTE(branch)` | 50,000 / 25,001 | 0 | 0 | 150,002 |
| Fork point | Widened | `UndirectedRelationshipIndexSeek` `HAS_ATTRIBUTE(branch)` | 50,000 / 25,001 | 20,000 | 20,000 | 1,070,002 |
| Unbounded | Open-edge | `UndirectedRelationshipIndexSeek` `HAS_ATTRIBUTE(branch)` | 50,000 / 25,001 | 5,000 | 0 | 505,002 |
| Unbounded | Widened | `UndirectedRelationshipIndexSeek` `HAS_ATTRIBUTE(branch)` | 50,000 / 25,001 | 25,000 | 20,000 | 1,645,002 |

"Candidates" is the row count leaving `WITH DISTINCT field`; "unretained" is what survives the
retention predicate. Both bounds that traverse from the owning edge emit the seek's rows in both
orientations, which the label filter immediately halves. The fork-point bound finds no open-edge
candidate in this dataset by construction — its open population is live and never lost an existence
edge — which makes its 150,002 db hits a pure floor cost, paid before a single candidate is produced.

Findings:

- **No `AllNodesScan` and no `CartesianProduct` in any of the six plans.** Every plan is seeded by an
  index: a range seek on `Node(uuid)` for the explicit-ids bound, and a union of range seeks on
  `HAS_ATTRIBUTE(branch)` and `IS_RELATED(branch)` for the other two. The label anchoring required by
  FR-016 costs nothing at the seed — labels are checked in a filter directly above it.
- **Both anchor modes seed identically.** The anchor mode is one conjunct (`anchor.to IS NULL`) in the
  filter above the seed, so it changes how many rows survive, never how the traversal starts.
- **The stamp derivation is paid per unretained candidate, not per candidate.** It sits above the
  retention predicate, so it never touches a retained vertex. On the widened unbounded form its 20,000
  unretained rows cost 360,000 db hits (1,285,002 → 1,645,002, +28%), spent on two `Expand(All)` hops
  per row — field to linked node, linked node to its existence edges — plus one more expand inside the
  per-branch latest-edge subquery. No new seed operator and no `CartesianProduct`: the planner drives
  it with `Apply` off the already-bound `field`, and the existence lookups expand from `linked` rather
  than seeking `IS_PART_OF(branch)`. On the open-edge unbounded form it costs nothing at all, because
  nothing in this dataset reaches it.
- **The widened anchor is materially less selective, and the gap grows over time.** It carries 5x the
  candidates (25,000 against 5,000) and 3.3x the db hits on the unbounded bound, 7.1x on the fork-point
  bound. The extra candidates are exactly the already-retired and superseded vertices, a population
  that only ever grows: the open-edge anchor is self-limiting because closing the owning edge removes
  the vertex from the anchor permanently, while the widened anchor re-reads every vertex ever retired
  on every pass.
- **The retention predicate multiplies the candidate count by the window count.** The inner
  `linked, field, window_pairs` row count is 100,000 for the widened unbounded form against 20,000 for
  the open-edge one — candidates times four branches in both cases. This is the FR-018 growth-with-
  open-branch-count risk showing up in the plan, and it is why a larger candidate set is expensive
  rather than merely wider.
- **The explicit-ids bound is barely affected by the anchor mode** (121 against 157 db hits) because
  the uuid seek dominates. Whatever the runtime paths gain from the open-edge anchor, at the node-id-
  bounded ones it is not throughput.
- **The fork-point bound's seed is every global owning edge in the graph.** The fork point is applied
  above the seed, as an `IS_PART_OF` expand with `LIMIT 1` per anchor row, not as part of it. Its
  cost therefore tracks the total number of branch-agnostic fields rather than anything about the
  branch being deleted — 150,002 db hits even with the open-edge anchor. This is where the FR-018 gate
  (T020) will bite, and it is the measurement R5 left open.
- **A plan compiled before index sampling completes degrades.** Immediately after the dataset was
  loaded, the same six queries planned as full index scans (`WHERE branch IS NOT NULL`) with
  zero-row estimates throughout; they replanned into the seeks above once sampling caught up and the
  query caches were cleared. `m076` runs right after an upgrade, on exactly such a database, so the
  first pass may plan worse than the table shows. Reconfirmed on the 2026-08-17 re-measurement, which
  had to be discarded and re-run: the pass taken immediately after the reload seeded the node-id bound
  with a `NodeIndexScan` over all 25,000 indexed nodes instead of a two-key seek (25,114 db hits
  against 121, a 200x error on the cheapest bound) and the fork-point bound with a scan of all 65,000
  `HAS_ATTRIBUTE` edges. A measurement of this query is worthless until the seeds are seeks.

**Conclusion**: the split is justified, and the plans support confining the widened anchor to the
migration — but for a slightly different reason than the spec gives. The spec's reasoning is about
per-pass cost, and on per-pass cost alone the widened anchor would be defensible at the node-id-bounded
runtime paths (1.3x). What is not defensible is the trend: the widened anchor's candidate set is the
retired backlog, so a runtime path using it gets monotonically slower for the lifetime of the
deployment and never recovers, and the FR-018 gate would be re-broken by ordinary use rather than by a
code change. For the migration the same cost is a bounded one-off: 1.65 million db hits on a
160,000-vertex graph, batched at 500 rows per transaction, on a path that runs once per upgrade.
Acceptable there, not acceptable at runtime.

The per-candidate stamp derivation does not disturb that conclusion, and mildly reinforces it. It is
charged per *unretained* candidate, and the widened anchor's whole advantage in candidate count is
unretained vertices, so the derivation lands entirely on the migration side of the split: it widens
the unbounded gap from 2.5x to 3.3x and leaves all four runtime combinations at their recorded cost.

One correction to R5, on the evidence above: the anchor is selective *within* `HAS_ATTRIBUTE` but the
seek's cost is proportional to the number of global owning edges, not zero on a deployment with no
branch-agnostic fields at all — such a deployment matches zero rows only because the index seek finds
none, which is genuinely cheap, but a deployment with many branch-agnostic fields pays for all of them
on the fork-point bound regardless of which branch is being deleted. Narrowing that bound is the
recommended follow-up if T020's gate fails.

## R11 — An empty judging-branch set is deliberately unguarded

**Decision** (maintainer, 2026-08-17): add no guard. There is always a default branch, so the case
cannot arise.

**Findings**: once the branch windows are derived inside Cypher from `(:Branch)` rather than passed
in as a parameter, "no branches to judge with" stops being a caller mistake and becomes a statement
about the graph. The retention subquery seeds on `MATCH (branch:Branch) WHERE branch.name <>
$global_branch_name`; with zero rows the aggregation yields `NULL`, `coalesce(…, 0)` makes the live
count `0`, and every candidate is judged unretained. The failure direction is releasing values that
are still held, which is the corrupting one — scoped to the nodes named by the anchor rather than the
whole graph, but corrupting nonetheless.

Recorded because the equivalent shape *was* reachable in the earlier windows-as-parameter design and
was rated critical there. Note also that the obvious one-line guard does not work: the aggregation
collapses "no branch rows" and "branches exist but none retains" into the same `NULL`, and the second
is the normal close path — so a guard has to count judging branches separately rather than treat a
`NULL` maximum as retention.

## Resolved unknowns summary

| Unknown | Status |
|---|---|
| Branch-deletion candidate selectivity | Design fixed (R5); acceptance number measured during implementation against the FR-018 gate |
| Acceptable timing regression | ≤10% median per operation (pinned in spec FR-018 / SC-008) |
| Base-branch diff availability at rebase | Confirmed available (R4) |
| Migration template and non-fatal reporting | Confirmed via `m075` (R7) |
| Schema-removal leak mechanism | Confirmed by the shipped docstring (R8) |

No `NEEDS CLARIFICATION` markers remain.
