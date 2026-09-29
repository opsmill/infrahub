# Research: Numbers you give the pool

**Feature**: `specs/ifc-3184-pool-number-attach` | **Date**: 2026-09-16 |
**Verified against**: `origin/develop` @ `ea85f894f`

This document resolves the unknowns the spec left open and records the decisions the plan builds on.
Every code citation is `module::Symbol` — never a line number, per `dev/guidelines/documentation.md`.

---

## 0. Corrections to the source PRD

Five claims in `POOL-ASSIGNMENT-PRD.md` do not survive contact with the code. None of them change
what the feature must do; three change how it must be built. They are recorded here so the plan does
not inherit a false premise, and they are reported in `alignment-check.md` as **PRD errors**, not as
spec drift.

| # | PRD claim | Reality | Consequence |
|---|---|---|---|
| 1 | "Every number-pool read query joins `res.identifier = n.uuid`" (quoted from the P1 brief) | Only `NumberPoolGetUsed` and `NumberPoolGetFree` do. `NumberPoolGetAllocated` reaches the node through `HAS_SOURCE`; `NumberPoolGetReserved` never reaches the node; `NumberPoolGetTaken` never reads the edge. | The uuid-join removal is smaller than advertised, but `NumberPoolGetAllocated` is **bigger**: dropping the pool from `HAS_SOURCE` (FR-030b) removes its only path to the node, so it is a rewrite, not an edit. This is exactly why FR-030c exists — the PRD reaches the right conclusion from a wrong premise. |
| 2 | The multi-pool collapse survivor is "the most recent `from`, matching the rule `m066` uses for schema pools" | `m066_consolidate_duplicate_number_pools::Migration066._find_duplicate_groups` keeps the **earliest** (`ORDER BY created_at ASC`, `chronological_pool_ids[0]`; docstring: *"Keeps the earliest pool (by creation timestamp)"*). | The rule stands (most recent `from` is right for a *record*: the latest claim is the current one), but the justification is false. `m066` picks the oldest *pool vertex* because schema parameters already point at it — a different problem. Plan records the rule on its own merits. **Decision D7.** |
| 3 | "absent versus explicit-null are distinguishable at the GraphQL input layer (verified on the pinned graphene)" | True of the raw payload dict, and the **update** path already uses it (`BaseAttribute.from_graphql` tests `if "from_pool" in data`). The **create** path throws it away: `BaseAttribute.__init__` does `self.value = data.get("value")` / `self.from_pool = data.get("from_pool")`. | Carrying presence into the create path is real work the PRD does not scope. **Decision D3.** |
| 4 | Detach "ends the single `-global-` record"; re-pool "ends A's record and begins B's" | Nothing in the codebase has ever closed an `IS_RESERVED` edge except `PoolChangeReserved`, and `NumberPoolSetReserved` is a bare `CREATE`. There is also no lock on pool A during a write that names pool B: `lock_utils::get_lock_names_on_object_mutation` derives lock names from the *payload*, so it locks B only. | FR-024a/FR-024b need pool A's lock too, or the collapse races. The PRD does not mention this. **Decision D6.** |
| 5 | "`NumberPoolGetAllocated` gates every row on `hs_active = TRUE`, so a user-set source today removes an allocated number from the list while it stays reserved" | Confirmed, and worse than stated: the `hs_active` subquery is a **plain** (non-`OPTIONAL`) `CALL`, so a row with no qualifying `HAS_SOURCE` is dropped outright; and the subquery is branch- and time-unaware. | The PRD's diagnosis is right. Five existing component tests pin the current behaviour and must be rewritten with the query. **Decision D5.** |

| 6 | *Testing Decisions*: "existing pool-lifecycle coverage exercises the **branch-agnostic** attribute configuration. This slice targets **branch-aware** plain number attributes … A row marked covered is covered for one configuration, not both." | **Inverted.** `BaseNodeSchema.branch` defaults to `AWARE` and `AttributeSchema.branch` is `None` (inherited), so *every* number-pool test schema in the repo is branch-**aware** unless it opts out — and only two places do, neither of them a pool lifecycle test. All pool allocation/lifecycle coverage is already branch-aware. | The warning is still *correct in form* — one configuration is under-covered — but it points at the wrong one. The thin configuration is branch-**agnostic**. Re-aim the audit. **Decision D15.** |
| 7 | "the branch-merge suite under schema lifecycle" is listed as prior art for merge behaviour | `backend/tests/integration/schema_lifecycle/test_number_pool_branch_merge.py` **merges no branch**. Despite the filename, all three of its classes assert pool *identity* across branches. | Merge behaviour for pools is covered only by `test_number_pool_query.py::TestNumberPoolGetAllocated::test_NumberPoolGetAllocated_excludes_allocation_after_merging_cleared_source` and the agnostic-retirement merge module. The record-lifecycle "merge of a value change" row is a genuine gap, not an extension. |
| 8 | "A working exploratory repro exists and should be promoted rather than rewritten" | It exists **outside the repo**, in a previous session's `/tmp` scratchpad — not tracked, not stashed, not on any branch. It would not have survived temp cleanup. | Rescued to `artifacts/test_fr036a_repro.py` in this spec directory as part of planning. Promote from there. |

