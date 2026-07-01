# PRD: User-Facing Schema Separation (INFP-234)

## Problem Statement

The schema that users author against (the "user-facing schema") is generated as a partial copy of Infrahub's internal schema, and it is wrong in two ways. It exposes fields users are not meant to set (e.g. `inherited`), so users set them and create problems in Infrahub. And it under-specifies fields whose valid values are already known internally — attribute `kind`, for example, is published as a bare string with no enumeration of valid kinds. Humans produce technically-invalid schemas as a result, and an LLM generating a schema has no way to know which fields exist or what values they accept, so it cannot reliably produce a correct schema at all.

## Solution Overview

Generate the user-facing schema as a distinct contract instead of dumping the internal model. From the single internal source of truth, Infrahub produces three schemas: an external **write** schema (exactly what a user may submit), an external **read** schema (adds fields the user may see but not set), and the **internal** schema. Every field is classified by visibility; fields whose allowed values are already known internally publish those values as enumerations. The write and read models live in the Python SDK, so a schema can be validated locally without a running server, and the server validates with the same models. Submitting a field a user may not set is rejected with a clear, field-level error rather than silently accepted.

## User Stories

1. As an LLM agent, I want the write schema to list exactly which fields exist and which values each constrained field accepts, so that I can generate a valid schema without guessing.
2. As an LLM agent, I want an invalid submission rejected with a machine-readable, field-level error, so that I can correct my output automatically instead of loading a broken schema.
3. As a human schema author, I want internal-only fields to stop being advertised as settable, so that I don't set fields that break Infrahub.
4. As a human schema author, I want a clear error naming the offending field when I submit something invalid, so that I can fix it quickly.
5. As an SDK user, I want to validate a schema locally with no server, so that I can catch errors in CI or offline before a round-trip.
6. As an SDK user, I want the local verdict to match the server's for field and enum rules, so that a locally-valid schema is not rejected on load.
7. As a maintainer, I want the write/read/internal models generated from one source, so that they cannot drift apart.
8. As a maintainer, I want a new field hidden from users by default, so that we never leak an internal field by forgetting to classify it.

## User Journeys (prioritised)

### P1 — Agent authors a valid schema unassisted
- Journey: An LLM agent fetches the published write schema, generates a payload, and submits it to `/api/schema/load`.
- Acceptance: **Given** an agent has the published write schema, **When** it generates a payload and POSTs it, **Then** either the payload validates and loads because the schema stated exactly which fields exist and each constrained field's allowed values, or it is rejected with a field-level machine-readable error — never silently accepting an invalid schema.

### P2 — Offline schema validation (ships independently)
- Journey: A developer or agent validates a schema against the SDK's write model with no running server.
- Acceptance: **Given** only the Infrahub SDK is installed and no server is running, **When** a schema is validated against the SDK write model, **Then** unknown / read-only / internal fields and out-of-enum values are caught locally, and the same models re-validate server-side so a locally-valid schema is not rejected for field/enum reasons on load.

## Functional Requirements

- **FR-001**: `backend.generate` MUST emit three model sets (write, read, internal) from the single field-definition source. *Verify:* generated output contains three model families; regeneration is idempotent.
- **FR-002**: Every schema field MUST carry a `visibility` classification (`internal` / `read` / `write`); an unset marker MUST default to `internal`. *Verify:* unit test on the default and on per-model field membership.
- **FR-003**: The write model MUST reject any field not at `write` level (read, internal, or unknown) with a field-level error naming the field. *Verify:* POST containing `inherited` plus a bogus field returns a 4xx naming each.
- **FR-004**: Any field whose internal definition carries an `enum=` or equivalent bounded type MUST surface that enumeration in the write and read models, across the attribute, relationship, node, and generic families. *Verify:* generated write schema for `kind` contains the full set of valid kinds; a scan asserts no bare-string field exists where an internal enum is defined.
- **FR-005**: The read model MUST include `read`-level fields and exclude `internal` fields. *Verify:* GET returns `inherited`; it never returns internal bookkeeping fields.
- **FR-006**: The write and read models MUST be generated into the Python SDK and be importable with only the SDK installed (no server, no backend package). *Verify:* import and validate a payload in an SDK-only environment.
- **FR-007**: The backend MUST validate write submissions and serialise read responses using the SDK-hosted models, not a backend-local copy. *Verify:* a rule change in the generated model changes both server and SDK behaviour.
- **FR-008**: The SDK's existing hand-written schema models MUST be replaced by the generated write/read models, leaving no third parallel definition. *Verify:* old model classes are removed; SDK callers use the generated ones.

## Key Entities

- **AttributeSchema / RelationshipSchema / NodeSchema / GenericSchema** *(existing)*: the field definitions that gain a `visibility` classification; source of the generated models.
- **`visibility` field marker** *(new)*: ordinal metadata on each field definition; determines which of the three models a field appears in. Governance-relevant: it is the control that decides what users can touch.
- **Write / Read generated models** *(new)*: the externally-visible contract, hosted in the Python SDK, consumed by both the SDK and the backend API.
- **Internal generated model** *(existing)*: unchanged full model, backend-only.

## Edge Cases

- API round-trip (`GET /api/schema` → edit → `POST /api/schema/load`) breaks this cycle because read-level fields are now rejected on write; the write-shaped export that fixes this is deferred, and the minority of clients doing this must strip read fields against the published write schema in the meantime.
- The `kind` field that `APISchemaMixin` injects from `namespace` + `name` must remain compatible with the write model.
- Schema `extensions` payloads must be subject to the same write-model rejection rules as node/generic definitions.
- Reading back a previously-stored schema that contains fields now classified `read` must still succeed (read is a superset of write, so this is safe).
- Version skew between SDK-side validation and the server's schema version: the `version` field on the load payload is the compatibility anchor; behaviour on mismatch is defined at spec time.

