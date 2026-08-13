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

**Decision**: Extract a pure function that produces, for every open branch, the
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

**Decision**: One query class parameterised by a discriminated candidate bound — either an
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

## Resolved unknowns summary

| Unknown | Status |
|---|---|
| Branch-deletion candidate selectivity | Design fixed (R5); acceptance number measured during implementation against the FR-018 gate |
| Acceptable timing regression | ≤10% median per operation (pinned in spec FR-018 / SC-008) |
| Base-branch diff availability at rebase | Confirmed available (R4) |
| Migration template and non-fatal reporting | Confirmed via `m075` (R7) |
| Schema-removal leak mechanism | Confirmed by the shipped docstring (R8) |

No `NEEDS CLARIFICATION` markers remain.