A ninth item is not a PRD error but a cross-slice contradiction: `POOL-RANGES-PRD.md` (P1) carries
**FR-030a / Decision 2** — "*The `source` slot is pool-owned for both provisioned and assigned
values, and users cannot clear it*" — which this slice's FR-030b/FR-030a-deletion directly reverses.

**Resolved 2026-09-16 by the PRD owner: P2 wins** — `source` can be cleared on pool-sourced
attributes, and P1's FR-030a / Decision 2 are superseded. No design change here; FR-030b/FR-030c were
already written this way. The remaining action is mechanical: delete FR-030a, Decision 2 and the
resolved open question #2 from `POOL-RANGES-PRD.md` before P1 enters spec-kit. Risks R2/R14 closed.

---

## 1. Where everything lives today

| Concern | Location |
|---|---|
| All pool Cypher (number + both IP shapes) | `core/query/resource_manager.py` |
| Number-pool node behaviour, allocation, lock | `core/node/resource_manager/number_pool.py::CoreNumberPool` |
| The `from_pool` entry point | `core/node/__init__.py::Node.handle_pool` |
| Create-side payload lift | `core/attribute.py::BaseAttribute.__init__` |
| Update-side payload lift | `core/attribute.py::BaseAttribute.from_graphql` |
| Lock-name derivation | `core/node/lock_utils.py::get_lock_names_on_object_mutation` |
| Utilization arithmetic | `pools/number.py::NumberUtilizationGetter` |
| Pool GraphQL read surface | `graphql/queries/resource_manager.py` (`PoolUtilization.resolve`, `resolve_number_pool_utilization`, `resolve_number_pool_allocation`, `PoolAllocated.resolve`) |
| Attribute `source` read path | `core/query/node.py::NodeListGetAttributeQuery._add_source_to_query` / `._include_source` |
| Cross-branch retention predicate | `core/query/agnostic_retention.py::UNRETAINED_AGNOSTIC_FIELD_PREDICATE` |
| Object conversion (sole `PoolChangeReserved` caller) | `core/convert_object_type/object_conversion.py` |
| Edge-type enum | `core/constants/database.py::DatabaseEdgeType.IS_RESERVED` |

`IS_RESERVED` has a remarkably small footprint: `core/query/resource_manager.py`,
`core/constants/database.py`, `m029_duplicates_cleanup.py`, `m066_consolidate_duplicate_number_pools.py`,
and two test helpers. It is **not** documented in `dev/knowledge/backend/database-schema.md` — that
file's edge-type table omits it entirely. Closing that gap is part of this work.

### The edge as it exists

```
(:CoreNumberPool {uuid})-[:IS_RESERVED {branch:"-global-", branch_level:1,
                                        status:"active", from:<ts>, identifier:<node uuid>}]
    -> (:AttributeValue:AttributeValueIndexed {value, is_default:false})   // MERGE'd, shared
```

Properties: `branch`, `branch_level`, `status`, `from`, `identifier`. That is all — no `to` at
creation, no `provenance`, no user ids. The only writer that ever sets `to` is `PoolChangeReserved`.
**Nothing anywhere sets `status = "deleted"` on an `IS_RESERVED` edge.**

The two IP shapes point at `:Node` (`BuiltinIPPrefix` / `BuiltinIPAddress`) and are written only
when an identifier is supplied, so an IP allocation without one leaves no edge at all.

### Liveness is inconsistent across the four read queries

| Query | Branch filter on `IS_RESERVED`? | `status` check on it? | Node join |
|---|---|---|---|
| `NumberPoolGetAllocated` | **No** — `ir` is absent from `all(r in [ha, hv, hs] …)` | **No** | via `HAS_SOURCE` |
| `NumberPoolGetReserved` | Yes | **No** | none (identifier equality only) |
| `NumberPoolGetUsed` | Yes | Yes (in the `is_active` conjunction) | `n.uuid = res.identifier` |
| `NumberPoolGetFree` | Yes | Yes | `n.uuid = res.identifier` |

A closed reservation edge therefore still satisfies `NumberPoolGetAllocated`. This is latent today
because nothing closes one; it becomes load-bearing the moment detach and re-pool do.

---

## 2. Decisions

### D1 — Re-anchor `IS_RESERVED` to the `Attribute` vertex

**Decision**: the edge becomes `(:CoreNumberPool)-[:IS_RESERVED {…, provenance}]->(:Attribute)`,
branch-agnostic as now. What it reserves is resolved forward through `HAS_VALUE`, per branch.

