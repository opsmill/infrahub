# Contract: pool query surface

**Status**: **published contract change** — governed by
[ADR 0010](../../../adr/0010-generated-user-facing-schema-contract.md).

**Owner**: `backend/infrahub/graphql/queries/resource_manager.py` (pool query),
`backend/infrahub/graphql/manager.py` (the `from_pool` field on `NumberAttribute`)

---

## Governance

This slice **must be named explicitly in the published-contract review**, alongside P1's and P3's
`NumberPoolParameters` changes. One review, one SDK type regeneration — not three.

Three kinds of change are in scope, and the third is the dangerous one:

| Change | Visible in the generated schema? |
|---|---|
| `provenance` on each in-use row | **yes** |
| The out-of-space bucket | **yes** |
| `from_pool` on `NumberAttribute` | **yes** |
| `source` no longer names the tracking pool (FR-030b) | **no** — the field name and type are unchanged; only what populates it changes |

FR-030b **must be named in the review in words**, because nothing in the generated artefacts will
surface it. A reviewer diffing `schema/schema.graphql` will see the new `from_pool` field and no
trace of the change that removes the pool from what every pooled attribute reports as its source.

Generated files are regenerated, never hand-edited:
`uv run invoke backend.generate`, `schema.generate-graphqlschema`, `schema.generate-jsonschema`,
`docs.generate`. CI's `validate-generated-documentation` job fails on stale output.

---

## 1. `provenance` on in-use rows

**Shipped 2026-10-07** as `PoolAllocatedNode.provenance`, a nullable `PoolRecordProvenance` enum
(`ALLOCATED` / `PROVIDED`). It is nullable because the type is shared with the IP address and prefix
pool rows, which carry none.

Each row of a number pool's allocated/in-use list reports `provenance`, a closed set:

| Value | Meaning |
|---|---|
| `ALLOCATED` | The pool allocated the number this row's branch holds |
| `PROVIDED` | The user gave the pool the number this row's branch holds |

Two values, not three. Under FR-021/FR-024, "provided" and "attached" are the same request made on
create and on update, so they do not merit separate values. The label is not stored: it is read per
row from the record's `allocated_values` against the row's branch-resolved value, so it is correct
on every branch (FR-026). A record with no list reads `ALLOCATED` for every value.

**Row cardinality (FR-028a)**: one row per **(record, branch-resolved value)**. A record whose object
holds `1` on the default branch and `5` on another contributes **two rows**. Several objects holding
the same number under one pool contribute one row each, each naming its own holder and its own
`provenance`.

**Utilization is unaffected by row count.** It counts distinct elements of the effective space
consumed — a number held by three objects consumes one element. Counting rows would let utilization
exceed 100%.

---

## 2. The out-of-space bucket

A tracked number outside the pool's effective space is reported in a **separate bucket**, not folded
into the utilization fraction.

**Row shape matches the in-use row**: `value`, `holder`, `branch` (FR-027a).

### The bucket is a flat list, not per-branch buckets

The three utilization *figures* are split by branch because a fraction cannot carry per-item detail.
A bucket is already a list of rows and can, so grouping by branch is a client concern and the count
stays derivable.

### The branch is load-bearing, not cosmetic

Under FR-028a one record can straddle the boundary: an object holding `50` on the default branch and
`500` on another, under a pool over 1–100, appears in the utilization fraction **and** in the bucket
at once. Without the branch on the row, the operator reads "500 is out of range, held by X" while the
UI shows X holding 50, with nothing to explain the contradiction.

### Semantics

- A number outside the ranges, or inside the attribute's excluded values, is **accepted and tracked**
  (FR-029 deleted — the pool refuses no provided value).
- It is invisible to allocation and consumes nothing.
- If the effective space later covers it — a range widened, a range re-added — it moves into the
  in-use fraction **with no re-attach** (FR-002a).
- Two paths reach this state: attached there, or a range removed under it. Both must be tested; the
  resulting state is identical.

### Why it ships now rather than with the frontend

Deleting FR-029 makes an out-of-space attach reachable from day one. Without the bucket that attach
is a silent no-op — the operator learns nothing. It is also one published-contract review with
`provenance`, not two.

---

## 3. `source` — populated only by a stored user-set edge

| | Before | After |
|---|---|---|
| Field | `source: LineageSource` | **unchanged** |
| Populated by | a stored `HAS_SOURCE` edge written by the pool | a stored `HAS_SOURCE` edge the user set; **never the pool** |
| Display for an attribute with no user source | the pool | **null** |
| Display for an attribute with a user source | previously impossible (refused) | the user's source |
| Appears in branch diffs | yes | **no** |

