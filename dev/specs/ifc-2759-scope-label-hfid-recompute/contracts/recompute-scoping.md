# Contract: Display-label & HFID recompute scoping (internal backend interfaces)

**Date**: 2026-06-19 · **Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md)

This feature exposes no new external (REST/GraphQL) surface. The contracts below are **internal** Python interfaces, expressed as signatures + behavioral guarantees so implementation and tests can be written against them. Per `dev/rules/code-doc-style.md`, shipped source carries no spec IDs — they appear here only.

## 1. Shared scoping core — relocation

**From**: `backend/infrahub/computed_attribute/scoping.py`
**To**: `backend/infrahub/core/schema/recompute_scoping.py`

Moved (shape-preserving, generalized where noted in `data-model.md`): `ChangedElementSet`, `DependencySet`, `RecomputeCandidate` (new generic), `DependencyDeriver` (protocol, generalized), `RecomputeScoper`, `RecomputeScopingReport`, `SkippedCandidate`, `_resolve_changed_elements`, and `IMPRECISE_READ_FIELDS`.

**Guarantees**:
- `computed_attribute`, `display_labels`, `hfid` import these from `core.schema.recompute_scoping`. No feature package imports another feature package for scoping.
- The move is behavior-preserving: existing `backend/tests/unit/computed_attribute/test_scoping.py` and `backend/tests/component/computed_attribute/test_scoped_recompute_*.py` pass unchanged (adapting only import paths / `ComputedAttributeRef` shape, not assertions).

## 2. `RecomputeScoper` (single entry point) — generalized

**File**: `backend/infrahub/core/schema/recompute_scoping.py`

```python
class RecomputeScoper:
    def __init__(self, *, derivers: Mapping[str, DependencyDeriver]) -> None: ...

    def scope(
        self,
        *,
        candidates: Sequence[RecomputeCandidate],
        changed_elements: ChangedElementSet | None,
    ) -> RecomputeScopingReport: ...
```

**Behavioral contract** (`scope`) — unchanged decision logic, generalized over candidate type:

| Input condition | Required output | Requirement |
|-----------------|-----------------|-------------|
| `changed_elements is None` | `selected = all candidates`, `skipped = []`, `fallback_full_recompute = True` | FR-006, SC-005 |
| candidate's `DependencySet.depends_on_everything` | candidate in `selected`; `fallback_full_recompute` stays `False`; others still evaluated | FR-005 |
| `read_kinds ∩ (added_kinds ∪ removed_kinds) ≠ ∅` | candidate in `selected` | FR-003 |
| `∃ kind: read_fields[kind] ∩ changed_fields[kind] ≠ ∅` | candidate in `selected` | FR-001, FR-002, FR-004 |
| none of the above | candidate in `skipped` with reason | FR-001, FR-002, SC-001 |

**Invariants**: `selected ∪ skipped == candidates`; `selected ∩ skipped == ∅`; per-candidate `depends_on_everything` does not set `fallback_full_recompute`; deterministic; no DB/network in `scope()`.

## 3. `DependencyDeriver` implementations — new

**Files**: `backend/infrahub/display_labels/scoping.py`, `backend/infrahub/hfid/scoping.py`

```python
class DisplayLabelDependencyDeriver:        # backed by DisplayLabels registry + DerivedFieldLookup
    def __init__(self, *, template_nodes: Mapping[str, TemplateLabel],
                 peer_kinds: Mapping[tuple[str, str], str],
                 derived_fields: DerivedFieldLookup) -> None: ...
    def derive(self, *, candidate: RecomputeCandidate) -> DependencySet: ...

class HFIDDependencyDeriver:                 # backed by HFIDs registry + DerivedFieldLookup
    def __init__(self, *, definitions: Mapping[str, HFIDDefinition],
                 peer_kinds: Mapping[tuple[str, str], str],
                 derived_fields: DerivedFieldLookup) -> None: ...
    def derive(self, *, candidate: RecomputeCandidate) -> DependencySet: ...
```

**Guarantees** (both):
- `derive()` is side-effect-free; reads only the injected metadata (no DB/network).
- The returned `DependencySet.read_fields[owner_kind]` MUST include the owner's own definition token (`"display_labels"` / `"human_friendly_id"`) so a definition edit recomputes the kind (FR-004).
- `read_fields` / `read_kinds` MUST cover owner attributes, traversed relationships, and peer fields reached through them (FR-003).
- `depends_on_everything=True` MUST be set (never raise) when any read field satisfies `DerivedFieldLookup.is_derived(...)` — a peer's `display_label`/`hfid`, or a computed attribute on the read kind (FR-005).
- Construction inputs are required (no optional collaborators) per `dev/rules/backend-component-design.md`.

## 4. Setup-flow integration

**Files**: `backend/infrahub/display_labels/tasks.py` (`display_labels_setup_jinja2`), `backend/infrahub/hfid/tasks.py` (`hfid_setup`)

Each flow MUST:

1. Accept `changed_elements: ChangedElementsPayload | None = None` and normalize via the shared `_resolve_changed_elements`.
2. Build the candidate list for the branch (one candidate per kind that defines a display label / HFID).
3. Construct the deriver (with the per-branch `DerivedFieldLookup`) and call `RecomputeScoper.scope(...)`.
4. Proceed with the existing per-kind hash check + node sweep **only** for `report.selected` kinds.
5. Log at info: selected count, total candidate count, and `fallback_full_recompute` (distinguish precise scoping from fallback — FR-009). Log skipped candidates + reasons at debug.

**Guarantees**:
- `changed_elements is None` ⇒ every kind that would recompute today still does; the per-kind hash check and per-node sweep are byte-for-byte unchanged (FR-006, FR-010, SC-005).
- Branch scoping is applied before and independently of changed-element scoping; no cross-branch broadening (a test asserts this — Constitution II).
- The per-node job flows (`process_display_label`, `process_hfid`, `trigger_update_display_labels`, `trigger_update_hfid`) are unchanged.
- `BranchDeletedEvent` continues to flow with `changed_elements is None` ⇒ full recompute.

## 5. Trigger wiring

**Files**: `backend/infrahub/display_labels/triggers.py` (`TRIGGER_DISPLAY_LABELS_ALL_SCHEMA`), `backend/infrahub/hfid/triggers.py` (`TRIGGER_HFID_ALL_SCHEMA`)

Add the `changed_elements` Prefect parameter to each `ExecuteWorkflow`, mirroring `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA`:

```jinja
"changed_elements": {
  "__prefect_kind": "json",
  "value": {"__prefect_kind": "jinja",
            "template": "{{ event.payload['data']['changed_elements'] | default(none, true) | tojson }}"}
}
```

**Guarantees**: the payload round-trips through Prefect workflow parameters and is deserialized to `ChangedElementsPayload | None` at the flow boundary; absence yields `None`.

## Out of scope (sibling tickets)

- Merge/rebase paths emitting `changed_elements` — IFC-2758 / IFC-2761.
- Per-node short-circuit before render/transform — IFC-2762.
- Performance benchmarks for scoping — IFC-2746.
- Transform computed attributes on Git import — IFC-2760.
- Precise transitive resolution of derived reads (this feature is conservative: derived read ⇒ recompute always).
