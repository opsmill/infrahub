# Data Model: Numbers you give the pool

**Feature**: `specs/ifc-3184-pool-number-attach` | **Date**: 2026-09-16

Graph-level data model for the number-pool reservation ledger, before and after the re-anchoring.
Conventions follow `dev/knowledge/backend/database-schema.md`.

---

## 1. The reservation record

### Today

```
(:CoreNumberPool {uuid})
    -[:IS_RESERVED {branch:"-global-", branch_level:1, status:"active",
                    from:<ts>, identifier:<node uuid>}]->
(:AttributeValue:AttributeValueIndexed {value:<int>, is_default:false})
```

The target is the **shared, `MERGE`'d** value vertex. `AttributeValue` de-duplicates on
`value` **and** `is_default`, so every attribute in the graph holding `50` points at the same vertex.

Ownership is expressed by the `identifier` property holding the owning node's uuid, and liveness is
resolved by joining that string back to a node:
`(pool)-[res]->(av)<-[hv:HAS_VALUE]-(attr:Attribute)<-[ha:HAS_ATTRIBUTE]-(n) WHERE n.uuid = res.identifier`.

### After

```
(:CoreNumberPool {uuid})
    -[:IS_RESERVED {branch:"-global-", branch_level:1, status:"active",
                    from:<ts>, to:<ts|null>, provenance:"allocated"|"provided",
                    identifier:<node uuid>}]->
(:Attribute {uuid, name, branch_support})
```

The target is the **per-object** attribute vertex. Ownership is the edge itself — the vertex it
points at *is* the owner. What the record reserves is resolved **forward**, per branch:

```
(pool)-[res:IS_RESERVED]->(attr:Attribute)-[hv:HAS_VALUE]->(av:AttributeValueIndexed)
                          (attr)<-[ha:HAS_ATTRIBUTE]-(n:Node)-[ipo:IS_PART_OF]->(:Root)
```

### Property changes

| Property | Before | After | Notes |
|---|---|---|---|
| `branch` | `"-global-"` | unchanged | Attach and detach take effect on every branch at once, symmetric with allocation |
| `branch_level` | `1` | unchanged | |
| `status` | `"active"`, never anything else | unchanged | Nothing ever sets `"deleted"` on this edge, before or after |
| `from` | set at creation | unchanged | |
| `to` | only ever set by `PoolChangeReserved` | **now also set by release and by close-before-create** | Time-close, not tombstone — see §4 |
| `identifier` | **load-bearing** for liveness | **retained, no longer load-bearing** | Kept for diagnostics and for the IP shapes; liveness no longer depends on it, which is what unblocks P4 |
| `provenance` | — | **new**: `allocated` \| `provided` | Absent means `allocated`, so no backfill is needed |

`provenance` is deliberately two-valued, not three: under FR-021/FR-024, "provided" and "attached"
are the same request made on create and on update.

### The three `IS_RESERVED` shapes after this slice

| Pool kind | Target | Changed by this slice |
|---|---|---|
| `CoreNumberPool` | `:Attribute` | **yes** |
| `CoreIPPrefixPool` | `:Node` (`BuiltinIPPrefix`) | no |
| `CoreIPAddressPool` | `:Node` (`BuiltinIPAddress`) | no |

This is why `PoolChangeReserved` — which matches `(pool:Node)-[r:IS_RESERVED]->(resource)` with both
ends unlabelled and therefore serves all three — must branch on shape or be split. It is the one
query the claim "the six IP-pool queries are untouched" does not cover.

Both IP writers fire only when an identifier is supplied, so an IP allocation without one leaves no
edge at all. That asymmetry is unchanged.

---

## 2. What the record means

The record is a **claim**, not a value. Three facts follow, and they are the whole model:

1. **The record says which attribute a pool accounts for.** It does not say which number. The number
   is whatever that attribute holds, resolved per branch through `HAS_VALUE`.
