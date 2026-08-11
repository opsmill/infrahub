# Phase 1 Data Model: Scope Computed-Attribute Recompute to Actual Schema Changes

**Date**: 2026-06-03 (regenerated for Session 2026-06-03 clarifications)
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Research**: [research.md](./research.md)

No database/graph schema changes. The entities below are **in-memory** structures (frozen dataclasses / Pydantic) used to decide recompute scope at schema-change time. They map the spec's Key Entities onto concrete backend types.

## Entity: ChangedElementSet

The set of schema elements added, changed, or removed by a single schema update on one branch. Derived from `SchemaBranch.diff()` (`SchemaDiff` with `.added` / `.changed` / `.removed`) and carried on `SchemaUpdatedEvent`.

| Field | Type | Notes |
|-------|------|-------|
| `added_kinds` | `frozenset[str]` | Object-type kinds newly added by the change. |
| `removed_kinds` | `frozenset[str]` | Object-type kinds removed by the change. |
| `changed_fields` | `Mapping[str, frozenset[str]]` | kind → set of attribute/relationship names changed on that kind (includes computed-attribute definition edits). |

Availability is the container itself: the set is passed as `ChangedElementSet | None`, where `None` means the source path could not produce a diff (there is no separate `is_available` field).

**Validation / rules**:
- A `None` `ChangedElementSet` (the diff could not be produced for this path) ⇒ full recompute (FR-008, SC-005).
- `changed_fields` contains **every** element the diff reports as changed — no "value-affecting" filtering. Cosmetic edits (label, description, ordering) to a read element therefore select dependent attributes (FR-004, Q-D).
- A kind appearing in `added_kinds`/`removed_kinds` impacts any attribute whose dependency set reads that kind (FR-005).
- An attribute name in `changed_fields[kind]` that *is itself* a computed-attribute definition marks that attribute for recompute directly (FR-003).

**Maps to spec entity**: *Schema change*.

## Entity: DependencySet

For a single computed attribute, the schema elements its value reads — including those reached through relationships **at any depth**. Derived in-memory; not persisted.

| Field | Type | Notes |
|-------|------|-------|
| `owner_kind` | `str` | Kind that owns the computed attribute. |
| `attribute_name` | `str` | The computed attribute's name. |
| `kind` | `ComputedAttributeKind` | `JINJA2` or `TRANSFORM_PYTHON`. |
| `read_kinds` | `frozenset[str]` | Object-type kinds the value reads (owner + related, at any traversal depth). |
| `read_fields` | `Mapping[str, frozenset[str]]` | kind → attribute/relationship names read on that kind. |
| `depends_on_everything` | `bool` | `True` for the conservative cases (unanalyzable transform query; display-label/hfid dependency or a read kind the query analyzer cannot map to any concrete field; relationship depth/precision undeterminable) → always recompute (FR-006, FR-013). |

**Validation / rules**:
- Jinja2 derivation reuses `Jinja2ComputedRegistry` (`local_fields`, `relationship_dependencies`), following the chain to whatever depth the registry exposes; where depth/precision can't be determined, set `depends_on_everything` (FR-002, Q-B). Transform derivation parses the transform's GraphQL query via `GraphQLQueryAnalyzer` / `GraphQLQueryReport.requested_read`, which expresses reads at full depth.
- `depends_on_everything == True` short-circuits intersection (the attribute is always selected) but does **not** trigger a branch-wide full recompute — other attributes remain scoped (FR-013).
- The owner kind + attribute name is always part of the dependency set so that editing the attribute's own definition triggers recompute (FR-003).

**Maps to spec entity**: *Dependency set*.

## Entity: ComputedAttributeRef

Lightweight identity of a computed attribute, used in selected/skipped reporting and as the recompute job key.

| Field | Type | Notes |
|-------|------|-------|
| `branch` | `str` | Branch the attribute is scoped to. |
| `kind` | `str` | Owner object-type kind. |
| `attribute_name` | `str` | Attribute name. |
| `computed_kind` | `ComputedAttributeKind` | `JINJA2` or `TRANSFORM_PYTHON`. |

**Maps to spec entity**: *Computed attribute* (identity only; definition + per-object value remain as today).

## Entity: RecomputeScopingReport

The outcome of the scoping decision for one schema change on one branch. Logged for observability and consumed by the setup flows.

| Field | Type | Notes |
|-------|------|-------|
| `selected` | `list[ComputedAttributeRef]` | Attributes whose dependency set intersects the changed-element set (or whose `depends_on_everything` is true, or path-level fallback). Recompute is submitted for these. |
| `skipped` | `list[SkippedAttribute]` | Attributes deliberately not recomputed. |
| `fallback_full_recompute` | `bool` | `True` only when the changed-element set was unavailable for the whole path (FR-008); `selected` then contains all attributes. A per-attribute `depends_on_everything` does NOT set this flag (FR-013). |

### Sub-entity: SkippedAttribute

| Field | Type | Notes |
|-------|------|-------|
| `ref` | `ComputedAttributeRef` | The skipped attribute. |
| `reason` | `str` | e.g. `"no dependency on changed elements"`. |

**Validation / rules**:
- `selected` and `skipped` are disjoint and together cover every computed attribute considered for the branch (SC-002).
- Summary (`len(selected)` + identities) logged at info; `skipped` logged at debug (FR-012, SC-006).
- When `fallback_full_recompute` is `True`, `skipped` is empty.
- A single opaque attribute appears in `selected` (via its `depends_on_everything`) while unrelated attributes still appear in `skipped` — the report is the observable proof that FR-013 did not escalate to a full recompute.

## Relationships

```text
SchemaUpdatedEvent ──carries──▶ ChangedElementSet (optional)
                                       │
                                       ▼  (intersect with)
ComputedAttribute ──derives──▶ DependencySet ──┐
                                               ├──▶ RecomputeScopingReport { selected, skipped }
ChangedElementSet ─────────────────────────────┘            │
                                                            ▼
                                          submit recompute job per ComputedAttributeRef.selected
```

## State / lifecycle

No persistent state transitions. The lifecycle is per-schema-change and transient:

1. Schema change applied → `ChangedElementSet` built (or `None`).
2. Per computed attribute → `DependencySet` derived (cached per branch/schema version).
3. Intersection → `RecomputeScopingReport`.
4. `selected` → async recompute jobs submitted (existing per-object `process_jinja2` / `process_transform` flows, unchanged).
5. Report logged (info summary + debug skipped); structures discarded.
