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
