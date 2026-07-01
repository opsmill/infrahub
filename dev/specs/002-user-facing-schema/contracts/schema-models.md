# Contract: Generated Schema Models (write / read / internal)

Defines the shape and generation rules for the three model families. Consumers:
the backend API layer, the SDK, and any agent reading the published JSON-schema.

## Generation inputs → outputs

- **Input**: `internal.py` definitions, each field carrying `extra={"update": ..., "visibility": ...}`.
- **Process**: `uv run invoke backend.generate` renders, per family, three variants
  by filtering fields on `visibility` (see membership rule in data-model.md).
- **Outputs**:
  - Internal variant → `backend/infrahub/core/schema/generated/*.py` (unchanged location).
  - Write + Read variants → `python_sdk/infrahub_sdk/schema/` (generated; replace hand-written).
- **Guarantee**: regeneration is byte-stable (idempotent). CI validates no drift on both sides.
- **Shipping**: the generated SDK write/read models are committed, version-controlled
  artifacts included in the published SDK package (not build-time-only), so a consumer
  installing only the SDK obtains them (basis for the "importable with only the SDK
  installed" contract).

## Write model contract

- Contains **only** `write`-level fields for each family.
- `model_config` retains `extra="forbid"`.
- Constrained fields publish their allowed-value set (enum / `Literal`) so the
  emitted JSON-schema is complete.
- Importable with only the SDK installed (no backend, no server).
- Is the exact acceptance shape for `POST /api/schema/load`.

**Verification**:
- The write model for a node exposes no `read`/`internal` field (e.g. no `inherited`,
  no `used_by`, no parent back-reference).
- The attribute `kind` field's JSON-schema lists all of `ATTRIBUTE_KIND_LABELS`.
- A scan finds zero write-model fields typed as bare `str`/`int` where the source
  definition declares an `enum=`/enum `internal_kind`.

## Read model contract

- Contains `write` + `read` fields; excludes `internal`.
- Superset of the write model (every write field is present and identically typed).
- Injects `kind` from `namespace` + `name` (existing `APISchemaMixin` behaviour) for
  node/generic; carries any read-only response fields the GET endpoint returns today
  (e.g. `hash`) as read-level additions.
- Is the exact shape returned by `GET /api/schema`.

**Verification**:
- The read model includes `inherited`/`used_by`; excludes the parent back-reference.
- Every field of the write model is present in the read model with the same type.

## Internal model contract

- Unchanged field set and location; rich wrapper classes continue to extend it.
- Remains backend-only; not exported to the SDK.

**Verification**: existing internal-model tests continue to pass unchanged.

## Cross-variant invariants

- `write ⊆ read ⊆ internal` field-set nesting holds for every family.
- A field with no `visibility` is absent from write and read (internal-only).
- The base/derived inheritance (`base_node_schema` → node/generic) is preserved in
  each variant.
