# Contract: pool query surface

**Status**: **published contract change** — governed by
[ADR 0010](../../../dev/adr/0010-generated-user-facing-schema-contract.md).

**Owner**: `backend/infrahub/graphql/queries/resource_manager.py`

---

## Governance

This slice **must be named explicitly in the published-contract review**, alongside P1's and P3's
`NumberPoolParameters` changes. One review, one SDK type regeneration — not three.

Two distinct kinds of change are in scope, and the second is the dangerous one:

| Change | Visible in the generated schema? |
|---|---|
| `provenance` on each in-use row | **yes** |
| The out-of-space bucket | **yes** |
| `source` populated by derivation instead of a stored edge (FR-030b) | **no** — the field name and type are unchanged; only its provenance moves |

FR-030b **must be named in the review in words**, because nothing in the generated artefacts will
surface it. A reviewer diffing `schema/schema.graphql` will see no trace of a change that alters what
every pooled attribute reports as its source.

Generated files are regenerated, never hand-edited:
`uv run invoke backend.generate`, `schema.generate-graphqlschema`, `schema.generate-jsonschema`,
`docs.generate`. CI's `validate-generated-documentation` job fails on stale output.

---

## 1. `provenance` on in-use rows

Each row of a number pool's allocated/in-use list gains `provenance`, a closed set:

| Value | Meaning |
|---|---|
| `allocated` | The pool picked this number |
| `provided` | The user gave the pool this number |

Two values, not three. Under FR-021/FR-024, "provided" and "attached" are the same request made on
create and on update, so they do not merit separate values. Absent in storage means `allocated`.

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

## 3. `source` — same shape, different provenance

| | Before | After |
|---|---|---|
| Field | `source: LineageSource` | **unchanged** |
| Populated by | a stored `HAS_SOURCE` edge written by the pool | the user's `HAS_SOURCE` if one resolves active, else the pool reached by the inbound `-global-` `IS_RESERVED` edge |
| Display for an attribute with no user source | the pool | **the pool** — unchanged |
| Display for an attribute with a user source | previously impossible (refused) | the user's source |
| Appears in branch diffs | yes | **no** |

`CoreNumberPool` already inherits `LineageSource`
(`core/schema/definitions/core/resource_pool.py`), so it is already a legal occupant of the slot.

**Behaviour changes a client can observe:**

1. A user may now set `source` on a pool-tracked attribute (FR-030a deleted). Doing so hides *which*
   pool tracks it until the deferred `from_pool` output field lands. Nothing the pool computes is
   affected — utilization, the in-use list and next-value read the record only.
2. Allocating or attaching on a branch no longer shows a source change in the diff, only a value
   change. Defensible — the pool's claim is branch-agnostic, so diffing it per branch was always a
   fiction — but user-visible, and it needs a changelog entry.

### Implementation constraint

The derivation must return the **pool vertex**, not its uuid. Extraction builds
`AttributeNodePropertyFromDB(uuid=…, labels=…)` from the returned node's labels, and those labels are
what `graphql/types/interface.py::InfrahubInterface.resolve_type` uses to select the concrete GraphQL
type. Returning an id alone breaks `__kind__` resolution — assert the resolved kind in a test, not
just the uuid.

---

## 4. Not in this slice

- **A dedicated `from_pool` output field.** It is the end state and the only way to show a pool and a
  user source together. FR-030b makes it *cheaper* to add later, not harder — it would remove a
  branch in the source resolver rather than change a contract. Deferred: per-attribute user sources
  on pooled attributes are rare (automatic source assignment applies only to repository-managed core
  objects, not the user data nodes FR-030 scopes this to).
- **Bulk attach** and the pool-level mutation it would need. All-or-nothing cannot be built from N
  update calls. Deferred with the frontend.
- **Input shape changes.** No new input fields. `from_pool` changes meaning only — see
  [`from-pool-intent.md`](./from-pool-intent.md).