**Rationale** (the PRD's argument, verified):

1. It makes a value change a no-op for the ledger. Under value anchoring, "release the old number"
   is a `-global-` write answering a branch-scoped question, which cannot be made correct — the same
   scope mismatch that breaks detach. Anchored on the attribute, no ledger write happens at all.
2. It removes the uuid join from `NumberPoolGetUsed`/`GetFree`, and with it the duplicate-UUID
   hazard those two queries carry today with no guard (contrast
   `graph_traversal/_cypher.py::_SOURCE_MATCH`, which handles it explicitly).
3. It closes an `is_default` hazard: `AttributeValue` de-duplicates on `value` **and** `is_default`,
   so flipping that flag moves `HAS_VALUE` to a different vertex and silently orphans the record.
4. It inherits branch-agnostic retirement. Retirement's closing sweeps are **untyped and
   undirected** — `MATCH (field)-[e]-() WHERE e.branch = $global_branch_name …` in
   `core/query/node_agnostic_retirement.py`, `core/query/agnostic_field_closure.py`,
   `core/query/branch_agnostic_retirement.py` and m078 — so an edge incident on the `Attribute`
   vertex is swept automatically. Only the *anchoring* matches are typed
   (`HAS_ATTRIBUTE|IS_RELATED`), and those select candidate vertices, not edges to close.

**Alternative rejected** — *Option A: leave the anchor and extend retirement to close it.* It stops
the dead-edge leak and nothing else: it never fires for a branch-aware attribute (retirement acts on
global edges only, and a plain writable Number attribute is branch-aware by default, which is
exactly what FR-030 scopes this slice to), it leaves the value change unbuildable, and it fans out
over a globally shared value vertex before any identifier filter can apply.

**Known cost — an invariant is withdrawn.** Value anchoring enforces one-pool-per-attribute *by
accident*: pool A's record dies when the attribute's value moves away. Anchored on the attribute,
both records resolve forward to the same live value, so neither dies and pool A reports a number
pool B handed out. FR-024b restores the invariant by construction (D6). The same withdrawal is what
breaks object conversion (D8).

### D2 — Six queries rewritten, six left alone

Rewritten: `NumberPoolGetAllocated`, `NumberPoolGetReserved`, `NumberPoolGetUsed`,
`NumberPoolGetFree`, `NumberPoolSetReserved`, `PoolChangeReserved`.
Deleted by P1: `NumberPoolGetTaken` (FR-011).
Untouched: `IPAddressPoolGet/SetReserved`, `IPAddressPoolGetIdentifiers`,
`PrefixPoolGet/SetReserved`, `PrefixPoolGetIdentifiers`.

**`PoolChangeReserved` is the exception to "untouched"** and the PRD is right to flag it: it matches
`(pool:Node)-[r:IS_RESERVED]->(resource)` with both ends unlabelled, so it serves all three pool
shapes. It must branch on shape or be split. The claim "the six IP-pool queries are untouched" is
true only because `PoolChangeReserved` is not one of them.

### D3 — Carry payload *presence* into the create path

**Decision**: `BaseAttribute` records whether `value` and `from_pool` were present in the payload,
not just their values, and the intent resolver consumes the presence flags.

**Rationale**: the contract distinguishes three inputs — absent, explicit `null`, and a value — and
that distinction is what separates *no-op*, *detach* and *attach*. graphene preserves it in the
payload dict (graphql-core omits an unset field entirely; an explicit null lands as `key -> None`),
and `BaseAttribute.from_graphql` already relies on it with `if "from_pool" in data`. The create path
drops it in `BaseAttribute.__init__` (`data.get(...)`). Two fields are added alongside the existing
ones rather than changing their types, so nothing downstream that reads `attribute.value` or
`attribute.from_pool` changes.

**Precedent for the sentinel style**: `graphql/mutations/preferences.py::_Unset` — a typed enum
sentinel distinguishing "argument not provided" from explicit `null`, with the reasoning in its
docstring. That pattern works for top-level mutation *arguments*; for nested input objects,
dict-membership is the available mechanism and the one already in use.

**Caveat to carry into review**: `graphql/mutations/profile.py::InfrahubProfileMutation._validate_no_resource_pools_in_data`
carries a comment asserting the opposite — *"graphene InputObjectType may include keys with None
values for unset fields"*. Per graphene's `InputObjectTypeContainer` and graphql-core's
`coerce_input_value`, that is not true for these inputs: `setattr` populates attributes, not dict
keys. The comment is defensive but inaccurate, and a reviewer will read the new resolver against it.
Fix the comment in the same change.

### D4 — Extract `FromPoolIntentResolver` as pure decision logic

**Decision**: a pure module mapping `(value present?, value, from_pool present?, from_pool,
current tracking state)` → one intent: `allocate`, `attach`, `detach`, `re_pool_allocate`,
`re_pool_attach`, `discard_and_allocate`, `no_op`, or `refuse`. No database access, no node access.

**Rationale**: `Node.handle_pool` currently fuses seven concerns — template rejection, the
schema-`NumberPool` case, the user `from_pool` case, pool lookup by uuid *or* name (DB I/O), the
kind+attribute attachment check, allocation, and the `value`/`source` write-back — and it mutates
`attribute.from_pool` and `attribute.is_default` even on the preview pass that is supposed to have no
side effects. `from_pool` changes *meaning* without changing *shape*, so the decision table **is**
the contract (Constitution III); it has to be testable without a database.

**Boundary**: the resolver decides; `handle_pool` stays the executor and keeps the I/O. The
attachment check (FR-023) stays where it is — it needs the resolved pool node.

**Alternative rejected** — enrich `handle_pool` in place. It keeps a seven-branch decision table
reachable only through a database, which is how the current value-discard bug went unnoticed.

### D5 — The pool leaves `HAS_SOURCE`; `source` is derived

**Decision**: the pool is never written to `HAS_SOURCE`. `source` resolves to the user's edge when
one exists, and otherwise to the pool reached by the inbound `-global-` `IS_RESERVED` edge on the
same `Attribute` vertex.

**Why this is cheap**: `core/query/node.py::NodeListGetAttributeQuery._add_source_to_query` is
already a `CALL (a) { … }` subquery hanging off the very `Attribute` vertex the record is being
re-anchored to, and it is gated by `_include_source` (`MetadataOptions.SOURCE`), so it does not run
on reads that ask for no metadata. The addition is one `OPTIONAL MATCH` on an already-bound vertex
plus a `CASE`. No extra round trip, no N+1.

**Two concrete constraints the PRD does not state**:

1. The existing subquery matches **undirected and unlabelled** (`(a)-[rel_source:HAS_SOURCE]-(source)`),
   so nothing today constrains the peer to a `:Node` or to a kind — a `CoreNumberPool` already
   satisfies it, and `CoreNumberPool` is already declared a `LineageSource`
   (`core/schema/definitions/core/resource_pool.py`, mirrored in `core/protocols.py`).
2. Extraction reads `result.get_node("source").labels` to build
   `AttributeNodePropertyFromDB(uuid=…, labels=…)`, and those labels are what
   `graphql/types/interface.py::InfrahubInterface.resolve_type` later uses to pick the concrete
   GraphQL type. **The derived branch must return the pool vertex itself, not just its uuid**, or
   `__kind__` resolution breaks. This is the single most likely way to get D5 subtly wrong.

**Why it is required rather than nice-to-have**: detach cannot be made correct otherwise. Ending the
record is `-global-` and immediate; clearing a branch-aware `HAS_SOURCE` is branch-local. A detach on
a branch therefore left the default branch displaying a pool with no record behind it, and deleting
that branch made it permanent — detach's global write is destructive with nothing to heal it, unlike
allocation's, which self-heals through the liveness join.

**Accepted cost**: pool lineage leaves the diff. `HAS_SOURCE` is in
`core/diff/enricher/labels.py::PROPERTY_TYPES_WITH_LABELS` and is carried off `Attribute` vertices by
`core/diff/query/bulk_merge.py::BulkMergeAttributePropertyEdgesQuery`, so allocating or attaching on
a branch will show a value change with no accompanying source change. Changelog entry required.

**Incidental confirmation**: `BulkMergeAttributePropertyEdgesQuery` filters
`field.branch_support = "aware"`, so a `HAS_SOURCE` on a branch-*agnostic* attribute is never merged
at all — retirement is its only lifecycle path. That is orthogonal to this slice (FR-030 scopes it
to branch-aware attributes) but it explains why the existing agnostic-configured pool tests pass for
a different reason than the branch-aware ones will.

### D6 — Restore one-record-per-attribute by construction, and lock both pools

**Decision**: `NumberPoolSetReserved` becomes match-close-create — it closes any live record on the
target `Attribute` before creating its own. Additionally, `get_lock_names_on_object_mutation` must
contribute the lock of the pool **currently tracking** the attribute, not only the pool named in the
payload.

**Rationale for the lock half (new, not in the PRD)**: the invariant is enforced by a
close-then-create on the record, but the close touches pool A while the mutation holds only pool B's
lock (`RESOURCE_POOL_LOCK_NAMESPACE` keyed on the pool uuid, derived in `lock_utils` from the
payload's `from_pool.id`). Two concurrent re-pools of the same attribute into different pools would
each close the other's record and both create. Nothing today needs A's lock because nothing today
closes A's record.

**Cost**: the update path must read the attribute's current tracking pool before taking locks. The
update path already reads the node for uniqueness hashes
(`lock_utils::apply_payload_for_lock_names` "*the node itself is still read*"), so this is an extra
field on an existing read, not an extra round trip. The create path cannot be tracked by anything
yet, so it is unaffected.

**Alternative rejected** — a single global pool lock. It serialises all allocation across all pools
and is a much larger performance regression than the one FR-036a already forces.

### D7 — Migration survivor rule: most recent `from`

**Decision**: when the re-anchoring collapses several pools' records onto one `Attribute`, the
survivor is the record with the greatest `from`.

**Rationale on its own merits** (the PRD's `m066` justification is false — see §0): the record is a
claim, and the most recently made claim is the current one. The alternative — keep the earliest —
would make re-pooling silently revert to the original pool for any pre-upgrade object that had been
re-pooled by the old overwrite-the-source path.

`m066`'s earliest-wins rule answers a different question (which *pool vertex* survives dedup) and is
driven by schema parameters already pointing at the original.

### D8 — Object conversion re-targets the edge, not the identifier

**Decision**: `PoolChangeReserved` re-targets the **edge** to the new node's `Attribute` vertex,
matched by the pool's `node_attribute`, and branches on pool shape (the IP shapes keep re-pointing
at the same `:Node` resource and only relabel the identifier).

**Confirmed defect, verified on `develop`**: the query matches
`(pool:Node)-[r:IS_RESERVED]->(resource)` untyped, does `SET r.to = $at` and
`CREATE (pool)-[new_rel:IS_RESERVED $rel_prop]->(resource)` — re-creating against the *same*
`resource`. Its only caller, `core/convert_object_type/object_conversion.py`, has already run
`create_node`, so post-move the new object has its own `Attribute` vertex and the record points at
the abandoned one: the liveness join fails and the pool frees a number the converted object still
holds. On a non-unique attribute it hands that number to someone else; on a unique one the next save
fails.

**The existing test will not catch it.** `test_convert_number_pool` (in
`backend/tests/functional/convert_object_type/test_convert_object_type.py`) asserts through
`NumberPoolGetReserved`, which has no liveness join — it proves the edge exists, not that it points
anywhere real. Rewrite it to assert the value the pool *reports*. Note it exercises a schema-defined
`NumberPool` attribute, which FR-030 excludes from the feature but which the migration still
rewrites.

### D9 — FR-036a: reuse the retention predicate's shape, do not re-derive it

**Decision**: liveness becomes a per-branch resolution with a disjunction across branches, built on
the shape of `core/query/agnostic_retention.py::UNRETAINED_AGNOSTIC_FIELD_PREDICATE`.

That predicate already states the exact contract in its module docstring: *"Retention is decided per
branch **and** per linked vertex … Surviving edges are summed per branch, and only then is the
maximum taken across branches. Retention is a disjunction of what each branch holds live on its own,
never a pool the branches contribute to jointly."* Its mechanics transfer directly:

- each branch's window is `(branch @ $at) ∪ (origin_branch @ min(branched_from, $at)) ∪ (-global- @ $at)`;
- per-branch resolution is `ORDER BY branch_level DESC, from DESC, status ASC LIMIT 1` — the
  standard tie-break from `dev/knowledge/backend/database-schema.md`;
- `branch.status <> "DELETING"` excludes branches mid-delete;
- `count(DISTINCT … node.uuid)` is the duplicate-UUID guard;
- `max(…)` across branches is the disjunction.

**Amended 2026-09-18 — this decision was not carried out, and the contract it borrows is met without
it.** The shipped read has no branch filter, which is what makes it a disjunction: a value counts
while any branch holds it because nothing narrows the match to one branch. None of the four
mechanics above appear in the query. The retention predicate needs them because it resolves whether
a *field* is retained, reading backwards from the linked vertex; this read resolves which *values*
an attribute holds, reading forward from a `-global-` record through `HAS_VALUE`, and the forward
direction leaves nothing per-branch to resolve. The `DELETING` exclusion is kept.

**It is a new predicate, not a call to the existing one.** The existing one resolves whether a
*field* is retained (node existence + `HAS_ATTRIBUTE`); FR-036a needs whether a *value* is held
(node existence + `HAS_ATTRIBUTE` + `HAS_VALUE`, returning the resolved value per branch). Only the
shape is reused. The PRD's "may reduce to reusing that predicate's shape rather than deriving a
second copy of the same branch logic" is the right expectation, and the honest answer is: the shape,
yes; the query, no.

**Why the current code is wrong**: `NumberPoolGetUsed`/`GetFree` resolve liveness with a single
`ORDER BY … LIMIT 1` across *all* branches' edges at once, so a deleting branch's tombstoned
`HAS_ATTRIBUTE` — the highest `branch_level` — wins and marks the chain inactive everywhere. A value
change on a branch does not trigger it, because that writes a new value edge without tombstoning the
default branch's. This matches the PRD's reproduction exactly.

**Sequencing**: written *after* the re-anchoring, against the post-move edge chain. Writing it first
means writing it twice.

**Performance**: this is the slice's one real risk. Per-branch resolution multiplies edge resolution
by live branch count inside `get_resource`'s pool-wide lock (`RESOURCE_POOL_LOCK_NAMESPACE`, keyed on
the pool uuid). No numeric gate — SC-017 is withdrawn for want of evidence to calibrate one — but a
benchmark is mandatory and a superlinear curve is a release decision. See D12.

### D10 — Utilization arithmetic moves to a pure module, and today's distinct-counting is preserved

**Decision**: `PoolUtilizationReporter` (pure, no database) takes a record set and an effective
space and returns the distinct-element count, the branch split, and the out-of-space bucket.
`NumberUtilizationGetter` is reduced to a fetch-and-delegate seam.

**What must be preserved**: today's distinct-counting is an emergent property of three lines in
`pools/number.py::NumberUtilizationGetter.load_data` —

```python
self.used_default_branch = {entry.number for entry in self.used if entry.branch == registry.default_branch}
used_branches = {entry.number for entry in self.used if entry.branch != registry.default_branch}
self.used_branches = used_branches - self.used_default_branch
```

— i.e. the two sets partition a distinct union, so a number held on both the default branch and
another is counted once. FR-028a makes this an explicit invariant. Counting rows instead would let
utilization exceed 100%. This is also the handoff note to P1, whose read-query rewrite replaces this
code.

**Known defect inherited but not owned**: `NumberUtilizationGetter.total_pool_size` divides by
`end_range - start_range + 1 - get_attribute_nb_excluded_values()`, and
`CoreNumberPool.get_attribute_nb_excluded_values` sums *every* excluded value with no intersection
against the pool's span — so an attribute excluding `500-600` under a pool over `100–200` yields
`total_pool_size = 0` and a `ZeroDivisionError`. **P1 owns this** (its effective-space rule fixes
it). This slice must not paper over it: `PoolUtilizationReporter` takes the effective space as an
input and does not compute it.

### D11 — Consume P1's effective-space calculator through a seam; do not reimplement, do not block on it

**Decision**: `PoolUtilizationReporter` and the out-of-space partition depend on a narrow
membership interface — "is this value inside the pool's effective space?" plus "how many elements
does the effective space contain?" — defined in `contracts/effective-space.md`. P1 supplies the
implementation. Until it lands, a single-range adapter over today's `start_range`/`end_range` ∩
`[min_value, max_value]` satisfies the same interface.

**Rationale**: P1 has no spec directory yet — `POOL-RANGES-PRD.md` is still an *Idea Brief* with an
open `[NEEDS CLARIFICATION]` on zero-range pools. Making this slice's design wait on P1's
implementation would stall the foundational work, which is the item that most needs to merge early
(SC-022). Making it *reimplement* membership would violate the spec's explicit prohibition and
create the fourth disagreeing copy of exclusion arithmetic (P1's brief already counts three).

**This is a seam, not a fork**: the adapter is deleted when P1 lands, and the interface is the thing
P1 must satisfy. Recorded as a hard dependency in the plan's Risks.

### D12 — Benchmark instead of a latency threshold

**Decision**: benchmark allocation against `develop` before and after D9, varying live branch count,
and review the curve. No numeric gate.

**Rationale**: SC-017 was withdrawn in the PRD because the repo has no evidence for a realistic
live-branch ceiling and `tasks/performance.py` is not parameterised on branch count, which left an
invented constant carrying the whole criterion. The obligation is real; the threshold was not
defensible. A superlinear curve, or a large constant from nesting per-branch resolution inside a
query that already fans out over records, is a release decision.

### D13 — Migration shape: `ArbitraryMigration`, package form, four behaviours, counts to the console

**Decision**: `m079_reanchor_number_pool_reservations/` as a **package** (`__init__.py` +
`migration.py` + `queries.py`), exporting `Migration079`, `minimum_version = 78`; `GRAPH_VERSION`
bumps to `79`.

**Mechanics confirmed**:

- Registration is filename-driven — `core/migrations/graph/discovery.py::discover_migrations` matches
  `m(\d{3})_.+\.py` or a package `m(\d{3})_[^.]+/` and requires the class `Migration{NNN:03d}`.
  **There is no registry list to edit**, and a duplicate number hard-fails at import.
- `m076` and `m078` are the package-form precedents.
- `ArbitraryMigration` (not `GraphMigration`) because the four behaviours are sequenced with
  reporting between them; `GraphMigration` runs a flat query list in one implicit transaction.
- **Counts reach an operator only through `migration_input.console.log(...)`.**
  `MigrationResult.nbr_migrations_executed` is accumulated but `cli/db.py::migrate_database` never
  prints it. m078 is the template: `result.nbr_migrations_executed += edges_closed` *and*
  `console.log(f"Closed {edges_closed} …")`. Its component tests assert on the console string.
- `validate_migration` should re-run a read query and turn leftovers into `result.errors`, following
  `m077_delete_orphaned_account_children::Migration077.validate_migration`.
- **Known `ArbitraryMigration` hazard to avoid**: `m066::Migration066.execute` carries the comment
  *"returning here from inside the transaction context means that context sees no exception and
  commits, so a mid-loop failure can persist partial consolidation."* Do not repeat that shape.

**Duplicate-UUID resolution**: there is no shared helper. The canonical, best-documented idiom is
`graph_traversal/_cypher.py::_SOURCE_MATCH` — take each candidate vertex's latest `IS_PART_OF`
*without* pre-filtering on status, then keep it only if that latest edge is `active`, then
`ORDER BY branch_level DESC, from DESC LIMIT 1`. Copy that shape; do not invent a variant.

**Re-anchoring idiom**: `m066::Migration066._reassign_has_source` is the precedent —
`CREATE … SET new = properties(old) … DELETE old`, which preserves `branch`/`branch_level`/`from`/
`to`/`status` including `-global-`. That is a *hard* re-anchor with no history, which is correct
here: the record's history is not user-visible and a time-closed old edge would be read by
`NumberPoolGetAllocated`, which does not check `status` (§1).

### D14 — Fix the attribute-rename `-global-` bug by porting the existing `CASE`

**Confirmed**: `core/migrations/query/attribute_rename.py::AttributeRenameQuery.query_init` copies
every edge of the old attribute onto the new one with
`CREATE (new_attr)-[:$(type(r)) $rel_props_create]->(peer_node)`, where `$rel_props_create` is built
unconditionally from the migration branch (`"branch": self.branch.name`). There is **no**
`CASE WHEN r.branch = "-global-"` anywhere in that module, and the teardown closes only
`WHERE r.branch = $branch_name`.

**The fix exists elsewhere in the tree**:
`core/migrations/query/node_duplicate.py::NodeDuplicateQuery._render_sub_query_per_rel_type` does
`SET new_active_edge.branch = CASE WHEN {rel}.branch = "-global-" THEN "-global-" ELSE $branch END`
(and the same for `branch_level`), with `$rel_props_new`/`$rel_props_prev` deliberately omitting
`branch`/`branch_level`; its close uses `WHERE rel.branch IN ["-global-", $branch]`.
`node_remove.py` uses the same convention. Port it.

**Why it matters more after D5**: the record is the sole storage of the pool's claim, so relocating
the ledger edge onto a branch makes it invisible to a derivation that matches only `-global-` edges
— the attribute then reports **no source at all** while the ledger still holds the number reserved.

**Attribute removal needs no fix**: `core/migrations/query/attribute_remove.py::AttributeRemoveQuery`
already ends with `%(close_unretained_agnostic_fields)s`, so a removed attribute's global edges —
including the re-anchored record — are closed. This is the PRD's "likely a win", confirmed.

### D15 — Coverage audit result: what exists, what is genuinely missing

The spec's instruction was "audit existing coverage before writing anything". Done. The result
changes what needs writing.

**Already covered — extend, do not duplicate:**

| Lifecycle row | Existing test |
|---|---|
| Two branches allocate from one pool | `functional/pools/test_numberpool_branch.py::TestAttributeNumberPoolLifecycle::test_numberpool_assign_in_branch` (main `[1,2,3,7,8,9]`, branch2 `[1,2,3,4,5,6]`); also `integration/schema_lifecycle/test_number_pool_branch_merge.py::TestNumberPoolSingleInstanceAcrossBranches::test_instances_have_unique_values` and `component/core/resource_manager/test_number_pool_query.py::TestNumberPoolGetUsed::test_NumberPoolGetUsed` |
| Branch deleted → numbers reclaimed | `test_numberpool_branch.py::…::test_numberpool_branch_delete` |
| Object deleted → number reclaimed | `test_numberpool_branch.py::…::test_numberpool_node_delete`; `component/core/resource_manager/test_number_pool.py` |
| Allocation over pre-existing nodes | `functional/pools/test_numberpool_lifecycle.py::TestAttributeNumberPoolLifecycle::test_numberpool_existing_nodes` |
| Value freed by retirement is allocatable again | `component/core/agnostic_retirement/test_on_node_delete.py::TestAgnosticRetirementOnDelete::test_a_value_freed_by_retirement_is_allocatable_again_from_its_pool` — **asserts the exact edge tuple `("IS_RESERVED", GLOBAL_BRANCH_NAME, "active", None)` and calls `pool_reservation_edges`, so it breaks on the re-anchoring and must be updated in the same change** |
| `hs_active` / source-clear semantics | five tests in `test_number_pool_query.py::TestNumberPoolGetAllocated` — **all five are pinned to behaviour FR-030c deletes; they are rewritten, not kept** |

**Genuinely missing — new tests:**

1. A branch-level **value change** on a pooled attribute. No test in the repo. This is both the
   FR-031 no-ledger-write assertion and the FR-036a "must stay working" regression.
2. Deleting an object on a branch while another holds it, asserted through
   `get_used`/`get_free`/**actual reallocation**. `test_NumberPoolGetAllocated_includes_allocation_active_on_other_branch`
   covers the *query* on branch2 but never the allocation, which is where the collision is.
3. A **user-set, non-pool** `source` on a pooled attribute. No test sets an account or repository as
   the source of a pooled attribute, and none asserts what the `source` slot resolves to for display.
   This is all of SC-019.
4. Re-pool A→B; detach; duplicates under one pool; out-of-space bucket; the branch-straddling row.
   All new — the capability does not exist.
5. The migration's four behaviours.

**Two helpers must change with the edge:**
- `tests/helpers/agnostic_edges.py::pool_reservation_edges` hard-codes
  `MATCH (:Node {uuid: $pool_id})-[e:IS_RESERVED {identifier: $identifier}]->(:AttributeValue)` —
  both the target label and the identifier filter go away.
- `tests/db_snapshot.py::DbSnapshotterDeduplicated` carries a docstring saying it *"does not account
  for the IS_RESERVED edge type"*; re-check it once the edge hangs off `Attribute`.

**Test-tier note, contradicting the PRD's "Integration (Docker) now required".** The constitution
does require Docker integration coverage for schema migrations, but every existing *graph* migration
test (m063, m066, m076, m078) lives at the **component** tier under
`backend/tests/component/core/migrations/graph/`, and `backend/tests/integration_docker/` has no
number-pool module at all. Decision: put the behavioural coverage of the four migration behaviours at
the component tier, where the precedent and the fixtures are, and add **one** `integration_docker`
test for the upgrade path end-to-end. If added, it **must** carry a module-level
`pytestmark = pytest.mark.shard_a|shard_b` with a matching entry in the `backend-docker-integration`
`shard:` matrix in `.github/workflows/ci.yml` — `conftest.py` validates the full collection
`tryfirst`, so a missing marker fails CI rather than silently never running.

**Benchmark axis does not exist yet.** `tests/helpers/query_benchmark/benchmark_config.py::BenchmarkConfig`
has exactly three axes (`neo4j_image`, `neo4j_runtime`, `load_db_indexes`). The only branch-aware
benchmark, `query_benchmark/test_diff_query.py::test_diff`, creates exactly one extra branch and
varies data volume. A branch-count axis means extending `BenchmarkConfig` or adding a second
`parametrize` argument, plus a data generator that creates N branches — nothing in
`car_person_generators.py` does that. Scope this as real work, not a parameter tweak.

---

## 3. Sequencing

The dependency order is forced, not chosen:

```
D1 re-anchor + m079 migration + D14 rename fix   ← one change set, merges alone (SC-022 boundary)
        │
        ├── D8 conversion re-target  (needs the new anchor to re-target to)
        │
        └── D9 FR-036a cross-branch liveness  (written against the post-move edge chain)
                │
                ├── D3 presence flags ─┐
                ├── D4 intent resolver ─┼── attach / detach / re-pool  (US2, US3)
                ├── D6 invariant + lock ┘
                │
                └── D10 reporter + D11 space seam ── provenance + out-of-space bucket (US2)
```

`GRAPH_VERSION` is bumped once, by the first change set.

The foundational change set merges **ahead** of the feature work. That is not a release decision —
everything lands in the same minor — it is what makes SC-022 measurable: the figures a pool reports
can only be compared before and after the re-anchoring at a point where P1's ranges and this slice's
bucket have not yet moved them.

---

## 4. Open risks carried into the plan

| # | Risk | Handling |
|---|---|---|
| R1 | P1 has no spec; its effective-space calculator does not exist | D11 seam + single-range adapter; interface pinned in `contracts/effective-space.md` |
| R2 | ~~P1's FR-030a contradicts this slice's FR-030b~~ **CLOSED 2026-09-16 — PRD owner confirmed P2 wins**; `source` can be cleared on pool-sourced attributes | Amend `POOL-RANGES-PRD.md` (delete FR-030a, Decision 2, open question #2) before P1 enters spec-kit. No design impact here |
| R3 | FR-036a's per-branch resolution inside the pool lock | D12 benchmark; release decision on the curve |
| R4 | The migration deletes reservation data for the first time | Four behaviours, three reporting counts; Docker integration coverage; `validate_migration` post-condition |
| R5 | Published-contract gate (ADR 0010) | Two new output fields + a `source` provenance change the generated schema will not show; must be named explicitly in the contract review alongside P1/P3 |
| R6 | Concurrent re-pool of one attribute into two pools | D6 lock on the currently-tracking pool |
| R7 | `IS_RESERVED` is undocumented in `dev/knowledge/backend/database-schema.md` | Document the edge, its shapes and its liveness rule as part of this work |