The pool that tracks the attribute is reported by `from_pool` (section 4), never by `source`. The
read loads the pool into a property of its own (`tracking_pool` on the attribute), not into the
source property, so a save after a re-pool or a detach cannot write the pool back as a `HAS_SOURCE`
edge. The migration deletes every legacy `HAS_SOURCE` edge from an attribute to a number pool, so an
upgraded database reads the same way.

**Behaviour changes a client can observe:**

1. A pool-allocated number with no user-set source reads `source: null` where every released version
   reported the pool. A client that read the pool from `source` reads `from_pool` instead. Needs a
   changelog entry.
2. A user may set `source` on a pool-tracked attribute (FR-030a deleted). The pool stays visible
   through `from_pool`. Nothing the pool computes is affected — utilization, the in-use list and
   next-value read the record only.
3. Allocating or attaching on a branch no longer shows a source change in the diff, only a value
   change. The pool's claim is branch-agnostic, so diffing it per branch was always a fiction — but
   user-visible, and it needs a changelog entry.

---

## 4. `from_pool` on `NumberAttribute`

A read-only output field on `NumberAttribute`, the GraphQL type shared by the `Number`, `NumberPool`
and `Bandwidth` attribute kinds. A `Bandwidth` attribute carries the field and reads null. The input
field of the same name on the mutation keeps its meaning
([`from-pool-intent.md`](./from-pool-intent.md)); the two share a name only.

```graphql
type NumberAttributeFromPool {
  pool: CoreNumberPool!
  provenance: PoolRecordProvenance!
}

type NumberAttribute {
  # existing fields unchanged
  from_pool: NumberAttributeFromPool
}
```

### Null semantics

`from_pool` is null when no pool tracks the attribute: no `IS_RESERVED` edge on the global branch
from a `CoreNumberPool` to the attribute is active at the read's time. The read does not check the
pool node itself: a live edge implies a live pool, because deleting a pool ends every edge it holds.

### `pool`

The pool reached by the active global `IS_RESERVED` edge on the attribute. The edge is global, so
**the same pool is reported on every branch**, including a branch created before the attach.

The `pool` sub-selection is served by one batched load per request, not one read per attribute.
If the pool is deleted between the attribute read and that load, GraphQL nulls `from_pool`.

### `provenance`

Reuses the `PoolRecordProvenance` enum of section 1:

| Value | Meaning |
|---|---|
| `ALLOCATED` | The value the branch holds is in the record's `allocated_values` list, or the record has no list |
| `PROVIDED` | The value the branch holds is not in the record's `allocated_values` list |

It is read from the value the branch resolves for the attribute, so one attribute can read
`ALLOCATED` on a branch where the pool allocated its value and `PROVIDED` on a branch where a user set
a different value under the same pool.

### Cases

| Case | `from_pool` |
|---|---|
| Value inherited from a profile | The pool, with the provenance of the inherited value. The edge is on the object's own attribute and the read resolves the value the branch holds, inherited or not |
| Value outside the pool's ranges, or null, on the branch read | The pool and its provenance. Tracking is independent of the value |
| Read at a past time | The pool tracking the attribute at that time, with the provenance of the value the branch held then against the list the record had then |
| Mutation response (create, update, attach, detach) | The state after the write: `ALLOCATED` after an allocation, `PROVIDED` after an attach, null after a detach |
| Attribute with a user-set `source` | The pool; `source` reports the user's node. The two are independent |

### Pool delete ends tracking

Deleting a number pool ends every live `IS_RESERVED` edge the pool holds, in the same transaction as
the delete. Every attribute it tracked keeps its number, reads `from_pool: null` on every branch, and
can be attached to another pool afterwards — the same outcome as a detach. Both delete paths behave
this way: the `CoreNumberPoolDelete` mutation and the schema synchronizer removing the pool of a
`NumberPool` attribute kind.

### Consumers

- The frontend edit form reads `from_pool` to show the pool chip; it read `source.__typename` before.
  No other UI reads the field in this slice.
- The SDK does not select the field yet; see the SDK ticket.

---

## 5. Not in this slice

- **Bulk attach** and the pool-level mutation it would need. All-or-nothing cannot be built from N
  update calls. Deferred with the frontend.
- **Input shape changes.** No new input fields. The `from_pool` input changes meaning only — see
  [`from-pool-intent.md`](./from-pool-intent.md).
- **The tracking record's identifier on `from_pool`.** The nested shape leaves room for it later.
- **Rendering `from_pool` in the UI** beyond the edit form's pool chip, and **reading it from the
  SDK**.
