---
description: "Task list for User-Facing Schema Separation (INFP-234)"
---

# Tasks: User-Facing Schema Separation

**Input**: Design documents from `specs/002-user-facing-schema/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**Tests**: INCLUDED — the spec's Testing Decisions and the constitution's Test Discipline require them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (maps to spec user stories)
- Exact file paths are given per task.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Make the SDK submodule available and understand what it currently ships.

- [X] T001 Check out and sync the SDK submodule: `git submodule update --init python_sdk` then `uv sync --all-groups` (the write/read models will be generated into it).
- [X] T002 Audit the SDK's existing hand-written schema models under `python_sdk/infrahub_sdk/schema/` (e.g. `SchemaRootAPI`, `NodeSchemaAPI`, `GenericSchemaAPI`, `RelationshipSchemaAPI`, `AttributeSchemaAPI`): inventory their fields, `model_config`, and in-SDK consumers; record the mapping to the planned generated write/read models in `specs/002-user-facing-schema/research.md` (append an "SDK audit" section).
- [X] T003 [P] Confirm the Towncrier changelog setup and fragment types in `changelog/` so the breaking-change fragment (T027) uses a valid type.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The classification axis and the generator changes that every story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Add a `visibility` axis to the schema-field metadata in `backend/infrahub/core/schema/definitions/internal.py`: extend `ExtraField` (TypedDict) with a `visibility` key backed by a new ordinal enum (`internal < read < write`, default `internal`) added to `backend/infrahub/core/constants` (alongside `UpdateSupport`); update `SchemaAttribute`/`SchemaRelationship` to carry it.
- [X] T005 Set `visibility` on every field in `backend/infrahub/core/schema/definitions/internal.py` (base_node, node, generic, attribute, relationship, and structural relationships) per the resolved mapping in `schema-field-classification.md` (read: `inherited`, `used_by`, node `hierarchy`, relationship `hierarchical`; internal: attribute/relationship `node` back-reference; everything else write).
- [X] T006 Extend the generator to emit write/read variants: parameterize `backend/templates/generate_schema.j2` (and its per-schema import includes) plus `tasks/backend.py::_generate_schemas` to render each family in `write` and `read` variants by filtering fields on `visibility` (reuse `without_duplicates` per variant); leave the existing internal variant unchanged. NOTE: implemented via a dedicated self-contained template `generate_schema_sdk.j2` + `_generate_schemas_sdk` rather than branching the shared internal template, to guarantee the internal variant stays byte-identical.
- [X] T007 In the generator template/logic, propagate allowed-value sets into write/read fields (currently dropped): render enum-class-backed fields (`branch`, relationship `kind`/`cardinality`/`direction`/`on_delete`, `allow_override`, `display`, `state`) as their enum type, and list-backed sets (attribute `kind` → `ATTRIBUTE_KIND_LABELS`) as `Literal[...]`/`json_schema_extra` enum, so the emitted JSON-schema is complete. NOTE: all constrained fields (including enum-class-backed) render as `Literal[...]` of their allowed values in the SDK models so they are self-contained (no backend enum imports); the internal variant is unchanged.
- [X] T008 Point write/read generation output at `python_sdk/infrahub_sdk/schema/` as committed artifacts (mirror the existing `protocols.py`→SDK generation in `tasks/backend.py`); keep the internal variant writing to `backend/infrahub/core/schema/generated/`. NOTE: generated into a fresh `python_sdk/infrahub_sdk/schema/generated/` subpackage (write.py/read.py) so the hand-written main.py is untouched this chunk.
- [X] T009 Run `uv run invoke backend.generate` and `uv run invoke schema.generate-jsonschema`; verify idempotency (`uv run invoke backend.generate` again → `git diff --exit-code` clean) and commit the generated write/read models in the SDK.

**Checkpoint**: three model families generate from one source; write/read live in the SDK with enums; regeneration is stable.

---

## Phase 3: User Story 1 - Agent authors a valid schema unassisted (Priority: P1) 🎯 MVP

**Goal**: `POST /api/schema/load` accepts exactly the write model and rejects anything else with a field-level error; the published write JSON-schema is complete (enums present).

**Independent Test**: Fetch the generated write JSON-schema, build a payload from it, load it successfully; submit a payload with a non-settable/unknown field or out-of-enum value and get a field-level rejection.

### Tests for User Story 1 ⚠️ (write first, ensure they fail)

- [X] T010 [P] [US1] Functional test in `backend/tests/functional/api/test_load_schema.py`: a payload carrying `inherited` (read-level) plus an unknown field is rejected, and the error names each offending field.
- [X] T011 [P] [US1] Functional test in `backend/tests/functional/api/test_load_schema.py`: a payload setting attribute `kind` to a non-existent value is rejected, naming the field and the invalid value.
- [X] T012 [P] [US1] Unit test in `backend/tests/unit/core/schema/test_generated_visibility.py`: the generated write model for each family exposes zero read/internal fields, and a scan finds no bare-`str`/`int` field where an internal enum/`Literal` is defined (SC-001/SC-002).

### Implementation for User Story 1

- [X] T013 [US1] In `backend/infrahub/api/schema.py`, make the load path validate against the SDK write model (replace the `SchemaLoadAPI(SchemaRoot)` derivation with the generated SDK write model); retain `extra="forbid"` so non-write fields are rejected with field-level messages.
- [X] T014 [US1] Ensure the `kind`-from-`namespace`+`name` injection (`APISchemaMixin.set_kind`, `mode="before"`) remains compatible with the write model in `backend/infrahub/api/schema.py`.
- [X] T015 [US1] Ensure allowed-value validation is enforced by the write model itself (not only the internal-load `field_validator` in `backend/infrahub/core/schema/attribute_schema.py`), so out-of-enum values are rejected at the boundary.
- [X] T016 [US1] Regenerate and confirm the write JSON-schema (`schema/openapi.json` + the node-schema export) reflects the complete contract; commit.

**Checkpoint**: an agent can author a valid schema from the write contract alone; invalid submissions are rejected clearly.

---

## Phase 4: User Story 2 - Offline schema validation (Priority: P2)

**Goal**: The SDK validates a schema against the write model with no server, and the verdict matches the server's; the SDK's hand-written models are gone.

**Independent Test**: In an SDK-only environment, validate a good schema (passes) and a bad one (fails naming the field); confirm parity with the server for the same payloads.

### Tests for User Story 2 ⚠️

- [ ] T017 [P] [US2] SDK offline test in `python_sdk/tests/unit/test_schema_offline_validation.py`: with only the SDK installed, a valid payload passes and a payload with a non-settable/out-of-enum field fails naming the field.
- [ ] T018 [P] [US2] Parity contract test in `backend/tests/functional/api/test_load_schema.py`: the same payload yields the same field/enum verdict via SDK offline validation and via `POST /api/schema/load`.

### Implementation for User Story 2

- [ ] T019 [US2] Expose an SDK offline-validation entry point in `python_sdk/infrahub_sdk/schema/` that validates a payload against the generated write model and returns a field-level verdict.
- [ ] T020 [US2] Remove the SDK's hand-written schema models (from T002 audit) and repoint in-SDK consumers to the generated write/read models; keep public import paths stable where feasible.
- [ ] T021 [US2] Add an SDK CI check (in the SDK's own test/CI config) that the generated write/read models are present and non-stale (FR-012), matching the backend drift check.

**Checkpoint**: offline validation works from the SDK alone with server parity; no parallel hand-written models remain.

---

## Phase 5: User Story 3 - Stop advertising non-settable fields; correct read-back (Priority: P2)

**Goal**: `GET /api/schema` serialises via the read model — includes read-level fields, excludes internal — and historical schemas still read back; `id`-driven mutations remain authorised.

**Independent Test**: Read a schema back and confirm `inherited`/`used_by` present and internal back-reference absent; read back a pre-existing stored schema successfully.

### Tests for User Story 3 ⚠️

- [ ] T022 [P] [US3] Component test in `backend/tests/component/api/test_40_schema.py`: `GET /api/schema` returns `inherited`/`used_by` and never returns the internal parent back-reference or unclassified fields (FR-005/FR-006).
- [ ] T023 [P] [US3] Functional test in `backend/tests/functional/api/test_load_schema.py`: a stored schema containing a now-`read` field reads back without error (FR-010).
- [ ] T024 [P] [US3] Test in `backend/tests/functional/api/test_load_schema.py`: submitting an `id` that targets an existing object honours existing authorization and branch scoping (cannot rename/delete an object the caller may not modify) (R1).

### Implementation for User Story 3

- [ ] T025 [US3] In `backend/infrahub/api/schema.py`, make the GET path serialise via the SDK read model (rebase `APINodeSchema`/`APIGenericSchema`/`SchemaReadAPI` on the generated read model), preserving the `hash`/`kind` response fields as read-level.
- [ ] T026 [US3] Confirm the read model includes read-level fields and excludes internal; adjust the `read`-variant generation filter in `tasks/backend.py`/template if any field is misplaced.

**Checkpoint**: read-back is correct and backward-compatible; write and read models are both wired to the API.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T027 [P] Add a Towncrier changelog fragment in `changelog/` describing the breaking `POST /api/schema/load` behaviour (non-settable fields now rejected) (FR-011).
- [ ] T028 [P] Write an upgrade/migration note (in `docs/` upgrade guide) documenting the stricter load behaviour and how clients strip non-settable fields against the published write schema (FR-011).
- [ ] T029 Run the full `specs/002-user-facing-schema/quickstart.md` validation end-to-end.
- [ ] T030 [P] Run `uv run invoke backend.generate`, `schema.generate-jsonschema`, and `docs.generate`; run `/pre-ci` and confirm the generated-file/`docs.validate` CI checks pass on both backend and SDK.
- [ ] T031 [P] Update backend schema architecture notes in `dev/knowledge/backend/` to describe the write/read/internal model layering and the backend→SDK model dependency.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. T002 audit informs T020.
- **Foundational (Phase 2)**: depends on Setup. **Blocks all user stories.** T004→T005→T006→T007→T008→T009 are largely sequential (each builds on the prior); T004 and T005 touch the same file (internal.py) so are not parallel.
- **US1 (Phase 3)**: depends on Foundational (needs the generated write model + enums).
- **US2 (Phase 4)**: depends on Foundational; T020 also depends on T002 (audit) and T013 (backend no longer needs old SDK models). Independently testable once the write model exists.
- **US3 (Phase 5)**: depends on Foundational (needs the read model). Independent of US1/US2.
- **Polish (Phase 6)**: after the desired stories are complete.

### Within Each User Story

- Tests first (must fail), then implementation.
- Generation/model changes before API wiring; API wiring before serialization polish.

### Parallel Opportunities

- T003 can run alongside T001/T002.
- All `[P]` test tasks within a story (T010–T012, T017–T018, T022–T024) can run in parallel.
- US1 and US3 can proceed in parallel after Phase 2 (different endpoints/paths); US2 can start once the write model exists but T020 should follow T013.
- Polish tasks T027/T028/T030/T031 are parallelizable.

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational (CRITICAL) → 3. Phase 3 US1 → 4. STOP & validate the P1 authoring flow → deploy/demo.

### Incremental Delivery

Foundation → US1 (agent authoring, MVP) → US2 (offline validation) → US3 (read-back correctness) → Polish. Each story is independently testable and adds value without breaking prior ones.

---

## Notes

- Governance: this feature crosses the API-change and generated-files/submodule gates — the "ask first" discussion (recorded in the spec) must be settled before starting Phase 2/3 implementation.
- Do not hand-edit generated files (`backend/infrahub/core/schema/generated/`, generated SDK models); always regenerate via `uv run invoke backend.generate`.
- Commit after each task or logical group; regenerate + validate before pushing (`/pre-ci`).
- Open question (non-blocking): SC-004 benchmark target rate — set with product before measuring SC-004.
