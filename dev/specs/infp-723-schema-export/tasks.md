---
description: "Task list for INFP-723: export the running schema"
---

# Tasks: Export the Running Schema

**Input**: Design documents from `dev/specs/infp-723-schema-export/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The constitution (Principle IV) requires tests for every feature, and the spec names
tests (FR-023, FR-024, SC-001 to SC-003). Write each test task before the implementation task it covers, and
check that it fails first.

**Organization**: Tasks are grouped by user story (US1 to US4 of the spec). The `BRIEF` export is built on
the `FULL` document (research R1), so the `FULL` serializer is part of US1; US3 adds the tests and
documentation of the `FULL` behaviour on an instance that already has the schema.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: The user story of the spec (US1 to US4)

## Conventions for every task

- **Code style**: load `dev/guidelines/backend/python.md`, `dev/guidelines/backend/testing.md`,
  `dev/guidelines/backend/component-design.md` and `dev/guidelines/code-doc-style.md` before writing backend
  code or tests. In the SDK, follow `python_sdk/AGENTS.md`.
- **Two repositories**: tasks with paths under `python_sdk/` are made in the SDK repository, on branch
  `schema-export-infp-723` created from `origin/infrahub-develop` (T002), never from the SDK's `develop`. Never
  stage the `python_sdk` pointer in an Infrahub commit before T047.
- **Generated files**: never edit `python_sdk/infrahub_sdk/schema/generated/`, `schema/openapi.json` or
  `frontend/app/src/shared/api/rest/types.generated.ts` by hand. Regenerate them (T005, T045).
- **Citations**: name modules and symbols (`module::Symbol`), never line numbers.
- **Push and pull requests**: push a branch or open a pull request only when the user asks.

---

## Phase 1: Setup

**Purpose**: Approval of the API change and the working branches.

- [X] T001 Get the approval of D11 (REST endpoint `GET /api/schema/export`), as root `AGENTS.md` "Ask First" requires for an API change, and record who approved and when in the "Ask First" row of the Constitution Check in `dev/specs/infp-723-schema-export/plan.md`. Approved by Damien Garros on 2026-10-27.
- [X] T002 In `python_sdk/`, run `git fetch origin infrahub-develop` and create branch `schema-export-infp-723` from `origin/infrahub-develop`.
- [X] T003 [P] Create the package `backend/infrahub/core/schema/export/` with an empty `__init__.py`, and the test package `backend/tests/unit/core/schema/export/` with `__init__.py` and a `schemas/` directory for the rule schemas.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: The `infrahub_version` field and the mode enum, which every story uses.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Write a failing SDK test in `python_sdk/tests/unit/test_schema_offline_validation.py`: a document with `version: "1.0"` and `infrahub_version: "1.0.0"` passes `infrahub_sdk.schema.validate::validate_schema` with no error and no warning.
- [X] T005 Add `infrahub_version: str | None = None` to the write root only (the `with_version` case, after `version`) in `tasks/backend.py::_sdk_root`, without adding it to the read-only root fields. Run `uv run invoke backend.generate` and check that `python_sdk/infrahub_sdk/schema/generated/write.py::InfrahubSchemaWrite` gains the field and `python_sdk/infrahub_sdk/schema/generated/contract.py` does not change. T004 now passes.
- [X] T006 [P] Write a failing backend test in `backend/tests/unit/api/test_schema_load_contract.py`: `infrahub.api.schema::SchemaLoadAPI` accepts a payload with `infrahub_version`, `build_internal_schema` succeeds, and no contract warning is produced.
- [X] T007 Add `infrahub_version: str | None = None` to `infrahub.core.schema::SchemaRoot` in `backend/infrahub/core/schema/__init__.py`, after `version`. Nothing reads it (D7). T006 now passes.
- [X] T008 [P] Add `SchemaExportMode(InfrahubStringEnum)` with `BRIEF = "brief"` and `FULL = "full"` to `backend/infrahub/core/constants/__init__.py`, next to the other schema enums.
- [X] T009 [P] Add `infrahub_version` right after `version` in `python_sdk/infrahub_sdk/ctl/schema_format.py::FILE_ORDER`, with a test in `python_sdk/tests/unit/ctl/test_schema_format.py` that formatting keeps it in that position.

**Checkpoint**: `infrahubctl schema load` and `POST /api/schema/load` accept `infrahub_version` with no warning.

---

## Phase 3: User Story 1 - Export the running schema and load it into an empty instance (Priority: P1) 🎯 MVP

**Goal**: `GET /api/schema/export` returns a document that loads into an empty instance and gives the same
user-defined schema (FR-001 to FR-013).

**Independent Test**: The in-memory round trip in `test_round_trip.py` passes for every rule schema,
`models/base/` and `models/examples/`, in both modes; the functional test loads the endpoint's response into
an empty database with no warning.

### Tests for User Story 1

- [X] T010 [P] [US1] For each export rule below, first look for an existing fixture that covers it (`backend/tests/fixtures/schemas/`, the schema fixtures of `backend/tests/conftest.py` and `backend/tests/unit/conftest.py`) and reuse it (constitution Principle IV). Write a small YAML schema in `backend/tests/unit/core/schema/export/schemas/` only for a rule no fixture covers, with a one-line header saying the rule it covers. List in the test module which fixture covers which rule. Rules: labels set and derived; `optional` with `default_value`; relationship `min_count`/`max_count`, `identifier` and `on_delete` derived and set; attribute and relationship `branch` equal to and different from the derived value; `order_weight` with gaps; `human_friendly_id` from a unique attribute; `unique: true` with its single-attribute constraint (FR-008); the generic and two nodes of the D4 example in the design document (FR-007); dropdown choices with some colours set; deprecated top-level `regex`/`min_length`/`max_length` (FR-009); NumberPool `ranges` and the `start_range`/`end_range` shorthand; a node with `generate_template: true`; a hierarchical generic; a user relationship of kind `Group` that is not generated; an extension of a user node (FR-004); an extension of a Core node (FR-005); `display_labels` and `default_filter`.
- [X] T011 [US1] Write `backend/tests/unit/core/schema/export/test_round_trip.py`. A helper loads a schema into a processed branch as `backend/tests/unit/core/schema/test_schema_branch.py::_load_processed_branch` does, exports it, loads the export into a new processed branch, and asserts: the export validates against `infrahub_sdk.schema.generated.write::InfrahubSchemaWrite`; the set of warning messages that `infrahub.core.schema::SchemaRoot.gather_warnings` gives for the export is contained in the set it gives for the source schema (FR-012; warnings are per element, so compare messages, not counts, research R6); the `FULL` documents of both branches are equal (data-model "Schema equality"); a second export equals the first apart from `infrahub_version` (FR-013). Parametrize over every file of T010, `models/base/` as one set, and each YAML schema of `models/examples/` (with `models/base/` when it references it), in both modes. Record the time of the `models/base/` export in the test output.
- [X] T012 [P] [US1] Write `backend/tests/unit/core/schema/export/test_brief_rules.py` with exact-output assertions in `brief` mode: the D4 example gives the export shown in the design document (copied properties written on the nodes, the generic's uniqueness constraint and the `Device` `human_friendly_id` left out); FR-008; FR-009 (settings only under `parameters`); no `member_of_groups`, `subscriber_of_groups`, `profiles`, `object_template`, `parent` or `children`, while the user relationship of kind `Group` stays (FR-003, research R3); the Core extension is absent (FR-005); `version` is `"1.0"` and `infrahub_version` is `infrahub.__version__` (FR-001, FR-010).

### Implementation for User Story 1

- [X] T013 [US1] Implement `SchemaExportSerializer` in `backend/infrahub/core/schema/export/serializer.py` (research R2 to R5). Entry method takes a `SchemaBranch` and a list of namespaces and returns the `FULL` document: user-defined generics and nodes outside `infrahub.core.constants::RESTRICTED_NAMESPACES`; every field of the matching SDK write model, defaults included, except `id`, `state` and NumberPool `number_pool_id`; local attributes and relationships only (`inherited` false); generated relationships removed by name, kind and identifier together; validation settings only under `parameters`; ordering of research R5.
- [X] T014 [US1] Implement `BriefSchemaMinimizer` in `backend/infrahub/core/schema/export/minimizer.py` (research R1). The constructor takes the serializer and a factory that returns a new `SchemaBranch` with the internal schema and the core models loaded. The entry method takes the `FULL` document of the exported namespaces and the `FULL` document of the other user namespaces. It removes the fields of the research R1 table and the values equal to the write-model default, except the FR-007 properties on a node whose `inherit_from` has a generic that sets them (research R4); then it loads both documents into a new branch, processes it, serializes the exported namespaces, and writes back every value that differs, matching elements by `kind` or `name`, until nothing differs.
- [X] T015 [US1] Implement `SchemaExporter` in `backend/infrahub/core/schema/export/exporter.py`. The constructor takes the serializer and the minimizer. The entry method takes the `SchemaBranch`, the namespaces (all user namespaces when none are given) and a `SchemaExportMode`, and returns an `infrahub_sdk.schema.generated.write::InfrahubSchemaWrite` built with `model_validate` from the document with `version: "1.0"`, `infrahub_version` from `infrahub::__version__`, `generics` and `nodes` (empty lists when nothing is selected). Never return an untyped `dict` (constitution Principle III); the API handler serialises it with `model_dump(mode="json", exclude_unset=True)`. Export the public names from `backend/infrahub/core/schema/export/__init__.py`.
- [X] T016 [US1] Run T011 and T012 and fix the export until they pass. When a rule schema fails, fix the serializer or the minimizer, never the expected output, unless the expectation contradicts research R1 to R6.
- [X] T017 [US1] Add `GET /api/schema/export` in `backend/infrahub/api/schema.py`, declared before `get_schema_by_kind`, as specified in [contracts/rest-schema-export.md](contracts/rest-schema-export.md): `branch` through `infrahub.api.dependencies::get_branch_dep`, `namespaces: list[str] | None`, `mode: SchemaExportMode = SchemaExportMode.BRIEF`, `get_current_user` as the only access dependency; build the exporter in the handler from the branch schema in the registry; a document that fails validation returns HTTP 500 with a message that does not include the schema. Give the route a summary and a description for the OpenAPI schema.
- [X] T018 [P] [US1] Add tests to `backend/tests/component/api/test_40_schema.py`: 200 with `version`, `infrahub_version`, `generics`, `nodes`; default mode is `brief`; `branch` selects the branch schema (US1 scenario 5); unknown branch gives 400; `mode=other` gives 422; anonymous access gives 200 when allowed and 401 when not; the route is not handled as a schema kind.
- [X] T019 [US1] Write two independent `TestInfrahubApp` classes in `backend/tests/functional/api/test_schema_export.py` (a class cannot empty its database part-way, research R14). Both use `models/base/` plus a schema with `generate_template: true`, and the in-memory export of these files built with the exporter as in T011. `TestSchemaExportFromLoadedSchema`: load the files through the SDK client, call the endpoint, assert the response equals the in-memory export apart from `infrahub_version`. `TestSchemaExportIntoEmptyInstance`: load the in-memory export into the empty database through `POST /api/schema/load`, assert success and no warning (US1 scenarios 2 and 4), then call the endpoint and assert it returns the same document apart from `infrahub_version` (scenario 3).

**Checkpoint**: The endpoint works and is tested. User Story 1 can be demonstrated with `curl` and
`POST /api/schema/load`.

---

## Phase 4: User Story 2 - Export the schema with `infrahubctl` (Priority: P1)

**Goal**: `infrahubctl schema export` calls the endpoint, writes one file per namespace or one file, and
fails clearly on an older server (FR-019 to FR-022). All tasks are in the SDK repository.

**Independent Test**: The SDK unit tests of T020 and T021 pass, and the manual check in
[quickstart.md](quickstart.md) steps 2 to 4 and 7 gives the expected output.

### Tests for User Story 2

- [X] T020 [P] [US2] Rewrite `python_sdk/tests/unit/sdk/test_schema_export.py` for both clients (`clients: BothClients`) with `pytest_httpx`: `export()` calls `GET /api/schema/export` with `branch`, `namespaces` and `mode` and returns the body; 404 and 422 raise `infrahub_sdk.exceptions::VersionNotSupportedError` naming "Schema export"; 400 raises `BranchNotFoundError`. Remove the tests of `_build_export_schemas` and `schema_to_export_dict`.
- [X] T021 [P] [US2] Write `python_sdk/tests/unit/ctl/test_schema_export_app.py` with `typer.testing.CliRunner` and `httpx_mock`, as `python_sdk/tests/unit/ctl/test_schema_app.py` does: two namespaces give `network.yml` and `dcim.yml`, each with `version`, `infrahub_version`, `generics` and `nodes` of its namespace (US2 scenario 1); `--single-file` gives one `schema.yml` equal to the response (scenario 2); `--mode full` sends `mode=full`; an empty response prints "No user-defined schema found to export." and writes no file; a 422 prints "Schema export requires Infrahub X or later." without a traceback and exits with code 1 (scenario 4).

### Implementation for User Story 2

- [X] T022 [US2] Rewrite `InfrahubSchema.export` and `InfrahubSchemaSync.export` in `python_sdk/infrahub_sdk/schema/__init__.py` to the signature in [contracts/cli-schema-export.md](contracts/cli-schema-export.md), returning `InfrahubSchemaWrite`, with a module constant `SCHEMA_EXPORT_MIN_INFRAHUB_VERSION = "1.13.0"` named in `VersionNotSupportedError`. Remove `InfrahubSchemaBase._build_export_schemas`, and remove `SchemaExport`, `NamespaceExport` and `schema_to_export_dict` from the imports and `__all__`.
- [X] T023 [US2] Delete `python_sdk/infrahub_sdk/schema/export.py`, and check with `grep -rn "schema.export\|schema_to_export_dict\|SchemaExport" python_sdk/infrahub_sdk python_sdk/tests` that nothing still refers to it.
- [X] T024 [US2] Rewrite `python_sdk/infrahub_sdk/ctl/schema.py::export`: add `--mode` (`brief` or `full`, default `brief`) and `--single-file`; dump the returned model with `model_dump(mode="json", exclude_unset=True)`, split it by namespace into `<namespace lower case>.yml` files, each with `version` and `infrahub_version` first, or write the whole response to `schema.yml` with `--single-file`; keep `--directory`, `--branch`, `--namespaces`, `--debug` and the message for an empty export.
- [X] T025 [US2] Add `VersionNotSupportedError` to the exceptions that `python_sdk/infrahub_sdk/ctl/utils.py::handle_exception` prints without a traceback. T020 and T021 now pass.
- [X] T026 [US2] Ask the user which Infrahub release ships the endpoint. Answer: 1.13.0 (Damien Garros, 2026-10-27), used by T022.
- [X] T027 [P] [US2] Regenerate the CLI reference with `uv run invoke docs-generate` in `python_sdk/` and check that `python_sdk/docs/docs/infrahubctl/infrahubctl-schema.mdx` documents `--mode` and `--single-file`.
- [X] T028 [P] [US2] Add `python_sdk/changelog/+schema-export-endpoint.added.md` (`--mode`, `--single-file`, export served by Infrahub) and `python_sdk/changelog/+schema-export-endpoint.removed.md` (`SchemaExport`, `NamespaceExport`, `schema_to_export_dict`, `infrahub_sdk.schema.export`; `infrahubctl schema export` requires the new Infrahub release), using the `creating-changelog-entries` skill.
- [X] T029 [US2] Run the SDK checks (`uv run invoke format lint` and `uv run pytest tests/unit` in `python_sdk/`), then commit on the SDK branch. Push and open the pull request against `infrahub-develop` only when the user asks.

**Checkpoint**: The SDK branch is ready to merge before the Infrahub pull request (plan, delivery order).

---

## Phase 5: User Story 3 - Export every value to update an instance that already has the schema (Priority: P2)

**Goal**: A `FULL` export overwrites values that a `BRIEF` export leaves to the target (FR-014 to FR-015a).
The `FULL` serializer and the `mode` parameter exist from US1; this phase tests the behaviour on an existing
instance.

**Independent Test**: The functional test of T031 and the unit test of T032 pass.

- [X] T030 [P] [US3] Add tests to `backend/tests/unit/core/schema/export/test_brief_rules.py` (or a new `test_full_mode.py` in the same directory): in `full` mode every attribute and relationship has `label`, `optional`, `branch` and `order_weight`, a node with a unique attribute has `human_friendly_id`, and the export still leaves out IDs, `state`, inherited and generated elements, restricted namespaces and the Core extension (FR-015, US3 scenario 3).
- [X] T031 [US3] Add `TestSchemaExportExistingInstance` to `backend/tests/functional/api/test_schema_export.py`: export in both modes a schema whose attribute `hostname` has the derived label; load into the same database a version where `hostname` has `label: Hostname`; then load the `brief` export and assert the label stays `Hostname`, and load the `full` export and assert it becomes the derived label (US3 scenarios 1 and 2).
- [X] T032 [US3] In `backend/tests/unit/core/schema/export/test_full_mode.py`, build a source and a target as two processed branches that differ only in the `branch` of one relationship (the load refuses to create this state in one database, research R14). Load the `full` export of the source into a copy of the target as `infrahub.api.schema::evaluate_candidate_schemas` does, and assert that `SchemaBranch.validate_update` reports a `NOT_SUPPORTED` error for that relationship; then assert that the `brief` export gives no error (FR-015a, research R10).

**Checkpoint**: The behaviour of both modes on an existing instance is tested and matches the
documentation of T042.

---

## Phase 6: User Story 4 - Export only some namespaces (Priority: P3)

**Goal**: A namespace filter exports only the selected namespaces, with no warning, and the derived values
of the selected namespaces still take the other namespaces into account (FR-017).

**Independent Test**: The tests of T033 and T034 pass.

- [X] T033 [P] [US4] Add a test to `backend/tests/unit/core/schema/export/test_round_trip.py`: with `Network` and `Dcim`, where a `Network` relationship points to a `Dcim` node with another `branch` support, exporting `namespaces=["Network"]` contains only `Network`, and the relationship `branch` is left out in `brief` mode exactly when processing with `Dcim` present derives the same value (research R1 step 3).
- [X] T034 [US4] Add `TestSchemaExportNamespaces` to `backend/tests/functional/api/test_schema_export.py`: export `namespaces=Network`, check only `Network` is present and the response has no warning field, then load it into a database that has the `Dcim` schema and assert success (US4 scenarios 1 and 3).

**Checkpoint**: All four user stories are implemented and tested.

---

## Phase 7: Polish and cross-cutting concerns

- [X] T035 Write `backend/tests/unit/core/schema/export/test_field_coverage.py` (FR-023, SC-003): a registry maps each `(model, field)` of `NodeSchemaWrite`, `GenericSchemaWrite`, `AttributeSchemaWrite`, `RelationshipSchemaWrite` and the attribute parameter write models in `infrahub_sdk.schema.generated.write` to the T010 schema that sets it to a non-default value, or to a reason why no test is needed; the test fails for a field missing from the registry and for a registry entry whose schema does not set the field.
- [X] T036 [P] Run `uv run invoke schema.generate-jsonschema`, then `pnpm codegen:openapi` in `frontend/app/`, and commit `schema/openapi.json` and `frontend/app/src/shared/api/rest/types.generated.ts`.
- [X] T037 [P] Write `docs/docs/schema/export.mdx` with the `opsmill-docs:writing-infrahub-docs` skill: what the export contains, the endpoint and `infrahubctl schema export` with `--mode` and `--single-file`, the two modes, and the known limitations (D2 Core extensions are not exported; D3 a value equal to the derived value is left out in `brief`; D4 properties copied from a generic are fixed on the node; research R5 stale weights on inherited elements; research R6 deprecated fields keep their warnings; research R10 a `full` load is refused when `branch`, `identifier` or `direction` differs; research R11 which fields a `brief` load keeps on an existing instance; an older release rejects `infrahub_version`). Add it after `schema/create-and-load` in `docs/sidebars.ts`. Run `uv run invoke docs.lint`.
- [X] T038 [P] Check that `docs/docs/objects/import-from-csv.mdx` still describes `infrahubctl schema export` correctly, and update it if not.
- [X] T039 [P] Write `dev/knowledge/backend/schema-export.md` following `dev/guidelines/documentation.md`: what schema processing derives (research R1 table, R3, R4), the remove-and-restore algorithm, how fields are chosen from the write models (R2), and what to do when a schema field is added (T035). Link it from the knowledge list in `backend/AGENTS.md`.
- [X] T040 [P] Add `changelog/10094.added.md` (the GitHub issue of IFC-2964) with the `creating-changelog-entries` skill: the export endpoint, its two modes, and `infrahub_version` accepted on load.
- [X] T041 Run the unit tests of T011 and report the export time of `models/base/` in both modes in the pull request description (plan, Performance Goals).
- [X] T042 Check that the documentation of T037 matches the results of T031 and T032, and fix the page if not.
- [X] T043 Re-read `dev/specs/infp-723-schema-export/spec.md`, `plan.md` and `research.md` against the code, and update every statement the implementation changed (root `AGENTS.md`, "Always Do").
- [ ] T044 Once the SDK pull request is merged, update `python_sdk` to the merged commit on `origin/infrahub-develop` and run `uv run invoke backend.generate` to check that the generated SDK models match.
- [X] T045 Run `/pre-ci` and fix every failure.
- [ ] T046 Run the automated checks and the manual check of [quickstart.md](quickstart.md) and report the results.
- [ ] T047 Commit the submodule bump with the Infrahub changes. Push and open the pull request only when the user asks.
- [ ] T048 Write `tests/e2e/schema/test_schema_export.py` (constitution Principle IV; no browser): with the `schema_base` fixture of `tests/e2e/conftest.py`, call `infrahub_client.schema.export()`, send the result to `infrahub_client.schema.check()`, and assert an empty diff and no warning. Run it with `uv run pytest -c tests/e2e/pytest.ini tests/e2e/schema/test_schema_export.py -s --pdb` after T044.

---

## Dependencies and execution order

### Phase dependencies

- **Setup (Phase 1)**: T001 blocks T017 only. T002 blocks every task under `python_sdk/`.
- **Foundational (Phase 2)**: blocks all user stories. T005 needs T002 (it writes into the SDK checkout).
- **US1 (Phase 3)**: after Phase 2. T013 → T014 → T015 → T016 → T017 → T018, T019.
- **US2 (Phase 4)**: after Phase 2. Independent of US1 in code; its manual check needs the endpoint of T017.
- **US3 (Phase 5)**: after T017.
- **US4 (Phase 6)**: after T017.
- **Polish (Phase 7)**: T035 after T010; T036 after T017; T037 and T042 after T031 and T032; T044 after the SDK pull request is merged; T048 after T044; T045 to T047 last.

### Parallel opportunities

- Phase 2: T004, T006, T008 and T009 together; T005 and T007 then make T004 and T006 pass.
- US1 and US2 can run at the same time after Phase 2, by two people or two sessions: one in `backend/`, one in `python_sdk/`.
- In US1: T010 and T012 together; T018 next to T019.
- In US2: T020 and T021 together; T027 and T028 together.
- After T017: US3 and US4 together.
- Polish: T036 to T040 together.

### Parallel example: User Story 2

```text
T020 Rewrite python_sdk/tests/unit/sdk/test_schema_export.py
T021 Write python_sdk/tests/unit/ctl/test_schema_export_app.py
```

## Implementation strategy

### First deliverable: User Story 1

1. Phases 1 and 2.
2. Phase 3: the endpoint with both modes and the round-trip tests.
3. Stop and validate: `curl` the endpoint and load the response into an empty instance (quickstart).

### Incremental delivery

1. US1: the endpoint. Usable with `curl` and `POST /api/schema/load`.
2. US2: the SDK pull request. Merges first (plan, delivery order).
3. US3 and US4: tests and documentation of the modes on an existing instance and of the namespace filter.
4. Polish: field coverage, generated files, documentation, submodule bump, `/pre-ci`.
