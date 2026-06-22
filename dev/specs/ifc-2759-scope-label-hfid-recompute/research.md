# Phase 0 Research: Scope display label and HFID recompute on schema updates

**Date**: 2026-06-19 · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

All findings are grounded in the current `develop` tree (PR #9467 already merged). File:line references are anchors, not contracts.

## R1. Does the change-set payload capture display-label / HFID definition edits? (resolves the load-bearing assumption)

**Decision**: Yes. The deriver's own-definition dependency uses the NodeSchema property tokens `display_labels` (display labels) and `human_friendly_id` (HFIDs).

**Evidence**:
- `build_changed_elements_payload` (`backend/infrahub/events/schema_action.py:30-59`) flattens attribute/relationship element buckets but keeps **node-level scalar fields under their own name** (`else: names.add(field_name)`, line 51-52).
- NodeSchema defines these node-level properties: `human_friendly_id: list[str] | None` (`backend/infrahub/core/schema/generated/base_node_schema.py:56`) and `display_labels: list[str] | None` (line 66).
- Therefore an edit to a kind's display-label or HFID definition surfaces in `changed_fields[kind]` as `"display_labels"` / `"human_friendly_id"`.

**Consequence**: `DisplayLabelDependencyDeriver` must include `"display_labels"` in `read_fields[owner_kind]`; `HFIDDependencyDeriver` must include `"human_friendly_id"`. This satisfies FR-004.

**Verification task**: a unit test asserts that editing only the definition yields a `changed_fields` entry containing the exact token, and that the deriver's set intersects it. Do not hardcode the token in two places without that test — if the diff ever keys these differently, the test fails loudly rather than silently skipping recompute.

## R2. How to generalize the scoper without breaking the computed-attribute path

**Decision**: Extract the candidate-generic core to `backend/infrahub/core/schema/recompute_scoping.py`; keep the Jinja2/Python derivers in `computed_attribute/scoping.py` importing from core. Make the scoper accept a generic `RecomputeCandidate` and select derivers by a string `deriver_key`.

**Rationale**:
- The current `RecomputeScoper.scope()` keys derivers by `ComputedAttributeKind` and reads `candidate.kind` / `candidate.attribute_name` for the own-definition check (`computed_attribute/scoping.py:112-184`). Generalizing the key to a string and the candidate to `{branch, kind, name, deriver_key}` removes the computed-attribute coupling while preserving the decision logic verbatim.
- `ComputedAttributeRef` is retained (its existing fields) and adapted to the generic candidate so the existing unit tests (`backend/tests/unit/computed_attribute/test_scoping.py`) and component tests (`test_scoped_recompute_jinja2.py`, `test_scoped_recompute_python.py`) keep compiling and passing — this is the behavior-preserving guard.
- Module direction: `core/schema` is imported by feature packages, never the reverse. Putting the core in `computed_attribute` would force `display_labels`/`hfid` to depend on an unrelated feature.

**Alternatives considered**:
- *Import the core from `computed_attribute`*: rejected — backwards dependency, violates the layering the rest of the codebase follows.
- *Reuse `ComputedAttributeRef` with synthetic attribute names (`"display_label"`)*: rejected — overloads a computed-attribute type for non-attributes; confusing in reports and logs.
- *A second, parallel scoper*: rejected by Constitution VII (no parallel implementation of the same decision) and the ticket's own "generalize the scoper" instruction.

**IMPRECISE_READ_FIELDS placement**: currently `frozenset({"display_label", "hfid"})` in `schema_branch_computed/python_transform.py:19`, imported by `computed_attribute/scoping.py:20`. Since three deriver families now consult it, relocate it to `core/schema/recompute_scoping.py` and re-import where used. Behavior-preserving.

## R3. Display-label dependency derivation

**Decision**: `DisplayLabelDependencyDeriver.derive(candidate)` maps `TemplateLabel` → `DependencySet`:
- `read_fields[owner_kind]` = `attributes ∪ {"display_labels"}` (own definition).
- For each relationship in `relationships`, add the relationship name to `read_fields[owner_kind]` and the peer fields from `relationship_fields[rel]` to `read_fields[peer_kind]`, with `peer_kind` resolved from the schema.
- `read_kinds` = owner kind ∪ peer kinds reached.
- `depends_on_everything=True` when any read field is a derived value (see R5).

**Evidence**: `TemplateLabel{template, attributes, relationships, relationship_fields, get_hash}` and the `DisplayLabels` registry accessors (`get_template_nodes()`, `get_related_trigger_nodes()`, `get_related_template()`) in `backend/infrahub/core/schema/schema_branch_display.py:12-135`. The inverse relationship triggers (`RelationshipTriggers`) already encode "peer kind change → owner recompute", which is the same edge the dependency intersection needs.

**Candidate source**: the kinds with a display label come from `DisplayLabels.get_template_nodes()`; the setup flow already enumerates these.

## R4. HFID dependency derivation

**Decision**: `HFIDDependencyDeriver.derive(candidate)` maps `HFIDDefinition` → `DependencySet` identically to R3, with `"human_friendly_id"` as the own-definition token and `relationship_fields` for peer reads.

**Evidence**: `HFIDDefinition{hfid, attributes, relationships, relationship_fields, filter_key, fields, has_related_components, get_hash}` and the `HFIDs` registry (`get_node_definition()`, `get_template_nodes()`, `get_related_trigger_nodes()`, `get_related_definition()`) in `backend/infrahub/core/schema/schema_branch_hfid.py:12-120`. HFID composition is a list of schema paths (`["name__value", "owner__name__value"]`) decomposed into `attributes` / `relationships` / `relationship_fields` at registration (`register_hfid_schema_path`, lines 63-91) — the same shape the display-label path uses, which is why one deriver implementation pattern serves both.

**Divergence from display labels (R5)**: HFID path components are plain attribute names with no marker for "this attribute is itself computed", so the derived-value check must consult the schema's computed-attribute set, not just `IMPRECISE_READ_FIELDS`.

## R5. Transitive / derived-value hazard

**Decision**: A deriver marks `depends_on_everything=True` when any read field resolves to a derived value on its kind. "Derived value" = the pseudo-fields `display_label` / `hfid` (a peer's computed identity, matched against `IMPRECISE_READ_FIELDS`) **or** a computed attribute defined on the read kind. Inject a `derived_fields` lookup — `set[tuple[str, str]]` of `(kind, field_name)` for computed attributes, plus the `IMPRECISE_READ_FIELDS` tokens — built once per branch from the schema and passed to the deriver at construction.

**Rationale**: Correctness over precision (FR-005, Constitution IV/V tie-break toward correctness). The existing computed-attribute Jinja2 deriver already uses the `IMPRECISE_READ_FIELDS` shortcut (`computed_attribute/scoping.py:271`); this generalizes the same posture and additionally covers an HFID/display-label that reads a computed attribute — which the spec explicitly calls out.

**Alternatives considered**:
- *Precise transitive resolution (recurse into the derived value's own dependencies)*: rejected for this ticket — higher complexity and risk; the conservative "always recompute" is correct and matches #9467's posture. A future precision pass can replace it without changing the contract.
- *Ignore the computed-attribute-read case (only check `IMPRECISE_READ_FIELDS`)*: rejected — leaves a real staleness hole for HFIDs/labels reading a computed attribute, which FR-005 forbids.

**Scope note**: this is the only genuinely new logic versus the computed-attribute path and the documented divergence point if HFID detection proves harder than display-label detection (the ticket allows a split; the plan keeps them together because the `derived_fields` lookup serves both).

## R6. Threading `changed_elements` into the setup flows

**Decision**: Mirror `TRIGGER_COMPUTED_ATTRIBUTE_ALL_SCHEMA` exactly.

**Evidence / pattern**: `computed_attribute/triggers.py:29-70` passes `changed_elements` via a Prefect Jinja parameter (`{{ event.payload['data']['changed_elements'] | default(none, true) | tojson }}`), and `computed_attribute_setup_jinja2/python` accept `changed_elements: ChangedElementsPayload | None = None` and normalize via `_resolve_changed_elements` (`computed_attribute/tasks.py:85-97`). The display-label and HFID triggers (`display_labels/triggers.py:6-22`, `hfid/triggers.py:6-22`) currently omit this parameter; the setup flows (`display_labels/tasks.py:136`, `hfid/tasks.py:131`) omit the argument.

**Decision detail**: move `_resolve_changed_elements` to the shared `core/schema/recompute_scoping.py` so all three flows use one normalizer.

## R7. Interaction with the existing hash-vs-default check

**Decision**: Scoping is an additional filter applied **before** the existing per-kind hash check and node sweep. A kind is processed only if (a) its dependency set intersects the change set (or it depends on everything / the change set is `None`), and then (b) the existing hash check still applies as today.

**Evidence**: display labels skip a kind unless its `template_hash` differs from default (`display_labels/tasks.py:162-178`); HFID compares `hfid_hash` (`hfid/tasks.py:154-171`). These are orthogonal to dependency scoping and stay in place. The new scoping only narrows the candidate set fed into that existing logic; on the `None` fallback path the candidate set is unchanged, so behavior is identical (SC-005).

## R8. Test strategy

**Decision**:
- **Unit** (`tests/unit/display_labels/test_scoping.py`, `tests/unit/hfid/test_scoping.py`): exercise each deriver and the generic scoper with a `CannedDeriver`-style fixture (the pattern in `tests/unit/computed_attribute/test_scoping.py`). Cases: hit via own definition, via owner attribute, via relationship peer field, via added/removed kind; skip on no overlap; `depends_on_everything` always selected; `changed_elements is None` → fallback.
- **Component** (`tests/component/display_labels/test_scoped_recompute.py`, `tests/component/hfid/test_scoped_recompute.py`): mirror `tests/component/computed_attribute/test_scoped_recompute_jinja2.py` using `ScopedRecomputeTestBase` + `WorkflowRecorder`; assert submitted kinds for an unrelated change (zero) vs. a read-field change (recomputed), including across a relationship.
- **Fallback guard**: the existing `tests/functional/display_labels/test_display_label_task_optimization.py` and `tests/functional/hfid/test_hfid_task_optimization.py` (which assert the full sweep) must pass unchanged on the `changed_elements is None` path.
- **integration_docker**: one assertion that a scoped schema change refreshes only the affected kinds' labels/HFIDs end-to-end (Constitution IV requires integration_docker for triggered-action paths).

**Rationale**: reuses established adapters (`WorkflowRecorder`, `ScopedRecomputeTestBase`) per Constitution IV (no mocks; adapter pattern). No new test infrastructure.

## Open items carried into tasks

- Confirm the exact peer-kind resolution from a relationship name in both registries (whether the deriver reads peer kind from `RelationshipIdentifier`/`relationship_fields` or must look it up on the schema). Cheap to resolve at implementation; does not change the contract.
- Confirm `BranchDeletedEvent` continues to flow as `changed_elements is None` for both subsystems (it shares the trigger event set) — full recompute on branch deletion is the intended fallback.