## Success Criteria

- **SC-001**: The write schema exposes zero internal-only fields — every field present is user-settable.
- **SC-002**: Zero constrained fields publish a bare type where the allowed value set is already known internally (100% enum propagation).
- **SC-003**: 100% of submissions containing a non-writable field are rejected with a field-level error; zero are silently accepted.
- **SC-004**: An agent given only the write schema loads a valid schema for a benchmark task set at or above a target pass rate, with no human correcting field names or kinds. *(Target rate set with product.)*
- **SC-005**: A schema can be validated with only the SDK installed and no server process, and the local verdict matches the server's for field and enum rules.

## Implementation Decisions

- Modules to build / modify:
  - `visibility` field marker (backend schema definitions, extends): adds the ordinal visibility axis to field definitions.
  - Schema model generator (backend generate pipeline, extends — deep module): emits three model sets from one source, filters by visibility, propagates known enums/constraints, and writes the write/read models into the SDK.
  - Generated write/read models (Python SDK, new): the externally-visible contract, importable without a server.
  - SDK schema validation surface (Python SDK, extends/replaces): replaces the hand-written SDK schema models and exposes offline validation.
  - API schema-load validation (backend API, extends): validates against the SDK write model with hard rejection and field-level errors; serialises GET via the read model.
- API / interface surface: `/api/schema/load` becomes stricter (breaking for payloads carrying non-write fields); `/api/schema` read shape changes; new SDK local-validation entry point. The write-shaped export endpoint is out of scope this cycle.
- Error handling: field-level, machine-readable rejection errors that name the offending field and why it is not accepted.
- Data / persistence: none — this is an API-model and generation-layer change, no stored-data model change or migration.
- Frontend surface: none in this cycle; the `schema-visualizer` package is a separate downstream consumer assessed later.
- SDK / CLI surface: the SDK gains the generated write/read models and a local-validation capability; hand-written schema models are removed.

## Testing Decisions

- **What makes a good test here.** Test the externally-observable contract — which fields each model accepts/emits, that constrained fields carry their enums, and that invalid submissions are rejected with the right error — not the internals of the generator.
- **Unit tests** (agreed): schema model generator (idempotency, per-model field membership, enum propagation); API rejection behaviour (field-level errors); SDK offline validation (SDK-only import and verdict parity with the server).
- **Integration / contract tests**: server/SDK parity — the same payload yields the same field/enum verdict locally and on `/api/schema/load`; a load with an internal/read field is rejected end-to-end.
- **E2E scenario**: an agent-style flow fetches the write schema, generates a payload, loads it successfully; a second payload carrying `inherited` is rejected with a field-level error.
- **Prior art**: existing schema-load API tests and the schema-generation tests under the backend test suite.

## Constitution Alignment

- **III — Type Safety & Explicit Contracts**: directly advances it; the feature defines the REST/SDK contract explicitly and makes consumers use generated types.
- **VII — Simplicity & Maintainability**: one generated source produces three outputs and deduplicates the SDK's schema models rather than adding a parallel set.
- **VI — Security & Input Boundaries**: hard rejection enforces validation at the API boundary instead of silently accepting invalid input.
- **I — Schema-Driven Integrity**: fewer invalid schemas enter the system, protecting downstream data.

## Governance Gates Crossed

- [x] **GraphQL schema modifications** — not expected (schema load is REST); confirm at spec time.
- [x] **API / public interface change** — `/api/schema/load` and `/api/schema` change shape/behaviour; breaking for non-write payloads. Ask-first.
- [ ] **Database schema or migration change** — none.
- [ ] **New dependency** — none.
- [x] **CI/CD workflow change** — the generate pipeline now writes into the `python_sdk` submodule; confirm CI handles the submodule write and that generated files are validated on both sides.
- [ ] **Authentication / authorization change** — none.
- [x] **Generated files + submodule commits** — new/changed generated models in backend and `python_sdk`; regenerate and commit (`backend.generate`, `schema.generate-jsonschema`, `docs.generate`) with explicit submodule commits.

## Assumptions

- The visibility hierarchy is nested (`write ⊆ read ⊆ internal`); there are no write-only fields (settable but not returned).
- The dominant authoring path is user-authored, write-shaped YAML loaded into Infrahub; API read-modify-write round-tripping is a minority path.
- Internal `enum=` definitions are authoritative and complete at generation time.
- The backend already depends on the SDK at runtime, and the generate pipeline can target the SDK submodule.

## Out of Scope

- The write-shaped export capability (export excluding read-only fields, emitting only user-defined values with defaults omitted) — deferred; needs value provenance.
- Kind-conditional `read_only` defaults for `computed_attribute` / `NumberPool` attributes — a defaults-and-conditional-validation problem, tracked separately.
- Changes to the `frontend/packages/schema-visualizer` consumer — assessed after the models land.

## Open Questions

- [NEEDS CLARIFICATION: the concrete per-field classification — every field in the attribute/relationship/node/generic definitions must be assigned write/read/internal. Mechanical; resolved at spec time.]
- [NEEDS CLARIFICATION: the SC-004 target pass rate and benchmark task set — needs product input.]

## Further Notes

- Related ADRs: none directly; honours `dev/adr/` decisions in the schema area.
- Source of this PRD: a grilling session on Jira idea INFP-234, grounded in the current schema-generation code (single internal source, existing `extra={}` field-metadata channel, `ATTRIBUTE_KIND_LABELS` enum dropped during generation).
