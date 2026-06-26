# Phase 1 Data Model: Coalesce merge and rebase recompute fan-out

**Date**: 2026-06-26 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

No persisted (Neo4j) model changes. These are in-memory records (frozen dataclasses, Constitution III) the coordinator builds from the merge/rebase changelog and hands to the batched recompute. Reuse existing target types from the derivers where they exist (the computed-attribute `ResolvedComputedTarget`; the display-label/HFID definition/template metadata) rather than re-declaring them.

## Records

### `MergeChange` (one changed node from the changelog)

```python
@dataclass(frozen=True)
class MergeChange:
    node_id: str
    kind: str
    action: str                 # "created" | "updated" | "deleted"
    changed_fields: frozenset[str]   # attribute/relationship names that changed
```

Built from the diff changelog the merge/rebase already collects to build events.

### `ChangeSignature` (dedup key for derivation)

```python
@dataclass(frozen=True)
class ChangeSignature:
    kind: str
    action: str
    changed_fields: frozenset[str]
```

The changed-node set collapses to a few signatures. Derive affected targets **per signature**, then map back to the node ids sharing it (Constitution V, research R2).

### `AffectedTarget` (a derived value type to recompute)

```python
@dataclass(frozen=True)
class AffectedTarget:
    family: str                 # "computed_attribute" | "display_label" | "hfid"
    target_kind: str
    attribute_name: str | None  # set for computed attributes; None for display label / hfid
    reads_across_relationship: bool   # True only when an async peer trigger exists for this target
    node_filter: object         # how to find the reader nodes (reuse the deriver/facade filter type)
    precise: bool               # False when produced by the bounded fallback (research R8)
```

`reads_across_relationship` captures the per-family difference the code analysis flagged: a self-only HFID has no peer trigger and is not in the cross-node set; a peer-reading display label is. The coordinator does not apply one rule across families.

### `CoalescedRecompute` (the deduplicated work the operation submits)

```python
@dataclass(frozen=True)
class CoalescedRecompute:
    branch: str                 # destination branch for merge; user branch for rebase (FR-014)
    targets: frozenset[AffectedTarget]   # deduplicated across all changes and families
    fallback_used: bool                  # any AffectedTarget with precise=False
```

`branch` carries the per-operation difference (merge → destination, rebase → user). `targets` is the union over all changes, deduplicated, so a derived value is recomputed at most once (FR-003), with reader node ids resolved by one query over the union (no per-target re-query, Constitution V).

## Deriver inputs (what the display/HFID deriver reads)

The new display-label/HFID deriver is built to the computed-attribute pattern and reads the dependency metadata already recorded on the definitions (exposed via the schema-branch facades):

- per target: the local attributes it reads, the relationships it reads across, and the relationship fields per relationship.
- the related-trigger maps (which related kind, changed via which field, drives which target kind), used to turn a changed `(kind, field)` into cross-node targets.

No new persisted metadata is introduced; the deriver reads what the schema already records.

## Relationships

```text
merge / rebase changelog  ──►  set[MergeChange]
        │  group by ChangeSignature (dedup derivation; Constitution V)
        ▼
   derivers (computed reused; display/HFID built here)  ──►  set[AffectedTarget]  (precise or bounded fallback)
        │  resolve reader node ids with one query over the union
        ▼
   CoalescedRecompute(branch=dest|user)  ──►  batched/chunked submit via existing flows  ──►  values written
```

## Invariants / validation

- Final derived values equal a from-scratch recompute (FR-002, FR-010); verified on the full stack, on the correct branch per operation (FR-014).
- `targets` deduplicated: one entry per `(family, target_kind, attribute_name)` regardless of how many changed nodes affect it (FR-003).
- Coverage: updates fan out to cross-relationship readers; creations cover all the new node's families; readers of deleted nodes are included; readers existing only on the destination branch are always recomputed (FR-001, FR-005, FR-013, FR-015).
- Precision: `precise=False` only where the deriver cannot resolve precisely; whenever `fallback_used` the run logs what was over-approximated (FR-012). Never silent under-recompute.
- The coordinator is read-only with respect to schema and writes no derived values itself (the reused flows do).
