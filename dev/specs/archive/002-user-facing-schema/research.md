# Research: User-Facing Schema Separation

Phase 0 decisions. All resolved; no open NEEDS CLARIFICATION blocking planning (the one remaining spec marker — SC-004 benchmark target — is a product metric, not a technical unknown).

## D1 — How to produce three model families from one source

**Decision**: Parameterize generation by `visibility` and emit write/read families in addition to the existing internal family, from the same `internal.py` definitions, via the existing Jinja generator.

**Rationale**: The generator (`tasks/backend.py::_generate_schemas`) already renders all model files from a single template (`backend/templates/generate_schema.j2`) parameterized by `schema`/`node`/`parent`. Adding a `visibility` filter over `node.attributes` (and the structural relationships) plus a variant name is a localized extension. The `without_duplicates()` base/derived split already in place is reused per variant.

**Alternatives considered**:
- *Runtime filtering of one model* — rejected: cannot produce a JSON-schema that omits non-write fields (agents read the omitted-field contract), and cannot reuse `extra="forbid"` for rejection.
- *Hand-written second model set* — rejected: violates single-source (Principle VII) and reintroduces drift.

## D2 — Where the classification lives

**Decision**: Extend `ExtraField` (TypedDict) in `internal.py` with a `visibility` key (an ordinal enum `internal < read < write`), set it per `SchemaAttribute`/`SchemaRelationship`, default `internal` when unset. Orthogonal to the existing `update:` axis.

**Rationale**: `extra={}` already flows into generation end-to-end (proven by `update:` → `json_schema_extra`). Reusing it keeps the change in one place. The resolved per-field mapping is in `schema-field-classification.md`.

**Alternatives considered**: a separate parallel table keyed by field name — rejected: drifts from the definitions it describes.

## D3 — How rejection of non-write fields works

**Decision**: Rely on the existing `model_config = ConfigDict(extra="forbid")` on `SchemaRoot` and node models. The write model simply omits `read`/`internal` fields; submitting them then triggers Pydantic's extra-field rejection, which names the field. Add a targeted check only where the message needs to be clearer (e.g. distinguishing "read-only field" from "unknown field").

**Rationale**: `extra="forbid"` is already enforced (`core/schema/__init__.py:64`). This means most of FR-003 is achieved structurally by generating the right write shape — minimal new validation code. Confirmed: unknown fields are already rejected today; the bug is only that `inherited`/etc. are *known* fields on the current model.

**Alternatives considered**: a bespoke `model_validator(mode="before")` enumerating disallowed fields — kept as a thin enhancement only for message quality, not as the primary mechanism.

## D4 — How to propagate enums / allowed-value sets

**Decision**: Render the allowed-value set into the write/read field so it appears in the emitted JSON-schema. For fields whose `internal_kind` is an Enum class (e.g. `BranchSupportType`, `RelationshipKind`, `RelationshipCardinality`, `RelationshipDirection`, `RelationshipDeleteBehavior`, `AllowOverrideType`, `SchemaAttributeDisplay`, `HashableModelState`), type the field as that enum. For list-backed sets (`ATTRIBUTE_KIND_LABELS`), render a `Literal[...]` (or attach `json_schema_extra={"enum": [...]}`) so the JSON-schema carries the values.

**Rationale**: Today the template drops `enum=` entirely and relies on a runtime `field_validator` (`attribute_schema.py:104`) that only fires internally. Putting the constraint in the write/read model means the JSON-schema an agent reads is complete (FR-004/SC-002) and validation is automatic on both server and SDK.

**Alternatives considered**: keep bare `str` + document allowed values elsewhere — rejected: defeats the feature's core purpose (machine-readable completeness).

## D5 — Backend consumes SDK-hosted write/read models

**Decision**: Generate write/read models into `python_sdk/infrahub_sdk/schema/`, replacing the SDK's current hand-written schema models. The backend's `api/schema.py` imports these SDK models for `/api/schema/load` validation and `/api/schema` serialization, replacing the current `SchemaLoadAPI(SchemaRoot)` / `APINodeSchema(NodeSchema)` derivations. The rich **internal** models in `backend/infrahub/core/schema/` stay as-is.

**Rationale**: This is the explicit PRD decision (single implementation → parity). It inverts today's direction (backend currently owns models; SDK mirrors them) but is safe because generation is a dev-time step and the `protocols.py`-into-SDK precedent already exists. The backend keeps depending on the SDK at runtime (already the case via the editable path dependency).

