# Contract: Recompute Scoping (internal backend interfaces)

**Date**: 2026-06-03 (regenerated for Session 2026-06-03 clarifications)
**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md)

This feature exposes no new external (REST/GraphQL) surface. The contracts below are **internal** Python interfaces. They are expressed as signatures + behavioral guarantees so implementation and tests can be written against them. (Per `dev/rules/code-doc-style.md`, the shipped source will not carry spec IDs — they appear here only.)

## 1. `SchemaUpdatedEvent` payload extension

**File**: `backend/infrahub/events/schema_action.py`

Add an optional changed-element set to the event. Backward compatible: existing emitters that pass nothing yield `None`.

```python
class SchemaUpdatedEvent(InfrahubEvent):
    branch_name: str
    schema_hash: str
    changed_elements: ChangedElementsPayload | None = None  # NEW
```

`ChangedElementsPayload` (Pydantic, JSON-serializable for Prefect workflow params):

```python
class ChangedElementsPayload(BaseModel):
    added_kinds: list[str]
    removed_kinds: list[str]
    changed_fields: dict[str, list[str]]  # kind -> changed attribute/relationship names
```

**Guarantees**:
- `changed_elements is None` ⇒ downstream MUST perform full recompute (FR-008).
- `changed_fields` carries every element the `SchemaDiff` reports as changed — no value-affecting filtering; cosmetic edits are included (FR-004).
- The payload MUST round-trip through `get_resource()` / Prefect workflow parameters (it is read in `triggers.py`).
- The two emitters that compute a `SchemaDiff` (`api/schema.py` schema load, `graphql/mutations/schema.py` interactive edit) populate it; branch deletion leaves it `None`. Merge and rebase do NOT emit `SchemaUpdatedEvent` — they emit `BranchMergedEvent`/`BranchRebasedEvent` plus per-node events — so this feature's schema-scoped recompute does not run on the merge/rebase path. This is unchanged from before the feature. Computed values stay correct on merge through the existing data-change recompute path (node events); a merge that applies only a schema change, with no object-data change, does not recompute.

## 2. Dependency deriver `Protocol`

**File**: `backend/infrahub/computed_attribute/scoping.py`

```python
class ComputedAttributeDependencyDeriver(Protocol):
    """Derive the dependency set for one kind of computed attribute."""

    def derive(
        self,
        *,
        computed_attribute: ComputedAttributeRef,
    ) -> DependencySet: ...
```

Two implementations:

- `Jinja2DependencyDeriver` — backed by `Jinja2ComputedRegistry` (`local_fields`, `relationship_dependencies`); follows relationship chains to whatever depth the registry exposes and sets `depends_on_everything=True` when depth/precision cannot be determined (FR-002).
- `PythonTransformDependencyDeriver` — parses the transform's GraphQL query via `GraphQLQueryAnalyzer` (`GraphQLQueryReport.requested_read`) at full depth; sets `depends_on_everything=True` when the query cannot be analyzed, reads `display_label`/`hfid`, or analyzes to a read kind with no mappable concrete field (e.g. a query selecting only a human-friendly id, which the analyzer drops rather than mapping to backing schema elements — without this it would look like a precise read of nothing and be skipped on every change).

**Guarantees**:
- `derive()` is side-effect-free and reads only from the dependency data injected at construction (Jinja2 trigger nodes / transform read sets) — no database or network access.
- `read_kinds` / `read_fields` reflect reads at any relationship depth the value expresses.
- The returned `DependencySet` MUST include the attribute's own `(owner_kind, attribute_name)` so a definition edit triggers recompute (FR-003).
- `depends_on_everything=True` MUST be set rather than raising when analysis is impossible (FR-006, FR-013).

## 3. Scoping component (single entry point)

**File**: `backend/infrahub/computed_attribute/scoping.py`

```python
class RecomputeScoper:
    def __init__(
        self,
        *,
        derivers: Mapping[ComputedAttributeKind, ComputedAttributeDependencyDeriver],
    ) -> None: ...

    def scope(
        self,
        *,
        candidate_attributes: Sequence[ComputedAttributeRef],
        changed_elements: ChangedElementSet | None,
    ) -> RecomputeScopingReport: ...
```

**Behavioral contract** (`scope`):

| Input condition | Required output | Requirement |
|-----------------|-----------------|-------------|
| `changed_elements is None` | `RecomputeScopingReport(selected=all candidates, skipped=[], fallback_full_recompute=True)` | FR-008, SC-005 |
| attribute's `DependencySet.depends_on_everything` | attribute in `selected`; `fallback_full_recompute` stays `False`; other attributes still evaluated normally | FR-006, FR-013 |
| attribute's `read_kinds` ∩ (`added_kinds` ∪ `removed_kinds`) ≠ ∅ | attribute in `selected` | FR-005 |
| ∃ kind: `read_fields[kind]` ∩ `changed_fields[kind]` ≠ ∅ | attribute in `selected` | FR-002, FR-004 |
| attribute's own `(owner_kind, attribute_name)` ∈ `changed_fields` | attribute in `selected` | FR-003 |
| none of the above | attribute in `skipped` with reason | FR-007, SC-001 |

**Invariants**:
- `selected` ∪ `skipped` == `candidate_attributes`, and `selected` ∩ `skipped` == ∅ (SC-002).
- A per-attribute `depends_on_everything` MUST NOT set `fallback_full_recompute` — one opaque attribute does not disable scoping for the branch (FR-013).
- Determinism: same inputs ⇒ same report.
- No DB or network access inside `scope()` (unit-testable).

## 4. Setup-flow integration

**File**: `backend/infrahub/computed_attribute/tasks.py`

`computed_attribute_setup_jinja2` and `computed_attribute_setup_python` MUST:

1. Read `changed_elements` from workflow parameters (threaded from the event via `triggers.py`).
2. Build the candidate attribute list for the branch (as today).
3. Call `RecomputeScoper.scope(...)`.
4. Submit `TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES` / `TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES` only for `report.selected`.
5. Log: info summary (`len(selected)` + identities); debug list of `report.skipped` with reasons (FR-012, SC-006).

**Guarantees**:
- Branch scoping (`registry.get_altered_schema_branches()`, `branches_out_of_scope`) is applied **before** and independently of changed-element scoping; no cross-branch broadening (FR-010). A test MUST assert this (Principle II).
- The merge/rebase path does not emit `SchemaUpdatedEvent`, so it neither populates `changed_elements` nor triggers this feature; a characterization test MUST assert that merging a branch schema change does not trigger schema-scoped recompute on the target branch (Principle II).
- The per-object job flows (`process_jinja2`, `process_transform`, `trigger_update_*`) are unchanged (async, eventually consistent — FR-011).
- `BranchDeletedEvent` continues to flow through with `changed_elements is None` ⇒ full recompute (edge case: branch deletion).
