# Research: Export the Running Schema

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-10-26

## Sources

- The design document
  [INFP-723 · Export the running schema](https://app.notion.com/p/opsmill/INFP-723-Export-the-running-schema-401228b83025812589c6e6664594db35)
  (Notion, status "Draft", read on 2026-10-26). D1 to D12 refer to its section 3.
- The cards [INFP-723](https://opsmill.atlassian.net/browse/INFP-723) and
  [IFC-2964](https://opsmill.atlassian.net/browse/IFC-2964)
  ([opsmill/infrahub#10094](https://github.com/opsmill/infrahub/issues/10094)).
- The code on `develop` at `bc12036`, and the `python_sdk` submodule at `8e4a455` (contained in
  `origin/infrahub-develop`; the 30 commits after it touch neither `infrahub_sdk/schema/` nor
  `infrahub_sdk/ctl/schema.py`).
- [ADR 0010](../../adr/0010-generated-user-facing-schema-contract.md): the write and read schema models are
  generated from the field `visibility` in `backend/infrahub/core/schema/definitions/internal.py`.

Each finding below was read from the code. Findings marked **not verified** were not run.

## R1. How `BRIEF` decides which values to leave out

- **Decision**: Remove, then restore until nothing changes.
  1. Build the `FULL` document for the selected kinds (R2).
  2. Remove from it every value in the list of derivable fields (R1 table) and every value equal to its
     write-model default.
  3. Process the result in memory: load the internal schema, the core models, the user namespaces that are
     not exported (as `FULL` documents, so peers resolve), then the candidate, and call
     `infrahub.core.schema.schema_branch::SchemaBranch.process`.
  4. Build the `FULL` document of the processed result and compare it with step 1, field by field, with
     elements matched by `kind` (nodes, generics) or `name` (attributes, relationships, dropdown choices).
  5. Write back each value that differs, and repeat from step 3 until the comparison finds no difference.
  The loop ends: each pass only adds values back, and there are finitely many.
- **Rationale**:
  - Several derivations depend on other values or on order and cannot be decided per field: dropdown
    colours (`infrahub.core.schema.schema_branch::SchemaBranch.process_dropdowns` picks a colour not already
    used), the `human_friendly_id` taken from the first unique attribute in list order
    (`SchemaBranch._derive_human_friendly_id`), and `order_weight` (R5). A fixed rule list repeats the drift
    that IFC-2964 is about.
  - `SchemaBranch.process` does not access the database (no `await` in `schema_branch.py`), and
    `infrahub.api.schema::evaluate_candidate_schemas` already loads and processes a candidate in memory.
    `backend/tests/unit/core/schema/test_schema_branch.py::_load_processed_branch` does the same in tests.
  - `process` reads `config.SETTINGS.main.schema_strict_mode` and
    `config.SETTINGS.security.restrict_untrusted_jinja2_filters`. The simulation runs in the same process
    with the same settings as a load, so it reaches the same result as a load on that instance.
- **Alternatives considered**:
  - A fixed list of rules, as the SDK has today (`infrahub_sdk.schema.export`). Rejected: it cannot
    reproduce order-dependent values and drifts from the schema model.
  - Try removing one field at a time and process after each. Rejected: one `process` run per field is too
    slow on `models/base/`.

Fields removed in step 2 (each is restored by step 5 when processing does not reproduce it):

| Element | Fields | Derived by |
|---------|--------|------------|
| Node, generic | `label` | `SchemaBranch.process_labels` |
| Node | `human_friendly_id`, `uniqueness_constraints`, `display_label`, only when no generic in `inherit_from` sets the property (R4) | `SchemaBranch._derive_human_friendly_id`, `SchemaBranch.sync_uniqueness_constraints_and_unique_attributes`, `validators.schema_branch.display_label_validator::DisplayLabelValidator` |
| Generic | `human_friendly_id`, `uniqueness_constraints`, `display_label` | same |
| Attribute | `label`, `optional`, `branch`, `order_weight` | `process_labels`, `process_default_values`, `process_deprecations`, `process_branch_support`, `_generate_weight_*` |
| Relationship | `label`, `optional`, `min_count`, `max_count`, `identifier`, `on_delete`, `branch`, `order_weight` | `process_labels`, `process_cardinality_counts`, `generate_identifiers`, `process_relationships`, `process_branch_support`, `_generate_weight_*` |
| Dropdown choice | `label`, `description`, `color` | `process_dropdowns` |

## R2. Which fields the export writes

- **Decision**: The fields of the SDK write models, generated from the `visibility` of each field
  (ADR 0010): `infrahub_sdk.schema.generated.write::NodeSchemaWrite`, `GenericSchemaWrite`,
  `AttributeSchemaWrite`, `RelationshipSchemaWrite` and the attribute parameter write models. Three write
  fields are left out in both modes because they identify an element in one instance: `id`, `state` and the
  NumberPool `number_pool_id` (set by `infrahub.pools.schema_number_pool_synchronizer`).
- **Rationale**: Visibility is the source of truth that ADR 0010 already uses for the load contract, so a
  field added with `WRITE` visibility is exported, and one with `READ` or `INTERNAL` visibility is not. This
  is what IFC-2964 asks for: the list comes from the internal schema, not from a hand-maintained copy.
  Read-only fields (`hash`, `kind`, `inherited`, `used_by`, `hierarchy`, relationship `hierarchical`) are
  not on the write models, so the load never reports them as read-only (FR-012).
- **Alternatives considered**: The backend generated models in `backend/infrahub/core/schema/generated/`.
  Rejected: they carry the `update` flag but not the visibility.

## R3. Elements the export leaves out

| Element | How it is recognised |
|---------|----------------------|
| Restricted namespaces, including generated profiles (`Profile`) and templates (`Template`), and extensions to their kinds | `infrahub.core.constants::RESTRICTED_NAMESPACES`; `SchemaBranch.get_namespaces` uses the same list for `user_editable` |
| Inherited attributes and relationships | `inherited=True`, set by `infrahub.core.schema.node_inheritance_handler::NodeInheritanceHandler` |
| `profiles`, `object_template` | not stored, `infrahub.core.schema.manager::SchemaManager._virtual_relationship_names`; generated by `SchemaBranch.manage_profile_relationships` and `SchemaBranch.manage_object_template_relationships` |
| `member_of_groups`, `subscriber_of_groups` | name, kind `Group` and identifier `group_member` or `group_subscriber` (`SchemaBranch.add_groups`) |
| `parent`, `children` of a hierarchy | name, kind `Hierarchy` and identifier `parent__child` (`SchemaBranch.add_hierarchy_generic`, `add_hierarchy_node`) |

- **Decision**: Recognise generated relationships by name, kind and identifier together.
- **Rationale**: Users may set the relationship kinds `Group` and `Hierarchy` themselves (no validation
  blocks it; **not verified**). The SDK uses the kind alone (`infrahub_sdk.schema.export::_AUTO_GENERATED_REL_KINDS`),
  which would drop such a relationship.
- An extension to a Core node is stored as an attribute of a node in a restricted namespace, so filtering
  by namespace leaves it out (FR-005, D2).

## R4. Properties copied from a generic (FR-007)

- **Decision**: On a node, a property in the FR-007 list is written whenever a generic in `inherit_from`
  sets that property. It is not a candidate for removal in R1 step 2. When no generic sets it, R1 applies.
- **Rationale**: `NodeInheritanceHandler.inherit_from_interface` copies the property from the first generic
  in `inherit_from` that sets it, when the node's value is empty. The stored node cannot tell a copied value
  from one the user wrote (D4). The list in `inherit_from_interface` matches FR-007 exactly.
- `display_labels` and `display_label` are also copied by `DisplayLabelValidator`, which copies only when
  exactly one generic sets them. The rule above covers both cases.

## R5. Order of the document and `order_weight`

- **Decision**:
  - `generics` before `nodes`, each sorted by namespace and then by name.
  - Attributes, then relationships, each sorted by stored `order_weight` and then by name.
  - `order_weight` is removed in R1 step 2 and restored by step 5 when processing gives a different value.
- **Rationale**:
  - FR-013 needs a stable order, and sorting by kind gives the same document after a reload.
  - `SchemaBranch._generate_weight_generics` and `_generate_weight_nodes_profiles` give an element without a
    weight `position * 1000`, counting attributes and then relationships in list order, inherited elements
    included. Writing the elements in weight order lets most weights drop out. Gaps left by removed elements
    are never renumbered, so their weights are restored by step 5.
- **Known limitation**: `update_from_generic` keeps a node's own `order_weight` and `branch` on inherited
  elements, so a weight that drifted after a change to the generic is not reproduced. Neither mode can
  reproduce it, because inherited elements are not exported. The documentation states it.

## R6. Deprecated fields and warnings on load

- **Finding**: `infrahub.core.schema::SchemaRoot.gather_warnings` warns on every `display_labels`, every
  `default_filter`, the top-level `min_length` and `max_length`, and the NumberPool `start_range` and
  `end_range` shorthand (`SchemaRoot._number_pool_shorthand_warnings`).
- **Finding**: Processing does not convert the NumberPool shorthand into `ranges`
  (`infrahub.core.schema.attribute_parameters::NumberPoolParameters.validate_ranges` keeps it). This answers
  the check that the spec listed under "Not decided yet".
- **Decision**:
  - Validation settings are written only in `parameters` (FR-009). The legacy top-level fields are synced
    both ways with `parameters`, and `parameters` wins (`SchemaBranch._reconcile_legacy_attribute_parameters`),
    so this reloads identically and removes one source of warnings.
  - `display_labels`, `default_filter` and the NumberPool shorthand are written as they are stored. The
    load then gives the same deprecation warnings as the load that created them.
- **Rationale**: Dropping `display_labels` or `default_filter` changes the stored schema (FR-012 asks for an
  identical schema), and converting the shorthand changes the stored value. These fields exist only when a
  schema owner wrote them, so the source load gave the same warnings.
- **Warnings are reported per element**: `gather_warnings` adds one warning per node or generic. A
  `default_filter` or `display_labels` copied from a generic onto its nodes (FR-007) therefore gives one
  warning per node, where the source load gave one for the generic. The tests compare the warning messages
  (the deprecated fields named), not their number.
- **Spec change**: FR-012 and SC-001 say "no warnings". They now say "no warnings other than the
  deprecation warnings for deprecated fields that the source schema contains". This is the only way to
  meet "identical schema" for a source that uses deprecated fields.

## R7. Infrahub version field

- **Decision**: Name `infrahub_version`, a string, optional, written by the export with
  `infrahub::__version__`.
  - SDK: add `infrahub_version: str | None = None` to the write root through
    `tasks/backend.py::_sdk_root`, then regenerate with `uv run invoke backend.generate`. Do not add it to the
    read-only root fields: a read-only field gives a warning (FR-012).
  - Backend: add `infrahub_version: str | None = None` to `infrahub.core.schema::SchemaRoot`, which forbids
    extra keys and is built from the request body by `infrahub.api.schema::SchemaLoadAPI.build_internal_schema`.
    No code reads it (D7).
  - Formatter: add it to `infrahub_sdk.ctl.schema_format::FILE_ORDER` after `version`.
- **Rationale**: `SchemaLoadAPI` subclasses the generated `InfrahubSchemaWrite`, and
  `infrahub_sdk.schema.validate::validate_schema` reports any unknown root key as an error, so both the SDK
  validation and `POST /api/schema/load` accept the field once it is generated. The editor JSON Schema
  (`infrahub dev export-node-schema`, `infrahub.core.schema.write_json_schema::build_write_json_schema`) is
  built from the same model, so it gains the field too. How that file is published to `schema.infrahub.app`
  is **not verified**.

## R8. Mode parameter

- **Decision**: Query parameter `mode`, a string enum `SchemaExportMode` with values `brief` (default) and
  `full`. `infrahubctl schema export --mode brief|full`.
- **Rationale**: Lower-case values follow the other string enums in the REST API, such as
  `BranchSupportType`. The spec writes the modes as `BRIEF` and `FULL`; they are the same modes.

## R9. Endpoint

- **Decision**: `GET /api/schema/export` in `infrahub.api.schema`, declared before `get_schema_by_kind`
  (`/{schema_kind}`). Otherwise `/export` is read as a schema kind.
  - `branch`: `infrahub.api.dependencies::get_branch_dep`, as `GET /api/schema`. A missing branch means the
    default branch; an unknown one gives `BranchNotFoundError` (HTTP 400). This answers the spec's
    assumption on an unknown branch.
  - `namespaces`: `list[str] | None`, exact match, as `GET /api/schema`.
  - Access: `infrahub.api.dependencies::get_current_user` only, as `GET /api/schema`. Anonymous access works
    when `allow_anonymous_access` is on (D10).
  - Response: the document, validated against the SDK `InfrahubSchemaWrite` model and serialised with the
    values that were set only, so values left out stay out and an export that would not load fails in
    Infrahub, not on the target.
- **Rationale**: Same parameters and access as `GET /api/schema` (D10, D11). Validating the response against
  the write model gives a check of FR-012 on every call.

## R10. `FULL` export and settings Infrahub cannot update

- **Finding**: The load refuses the change. `evaluate_candidate_schemas` calls
  `SchemaBranch.validate_update` with `enforce_update_support=True`, and
  `infrahub.core.models::SchemaUpdateValidationResult._process_field` adds a `NOT_SUPPORTED` error for node
  `branch`, attribute `branch`, relationship `identifier`, `branch`, `direction` and `hierarchical`, and
  NumberPool `number_pool_id`. `POST /api/schema/load` then returns HTTP 422 before any migration.
  - Exception: a change of a generic's own `branch` is skipped (`GENERIC_ATTRIBUTES_TO_IGNORE`) and applied.
  - Only `backend/tests/unit/core/schema/test_schema_update_validation.py::test_relationship_identifier_update_is_not_supported`
    tests this path. The `branch` case is from reading the code, **not verified**; a functional test in this
    feature covers it (FR-015a).
  - The error text from `SchemaUpdateValidationError.to_string` ends with `None`, because no message is set.
    Fixing it is outside this feature.
- **Decision**: No change to the load (FR-015a). The documentation states that a `FULL` load into an
  instance where one of these settings differs is refused, and that a `BRIEF` export then loads, because it
  leaves the derived value out.

## R11. Merge into an existing schema (User Story 3)

- **Finding**: `infrahub.core.models::HashableModel.update` copies an incoming value only when it is not
  `None`.
  - Fields with a `None` default keep the target's value when the export leaves them out: node `label`,
    `human_friendly_id`, `display_label`, `icon`, `order_by`, `uniqueness_constraints`, `menu_placement`;
    attribute and relationship `label`, `branch`, `order_weight`, `default_value`, `identifier`, `on_delete`.
  - Fields with another default are reset to it: `optional`, `unique`, `read_only`, relationship
    `cardinality`, `min_count`, `max_count`, `direction`.
  - Attributes and relationships only in the target stay, unless the file marks them `state: absent`.
- **Consequence**: A `FULL` export overwrites the first group. The documentation lists both groups.

## R12. SDK and `infrahubctl`

- **Decision**:
  - `InfrahubSchema.export` and `InfrahubSchemaSync.export` call `GET /api/schema/export` with `branch`,
    `namespaces` and `mode`, and return the document as a `dict`.
  - Remove `infrahub_sdk/schema/export.py`, `SchemaExport`, `NamespaceExport`, `schema_to_export_dict`,
    `RESTRICTED_NAMESPACES` in that module and `InfrahubSchemaBase._build_export_schemas`. Nothing outside the
    SDK imports them.
  - HTTP 404 or 422 on that URL raises `infrahub_sdk.exceptions::VersionNotSupportedError` ("Schema export
    requires Infrahub X or later"). An older server answers 422, because `/api/schema/export` reaches
    `get_schema_by_kind` and raises `SchemaNotFoundError` (**not verified** against a running server).
  - The client returns the generated `infrahub_sdk.schema.generated.write::InfrahubSchemaWrite`, parsed from
    the response, so the values left out stay unset and `model_dump(exclude_unset=True)` gives back the
    response (constitution Principle III).
  - `infrahub_sdk.ctl.utils::handle_exception` prints `VersionNotSupportedError` without a traceback.
  - `infrahubctl schema export` splits the document by namespace into `<namespace>.yml` files, as today.
    `--single-file` writes the whole document to `schema.yml` in the directory. `--mode` passes the mode.
  - `infrahub_sdk.ctl.schema_format::RESTRICTED_NAMESPACES`, used by `infrahubctl schema format`, stays: it is
    not part of the export (SC-005 covers the export rules only).
- The release that ships the endpoint, which the error message names, is 1.13.0 (decided by Damien Garros
  on 2026-10-27; it matches the roadmap field of INFP-723).

## R13. Delivery order

- **Finding**: The SDK write models in `infrahub_sdk/schema/generated/` are produced by this repository's
  generator (`tasks/backend.py`), and CI checks them with `git -C python_sdk diff --exit-code
  infrahub_sdk/schema/generated`.
- **Decision**: Prepare both pull requests together. The SDK pull request against `infrahub-develop`
  carries the regenerated models (with `infrahub_version`), the CLI and client changes and their tests. It
  merges first. The Infrahub pull request carries the generator change, the backend and the submodule bump
  to the merged SDK commit.

## R14. Tests

- **Decision**:
  - **Unit** (`backend/tests/unit/core/schema/export/`), in memory, as `_load_processed_branch`: for each
    YAML schema in `models/base/` (6 files, loaded as one set) and `models/examples/` (each with
    `models/base/` when it needs it), and one small schema per rule in R1, R3, R4 and R6, in both modes: export,
    load into a new branch, process, compare `FULL` documents (FR-012), export again and compare (FR-013).
  - **Unit**, field coverage (FR-023): iterate the fields of the five write models and the attribute
    parameter write models, and fail for any field that is in neither the map of fields to the test schema
    that covers them nor the list of fields that need no test, each with a reason.
  - **Functional** (`backend/tests/functional/api/`, `TestInfrahubApp`, an empty database per class). A
    class cannot empty its database part-way, so the round trip uses two independent classes and the
    in-memory export as the link: the first loads the source schema through the API and checks that the
    endpoint returns the in-memory export of the same files; the second loads that in-memory export into its
    empty database through `POST /api/schema/load`, checks the warnings, and checks that the endpoint
    returns it again (US1). Also User Story 3 (label kept by `BRIEF`, replaced by `FULL`) and a namespace
    filter (US4), each in one database.
  - **Unit**, FR-015a: a `FULL` change of a setting Infrahub cannot update cannot be set up in one database,
    because the load refuses to create it. The test builds the source and the target as two processed
    branches and checks that `SchemaBranch.validate_update` reports `NOT_SUPPORTED`, as
    `evaluate_candidate_schemas` does on a load.
  - **End-to-end** (`tests/e2e/schema/`, testcontainers stack, no browser): load `models/base/`, export
    through the SDK client, and send the export to `POST /api/schema/check`; expect an empty diff and no
    warning. This covers the deployed stack (constitution Principle IV).
  - **Component** (`backend/tests/component/api/test_40_schema.py`): parameters, anonymous access, unknown
    branch (400), unknown mode (422).
  - **SDK unit**: client export for both clients with `pytest_httpx`; `VersionNotSupportedError` on 422; CLI
    with `typer.testing.CliRunner` (files per namespace, `--single-file`, `--mode`, clean error);
    validation accepts `infrahub_version` with no warning (`tests/unit/test_schema_offline_validation.py`).
- **Rationale**: `dev/guidelines/backend/testing.md` asks for the cheapest tier that covers the behaviour.
  The round trip is in memory, and the functional tier covers the real load once per story.

## R15. Documentation and changelog

- `docs/docs/schema/export.mdx`, a new page next to `create-and-load.mdx`, with the modes, the single-file
  option and the known limitations (D2, D3, D4, R5, R6, R10, R11).
- `docs/docs/objects/import-from-csv.mdx` mentions `infrahubctl schema export`; check it still holds.
- `python_sdk/docs/docs/infrahubctl/infrahubctl-schema.mdx` is generated by `uv run invoke docs-generate` in
  the SDK.
- Changelog: an `added` fragment in `changelog/` and, in the SDK, an `added` and a `removed` fragment (the
  public export symbols).
- `dev/knowledge/backend/schema-export.md`: schema processing as it applies to the export, and the R1
  algorithm. The constitution asks for a knowledge update on a backend architecture change; the design
  document lists it as a follow-up.
