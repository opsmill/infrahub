# Contract: effective space (consumed from P1)

**Status**: internal seam. **This slice consumes it and MUST NOT reimplement it.**

**Producer**: P1 — *several ranges* (`POOL-RANGES-PRD.md`, INFP-325).
**Consumers in this slice**: `PoolUtilizationReporter`, the out-of-space partition.

---

## Definition

> **Effective space** = `union(ranges) ∩ [min_value, max_value] − excluded values that intersect it`

Excluded values that do not intersect are **not** subtracted. That clause is not a detail: it is the
fix for a live `ZeroDivisionError` (see *Inherited defect* below).

P1's Decision 8 makes this one rule feed size, utilization, allocation order and fullness.

---

## Why a seam exists

P1 has **no spec directory**. `POOL-RANGES-PRD.md` is still an Idea Brief with an open
`[NEEDS CLARIFICATION]` on zero-range pools. Three options were available:

1. **Wait for P1.** Rejected — it stalls this slice's foundational change set, which is the item that
   most needs to merge early so SC-022 stays measurable.
2. **Reimplement membership here.** Rejected — the spec forbids it explicitly, and P1's brief already
   counts *three* disagreeing copies of exclusion arithmetic (`get_next`'s `skip_excluded` closure,
   its effective-range maths, and `total_pool_size`). A fourth is the opposite of the consolidation
   P1 exists to do.
3. **Pin the interface, adapt behind it.** Chosen.

The adapter is **deleted** when P1 lands. The interface is the thing P1 must satisfy.

---

## Interface

Two operations. Nothing else in this slice needs the space.

| Operation | Signature (shape, not literal) | Used by |
|---|---|---|
| **membership** | `contains(value: int) -> bool` | the in-space / out-of-space partition |
| **size** | `element_count() -> int` | the utilization denominator |

Properties the implementation must have:

- **Total.** `contains` answers for every integer, including values far outside every range. There is
  no "unknown".
- **Pure.** No database access. `PoolUtilizationReporter` is a pure module and is unit-tested without
  one.
- **Consistent.** `element_count()` equals the number of distinct integers for which `contains` is
  true. The reporter asserts a bounded utilization against this.
- **Empty is legal.** `element_count() == 0` must be representable and must not raise. P1's open
  question asks what a zero-range pool reports; this slice needs only that it does not crash, and
  `PoolUtilizationReporter` must handle a zero denominator without dividing.

---

## Interim adapter (until P1 lands)

A single-range adapter over today's model:

```
union({[start_range, end_range]}) ∩ [min_value, max_value] − intersecting excluded values
```

This is exactly the effective range `CoreNumberPool.get_next` already computes inline
(`effective_start = max(start_range, min_value)`, `effective_end = min(end_range, max_value)`), lifted
behind the interface. It is **not** new arithmetic — it is the existing arithmetic given a name and a
seam.

The adapter lives in `backend/infrahub/pools/effective_space.py` and is deleted when P1's calculator
lands. The interface does not change.

---

## Inherited defect — P1 owns the fix, this slice must not paper over it

`NumberUtilizationGetter.total_pool_size` divides by

```
end_range - start_range + 1 - CoreNumberPool.get_attribute_nb_excluded_values()
```

and `get_attribute_nb_excluded_values` sums **every** excluded value on the attribute with no
intersection against the pool's span. An attribute with `excluded_values: "500-600"` under a pool over
100–200 therefore yields `total_pool_size = 0`, and `utilization` divides by it — a live
`ZeroDivisionError`.

P1's FR-006 fixes this by making the intersection part of the definition. This slice **must not**
work around it locally: `PoolUtilizationReporter` takes the effective space as an **input** and does
not compute it. The interim adapter implements the intersecting rule, so the defect does not survive
behind the seam either.

---

## Related P1 requirements this slice depends on

| P1 requirement | What this slice needs from it |
|---|---|
| **FR-002a** | A record outside every effective range is retained and stays associated with the pool. This slice narrows "excluded from utilization" to "excluded from the utilization *fraction*" — such records are **bucketed, not hidden**. |
| **FR-006** | The effective-space rule itself. |
| **FR-011** | Deletion of the hand-set-value scan (`NumberPoolGetTaken` and the `attribute.unique` branch in `get_next`). This slice relies on the deletion but does not carry it. |

---

## Cross-slice contradiction — RESOLVED 2026-09-16 (P2 wins)

P1's brief carries **FR-030a / Decision 2**:

> *The `source` of a pool-tracked value is the pool, for both provisioned and assigned values, and
> users cannot clear it.*

This slice's **FR-030b** removes the pool from `HAS_SOURCE` entirely and **deletes FR-030a**, because
the two edges cannot be kept in sync — their *scopes* differ, not merely their semantics, and detach
could not have been made correct otherwise.

**Resolved 2026-09-16 by the PRD owner: P2 wins.** `source` can be cleared on pool-sourced
attributes. P1's FR-030a and Decision 2 are superseded and must be deleted from `POOL-RANGES-PRD.md`,
along with its resolved open question #2 (*"detach clears the pool-owned `source`"*), which cites a
P2 clause FR-025 no longer contains. Do this **before P1 enters spec-kit**.

Note for whoever amends P1: under FR-030b there is no pool-owned source to clear, because the pool is
never written to `HAS_SOURCE`. What a user clears is **their own** source edge, after which the slot
falls back to the derived pool — clearing *reveals* the pool rather than emptying the field.

Risk **R2**/**R14** in [`../plan.md`](../plan.md) are closed.