2. **Every read requires the owning object to still hold a value.** That liveness join, not record
   deletion, is what frees a number. Deleting the object, or changing the number without naming a
   pool, therefore needs no cleanup write.
3. **A value change writes nothing to the ledger.** This is FR-031 satisfied by construction, and it
   is the reason the anchor moved. Under value anchoring, "release the old number" would be a
   `-global-` write answering a branch-scoped question — it would free the number for every branch
   while others still hold it.

### Consequence: one record, several rows

Because a record is anchored on the attribute and resolves forward per branch, **one record can
reserve several values at once** — one per branch that holds a different value.

An object holding `1` on the default branch and `5` on a user branch contributes **two rows** to the
in-use list and consumes **two elements** of the effective space. Both numbers are genuinely
unavailable, so this is correct, not double-counting (FR-028a).

The same mechanism is what lets a single record straddle the effective-space boundary: holding `50`
on the default branch and `500` on another, under a pool over 1–100, the record appears in the
utilization fraction *and* in the out-of-space bucket at once. This is why out-of-space rows must
carry a branch (FR-027a) — without it the operator reads "500 is out of range, held by X" while the
UI shows X holding 50, with nothing to explain the contradiction.

---

## 3. Utilization arithmetic

| Quantity | Rule |
|---|---|
| **Utilization** | Count of **distinct elements of the effective space** consumed. Never a count of records. A number held by three objects consumes one element. |
| **In-use list** | One row per **(record, branch-resolved value)**, each carrying value, holder, branch and `provenance`. Every holder is visible. |
| **Out-of-space bucket** | Rows for tracked values outside the effective space, same shape: value, holder, branch. **Not** split into per-branch buckets — a fraction cannot carry per-item detail, but a list of rows can, and the count stays derivable. |
| **Release** | Ending one record must not affect another record holding the same number. |

Counting rows instead of distinct values would let utilization exceed 100%. Today this invariant
emerges from three lines of set comprehension in `pools/number.py::NumberUtilizationGetter.load_data`,
which partition a distinct union; `PoolUtilizationReporter` makes it explicit and testable.

**Effective space** is `union(ranges) ∩ [min_value, max_value] − intersecting excluded values`.
It is **consumed from P1**, never recomputed here — see `contracts/effective-space.md`.

---

## 4. Record lifecycle

### States

```
      ┌──────────── allocate / attach ────────────┐
      │                                            v
 (no record)                                  [live record]
      ^                                        │  │  │  │
      │                                        │  │  │  └── value change ──> no write, record unchanged
      └── release (to = $at) ──────────────────┘  │  └───── object deleted / branch deleted ──>
                                                  │            record retained, liveness join fails,
                                                  │            number stops counting, no cleanup write
                                                  └──────── re-pool ──> A closed, B created (one operation)
```

There is no tombstone state. Closing is `to = $at`, never `status = "deleted"`, for two reasons: it
matches every existing global-edge closure in the tree (retirement, `PoolChangeReserved`), and a
`status="deleted"` edge is terminal per the database-schema doc — wrong for a record that a later
re-attach may recreate.

### Events

| Event | Behaviour | Ledger write? |
|---|---|---|
| Allocate | Record created, `provenance=allocated` | create |
| Attach (`value` + `from_pool`) | Record created, `provenance=provided` | create |
| Re-attach the same value + pool | No-op (idempotent — clients resend every field) | none |
| Value change, no pool named | Record unchanged; it tracks the attribute, not the value | **none** |
| Detach (`from_pool: null`) | Record ended; number unchanged on the object | release |
| Re-pool A → B | A ended and B created in one operation | release + create |
| Object deleted | Record retained; liveness join fails | none |
| Branch deleted (object existed only there) | Same mechanism | none |
| Attach or detach on a branch, branch then deleted | Permanent — global and immediate, like allocation | n/a |
| Object converted to another type | Record re-targeted to the new object's attribute | re-target |
| Attribute renamed in schema | Record must stay `-global-` | (migration must preserve) |
| Attribute removed from schema | Record closed by retirement's sweep | close |
| Two branches allocate from one pool | Records are global and reads branch-agnostic; the second branch cannot get the same number | create ×2 |
| Two branches hand-set the same number, both attached | Both records exist; a uniqueness constraint refuses at merge, otherwise both survive and the free-number query collapses them | create ×2 |