**Risk / dependency**: the `python_sdk` submodule is **not checked out in this worktree**. An audit-and-replace of the SDK's existing `NodeSchemaAPI`/`SchemaRootAPI`/`GenericSchemaAPI` models must happen against the checked-out submodule (first implementation task). Build ordering: `backend.generate` reads backend `internal.py` → writes SDK schema files → backend imports them. `APISchemaMixin.set_kind` (injects `kind` from `namespace`+`name`, `mode="before"`) stays compatible and moves to sit with the read model.

**Alternatives considered**: two generated copies (backend + SDK) — rejected per Complexity Tracking (drift-review burden).

## D6 — Backward compatibility & round-trip

**Decision**: Accept that read-modify-write round-trips via the API break this cycle (read-only fields now rejected on load); document the mitigation (clients strip against the published write schema); defer the write-shaped export to a later cycle.

**Rationale**: Matches the spec's edge-case analysis; the dominant authoring path is write-shaped YAML. Stored-schema read-back stays safe because read ⊇ write.

## Prior art (tests to extend)

- `backend/tests/functional/api/test_load_schema.py` — load endpoint (idempotency, absent/delete, extensions).
- `backend/tests/component/api/test_40_schema.py` — GET /api/schema read.
- `backend/tests/component/core/test_schema.py` — model validation + deprecation warnings.
- SDK submodule schema tests — for offline validation.

## SDK audit (T002)

Audited `python_sdk/infrahub_sdk/schema/` at submodule commit `38216f3` (`v1.13.2-939-g38216f3`). The data models live in `main.py`; `__init__.py` re-exports them and adds the `InfrahubSchema[Sync]` client and type aliases; `export.py`/`repository.py` are adjacent (repository config is out of scope for this feature).

### The SDK already ships two parallel model families

This is the central finding: the SDK **already** splits write vs read by hand, so the planned generated write/read split maps onto existing structure rather than inventing it.

| Concern | Write / input (no suffix) | Read / API (`API` suffix) |
|---|---|---|
| Root | `SchemaRoot` (`version`, `generics`, `nodes`, `node_extensions`) | `SchemaRootAPI` (`main` hash, `generics`, `nodes`, `profiles`, `templates`) |
| Node | `NodeSchema` | `NodeSchemaAPI` (+ `hash`, `hierarchy`) |
| Generic | `GenericSchema` | `GenericSchemaAPI` (+ `hash`, `hierarchical`, `used_by`, `restricted_namespaces`) |
| Attribute | `AttributeSchema` | `AttributeSchemaAPI` (+ `inherited`, `read_only`, `allow_override`) |
| Relationship | `RelationshipSchema` | `RelationshipSchemaAPI` (+ `inherited`, `read_only`, `hierarchical`, `allow_override`) |
| Attr/rel container | `BaseSchemaAttrRel` | `BaseSchemaAttrRelAPI` |
| Profile / Template | — (read-only concepts) | `ProfileSchemaAPI`, `TemplateSchemaAPI` |
| Shared base | `BaseSchema`, `BaseNodeSchema` (shared by both) | same |

Mapping to the planned generated models: **write model ⇐ the no-suffix family**, **read model ⇐ the `API` family**. The read family is a strict superset of write (read ⊇ write), matching D6. `NodeSchema.convert_api()` / `GenericSchema.convert_api()` already do write→read upcasting.

### Fields (write vs the read-only additions)

- `AttributeSchema` (write): `id, state, name, kind, label, description, default_value, unique, branch, optional, choices, enum, max_length, min_length, regex, order_weight`. Read adds `inherited, read_only, allow_override`.
- `RelationshipSchema` (write): `id, state, name, peer, kind, label, description, identifier, min_count, max_count, direction, on_delete, cardinality, branch, optional, order_weight`. Read adds `inherited, read_only, hierarchical, allow_override`.
- `BaseSchema` (shared): `id, state, name, label, namespace, description, include_in_menu, menu_placement, display_label, display_labels, human_friendly_id, icon, uniqueness_constraints, documentation, order_by`.
- `BaseNodeSchema` (shared): + `inherit_from, branch, default_filter, generate_profile, generate_template, parent, children`. `NodeSchemaAPI` read-adds `hash, hierarchy`.
- `GenericSchemaAPI` read-adds `hash, hierarchical, used_by, restricted_namespaces`.

### `model_config`

Every model uses `model_config = ConfigDict(use_enum_values=True)` — and nothing else. Notably **none of these models set `extra="forbid"`** (only the unrelated `repository.py` config models do). So the SDK today does **not** reject unknown fields — that strictness is new work (T013/T019). The generated write/read models must preserve `use_enum_values=True` (or equivalently serialize enums to values).

