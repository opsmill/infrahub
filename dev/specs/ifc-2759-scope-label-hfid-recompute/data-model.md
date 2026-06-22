# Phase 1 Data Model: Scope display label and HFID recompute on schema updates

**Date**: 2026-06-19 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

No persisted (Neo4j) data model changes. All entities are in-memory, derived per-branch from the active `SchemaBranch`, and transported via existing event/workflow payloads. Types are frozen dataclasses (internal) or Pydantic (transport), per Constitution III.

## Existing types reused (from PR #9467)

These move to `backend/infrahub/core/schema/recompute_scoping.py` unchanged in shape:

### `ChangedElementsPayload` (Pydantic, transport — stays in `events/schema_action.py`)

```python
class ChangedElementsPayload(BaseModel):
    added_kinds: list[str]
    removed_kinds: list[str]
    changed_fields: dict[str, list[str]]   # kind -> changed attribute/relationship/property names
```

Already populated on `SchemaUpdatedEvent`. `None` ⇒ full recompute. Node-level definition properties (`display_labels`, `human_friendly_id`) appear in `changed_fields[kind]` under their own name (see research R1).

### `ChangedElementSet` (frozen dataclass, internal)

```python
@dataclass(frozen=True)
class ChangedElementSet:
    added_kinds: frozenset[str]
    removed_kinds: frozenset[str]
    changed_fields: Mapping[str, frozenset[str]]

    @classmethod
    def from_payload(cls, payload: ChangedElementsPayload) -> ChangedElementSet: ...
```

### `DependencySet` (frozen dataclass, internal)

```python
@dataclass(frozen=True)
class DependencySet:
    owner_kind: str
    name: str                                   # derived value identity (attribute name / "display_labels" / "human_friendly_id")
    read_kinds: frozenset[str] = frozenset()
    read_fields: Mapping[str, frozenset[str]] = field(default_factory=dict)
    depends_on_everything: bool = False
```

> Generalized from the computed-attribute version: `attribute_name` → `name`, `kind` (enum) dropped from the set itself (moved to the candidate). The own field (`owner_kind`, `name`) is always present in `read_fields[owner_kind]`.

### `RecomputeScopingReport` / `SkippedAttribute` (frozen dataclasses, internal)

```python
@dataclass(frozen=True)
class SkippedCandidate:           # renamed from SkippedAttribute (generalized)
    candidate: RecomputeCandidate
    reason: str

@dataclass(frozen=True)
class RecomputeScopingReport:
    selected: list[RecomputeCandidate]
    skipped: list[SkippedCandidate]
    fallback_full_recompute: bool
```

## New / generalized types

### `RecomputeCandidate` (frozen dataclass, internal) — NEW

```python
@dataclass(frozen=True)
class RecomputeCandidate:
    branch: str
    kind: str            # owner kind
    name: str            # derived-value identity: attribute name, or "display_labels" / "human_friendly_id"
    deriver_key: str     # selects the deriver in RecomputeScoper.derivers
```

`ComputedAttributeRef` is retained for the computed-attribute call sites and adapts to this shape (keeps `branch`, `kind`, `attribute_name`, `computed_kind`; exposes `name`/`deriver_key` so existing tests and code keep working).

**Deriver keys** (string constants):

| Subsystem | `deriver_key` | `name` value |
|-----------|---------------|--------------|
| Computed attr (Jinja2) | `computed_attribute.jinja2` | attribute name |
| Computed attr (Python) | `computed_attribute.python` | attribute name |
| Display label | `display_label` | `"display_labels"` |
| HFID | `hfid` | `"human_friendly_id"` |

### `DependencyDeriver` (Protocol, internal) — generalized

```python
class DependencyDeriver(Protocol):
    def derive(self, *, candidate: RecomputeCandidate) -> DependencySet: ...
```

Implementations: `Jinja2DependencyDeriver`, `PythonTransformDependencyDeriver` (existing, signature adapted), `DisplayLabelDependencyDeriver` (new), `HFIDDependencyDeriver` (new).

### `DerivedFieldLookup` (frozen dataclass, internal) — NEW

Injected into the display-label and HFID derivers so they can flag reads of derived values (research R5).

```python
@dataclass(frozen=True)
class DerivedFieldLookup:
    computed_attributes: frozenset[tuple[str, str]]   # (kind, attribute_name) pairs that are computed
    imprecise_read_fields: frozenset[str] = IMPRECISE_READ_FIELDS   # {"display_label", "hfid"}

    def is_derived(self, *, kind: str, field: str) -> bool:
        return field in self.imprecise_read_fields or (kind, field) in self.computed_attributes
```

## Entity relationships

```text
SchemaUpdatedEvent ──carries──> ChangedElementsPayload ──from_payload──> ChangedElementSet
                                                                              │
RecomputeCandidate ──deriver_key selects──> DependencyDeriver ──derive──> DependencySet
                                                   │ (display/hfid)             │
                                          DerivedFieldLookup ─────────────────┘ (sets depends_on_everything)
                                                                              │
RecomputeScoper.scope(candidates, ChangedElementSet) ──intersect──> RecomputeScopingReport
                                                                       ├─ selected ─> submit recompute (existing per-kind sweep)
                                                                       └─ skipped  ─> info/debug log
```

## Validation / invariants

- `selected ∪ skipped == candidates`; `selected ∩ skipped == ∅`.
- A per-candidate `depends_on_everything` selects that candidate but MUST NOT set `fallback_full_recompute` (one opaque candidate does not disable scoping for the branch).
- `changed_elements is None` ⇒ `selected == candidates`, `fallback_full_recompute == True`.
- `derive()` is pure: reads only injected data (registries / lookups), no DB or network.
- Display-label and HFID candidates for the same kind are independent rows; a change touching one does not select the other (FR-007).