### Invariants

| # | Invariant | Enforced by |
|---|---|---|
| I1 | At most **one live record per `Attribute` vertex** | Match-close-create in the ledger (FR-024b) + the migration's collapse for pre-upgrade data + pool-A locking (D6) |
| I2 | A number counts as taken while **any** live branch holds an object carrying it | Cross-branch liveness union (FR-036a) |
| I3 | Liveness error is **one-sided** — may over-report taken, never under-report | Union can only add to the taken set |
| I4 | Utilization counts distinct elements, never records | `PoolUtilizationReporter` (FR-028a) |
| I5 | A value change never writes to the ledger | Attribute anchoring (FR-031 deleted) |
| I6 | The pool is **never** written to `HAS_SOURCE` | FR-030b; migration deletes legacy edges |

I1 holds today only as an emergent property of value anchoring — pool A's record dies when the
attribute's value moves away. The re-anchoring removes that accident, so I1 must be constructed.
This is a cost of the move, not an independent feature.

---

## 5. Attribute source

| | Before | After |
|---|---|---|
| Pool written to `HAS_SOURCE` | yes, branch-aware, inheriting the attribute's branch | **never** |
| User may set `source` on a pooled attribute | refused (FR-030a) | **allowed** (FR-030a deleted) |
| `source` read resolution | the stored `HAS_SOURCE` edge | user's `HAS_SOURCE` if one resolves active, else the pool reached by the inbound `-global-` `IS_RESERVED` edge on the same attribute |
| GraphQL field and type | `source: LineageSource` | **unchanged** — only what populates it moves |
| Appears in branch diffs | yes | **no** — accepted cost, changelog entry required |

`CoreNumberPool` already inherits `LineageSource`, and the existing source subquery already matches
undirected and unlabelled, so nothing about the published shape changes.

**The derivation must return the pool vertex, not its uuid.** Extraction builds
`AttributeNodePropertyFromDB(uuid=…, labels=…)` from the returned node's labels, and those labels are
what selects the concrete GraphQL type downstream. Returning an id alone breaks `__kind__`
resolution.

---

## 6. Migration `m079` — four behaviours

Package `backend/infrahub/core/migrations/graph/m079_reanchor_number_pool_reservations/`, exporting
`Migration079`. `minimum_version = 78`; `GRAPH_VERSION` 78 → 79. Registration is filename-driven
(`discover_migrations`) — no registry list to edit, and a duplicate number hard-fails at import.

| # | Behaviour | Destructive? | Reports a count? |
|---|---|---|---|
| 1 | **Re-anchor** every record from its value vertex to the owning `Attribute` | no | no |
| 2 | **Drop orphaned records** whose object no longer exists | **yes** | **yes** |
| 3 | **Collapse multi-pool records** onto one `Attribute` (I1) | **yes** | **yes** |
| 4 | **Delete legacy pool `HAS_SOURCE` edges** (I6) | **yes** | **yes** |

### Ordering is load-bearing

Behaviour 4's predicate must be evaluated against the set of records **live at the start of the
migration**, captured before behaviour 3 runs — or behaviour 4 must run before behaviour 3.

Otherwise: behaviour 3 collapses several pools' records onto one attribute and kills the losers, so
losing pool A no longer has a live record; behaviour 4 then looks for "a live record from that same
pool for that same attribute", does not find one, and **leaves A's legacy `HAS_SOURCE` in place**.
That edge wins the read slot forever, so the attribute reports pool A as its source while pool B
actually tracks the number — precisely the failure FR-030b exists to prevent, reintroduced by
ordering.

