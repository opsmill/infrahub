---

description: "Task list for exporting the running schema (IFC-2964)"
---

# Tasks: Export the running schema

**Input**: design documents in `dev/specs/ifc-2964-schema-export/`: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md).

**Tests**: requested. The spec success criteria (SC-001 to SC-006) and research R8 and R10 define the tests, so each story phase lists its tests before its implementation tasks.

**Organization**: tasks are grouped by user story, so each story can be built and tested on its own.

**Two repositories**: tasks on files under `python_sdk/` change the SDK repository ([opsmill/infrahub-sdk-python](https://github.com/opsmill/infrahub-sdk-python)) on a branch made from `origin/infrahub-develop`. The SDK pull request merges first (plan, delivery order). All other tasks change this repository.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task belongs to (US1 to US4)

---

## Phase 1: Setup

**Purpose**: create the packages and the SDK branch.

- [X] T001 Create the package `backend/infrahub/schema/export/` with empty files `__init__.py`, `models.py` and `exporter.py`, next to `backend/infrahub/schema/read_schema.py`
- [X] T002 [P] Create the test package `backend/tests/unit/schema/export/` with an empty `conftest.py`; add `__init__.py` files to `backend/tests/unit/schema/` and `backend/tests/unit/schema/export/` if sibling packages such as `backend/tests/unit/api/` have them
- [X] T003 [P] In `python_sdk/`, fetch `origin` and create a working branch from `origin/infrahub-develop` (not from the SDK `develop` branch, see `AGENTS.md`, section Submodules)

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the load contract change, the shared property list and the export models. Every story needs them.

**No user story work starts until this phase is complete.**

- [X] T004 Move the local list `properties_to_inherit` out of `NodeInheritanceHandler.inherit_from_interface` into a module-level constant in `backend/infrahub/core/schema/node_inheritance_handler.py` (research R9). Keep the same eight values in the same order: `human_friendly_id`, `display_label`, `display_labels`, `default_filter`, `menu_placement`, `uniqueness_constraints`, `icon`, `order_by`. `inherit_from_interface` reads the constant. Behavior does not change; the existing unit tests for inheritance must still pass
- [X] T005 Change the code generation (research R3, R5, contracts/schema-load-contract.md):
  - in `tasks/backend.py::_sdk_root`, add the field `infrahub_version: str | None = None` to the generated write root `InfrahubSchemaWrite` only, not to the other roots `_sdk_root` builds;
  - in `backend/infrahub/core/schema/definitions/internal.py::ExtraField`, add the key `keep_in_export: NotRequired[bool]` (working name), and set it to `True` on `inherit_from` of nodes and generics. T028 adds the mark to the other fields that need it;
  - in `tasks/backend.py`, write the marked fields into a new constant in `python_sdk/infrahub_sdk/schema/generated/contract.py`, keyed by write model name and built the same way as `READ_ONLY_FIELDS` (`_write_sdk_generated_contract`)
- [X] T006 Run `uv run invoke backend.generate` and check that the only changes in `python_sdk/infrahub_sdk/schema/generated/` are the new `infrahub_version` field on `InfrahubSchemaWrite` in `write.py` and the new constant in `contract.py` (depends on T003, T005). Do not edit the generated files by hand. Run it again after T028 changes a mark
- [X] T007 In `backend/infrahub/api/schema.py::SchemaLoadAPI.build_internal_schema`, leave `infrahub_version` out of the data used to build `SchemaRoot`. `SchemaRoot` keeps `extra="forbid"` and gains no field (research R5). This change and the `python_sdk` submodule bump must land in the same commit (plan, delivery order), see T053
- [X] T008 [P] Add a test to `python_sdk/tests/unit/sdk/test_schema.py` that `infrahub_sdk/schema/validate.py::validate_schema` accepts a document with `infrahub_version` and reports no error for it (FR-012)
- [X] T009 [P] Add a test class to `backend/tests/functional/api/test_load_schema.py` that sends a schema with `infrahub_version: "1.0.0"` to `POST /api/schema/load` and to `POST /api/schema/check`. Assert status 200, no warning about the field, and the same schema hash as the same schema loaded without the field (FR-012, contracts/schema-load-contract.md)
- [X] T010 [P] In `backend/infrahub/schema/export/models.py`, define `SchemaExportMode` as a string enum with the values `BRIEF` and `FULL` (no `IDS` value, D6), and `SchemaExportDocument` as a subclass of the SDK `InfrahubSchemaWrite` with the field rules from data-model.md, section SchemaExportDocument:
  - `version`: `str`, always `"1.0"`;
  - `infrahub_version`: `str`, required on the response, set from `infrahub.__version__`;
  - `generics`: `list[GenericSchemaWrite]`, sorted by kind;
  - `nodes`: `list[NodeSchemaWrite]`, sorted by kind;
  - `extensions`: never written.
- [X] T011 In `backend/infrahub/schema/export/exporter.py`, add a function that builds a new processed core-only `SchemaBranch` on each call, holding `internal_schema`, `core_models` and `deprecated_models` as `backend/infrahub/core/initialization.py::first_time_initialization` does, with a schema cache of its own (research R4). Do not use `SchemaBranch.duplicate`, because the copy shares the original's `_cache` dictionary. Add the `SchemaExporter` class skeleton with the constructor argument `baseline_factory` and the method `export(schema_branch, mode, namespaces) -> SchemaExportDocument` (data-model.md, section SchemaExporter). The exporter keeps no schema between calls
- [X] T012 In `backend/tests/unit/schema/export/conftest.py`, add the in-memory round-trip helper (research R8): process a test schema on a new baseline (source), export it with a given mode, load the export into a new baseline with `SchemaBranch.load_schema`, process it, and compare the user-defined nodes and generics of source and target, ignoring IDs. Compare both sides after the conversions in data-model.md, section Conversions, using the same function as the reduction loop (T022, T024), because the target stores NumberPool ranges as `ranges` where the source may hold `start_range` and `end_range`. The helper also exports the target and compares the two documents, ignoring `infrahub_version` (SC-003). Add a fixture that returns a `SchemaExporter` built with the baseline function from T011

**Checkpoint**: a schema with `infrahub_version` loads, the models exist and the round-trip helper runs.

---

## Phase 3: User Story 1 - Copy the schema to an empty instance (Priority: P1) (MVP)

**Goal**: `GET /api/schema/export` returns the `BRIEF` document of a branch, and that document loads into an empty instance with no edits and gives the same user-defined schema.

**Independent test**: load a test schema into an empty instance, export it, load the export into a second empty instance, and compare the user-defined schema of both, ignoring IDs (spec, User Story 1).

### Tests for User Story 1

Write these first and check that they fail before the implementation tasks.

- [X] T013 [P] [US1] Add the variation schemas to `backend/tests/unit/schema/export/conftest.py` as inline fixtures, one per export rule, each in its own namespace (research R8, spec Assumptions):
  - a generic that sets the eight inherited properties from T004 and a node that takes them (pinned, FR-005);
  - a node that takes `human_friendly_id` from a generic and has its own `unique: true` attribute, so its `uniqueness_constraints` differ from the generic's (research R8);
  - a node with no generic and a `unique: true` attribute, from which processing derives `human_friendly_id` and `uniqueness_constraints` (all three written in `BRIEF`, research R3);
  - a user node in the `Ipam` namespace (exported, while `IpamNamespace` is not, research R2);
  - Text, TextArea and List attributes with the deprecated top-level `regex`, `min_length` and `max_length` (FR-008);
  - a NumberPool attribute with `start_range` and `end_range`, and one with only `start_range` (FR-009);
  - an extension that adds attributes and relationships to a user node;
  - an extension to a kind in a restricted namespace (not exported, D2);
  - an attribute and a relationship whose `branch` differs from the value derived from the node or the peer;
  - a generic with the deprecated `display_labels` and `default_filter`;
  - a hierarchical generic and nodes, which get generated `Hierarchy` relationships;
  - a node with `generate_profile` and `generate_template` set, which gets generated `Profile` and `Template` relationships;
  - an attribute with an explicit `order_weight`, an attribute with `optional: true` and a `default_value`, and an attribute whose `label` equals the label derived from its name
- [X] T014 [P] [US1] In `backend/tests/unit/schema/export/test_brief_mode.py`, add one round-trip test per variation schema from T013 in `BRIEF` mode, using the helper from T012 (SC-001, SC-003). Assert on the export document itself:
  - no `id`, no attribute or relationship with `inherited: true` on a node, no relationship of kind `Group`, `Profile`, `Hierarchy` or `Template`, no restricted namespace, no `IpamNamespace` (FR-003, FR-004);
  - the pinned properties are written on the node that took them from its generic (FR-005);
  - a `label` equal to the derived label is left out (FR-006);
  - on the node with the `unique: true` attribute, `unique`, `human_friendly_id` and `uniqueness_constraints` are all written. Do not assert that a derived value next to its source is left out (FR-006, research R3);
  - the export did not reach the `FULL` fallback (research R3);
  - `regex`, `min_length` and `max_length` appear only under `parameters`, and NumberPool ranges only as `ranges`, with an unset bound left unset (FR-008, FR-009);
  - `version` is `"1.0"` and `infrahub_version` is `infrahub.__version__` (FR-010)
- [X] T015 [P] [US1] In `backend/tests/unit/schema/export/test_brief_mode.py`, add the loop-termination test (research R3): a stored schema that processing changes, so differences remain. Assert that `export` ends, returns the candidate and logs a warning that names the branch and each remaining difference (kind, element name, field)
- [X] T016 [P] [US1] In `backend/tests/unit/schema/export/test_brief_mode.py`, add the two fallback tests (research R3): a candidate that a validator rejects, and a stored schema that the current validators reject. Each asserts that `export` raises nothing, returns the same document as the `FULL` build, and logs a warning with the branch and the error message
- [X] T017 [P] [US1] In `backend/tests/unit/schema/export/test_brief_mode.py`, add the memory and read-only tests (research R4), using all variation schemas from T013 loaded together:
  - several exports in a row leave the size of the registry's schema cache for the branch unchanged, and the `SchemaExporter` instance holds no schema after `export` returns;
  - after one export in `BRIEF` mode and one in `FULL` mode, `SchemaBranch.get_hash()` for the branch and a `model_dump()` of every user node and generic in the registry are the same as before the exports. The variation schemas with the deprecated `regex`, `min_length` and `max_length` and the NumberPool `start_range` and `end_range` must be among them, because their conversion is the most likely place for an in-place change
- [X] T018 [P] [US1] In `backend/tests/unit/schema/export/test_field_coverage.py`, add the field coverage test (research R10, SC-004). Collect the write models from `infrahub_sdk/schema/generated/write.py` by walking the field annotations of `NodeSchemaWrite` and `GenericSchemaWrite` and opening unions and lists. `AttributeSchemaWrite` is an `Annotated` union with no `model_fields`, so the walk must reach its members (`TextAttributeWrite`, `NumberAttributeWrite`, `ListAttributeWrite`, `NumberPoolAttributeWrite`, `GenericAttributeWrite`); it also reaches `RelationshipSchemaWrite`, the attribute-parameter write models, `DropdownChoiceWrite`, `NumberPoolRangeWrite` and the computed-attribute write models. Compare their `model_fields` with a table in the test module where each entry names the variation schema from T013 that covers the field, or marks it as not needing a test with a reason. Fail on:
  - a field missing from the table;
  - a table entry for a field that no longer exists;
  - a table entry whose named variation schema does not set the field on at least one element of that model.

  The table records coverage only, not how the export treats a field
- [X] T019 [P] [US1] Create `backend/tests/functional/api/test_schema_export.py` with the reset helper (research R8). It deletes only the user-defined schema and the objects of those kinds, then reloads the schema registry from the database. It keeps the root, the branches, the core schema, and the accounts, API tokens, groups and permissions the class fixtures created, so the SDK client stays logged in. It does not call `delete_all_nodes`. After each reset, assert that `GET /api/schema` holds only the nodes and generics the core schema defines, which includes `IpamNamespace` in the unrestricted `Ipam` namespace (research R2). The helper must not delete `IpamNamespace`
- [X] T020 [US1] In `backend/tests/functional/api/test_schema_export.py`, add two `TestInfrahubApp` classes, one for `models/base/` and one for all variation schemas from T013 loaded together (research R8). Each class loads the schema through `POST /api/schema/load`, exports it with `GET /api/schema/export`, resets the database with the helper from T019, loads the export and compares the schema read back from `GET /api/schema` with the source, ignoring IDs. Assert:
  - the load gives no error and no warning other than the deprecation warnings for `display_labels` and `default_filter` (SC-002);
  - a NumberPool loaded with `start_range` and `end_range` has the same ranges on the target and the load gives no warning (SC-006);
  - a second export is identical to the first apart from `infrahub_version` (SC-003);
  - `GET /api/schema/export?branch=<name>` returns the schema of that branch (User Story 1, scenario 2);
  - after a reset, the export returns status 200 with `nodes` and `generics` empty, so `IpamNamespace` is not in it (contracts/schema-export-api.md);
  - the JSON body of the `BRIEF` response holds no key the loop removed: no `label` on an attribute whose label is derived from its name, and no field with its default value that the stored schema did not need (research R3, R8);
  - an account that has no permission other than the default read access can call the export and gets status 200, as it can for `GET /api/schema` (FR-002, D10);
  - the export time and pass count for `models/base/` are printed in the test output (research R4)

### Implementation for User Story 1

- [X] T021 [US1] In `backend/infrahub/schema/export/exporter.py`, build the `FULL` document of all user namespaces (research R1, R2):
  - the endpoint passes the branch schema from `registry.schema.get_schema_branch`, which returns the registry's own `SchemaBranch`, not a copy. Read its nodes and generics without copying them and never call `SchemaBranch.set` on it (research R4);
  - treat every stored element as read-only: these are the registry's own objects. Take `model_dump()` of each stored element and do every removal in this task, and every conversion in T022, on that data or on the write models. Never assign to, delete from or call a method that changes a stored element, and never use `model_copy()` on one, because its copy is shallow and shares nested lists and parameter objects with the registry;
  - build each node, generic, attribute, relationship and attribute-parameter entry by validating the stored element's dump against its SDK write model. `AttributeSchemaWrite` is an `Annotated` union of five attribute models that Pydantic selects by `kind`, not a model, so validate an attribute's dump with `TypeAdapter(AttributeSchemaWrite)`, not with one member model;
  - remove `id` on every element, every node and generic whose namespace is in `backend/infrahub/core/constants/__init__.py::RESTRICTED_NAMESPACES`, every node and generic whose kind the core schema definitions define (`core_models`, `deprecated_models`, `internal_schema`; read the kinds from the definitions without processing them, and keep no hand-written list; today this removes `IpamNamespace`), attributes and relationships with `inherited: true` on nodes, and relationships of kind `Group`, `Profile`, `Hierarchy` and `Template` (`RelationshipKind`);
  - write only values that are set (no `None`);
  - sort nodes and generics by kind, and attributes and relationships by `order_weight`, then by name (data-model.md)
- [X] T022 [US1] In `backend/infrahub/schema/export/exporter.py`, convert the deprecated forms in the `FULL` build (data-model.md, section Conversions). Convert the dumped data or the write models, never the stored attribute or its `parameters` object (see T021):
  - top-level `regex`, `min_length` and `max_length` on Text, TextArea and List attributes are written only under `parameters` (FR-008);
  - NumberPool `parameters.start_range` and `parameters.end_range` become one entry of `parameters.ranges` with the same bounds; a bound that was not set stays unset (FR-009)
- [X] T023 [US1] In `backend/infrahub/schema/export/exporter.py`, compute the pinned properties of each node (research R9): for a node with `inherit_from`, each property in the constant from T004 whose value equals the stored value of the first generic in `inherit_from` that sets it. Read the list from the constant; do not copy it. Only read the stored node and generics; do not change them (see T021)
- [X] T024 [US1] In `backend/infrahub/schema/export/exporter.py`, implement the `BRIEF` reduction loop as research R3 describes:
  1. start from the `FULL` document of all user namespaces;
  2. build a candidate by removing every optional field of each element, except the pinned properties from T023, the fields the write model requires, and the fields in the generated `keep_in_export` constant from T005 and T006;
  3. load the candidate into a new baseline from the baseline function with `SchemaBranch.load_schema` and run `SchemaBranch.process` with validation, as `backend/infrahub/api/schema.py::evaluate_candidate_schemas` does;
  4. compare every write-visible field of each exported element with the stored element, ignoring IDs, after applying the conversions from T022 to both sides, so a NumberPool stored with `start_range` and `end_range` equals one that holds the same bounds in `ranges`;
  5. put back from the `FULL` document every differing field the candidate does not hold;
  6. repeat while the previous pass put back at least one field.

  Keep the candidate as a dict built from the `FULL` document's `model_dump(exclude_unset=True)`, remove fields by deleting keys, and validate it into a `SchemaExportDocument` only at the end, so the document's set fields are the keys the loop kept (research R3). Do not try to remove a field again after the loop put it back: a derived value and its source are both written (FR-006).

  When differences remain, return the candidate and log a warning with the branch and each remaining difference (kind, attribute or relationship name, field). Log each field put back at debug level with its kind and element name
- [X] T025 [US1] In `SchemaExporter.export` in `backend/infrahub/schema/export/exporter.py`, catch `ValueError` and `infrahub.exceptions.ValidationError` raised while processing a candidate, stop the loop, log a warning with the branch and the error message, and return the `FULL` document (research R3). No other exception is caught
- [X] T026 [US1] In `SchemaExporter.export`, set `version` to `"1.0"` and `infrahub_version` to `infrahub.__version__`, and log the pass count and the export time at debug level with the branch name (research R4, FR-010)
- [X] T027 [US1] In `backend/infrahub/api/schema.py`, add `GET /api/schema/export` declared before `get_schema_by_kind` (research R7). It takes `branch` through `get_branch_dep` and the same authentication dependency as `get_schema` (D10, no new permission), gets the branch schema from `registry.schema.get_schema_branch`, gets a `SchemaExporter` through a FastAPI dependency, calls `export` with `SchemaExportMode.BRIEF` and all namespaces, and returns `SchemaExportDocument` with `response_model_exclude_unset=True` on the route, so a field the export left out is absent from the body (data-model.md, section Serialization). It has no error responses of its own (contracts/schema-export-api.md)
- [X] T028 [US1] Run `uv run pytest backend/tests/unit/schema/export/ backend/tests/functional/api/test_schema_export.py` and fix failures until every variation schema and `models/base/` round-trip in `BRIEF` mode without reaching the fallback and without remaining differences (research R8). When a candidate fails validation because the loop removed a field that processing does not derive, set `keep_in_export` on that field's definition in `backend/infrahub/core/schema/definitions/internal.py` and rerun T006; do not add a list of fields to the exporter. List the fields marked in the Infrahub pull request description

**Checkpoint**: User Story 1 works on its own. This is the MVP.

---

## Phase 4: User Story 2 - Update an instance that has an earlier version of the schema (Priority: P2)

**Goal**: the schema owner exports in `FULL` mode and gets every value of the user-defined schema, including derived values.

**Independent test**: load the same nodes with different labels into two instances, export from the first in `FULL` mode, and check that the export holds the first instance's labels (spec, User Story 2).

### Tests for User Story 2

- [X] T029 [P] [US2] In `backend/tests/unit/schema/export/test_full_mode.py`, add one round-trip test per variation schema from T013 in `FULL` mode (SC-001, SC-003), and the check that reads the exported document alone and finds every write-visible field that has a value on the stored element, except the ones FR-003 and FR-004 remove and the deprecated forms T022 converts (SC-005). This includes `state`, which every write model has, so a `FULL` export writes `state: present` on each element
- [X] T030 [P] [US2] In `backend/tests/unit/schema/export/test_full_mode.py`, add the label scenario (User Story 2): two in-memory schemas with the same nodes and different labels; the `FULL` export of the first holds its labels, and the `BRIEF` export of the first leaves out a label derived from the attribute name. Also assert that `FULL` writes `label`, `branch`, `order_weight` and a `human_friendly_id` taken from a unique attribute (FR-007)
- [X] T031 [P] [US2] In `backend/tests/functional/api/test_schema_export.py`, run both test classes from T020 in `FULL` mode as well as `BRIEF`, so each class resets the database once per mode (research R8). Add a test that `mode=OTHER` returns 422 with FastAPI's request validation error

### Implementation for User Story 2

- [X] T032 [US2] In `SchemaExporter.export` in `backend/infrahub/schema/export/exporter.py`, return the `FULL` document from T021 and T022 without running the reduction loop when `mode` is `SchemaExportMode.FULL` (FR-007)
- [X] T033 [US2] In `backend/infrahub/api/schema.py`, add the query parameter `mode: SchemaExportMode = SchemaExportMode.BRIEF` to `GET /api/schema/export` and pass it to `export` (FR-001)

**Checkpoint**: User Stories 1 and 2 both work on their own.

---

## Phase 5: User Story 3 - Export selected namespaces (Priority: P3)

**Goal**: the schema owner exports only some namespaces, and the values of each exported node are the same as in an export without the filter.

**Independent test**: export one namespace of a schema whose nodes reference a node in another namespace, and check the content of the export (spec, User Story 3).

### Tests for User Story 3

- [X] T034 [P] [US3] In `backend/tests/unit/schema/export/test_brief_mode.py` and `backend/tests/unit/schema/export/test_full_mode.py`, add a test with two namespaces where a node in the first has a relationship to a node in the second. Export with a filter on the first namespace and assert, in both modes, that the document holds only that namespace and that each node and generic in it is identical to the same entry of the unfiltered export (FR-011). Add a case where the filter names a restricted namespace and assert that it is ignored
- [X] T035 [P] [US3] In `backend/tests/functional/api/test_schema_export.py`, add a test for `GET /api/schema/export?namespaces=Location` on `models/base/`: the namespaces in the document are `["Location"]`, and relationships to kinds in other namespaces are written as in the unfiltered export (quickstart.md, manual scenario 3)

### Implementation for User Story 3

- [X] T036 [US3] In `SchemaExporter.export` in `backend/infrahub/schema/export/exporter.py`, apply the `namespaces` filter after the reduction loop (or after the `FULL` build in `FULL` mode), keeping only nodes and generics in the selected namespaces. The loop always runs on all user namespaces (research R6). Restricted namespaces in the filter are ignored
- [X] T037 [US3] In `backend/infrahub/api/schema.py`, add the repeatable query parameter `namespaces` to `GET /api/schema/export` with the same declaration as on `get_schema`, and pass it to `export` (FR-001, FR-011)

**Checkpoint**: User Stories 1, 2 and 3 work on their own.

---

## Phase 6: User Story 4 - Keep the current file layout of the CLI (Priority: P3)

**Goal**: `infrahubctl schema export` calls the endpoint, writes one file per namespace by default or one file with `--single-file`, and names the server version needed when the server has no endpoint.

**Independent test**: run the CLI with and without the single-file option and compare the files written (spec, User Story 4).

All tasks in this phase change the SDK repository and use `httpx_mock` for the HTTP responses, as the existing SDK tests do. They do not need the Infrahub endpoint to exist.

### Tests for User Story 4

- [X] T038 [P] [US4] Rewrite `python_sdk/tests/unit/sdk/test_schema_export.py` for the endpoint response (research R8):
  - `InfrahubSchema.export` and `InfrahubSchemaSync.export` send `GET /api/schema/export` with `branch`, each `namespaces` value and `mode`, and return the response as a `SchemaExportDocument` with the same content;
  - `split_by_namespace` returns one `SchemaExportDocument` per namespace, each with the `version` and `infrahub_version` of the input and the nodes and generics of that namespace in the input order;
  - a 422 with the message `Unable to find the schema 'export' in the registry` raises the error that names the first release with the endpoint (FR-016);
  - a 422 with any other message, and a 500, are reported as the server returned them and do not mention the release
- [X] T039 [P] [US4] Add CLI tests to `python_sdk/tests/unit/ctl/schema/test_schema.py` for `infrahubctl schema export` (contracts/infrahubctl-schema-export.md):
  - without `--single-file`: one file per namespace named `<namespace in lower case>.yml`, each with `version` and `infrahub_version`, then `generics`, then `nodes` (FR-014);
  - with `--single-file`: one file `schema.yml` that holds the endpoint's document (FR-014);
  - each file holds only the keys of the mocked response; a field the response left out is not written with its default value (research R8);
  - `--mode FULL` and each `--namespaces` value are sent to the endpoint (FR-013, FR-015);
  - an empty document prints `No user-defined schema found to export.`;
  - the older-server response prints the error naming the release and exits with code 1; any other error response is printed as the server returned it and exits with code 1

### Implementation for User Story 4

- [X] T040 [US4] In `python_sdk/infrahub_sdk/schema/export.py`, remove the client-side export rules and models: `schema_to_export_dict`, `RESTRICTED_NAMESPACES`, `_SCHEMA_EXPORT_EXCLUDE`, `_AUTO_GENERATED_REL_KINDS` and the other constants they use, `NamespaceExport` and `SchemaExport` (D8). Add (contracts/infrahubctl-schema-export.md, section SDK methods):
  - `SchemaExportDocument`: a subclass of `InfrahubSchemaWrite` from `infrahub_sdk/schema/generated/write.py` with `infrahub_version: str` required;
  - `split_by_namespace(document: SchemaExportDocument) -> dict[str, SchemaExportDocument]`: one document per namespace, each with the input's `version` and `infrahub_version` and the nodes and generics of that namespace in the input order.

  `python_sdk/infrahub_sdk/ctl/schema_format.py` has its own `RESTRICTED_NAMESPACES` constant for the offline formatter; it is not part of the export, so leave it unchanged
- [X] T041 [US4] In `python_sdk/infrahub_sdk/schema/__init__.py`, remove the removed names from the imports and from `__all__`, export `SchemaExportDocument` and `split_by_namespace`, and add a module constant that holds the first Infrahub release with the endpoint. Its value is the release that ships the endpoint; the sources do not confirm it (research R7), so confirm it with the release owner before the SDK pull request merges
- [X] T042 [US4] In `python_sdk/infrahub_sdk/schema/__init__.py`, rewrite `InfrahubSchema.export` and `InfrahubSchemaSync.export` to call `GET /api/schema/export` with `branch`, `namespaces` and a new `mode` argument (default `BRIEF`), and return the response as a `SchemaExportDocument` (the return type changes from `SchemaExport`). Treat only a 422 whose error message is `Unable to find the schema 'export' in the registry` as "endpoint missing" and raise an error that names the release constant from T041. Pass any other error response through unchanged (research R7, FR-016)
- [X] T043 [US4] In `python_sdk/infrahub_sdk/ctl/schema.py::export`, add `--mode [BRIEF|FULL]` (default `BRIEF`) and `--single-file` (default off), call the SDK `export` method, and write the files as contracts/infrahubctl-schema-export.md describes: the document itself with `--single-file`, otherwise one file per entry of `split_by_namespace`, with YAML written with `sort_keys=False` from `model_dump(exclude_unset=True)`, so a file holds only the keys of the response. Keep `--directory`, `--branch` and `--namespaces` as they are. On the older-server error and any other error response, print the message and exit with code 1
- [X] T044 [US4] Add the SDK changelog fragments in `python_sdk/changelog/` (plan, section Changelog fragments; use the `creating-changelog-entries` skill):
  - `changed`: `infrahubctl schema export` uses the endpoint and needs a server that has it, and lists each difference in the files it writes: `branch` written when it differs from the derived value; derived values such as a `label` taken from the name left out; `IpamNamespace` no longer written; the generated `object_template` relationship no longer written; `regex`, `min_length` and `max_length` written under `parameters`; NumberPool `start_range` and `end_range` written as `ranges`; an `infrahub_version` field in each file;
  - `changed`: `InfrahubSchema.export` and `InfrahubSchemaSync.export` return a `SchemaExportDocument` instead of a `SchemaExport`, and `split_by_namespace` gives one document per namespace;
  - `added`: the `--mode` and `--single-file` options;
  - `removed`: `schema_to_export_dict`, `RESTRICTED_NAMESPACES`, `NamespaceExport` and `SchemaExport` from `infrahub_sdk.schema`, each named
- [X] T045 [US4] In `python_sdk/`, regenerate the `infrahubctl` reference documentation with the SDK `docs-generate` invoke task, which rewrites `python_sdk/docs/docs/infrahubctl/infrahubctl-schema.mdx`. Run the SDK lint and unit tests for the changed files

**Checkpoint**: all four user stories work on their own.

---

## Phase 7: Polish, generated files and documentation

**Purpose**: generated contracts, documentation, changelog and the cross-repository commit.

- [X] T046 [P] Regenerate `schema/openapi.json` with `uv run invoke schema.generate-jsonschema`, then `frontend/app/src/shared/api/rest/types.generated.ts` with `cd frontend/app && pnpm codegen` (FR-017). Do not edit either file by hand
- [X] T047 [P] Regenerate the schema-file JSON schema built from `SchemaLoadAPI` (`backend/infrahub/cli/dev.py::export_node_schema`) with `uv run invoke schema.generate-infrahubnodeschema`, and the reference docs with `uv run invoke docs.generate`
- [X] T048 [P] Write `docs/docs/schema/export.mdx` and add it to the schema section of `docs/sidebars.ts` next to `schema/create-and-load` (FR-018). Use the `writing-infrahub-docs` skill. The page covers:
  - the `BRIEF` and `FULL` modes, and the `branch` and `namespaces` parameters;
  - the `infrahubctl schema export` options, including `--single-file` (D9);
  - the known limitations from D2 (extensions to restricted kinds are not exported, and neither is `IpamNamespace` or a change to it), D3 (a value equal to the derived value is left out and then follows its source field, while a derived value can be written next to the value it comes from) and D4 (properties taken from a generic are written on the node);
  - what a load into an instance that already has some of the same nodes does not change: nothing is removed, and a value the source does not set is not written (spec Edge Cases);
  - each case in spec Edge Cases where a load can fail, with the error the schema owner gets. Get each error text by running the case, not from memory
- [X] T049 [P] In `docs/docs/objects/import-from-csv.mdx`, the only page outside the reference that describes `infrahubctl schema export` today, update the row about the export so it matches the new output and links to `docs/docs/schema/export.mdx`. Change only the text about the export
- [X] T050 [P] Write `dev/knowledge/backend/schema-export.md` (FR-019, follow `dev/guidelines/documentation.md`), covering:
  - which fields the export writes, and that a field's `visibility` decides it (research R1);
  - how the `BRIEF` reduction loop decides which values to leave out, and how to find out why a value was left out: the debug log of fields put back (research R3);
  - the `keep_in_export` mark on field definitions: which fields have it, why, and how a missing mark shows in CI (research R3);
  - why a derived value can be written next to its source, and that the export leaves out kinds the core schema defines, such as `IpamNamespace` (research R2, R3);
  - that `BRIEF` output can change between releases when schema processing changes, while the export still loads to the same schema;
  - which properties a node keeps from its generic, and that the list is the constant in `backend/infrahub/core/schema/node_inheritance_handler.py` (research R9)

  Add an entry for it to the knowledge list in `backend/AGENTS.md`
- [X] T051 [P] Add the Infrahub changelog fragments in `changelog/` (plan, section Changelog fragments; use the `creating-changelog-entries` skill): `added` for `GET /api/schema/export` with the `BRIEF` and `FULL` modes, and `changed` for the schema load accepting and ignoring `infrahub_version`
- [ ] T052 Open the SDK pull request on `infrahub-develop` with T006, T008 and T038 to T045, and wait for it to merge (plan, delivery order). The generated `contract.py` must hold the final `keep_in_export` marks, so regenerate it after T028
- [ ] T053 Bump the `python_sdk` submodule to the merged SDK commit in the same commit as the `SchemaLoadAPI.build_internal_schema` change from T007 (plan, delivery order). The Infrahub pull request also carries the `tasks/backend.py` change from T005, so the generated-file check in CI agrees with the submodule
- [X] T054 Run `uv run invoke format`, `uv run invoke lint`, `uv run invoke docs.lint` and `uv run invoke docs.validate`, and fix every error
- [ ] T055 Run the automated checks and manual scenarios in [quickstart.md](quickstart.md) and record the export time and pass count for `models/base/` from the functional test output in the Infrahub pull request description

---

## Dependencies and execution order

### Phase dependencies

- **Setup (Phase 1)**: no dependency.
- **Foundational (Phase 2)**: depends on Phase 1. Blocks every user story.
- **User Story 1 (Phase 3)**: depends on Phase 2.
- **User Story 2 (Phase 4)**: depends on T021 and T022 (the `FULL` build) and T027 (the endpoint) from User Story 1.
- **User Story 3 (Phase 5)**: depends on T024 and T027 from User Story 1, and on T032 from User Story 2, because T034 tests the filter in `FULL` mode and T036 applies it after the `FULL` build.
- **User Story 4 (Phase 6)**: depends only on T003 and T006 in Phase 2, because its tests mock the endpoint. It can run in parallel with User Stories 1 to 3, and it must finish before T052. The SDK pull request itself waits for T028 (see Polish).
- **Polish (Phase 7)**: T046 and T047 need the endpoint and its parameters (T027, T033, T037). T052 needs Phase 6 and T028, because T028 can change the `keep_in_export` marks that the SDK's generated `contract.py` holds. T053 needs T052. T054 and T055 come last.

### Within each story

- Tests first; they fail before the implementation.
- In User Story 1: T021 and T022 (`FULL` build) before T023 and T024 (`BRIEF`), before T025 and T026, before the endpoint T027.

### Parallel opportunities

- T002 and T003 in Phase 1.
- T008, T009 and T010 in Phase 2. T008 needs T006; T009 needs T006 and T007.
- All User Story 1 test tasks T013 to T019, then T020 after T019.
- User Story 3 test tasks T034 and T035 once T032 is done.
- User Story 4 (SDK repository) alongside User Stories 1 to 3 (this repository).
- T046 to T051 in Phase 7.

## Parallel example: User Story 1

```text
Task: "Add the variation schemas to backend/tests/unit/schema/export/conftest.py"
Task: "Add the field coverage test in backend/tests/unit/schema/export/test_field_coverage.py"
Task: "Create the reset helper in backend/tests/functional/api/test_schema_export.py"
```

## Parallel example: User Story 4 and User Story 1

```text
Task: "Rewrite python_sdk/tests/unit/sdk/test_schema_export.py for the endpoint response"   (SDK repository)
Task: "Build the FULL document in backend/infrahub/schema/export/exporter.py"                (this repository)
```

## Implementation strategy

### First increment: User Story 1

1. Phase 1 and Phase 2.
2. Phase 3: the `BRIEF` export through the endpoint.
3. Check: `uv run pytest backend/tests/unit/schema/export/ backend/tests/functional/api/test_schema_export.py` passes, and no test schema reaches the fallback or leaves a difference.

### Next increments

1. User Story 2: the `mode` parameter and `FULL` tests.
2. User Story 3: the `namespaces` parameter.
3. User Story 4: the SDK and CLI, which can be built at any point after Phase 2 and merges before the Infrahub pull request.
4. Phase 7: generated files, documentation, changelog, the submodule commit.

## Notes

- After the first release that has the endpoint, add the SDK integration test for `infrahubctl schema export` in `python_sdk/tests/integration/` (plan, delivery order, step 3; research R8). It is not a task here, because it cannot pass against a released image before then.
- Follow-up from spec Follow-ups for the QA test plan: check that `order_weight` matches on the target after a schema has been loaded in several steps on the source.
- Between the SDK merge and the Infrahub merge, `infrahubctl schema export` from `infrahub-develop` fails against every server (plan, delivery order). Only the development SDK branch is affected.
