# Contract: `PoolRecordLedger`

**Status**: internal. Not published; no GraphQL surface.

**Owner**: `backend/infrahub/core/query/resource_manager.py` (Cypher) driven by the ledger seam.

**Consumers**: `Node.handle_pool`, `CoreNumberPool.get_resource`, object conversion.

---

## Rule

**Every write to a number pool's `IS_RESERVED` edge goes through the ledger.** No caller writes the
edge directly.

This is new. Today writes are scattered: `NumberPoolSetReserved` is a bare `CREATE` invoked from
`CoreNumberPool.reserve`, and `PoolChangeReserved` is the only query that has ever closed one.

---

## Operations

### `create(pool, attribute, allocated_value)`

`allocated_value` is the number the pool allocated in this write, or none when the pool only tracks
a number the attribute already holds.

**Match-close-create**, not `CREATE`:

1. Keep this pool's live record when the write allocates nothing, or allocates a number the record
   already lists. Otherwise close every **live** record on the target `Attribute` vertex
   (`to = $at`), whichever pool owns it.
2. When nothing was kept, create the new `-global-` record with `allocated_values`: the kept
   pool's list plus `allocated_value` when this pool's record was closed, else `[allocated_value]`
   or `[]`.

Both steps in one query. The close is what makes the one-record-per-attribute invariant hold **by
construction** (FR-024b) rather than by accident, and it is what makes re-pool a single operation
(FR-024a).

Today's bare `CREATE` is safe only because value anchoring kills the loser: pool A's record points at
`AttributeValue(50)`, so when pool B writes `500` onto the attribute, A's liveness join goes inactive
and A's record dies. Anchored on the attribute, both records resolve forward to the same live value,
neither dies, and pool A reports a number pool B handed out.

`allocated_values` is the list of every number the pool allocated to the attribute, on any branch.
A row of the in-use list reads `allocated` when its branch-resolved value is in the list and
`provided` otherwise; an absent list reads `allocated` for every value, and the re-anchoring
migration writes the anchored value into each legacy record's list (FR-026, FR-026e).

**The list is never changed in place.** Extending it is a close-and-create, so the history is kept
and the pool is stamped like any other record change. Nothing removes a member: a value change,
branch delete, object delete or merge writes nothing to the ledger, so a number the attribute no
longer holds stays listed. It is inert, because the label is read only for a row whose
branch-resolved value matches.

**An attach writes nothing onto this pool's live record.** The record tracks the attribute, not the
value, and the label of each row is computed at read time, so neither a hand-set number nor a
restated one changes the record. A number the pool once allocated therefore reads `allocated` on
every branch that holds it, including a branch where the user hand-set it after holding another
number (FR-026c, accepted). *(Revised 2026-10-07: replaces the single `provenance` property, its
update to `provided` on re-attach and the held-value comparison of 2026-10-05.)*

**Required interface change**: `CoreNumberPool.get_resource(db, branch, attribute: AttributeSchema,
identifier: str)` receives the attribute *schema* and a node uuid — it never sees the `Attribute`
**vertex**. Both the close-before-create and the re-anchored idempotency lookup need that vertex, so
it must be threaded through `get_resource` → `reserve` → the ledger. The caller
(`Node.handle_pool`) already holds the attribute instance.

The idempotency lookup changes meaning with it. Today `get_resource` asks `NumberPoolGetReserved`
"does this pool hold a reservation under this identifier?", and that is what makes re-creating the
same node reuse its number. Re-anchored, the question becomes **"is there a live record from this
pool on *this attribute*?"** — consistent with release, which does no identifier matching. The
identifier survives as a diagnostic, not as a join key.

**Locking**: the write takes an exclusive lock on the `Attribute` vertex before it reads any record
(a `SET` and `REMOVE` of a throwaway property, held until the transaction ends). A concurrent write
to the same attribute waits, then reads the records the first one committed. Without it, two
concurrent re-pools of one attribute into different pools each close the other's record and both
create, because neither can read the other's uncommitted edge. The caller still holds the lock of
the pool it allocates from. See `research.md` D6.

### `release(pool, attribute)`

End the single `-global-` record between a pool and an `Attribute`.

- **No identifier matching.** The anchor is already per-object, so identifier scoping disappears with
  the re-anchoring.
- The number on the object is **unchanged**.
- Releasing one record must not affect another record holding the same number (FR-028a): two objects
  holding `50` under one pool have two records, and detaching one leaves the other reporting `50`.

This query is **new** — nothing in the codebase releases a reservation today.

### `re_target(pool, from_attribute, to_attribute)`

Move a record from one `Attribute` vertex to another. Used **only** by object type conversion.

Must branch on pool shape: the shared query serves number pools (→ `:Attribute`), prefix pools
(→ `:Node`) and address pools (→ `:Node`). The IP shapes keep re-pointing at the same resource and
only relabel the identifier.

### No `move`

FR-031 is **deleted — satisfied by construction**. A value change writes nothing to the ledger: the
record tracks the attribute, and what it reserves is whatever values that attribute holds. The
record-move, its self-healing clause and its pool lock all go, taking with them the only hot-path
regression this slice would otherwise carry.

It was also not correctly implementable under the old anchoring: a record is `-global-` while a value
change is branch-scoped, so "release the old number" would free it for every branch while others
still hold it.

---

## Closing semantics

Closing is **`to = $at`** (time-close), never `status = "deleted"`.

Two reasons:

1. It matches every existing global-edge closure in the tree — branch-agnostic retirement's four call
   sites and `PoolChangeReserved` all time-close.
2. A `status="deleted"` edge is **terminal** per `dev/knowledge/backend/database-schema.md`: it always
   keeps `to: NULL`, never receives a `to`, and is never re-opened. That is wrong for a record a
   later re-attach may recreate.

---

## Read-side invariants the ledger's writes must respect

| # | Invariant | Why the ledger cares |
|---|---|---|
| L1 | Reads resolve forward through `HAS_VALUE`, per branch | A record pointing at an abandoned `Attribute` must report **nothing**, not report the edge (FR-030c) |
| L2 | Reads must apply a status and branch predicate to the reservation edge | `NumberPoolGetAllocated` applies **neither** today. Harmless while nothing closes a record; wrong the moment release and match-close-create do. Risk R8. |
| L3 | Membership of the allocated list is decided by the record and the liveness join **alone** | The `hs_active` gate goes with FR-030c — the pool is no longer in `HAS_SOURCE`, so gating on it would return nothing at all |
| L4 | Liveness is a **union across branches** | FR-036a. Taken on any live branch means taken everywhere; free only when no live branch holds it |

---

## What the ledger does not do

- It does not decide *whether* to write — that is `FromPoolIntentResolver`
  ([`from-pool-intent.md`](./from-pool-intent.md)).
- It does not clean up on object or branch deletion. **Nothing needs to**: every read requires the
  owning object to still hold the recorded value, so the liveness join frees the number on its own.
  This is also why the accumulated dead edges are a *leak*, not a correctness bug — and why the
  re-anchoring ends the leak by inheriting retirement's sweep rather than by adding cleanup writes.
- It does not touch `HAS_SOURCE`. The pool is never written there (FR-030b), so detach has nothing
  to clear — which is the whole reason detach is expressible at all.