Component test: two pools with live records on one attribute, both carrying legacy pool
`HAS_SOURCE` edges. After the migration the attribute reports the **surviving** pool and has **no**
stored source edge.

### Transaction shape

One transaction per behaviour, with the phase's count read back before the transaction commits.
**Never `return` from inside a transaction context** — that is the documented `m066` hazard
(*"returning here from inside the transaction context means that context sees no exception and
commits, so a mid-loop failure can persist partial consolidation"*).

### Irreversibility

`m079` is **irreversible**. Three of its four behaviours delete data and there is no reverse
migration; the recourse after a bad upgrade is a database restore.

Because of that, each destructive behaviour reports its count **twice**: once as a pre-count of what
it is about to act on, and once as a post-count of what it did. An operator who stops the upgrade
after seeing an unexpected pre-count still has the figure in the log.

### 1. Re-anchor

For each record: resolve `identifier` to the **active** `Node` vertex (duplicate-UUID aware), find
its `Attribute` by the pool's `node_attribute`, create the `-global-` edge, close the old one.

Duplicate-UUID resolution copies the idiom in `graph_traversal/_cypher.py::_SOURCE_MATCH`: take each
candidate vertex's latest `IS_PART_OF` **without** pre-filtering on status, keep it only if that
latest edge is `active`, then `ORDER BY branch_level DESC, from DESC LIMIT 1`. A kind, namespace or
inheritance migration can leave several `Node` vertices sharing one uuid; there is no shared helper,
so this idiom is copied, not invented.

Re-anchoring shape follows `m066::Migration066._reassign_has_source`:
`CREATE … SET new = properties(old) … DELETE old`, which preserves `branch`, `branch_level`, `from`,
`to` and `status` including `-global-`. A **hard** re-anchor with no history is correct here: the
record's history is not user-visible, and a time-closed old edge would still be read by
`NumberPoolGetAllocated`, which applies no status predicate to the reservation edge.

### 2. Drop orphaned records

Records whose `identifier` resolves to no active node. These are the dead rows the standing comment
in `core/query/resource_manager.py` has flagged for years — *"the relationship IS_RESERVED for Number
is not being cleaned up when the node or the branch is deleted"*. **The first deliberate deletion of
reservation data**, hence the count.

### 3. Collapse multi-pool records

Today several pools' records for one object can coexist with only one live, because value anchoring
kills the losers. After the move they would all be live, and pool A would report a number pool B
handed out — bucketed as out-of-space, so A's worklist would tell the operator to widen A to cover
B's number. Nonsense.

**Survivor: the record with the greatest `from`.** The record is a claim, and the most recently made
claim is the current one; keeping the earliest would make re-pooling silently revert to the original
pool for any pre-upgrade object re-pooled through the old overwrite-the-source path.

> The PRD justifies this rule as "matching the rule `m066` uses for schema pools". That is **false**:
> `m066` keeps the **earliest** (`ORDER BY created_at ASC`, `chronological_pool_ids[0]`, docstring
> *"Keeps the earliest pool"*). It answers a different question — which *pool vertex* survives dedup,
> where the original is the one schema parameters already point at. The rule here stands on its own
> merits. See `research.md` §0 item 2 and D7.

### 4. Delete legacy pool `HAS_SOURCE` edges

Scoped to `(a:Attribute)-[:HAS_SOURCE]->(pool:CoreNumberPool)` **where a live record from that same
pool exists for that same attribute**. Left in place they would win the read slot forever, so the
derivation would never fire for pre-upgrade data — and, being branch-aware edges carrying what is now
a `-global-` fact, they would reproduce the detach orphaning for exactly the objects most likely to
be detached during brownfield cleanup.

The predicate cannot catch a user source pointing elsewhere, and that is correct: it should not.
Where a user deliberately set the source to the tracking pool, deleting the edge changes nothing
visible — the derivation returns the same pool.

### Indexing

`core/graph/index.py::rel_indexes` gives every property edge type a `branch` range index —
`HAS_ATTRIBUTE`, `HAS_VALUE`, `IS_RELATED`, `IS_PROTECTED`, `HAS_SOURCE`, `HAS_OWNER`, `IS_PART_OF` —
and **nothing for `IS_RESERVED`**. That was defensible while the edge was touched only by pool
queries. It stops being defensible here: FR-030b puts an `OPTIONAL MATCH` for the record inside
`NodeListGetAttributeQuery`, which runs for **every attribute of every kind** read with metadata, the
overwhelming majority of which have no reservation at all.

Add:

```
IndexItem(name="reserved_branch", label="IS_RESERVED", properties=["branch"], type=IndexType.RANGE)
```

Measure the derivation's cost on a metadata read over a kind with **no** pool, not only on pooled
reads — the non-pooled path is the blast radius.

### Reporting and validation

Counts reach an operator **only** through `migration_input.console.log(...)`.
`MigrationResult.nbr_migrations_executed` is accumulated but `cli/db.py::migrate_database` never
prints it. Follow `m078`: set both. Its component tests assert on the console string, which is the
testable surface.

`validate_migration` re-runs a read query and turns leftovers into `result.errors`, following
`m077::Migration077.validate_migration`.

**Hazard to avoid**: `m066::Migration066.execute` carries the comment *"returning here from inside
the transaction context means that context sees no exception and commits, so a mid-loop failure can
persist partial consolidation."* Do not repeat that shape.

---

## 7. Untyped edge sweeps over `Attribute` vertices

Anchoring the record on the attribute puts it in the path of every untyped sweep over that vertex.

| Sweep | Effect | Action |
|---|---|---|
| **Attribute rename** | **Bug** — `AttributeRenameQuery` copies every edge with `$rel_props_create` built unconditionally from the migration branch, relocating the ledger edge onto a branch | Port the `CASE WHEN r.branch = "-global-"` that `NodeDuplicateQuery._render_sub_query_per_rel_type` already has, plus its `WHERE rel.branch IN ["-global-", $branch]` close |
| **Attribute remove** | **Win, already wired** — `AttributeRemoveQuery` ends with `%(close_unretained_agnostic_fields)s`, so the record is closed | Test it holds; no code change |
| **Branch-agnostic retirement** | **Intended** — this is the inheritance the move is for | Update the existing pool assertion, which pins the old target label |

Retirement's closing sweeps are **untyped and undirected** (`MATCH (field)-[e]-() WHERE
e.branch = $global_branch_name …`) across all four call sites, so an edge incident on the `Attribute`
vertex is swept automatically. Only the *anchoring* matches are typed (`HAS_ATTRIBUTE|IS_RELATED`),
and those select candidate vertices, not edges to close.

The rename bug matters more after FR-030b: the record is now the sole storage of the pool's claim, so
relocating it onto a branch makes it invisible to a derivation matching only `-global-` edges — the
attribute then reports **no source at all** while the ledger still holds the number reserved.

---

## 8. Entities not changed

| Entity | Status |
|---|---|
| `CoreNumberPool` | No new attribute from this slice. Ranges come from P1. Stays `BranchSupportType.AGNOSTIC`. Still `unique` on `name__value` only — there is **no** uniqueness constraint on `(node, node_attribute)`, so several pools may target one kind+attribute. |
| `NumberPoolParameters` | Unchanged here; P1 adds `ranges` and nullable scalars. |
| Allocation scope | Not involved. Scope decides which number is picked next and nothing else, so this slice is scope-unaware and does not depend on P3. With FR-031 deleted there is no second lock key to make scope-aware. |
| `AttributeValue` / `AttributeValueIndexed` | Unchanged. The record simply stops pointing at them. |
| IP pool ledgers | Unchanged, except that the shared re-target query must branch on shape. |