### Enums (defined in `main.py`, referenced by fields)

`RelationshipCardinality`, `BranchSupportType`, `RelationshipKind`, `RelationshipDirection`, `AttributeKind`, `SchemaState`, `AllowOverrideType`, `RelationshipDeleteBehavior`. Caveat: `AttributeKind` has a custom `__getattr__` emitting a `DeprecationWarning` for `STRING`; generation must not clobber that behavior. This is the enum inventory T007 must propagate into the generated JSON-schema.

### Behavior attached to the models (the main T020 risk)

The `API` models are **not** plain data — they carry substantial behavior that generated Pydantic models will not have:

- `BaseSchemaAttrRelAPI`: ~15 helpers — `get_field`, `get_attribute[_or_none]`, `get_relationship[_or_none]`, `get_relationship_by_identifier`, `get_matching_relationship`, and properties `attribute_names`, `relationship_names`, `mandatory_input_names`, `mandatory_attribute_names`, `mandatory_relationship_names`, `local_attributes`, `local_relationships`, `unique_attributes`.
- `BaseSchema`: properties `kind`, `supports_artifact_definition`, `supports_artifacts`, `supports_file_object`, `supports_hierarchy`, `hierarchical_relationship_schemas` (default/overridable).
- `NodeSchemaAPI`: overrides `supports_artifacts/file_object/hierarchy` and `hierarchical_relationship_schemas` (synthesizes parent/children/ancestors/descendants pseudo-relationships).
- `RelationshipSchemaAPI`: `cardinality_is_one` / `cardinality_is_many`.
- `SchemaRoot.to_schema_dict()`, `BranchSchema.from_api_response` / `from_schema_root_api`.

Implication for T020: a pure code-gen swap will drop these methods. The removal must either (a) generate plain data base models and keep hand-written behavior subclasses/mixins that inherit them, or (b) move the behavior onto wrappers. This is the biggest design decision deferred to T020 and should be settled before that chunk.

### In-SDK consumers (22 files)

Public surface is `infrahub_sdk.schema.__all__` (17 names) plus deep imports from `infrahub_sdk.schema.main`. Type aliases in `__init__.py`: `MainSchemaTypes = NodeSchema | GenericSchema` (write), `MainSchemaTypesAPI = NodeSchemaAPI | GenericSchemaAPI | ProfileSchemaAPI | TemplateSchemaAPI` (read), `MainSchemaTypesAll`. Consumers include `client.py`, `node/*` (`node.py`, `relationship.py`, `attribute.py`, `related_node.py`), `ctl/*` (schema, render, transform, repository, generator, check, utils, object/*, cli_commands), `spec/object.py`, `transfer/*`, `graphql/query_renderer.py`, `protocols_generator/generator.py`, `protocols_base.py`, `query_groups.py`, `pytest_plugin/utils.py`, `testing/schemas/*`. T020 must keep these import paths stable "where feasible" — favour re-exporting generated models under the same names in `schema/main.py` / `schema/__init__.py`.

### Discrepancies to fix during generation (T006/T007)

- `RelationshipSchema.cardinality: str = "many"` is a bare `str`, not the `RelationshipCardinality` enum — generation (T007) should emit the enum/`Literal`. Existing gap.
- Write `SchemaRoot` and read `SchemaRootAPI` are **not symmetric** (`version`/`node_extensions` vs `main`/`profiles`/`templates`). The generated write root should reflect the load contract (`version` + `nodes`/`generics`), not mirror the read root.
- `NodeExtensionSchema` exists on the write side (`SchemaRoot.node_extensions`) with no read equivalent; decide whether the generated write model retains node-extensions or the load path keeps a hand-written extension model.

## Towncrier setup (T003)

`[tool.towncrier]` in `pyproject.toml`: fragments live in `changelog/` with orphan prefix `+`, template `changelog/towncrier.md.template`, filename `CHANGELOG.md`. Fragment naming is `+<slug>.<type>.md`.

Valid fragment **types**: `security`, `removed`, `deprecated`, `added`, `changed`, `fixed`, `housekeeping`.

There is **no dedicated "breaking" type**. The T027 breaking-change fragment for the stricter `POST /api/schema/load` behaviour should therefore use type **`changed`** (`changelog/+<slug>.changed.md`), consistent with existing fragments (e.g. `+graphql-error-catalogue.changed.md`).
