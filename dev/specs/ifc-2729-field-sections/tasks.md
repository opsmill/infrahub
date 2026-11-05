# Tasks: Schema-defined field sections

**Input**: Design documents from `dev/specs/ifc-2729-field-sections/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/schema-api.md](contracts/schema-api.md),
[contracts/frontend-components.md](contracts/frontend-components.md), [quickstart.md](quickstart.md)

**Tests**: Requested. Every production task is preceded by the task that writes its test, and that
test must fail before the production task starts. Test functions are named after the behaviour they
check; no ticket key appears in a test name, a docstring or a comment.

**Organization**: Tasks are grouped by user story in priority order so each story can be
implemented, tested and delivered on its own. Paths are relative to the repository root. Symbols are
cited as `module::Symbol`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel: it touches different files than every incomplete task it could run
  beside, and depends on none of them
- **[Story]**: the user story the task belongs to (US1 to US6); only in the user-story phases
- Every task names its files, the symbols it adds or changes, the test names and the command that
  runs it when one exists

## Path Conventions

- Backend: `backend/infrahub/` (source), `backend/tests/` (unit, component, integration)
- Frontend: `frontend/app/src/` (source), `frontend/app/tests/fake/` (test factories)
- SDK: `python_sdk/` (Git submodule, separate repository `opsmill/infrahub-sdk-python`)
- Generator: `tasks/backend.py`; demo schema: `models/base/dcim.yml`; e2e: `tests/e2e/`
- Documentation: `docs/docs/schema/`, `docs/sidebars.ts`; changelog: `changelog/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The fixtures and constants every later phase reads. No production behaviour changes.

- [X] T001 [P] Create the shared backend fixture `backend/tests/helpers/schema/lag_interface.py` as plain dictionaries (not `NodeSchema` constructors, so the module imports before the model of Phase 2 exists): `LAG_INTERFACE` generic `InfraLagInterface` with containers `lacp` (label `LACP`, order_weight 100), `layer2` (label `Layer 2`, order_weight 200, description `Switching settings of the bundle`), `layer3` (label `Layer 3`, order_weight 300, `collapsed: true`); attributes `name`, `description` without container, `lacp_rate` and `lacp_mode` in `lacp`, `l2_mode` and `mac_address` (`display: extra`) in `layer2`, `mtu` in `layer3`; relationship `sub_interfaces` in `advanced`; `LAG_INTERFACE_L2` node `InfraLagInterfaceL2` inheriting from the generic and declaring no container; `LAG_INTERFACE_L3` node `InfraLagInterfaceL3` redeclaring `layer3` with label `Layer 3 (routed)`; `LAG_SCHEMA` dict with `version: "1.0"`, the generic and the two nodes, loaded by tests with `SchemaRoot(**LAG_SCHEMA)`
- [X] T002 [P] Add `ADVANCED_CONTAINER_NAME = "advanced"` next to `NAME_REGEX` in `backend/infrahub/core/constants/__init__.py`, with a one-sentence comment stating that the name is accepted as a `container` reference but never declared
- [X] T003 [P] Create `frontend/app/src/entities/nodes/object/domain/model/field-section.ts` with `DETAILS_SECTION = { name: "details", label: "Details", collapsed: false }` and `ADVANCED_SECTION = { name: "advanced", label: "Advanced", collapsed: true }` (the `FieldSection<T>` type is added in Phase 5 once the `ContainerSchema` type exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `ContainerSchema` model, the three internal schema properties, the SDK generator
entries and the regenerated files. Every user story reads these.

**Blocking**: No user-story work can begin until this phase is complete.

### Tests for the foundation

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 Extend `backend/tests/unit/core/schema/test_generated_visibility.py`: add `containers` to `REQUIRED_WRITE_FIELDS["node"]`, `container` to `REQUIRED_WRITE_FIELDS["attribute"]` and `REQUIRED_WRITE_FIELDS["relationship"]`, and a `ReadOnlyDeltaCase` for the `ContainerSchemaWrite` and `ContainerSchemaRead` pair with an empty delta (`state` is in both, `inherited` is in neither). Run `uv run pytest backend/tests/unit/core/schema/test_generated_visibility.py` and confirm the new cases fail

### Implementation of the foundation

- [X] T005 Create `backend/infrahub/core/schema/container.py::ContainerSchema(HashableModel)` patterned on `backend/infrahub/core/schema/dropdown.py::DropdownChoice`: `name: str` constrained by `NAME_REGEX`, `DEFAULT_NAME_MIN_LENGTH` and `DEFAULT_NAME_MAX_LENGTH`; `label: str`; `description: str | None = None`; `order_weight: int | None = None`; `collapsed: bool = False`; `state: HashableModelState = HashableModelState.PRESENT`; `inherited: bool = False`; `_sort_by = ["name"]`; and export it from `backend/infrahub/core/schema/__init__.py` next to `DropdownChoice` (import and `__all__`)
- [X] T006 Declare the three properties in `backend/infrahub/core/schema/definitions/internal.py`: add `ContainerSchema: "list[ContainerSchema__VARIANT__]"` to the `fixed_types` map of `SchemaAttribute._external_internal_kind`; add `containers` to `base_node_schema` next to `order_by` (kind `List`, `internal_kind=ContainerSchema`, optional, `default_factory="list"`, a `description`, `extra={"update": UpdateSupport.ALLOWED, "visibility": Visibility.WRITE}`); add `container` to `attribute_schema` and to `relationship_schema` next to `display` (kind `Text`, optional, default `None`, a `description`, the same `extra`)
- [X] T007 [P] Add `from infrahub.core.schema.container import ContainerSchema` to `backend/templates/basenodeschema_imports.j2` so the generated `base_node_schema.py` types the field as `list[ContainerSchema]`
- [X] T008 [P] Extend the SDK generator in `tasks/backend.py`: add `self.container_schema_fields` next to `self.dropdown_choice_fields` listing `name`, `label`, `description`, `order_weight` and `collapsed` through `_field`, and `state` as an explicit entry that mirrors the attribute-level `state` entry of `backend/infrahub/core/schema/definitions/internal.py::attribute_schema`: `SchemaAttribute(name="state", kind="Text", internal_kind=HashableModelState, description="Expected state of the container after loading the schema", default_value=HashableModelState.PRESENT, enum=HashableModelState.available_types(), enum_class="SchemaState", optional=True, extra={"update": UpdateSupport.NOT_APPLICABLE, "visibility": Visibility.WRITE})`; `_field` is not extended and `inherited` is never listed; add the `ContainerSchema{suffix}` family next to `DropdownChoice{suffix}`; add the `ContainerSchema` internal counterpart next to the `DropdownChoice` one
- [X] T009 Run the regeneration chain from the repository root: `uv run invoke backend.generate && uv run invoke schema.generate-jsonschema && uv run invoke docs.generate && (cd frontend/app && pnpm codegen:openapi)`; confirm `backend/infrahub/core/schema/generated/{base_node_schema,attribute_schema,relationship_schema}.py`, `python_sdk/infrahub_sdk/schema/generated/{read,write,contract}.py`, `schema/openapi.json`, `docs/docs/reference/schema/{node,generic,attribute,relationship}.mdx` and `frontend/app/src/shared/api/rest/types.generated.ts` changed and that `ContainerSchemaRead` carries `state` and not `inherited`
- [X] T010 Run the generated-file validations: `uv run invoke backend.validate-generated && uv run invoke schema.validate-jsonschema && uv run invoke schema.validate-graphqlschema && uv run invoke docs.validate && git diff --exit-code frontend/app/src/shared/api/rest/types.generated.ts`; `schema.validate-graphqlschema` must report no difference (FR-014)
- [X] T011 Run the foundation tests: `uv run pytest backend/tests/unit/core/schema/test_generated_visibility.py backend/tests/unit/core/schema/test_write_json_schema.py backend/tests/component/core/schema/test_schema_documentation.py`; the documentation test must find a description on `containers` and on both `container` properties
- [X] T012 Export `ContainerSchema = components["schemas"]["ContainerSchemaRead"]` from `frontend/app/src/entities/schema/domain/model/schema.ts` next to the other generated REST types
- [X] T013 Extend `frontend/app/tests/fake/schema.ts`: add `generateContainerSchema(overrides?: Partial<ContainerSchema>): ContainerSchema` with defaults `name: "lacp"`, `label: "LACP"`, `description: null`, `order_weight: null`, `collapsed: false`, `state: "present"`; add `containers: []` to the defaults of `generateNodeSchema`, `generateGenericSchema`, `generateProfileSchema` and `generateTemplateSchema`; add `container: null` to the defaults of `generateAttributeSchema` and `generateRelationshipSchema`; run `cd frontend/app && pnpm exec tsc --noEmit`

**Checkpoint**: The model, the properties, the generated files and the test factories exist. User
story implementation can begin.

---

## Phase 3: User Story 1 - Declare sections in the schema (Priority: P1) 🎯 MVP

**Goal**: A schema designer loads a schema with `containers` and `container` references, reads it
back unchanged on any branch and after a branch merge, reloads it with the list merged by name, and
gets one of three exact messages when a reference or a declaration is wrong. The inheritance merge
lands in this story: the shared fixture is a generic with two implementing nodes, and the validator
refuses the nodes' inherited references until the merge exists.

**Independent Test**: Load `LAG_SCHEMA` through a `SchemaBranch`, process it, read
`InfraLagInterfaceL2` back and check that it carries the generic's containers and that its
inherited fields keep their container; load it with an unknown container reference and compare the
error message.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation.** T014 and T015 pin the
> contract of Phase 2 and pass once written; they fail if the Phase 2 definitions are reverted. T016
> to T020 fail until the inheritance merge, the validator and the profile copy of this story land.

- [X] T014 [P] [US1] Add `LoadContractCase` entries to `backend/tests/unit/api/test_schema_load_contract.py`: `containers-and-container-accepted` (a node with two containers and fields referencing them loads with no warning), `unknown-field-inside-container-rejected` (an unknown key inside a container item is a 422), `container-missing-label-rejected` (an item without `label` is a 422), `container-name-outside-format-rejected` (an item named `Layer-2` is a 422), `container-state-absent-accepted-without-warning` (an item with `state: absent` loads with no read-only warning), `inherited-flag-inside-container-is-read-only` (an item sending `inherited: true` gets the read-only warning and the value is dropped). Run `uv run pytest backend/tests/unit/api/test_schema_load_contract.py`
- [X] T015 [P] [US1] Add to `backend/tests/unit/core/schema/test_schema_update_validation.py`: `test_changing_containers_emits_no_migration_and_no_constraint` (a label change and a new container on a node produce an empty migration list and an empty constraint list) and `test_moving_an_attribute_to_another_container_emits_no_migration_and_no_constraint`. Run `uv run pytest backend/tests/unit/core/schema/test_schema_update_validation.py`
- [X] T016 [P] [US1] Add to `backend/tests/unit/core/schema/test_node_inheritance.py`, using the file's existing node builder and `backend/infrahub/core/schema/node_inheritance_handler.py::NodeInheritanceHandler`: `test_node_without_containers_receives_the_generic_containers`, `test_node_container_replaces_the_generic_container_of_the_same_name_only`, `test_first_generic_wins_when_two_generics_declare_the_same_container`, `test_inherited_attribute_keeps_the_generic_container`, `test_locally_redeclared_attribute_keeps_its_own_container`, `test_inheriting_twice_yields_the_same_containers`. Run `uv run pytest backend/tests/unit/core/schema/test_node_inheritance.py`
- [X] T017 [P] [US1] Create `backend/tests/unit/core/schema/test_schema_branch_containers.py` with `RefusedContainerCase` and `AcceptedContainerCase` dataclasses, an `exact_message()` helper copied from `backend/tests/unit/core/schema/test_schema_branch_number_pool_scope.py::exact_message`, a `_processed_branch(schema)` helper that loads a `SchemaRoot` built from `tests.helpers.schema.lag_interface.LAG_SCHEMA` into a `SchemaBranch` and calls `process()`; refused cases: `test_attribute_referencing_an_undeclared_container_is_refused` (the case redeclares `mtu` locally on `InfraLagInterfaceL2` with `container: layer4`, so the message is `InfraLagInterfaceL2.attributes.mtu.container: container 'layer4' is not declared on InfraLagInterfaceL2`), `test_relationship_referencing_an_undeclared_container_is_refused` (`InfraLagInterfaceL2.relationships.sub_interfaces.container: container 'layer4' is not declared on InfraLagInterfaceL2`), `test_duplicate_container_names_are_refused` (`InfraLagInterface.containers: container names must be unique, duplicate 'lacp'`), `test_declaring_the_advanced_container_is_refused` (`InfraLagInterface.containers: 'advanced' is a built-in container and cannot be declared`); accepted cases: `test_advanced_reference_without_a_declaration_is_accepted`, `test_container_named_like_an_attribute_is_accepted`, `test_declared_container_with_no_field_is_accepted`, `test_container_without_order_weight_is_accepted`. Run `uv run pytest backend/tests/unit/core/schema/test_schema_branch_containers.py`
- [X] T018 [P] [US1] Add reload merge tests to `backend/tests/component/core/schema_manager/test_manager_schema.py` next to `test_clean_diff_after_reload_from_db`, each loading a node with containers, loading it again and reading it back: `test_reload_appends_a_container`, `test_reload_updates_a_container_label`, `test_reload_keeps_a_container_left_out_of_the_list`, `test_reload_removes_a_container_marked_absent`; and extend `test_schema_branch_add_profile_schema` and `test_manage_object_templates` with containers on the source node (a `deepcopy` of `schema_all_in_one` with a `grading` container on `TestingCriticality` and `container: grading` on its `level` attribute) asserting the profile and the template carry the same containers without an `inherited` key and that `get_attribute("level").container == "grading"`. Run `uv run pytest backend/tests/component/core/schema_manager/test_manager_schema.py -k "container or profile or template"`
- [X] T019 [P] [US1] Extend `backend/tests/component/core/schema/schema_branch/test_process_idempotency.py`: add two containers to `DEVICE_NODE` (a node, not a generic) and `container` on `DEVICE_NODE.role`, so `TestSchemaBranchDbRoundtrip::test_reload_matches_saved_schema` covers the database round trip of containers and references (FR-006). Run `uv run pytest backend/tests/component/core/schema/schema_branch/test_process_idempotency.py`
- [X] T020 [P] [US1] Create `backend/tests/integration/schema_lifecycle/test_schema_containers_branch_merge.py` with `TestSchemaLifecycleContainersBranchMerge(TestSchemaLifecycleBase)` from `backend/tests/integration/schema_lifecycle/shared.py`: `test_containers_loaded_on_a_branch_are_returned_on_that_branch`, `test_merging_the_branch_returns_the_containers_on_the_default_branch`, `test_a_label_change_on_the_branch_needs_no_migration`. Run `uv run pytest backend/tests/integration/schema_lifecycle/test_schema_containers_branch_merge.py`

### Implementation for User Story 1

- [X] T021 [US1] Add the container merge step to `backend/infrahub/core/schema/node_inheritance_handler.py::NodeInheritanceHandler.inherit_from_interface`, before the attribute loop and not in `properties_to_inherit`: for each container of the generic whose `name` is not in `{c.name for c in node.containers}`, append `ContainerSchema(**container.model_dump(exclude={"inherited"}), inherited=True)`
- [X] T022 [US1] Reset inherited containers in `backend/infrahub/core/schema/schema_branch.py::SchemaBranch.process_inheritance`: right after `node = node.duplicate()` and before the generic loop, set `node.containers = [c for c in node.containers if not c.inherited]`, with a one-sentence comment stating that the copies are rebuilt from the generics on every process
- [X] T023 [US1] Create `backend/infrahub/core/validators/schema_branch/container_validator.py::ContainerValidator` implementing the interface of `backend/infrahub/core/validators/schema_branch/interface.py`, patterned on `backend/infrahub/core/validators/schema_branch/hierarchical_nodes_restricted_words_validator.py::HierarchicalNodesRestrictedWords`: iterate `schema_branch.all_names`, `get(name, duplicate=False)`, and raise `ValueError` in this order with exactly `"{kind}.containers: container names must be unique, duplicate '{x}'"`, `"{kind}.containers: '{ADVANCED_CONTAINER_NAME}' is a built-in container and cannot be declared"`, `"{kind}.attributes.{name}.container: container '{x}' is not declared on {kind}"` and `"{kind}.relationships.{name}.container: container '{x}' is not declared on {kind}"`; accept `ADVANCED_CONTAINER_NAME` as a reference and a declared container with no field
- [X] T024 [US1] Copy the containers onto generated profiles and templates in `backend/infrahub/core/schema/schema_branch.py`: in `SchemaBranch.generate_profile_from_node` and `SchemaBranch.generate_object_template_from_node` pass `containers=[ContainerSchema(**c.model_dump(exclude={"inherited"})) for c in node.containers]` to the `ProfileSchema`, the `GenericSchema` and the `TemplateSchema` constructors (profiles and templates are generated before validation, so this must land with the validator or every schema with containers and profiles fails the load)
- [X] T025 [US1] Register the validator in `backend/infrahub/core/schema/schema_branch.py::SchemaBranch.__init__`: `self.validators = [HierarchicalNodesRestrictedWords(), ContainerValidator()]`
- [X] T026 [US1] Run the story: `uv run pytest backend/tests/unit/core/schema/test_node_inheritance.py backend/tests/unit/core/schema/test_schema_branch_containers.py backend/tests/unit/core/schema/test_schema_update_validation.py backend/tests/unit/api/test_schema_load_contract.py backend/tests/component/core/schema_manager/test_manager_schema.py -k "container or profile or template or reload" backend/tests/component/core/schema/schema_branch/test_process_idempotency.py backend/tests/integration/schema_lifecycle/test_schema_containers_branch_merge.py`

**Checkpoint**: A schema with containers loads, round-trips, merges on reload, gives each node the
containers of its generics and is refused with the three exact messages. The remaining inheritance
scenarios (a generic that drops a container, the hash after two processes, a redeclaration on
reload) are covered in User Story 2.

---

## Phase 4: User Story 2 - Inherit sections from a generic (Priority: P1)

**Goal**: A reference resolved through an inherited container is accepted, a dropped generic
container disappears from the node on the next process and its orphaned reference is refused, a
node that redeclares an inherited container on reload owns it from then on, and processing twice
yields the same containers and the same hash. The merge step and the reset landed in User Story 1
(T021 and T022); this story adds the tests that pin those scenarios.

**Independent Test**: Load `LAG_SCHEMA`, process it, read `InfraLagInterfaceL2` and
`InfraLagInterfaceL3` back and compare their containers and field assignments with the generic's.

### Tests for User Story 2

> **NOTE**: These tests pin the merge and the reset of T021 and T022. They pass once written and
> fail if either is reverted.

- [X] T027 [P] [US2] Add to `backend/tests/unit/core/schema/test_schema_branch_containers.py`: `test_reference_resolved_through_an_inherited_container_is_accepted` (the L2 node's `l2_mode` inherited from the generic resolves `layer2`) and `test_removing_a_container_from_the_generic_refuses_the_inherited_field_on_the_next_load` (message names `InfraLagInterfaceL2`, the node that fails). Run `uv run pytest backend/tests/unit/core/schema/test_schema_branch_containers.py`
- [X] T028 [P] [US2] Extend `backend/tests/component/core/schema/schema_branch/test_process_idempotency.py`: add containers to `NETWORK_ELEMENT_GENERIC` so `test_process_idempotency` and `test_reload_matches_saved_schema` cover inherited containers (FR-010), and add `test_process_twice_yields_the_same_hash_with_inherited_containers` (asserts `get_hash()` is equal after two `process()` calls) and `test_generic_dropping_a_container_removes_it_from_the_node_on_reprocess`. Run `uv run pytest backend/tests/component/core/schema/schema_branch/test_process_idempotency.py`
- [X] T029 [P] [US2] Add `test_reload_node_redeclaring_an_inherited_container_wins_on_reload` to `backend/tests/component/core/schema_manager/test_manager_schema.py` next to the reload merge tests of T018: load a generic with a container and a node inheriting it, reload the node redeclaring that container with another label, read the node back and assert the node's label and that the item's `inherited` is `False`. Run `uv run pytest backend/tests/component/core/schema_manager/test_manager_schema.py -k reload`

### Verification for User Story 2

- [X] T030 [US2] Run the story: `uv run pytest backend/tests/unit/core/schema/test_node_inheritance.py backend/tests/unit/core/schema/test_schema_branch_containers.py backend/tests/component/core/schema/schema_branch/test_process_idempotency.py backend/tests/component/core/schema_manager/test_manager_schema.py -k "container or reload or profile or template"`

**Checkpoint**: User Stories 1 and 2 pass together; the backend contract is complete.

---

## Phase 5: User Story 3 - View a node by section (Priority: P1)

**Goal**: The node detail page shows a Details card, one collapsible card per container ordered by
`order_weight`, an Advanced card last, omits empty cards, scopes the Extra control to each card, and
the schema viewer lists containers and each field's container.

**Independent Test**: Render `ObjectDetails` with a schema from `generateNodeSchema` carrying
containers and check the regions, their order, their rows and the collapse and Extra controls;
render it with a schema without containers and check a single region.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T031 [P] [US3] Create `frontend/app/src/entities/nodes/object/domain/rules/group-fields-by-section.test.ts` for `groupFieldsBySection`: `places the Details section first`, `orders weighted containers before unweighted ones and unweighted ones in declaration order`, `places the Advanced section last with collapsed true`, `drops a container with no item`, `keeps extra items in their section`, `yields one Details section for a schema without containers`, `places an item with an undeclared container name in Details`, `drops the section of a relationship filtered out before the call`. Run `cd frontend/app && pnpm test src/entities/nodes/object/domain`
- [X] T032 [P] [US3] Add to `frontend/app/src/entities/nodes/object/ui/object-details/object-details-card.test.tsx`: `starts collapsed when defaultCollapsed is true`, `expands when the header button is pressed`, `has no button in its title when defaultCollapsed is undefined`, `shows the description under the title outside the button and points aria-describedby at it`, `shows the Extra button only when the schema it receives has an extra field`; assertions through `getByRole("region", { name })` and `getByRole("button", { name })`. Run `cd frontend/app && pnpm test src/entities/nodes/object/ui/object-details`
- [X] T033 [P] [US3] Add a `describe("ObjectDetails sections")` block to `frontend/app/src/entities/nodes/object/ui/object-details/object-details.test.tsx`, with schemas from `generateNodeSchema`, `generateContainerSchema`, `generateAttributeSchema` and `generateRelationshipSchema`: `renders Details then the containers by order weight then Advanced` (order checked with `compareDocumentPosition` as in `frontend/app/src/entities/repository/ui/repository-object-details.test.tsx`), `renders each field once`, `renders no card for a container with no visible field`, `shows the Extra button only on the section with an extra field`, `starts the Advanced card collapsed`, `renders a single Details region for a schema without containers`, `shows a pool-allocated attribute inside a section with its pool row`, `renders the same sections for a profile schema`, `renders the same sections for an object template schema`. Run `cd frontend/app && pnpm test src/entities/nodes/object/ui/object-details`
- [X] T034 [P] [US3] Add to `frontend/app/src/entities/schema/ui/schema-viewer.test.tsx`: `lists the containers of a node`, `shows the container of an attribute and of a relationship`, `shows a dash for a field without container`, `shows no Containers block for a node without containers`. Run `cd frontend/app && pnpm test src/entities/schema`

### Implementation for User Story 3

- [X] T035 [US3] Add the `FieldSection<T>` type to `frontend/app/src/entities/nodes/object/domain/model/field-section.ts`: `{ container: Pick<ContainerSchema, "name" | "label" | "collapsed"> & Partial<Pick<ContainerSchema, "description" | "order_weight">>; items: T[] }`, importing `ContainerSchema` from `@/entities/schema/domain/model/schema`
- [X] T036 [US3] Create `frontend/app/src/entities/nodes/object/domain/rules/group-fields-by-section.ts::groupFieldsBySection<T>(containers, items, getContainer): FieldSection<T>[]`: Details first with the items whose container is `null`, `undefined` or an undeclared name; one section per declared container, weighted ones by ascending `order_weight` then unweighted ones in declaration order, items in input order; Advanced last from `ADVANCED_SECTION`; sections with no item dropped; the rule never filters, sorts or copies the items
- [X] T037 [P] [US3] Create `frontend/app/src/entities/nodes/object/ui/object-details/section-title.tsx::SectionTitle({ label, description, titleId, descriptionId })` rendering the label slot in an `h2` with `id={titleId}` and, when `description` is set, a muted `<p id={descriptionId}>` as the sibling that follows the `h2`, never inside it; the detail card passes the Disclosure trigger button as the label slot and the form panel passes plain text, as `contracts/frontend-components.md` states
- [X] T038 [P] [US3] Make `getRelationshipsVisibleInDataDisplay` of `frontend/app/src/entities/nodes/object/ui/object-details/object-data-display/object-data-display.tsx` a named export, with no new file, so the detail view applies the same filter before partitioning; `frontend/app/src/entities/nodes/object/domain/rules/get-relationships-visible-in-detailed-view.ts::getRelationshipsVisibleInDetailedView` exists with a different, kind-based predicate and is not what the data display uses, so it is not the filter to call
- [X] T039 [US3] Add `description?: string | null` and `defaultCollapsed?: boolean` to `frontend/app/src/entities/nodes/object/ui/object-details/object-details-card.tsx::ObjectDetailsCard`: when `defaultCollapsed` is undefined the header is unchanged for every existing caller; when defined, wrap the header and the rows in `Disclosure` and `DisclosurePanel` from `react-aria-components` as `frontend/app/src/entities/repository/ui/repository-activity-card/repository-last-runs.tsx` does, with the header DOM of `contracts/frontend-components.md` (`CardHeader > [h2 > Button(chevron, label)] [p.description, id=descriptionId] [Extra button]`): the trigger button carries `aria-describedby={descriptionId}`, the Extra button is a sibling of the `h2` in `CardHeader` (never inside the trigger), `defaultExpanded={!defaultCollapsed}`, the chevron rotation uses the same reduced-motion classes as the repository card; keep `role="region"`, `aria-labelledby` pointing at the `h2` id and `data-testid="object-details"`
- [X] T040 [US3] Compose the sections in `frontend/app/src/entities/nodes/object/ui/object-details/object-details.tsx::ObjectDetails`: filter with `getAttributesVisibleInDetailedView` and `getRelationshipsVisibleInDataDisplay`, sort with `sortByOrderWeight`, call `groupFieldsBySection(objectSchema.containers, fields, (field) => field.container)`, render one `ObjectDetailsCard` per section with `objectSchema={{ ...objectSchema, attributes, relationships }}` where `attributes` and `relationships` are the section's items split with `isRelationshipSchema` and `relationships` also includes every relationship of the full schema for which `isFromResourcePoolRelationship(relationship.name)` is true; the Details card passes no `defaultCollapsed`, a declared container passes its `collapsed` and `description`, the Advanced card passes `defaultCollapsed: true`
- [X] T041 [P] [US3] Add a `Containers` block to `frontend/app/src/entities/schema/ui/schema-viewer.tsx` on the node, generic, profile and template panel listing each container's name, label, order weight, collapsed flag and description with the existing `PropertyRow`; render nothing when the list is empty
- [X] T042 [P] [US3] Add a `Container` `PropertyRow` next to the `Display` row in `frontend/app/src/entities/schema/ui/attribute-display.tsx`, showing the container name or a dash when `null`
- [X] T043 [P] [US3] Add a `Container` `PropertyRow` next to the `Display` row in `frontend/app/src/entities/schema/ui/relationship-display.tsx`, showing the container name or a dash when `null`
- [X] T044 [US3] Run the story: `cd frontend/app && pnpm test src/entities/nodes/object/domain src/entities/nodes/object/ui/object-details src/entities/schema src/entities/repository` (the repository page tests must be unchanged)

**Checkpoint**: The MVP (Foundational + US1 + US2 + US3) renders the sections on the detail page of
any node whose schema declares containers, read from a server built on this branch.

---

## Phase 6: User Story 4 - Edit a node by section (Priority: P2)

**Goal**: The create and edit forms group the fields into bordered panels, one per section, always
expanded, without changing the data the form sends.

**Independent Test**: Render `DynamicForm` with `fields` from `buildFormField` and a `sections`
list, check the regions and their order, submit, and compare the payload with the same form
rendered without `sections`.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T045 [P] [US4] Add to `frontend/app/src/shared/components/form/utils/getFormFieldsFromSchema.test.ts`: `attaches its attribute schema to every attribute field` and `attaches its relationship schema to both fields of a bulk relationship pair`, with a schema whose attributes and relationships carry a `container`, asserting `field.attribute?.container` and `field.relationship.container` equal the schema's value. Run `cd frontend/app && pnpm test src/shared/components/form/utils`
- [X] T046 [P] [US4] Create `frontend/app/src/shared/components/form/dynamic-form.test.tsx` with attribute fields from `buildFormField` in `frontend/app/tests/fake/form.ts` and containers from `generateContainerSchema`: `renders a flat list without sections` (no `region`), `renders one panel per section headed by the container label in order weight order`, `renders the Details panel first`, `renders no panel when all its fields are filtered out`, `keeps a collapsed container expanded`, `renders a display extra field inside its panel` (the form never hides `display: extra` fields), `sends the same payload with and without sections`, `shows a validation error inside its panel`. Run `cd frontend/app && pnpm test src/shared/components/form`

### Implementation for User Story 4

- [X] T047 [US4] Create `frontend/app/src/shared/components/form/form-section-panel.tsx::FormSectionPanel({ label, description, children })` rendering `Card` with `variant="panel"` from `@infrahub/ui`, a `CardHeader` holding `SectionTitle` (imported from `@/entities/nodes/object/ui/object-details/section-title`) with ids the panel generates with `useId`, `role="region"` and `aria-labelledby` on the card, and a `CardContent` holding the fields; no Extra control and no collapse
- [X] T048 [US4] Add `sections?: ContainerSchema[]` to `frontend/app/src/shared/components/form/dynamic-form.tsx::DynamicForm`: `fields` stays the single source for default values and submission; when `sections` is undefined, or when `groupFieldsBySection(sections, fields, (field) => "relationship" in field ? field.relationship.container : field.attribute?.container)` yields only the Details section, render the flat list of today; otherwise render one `FormSectionPanel` per section, Details first, always expanded, with the fields in their input order
- [X] T049 [US4] Pass `sections={schema.containers}` to `DynamicForm` in `frontend/app/src/shared/components/form/node-form.tsx::NodeForm`; no other caller changes
- [X] T050 [US4] Run the story: `cd frontend/app && pnpm test src/shared/components/form src/entities/nodes/object`

**Checkpoint**: The edit form of a node with containers shows the panels and saves the same payload.

---

## Phase 7: User Story 5 - Reuse the sections outside the web interface (Priority: P2)

**Goal**: `GET /api/schema/{kind}` returns `containers` and each field's `container` on every
branch, `POST /api/schema/load` rejects an undeclared reference with the exact 422 body, the SDK's
offline validation accepts both properties and `infrahubctl schema format` places them in a fixed
position.

**Independent Test**: Register `LAG_SCHEMA` on the test app, read `InfraLagInterfaceL2` through the
API and compare; format a schema file with containers and compare the key order.

**SDK PR gate**: the SDK changes are a separate deliverable on `opsmill/infrahub-sdk-python`. T051
and T052 are written now; the `test_40_schema.py` cases pass only once T058 pins the merged SDK
commit, because the read models come from `infrahub_sdk.schema.generated.read`.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T051 [P] [US5] Create `backend/tests/fixtures/schemas/not_valid_container_01.json`: a schema file with the `InfraLagInterface` generic and its containers, and an `InfraLagInterfaceL2` node that redeclares `mtu` locally with `container: layer4`, so the expected message is `InfraLagInterfaceL2.attributes.mtu.container: container 'layer4' is not declared on InfraLagInterfaceL2`
- [X] T052 [US5] Add to `backend/tests/component/api/test_40_schema.py`, next to `test_schema_load_endpoint_constraints_not_valid`: `test_schema_kind_endpoint_returns_containers_and_field_containers` (register `LAG_SCHEMA`, assert the exact `containers` list with `state: "present"` on each item, no `advanced` item, no `inherited` key, and each attribute's and relationship's `container`), `test_schema_kind_endpoint_returns_empty_containers_for_a_node_without_sections`, `test_schema_kind_endpoint_returns_containers_on_a_non_default_branch` (`?branch=branch1`), `test_schema_load_endpoint_undeclared_container` (loads `not_valid_container_01.json`, asserts the 422 body of `contracts/schema-api.md`), `test_schema_load_endpoint_removes_a_container_marked_absent` (sends `state: absent`, asserts the container is gone and no read-only warning is returned); extend `test_schema_read_endpoint_visibility` with the three properties. Run `uv run pytest backend/tests/component/api/test_40_schema.py` (fails until T058)
- [X] T053 [P] [US5] Extend `python_sdk/tests/unit/ctl/test_schema_format.py`: add `containers` with two items and `container` on an attribute and a relationship to `NODE_DOC`; extend `test_node_key_order_is_canonical` (`containers` right after `uniqueness_constraints`) and `test_attribute_relationship_and_choice_inner_order` (`container` right before the trailing `order_weight`); add `test_container_item_key_order_is_canonical` (`name`, `label`, `description`, `order_weight`, `collapsed`, `state`). Add `test_valid_payload_with_containers_passes` to `python_sdk/tests/unit/test_schema_offline_validation.py` next to `test_valid_payload_passes`: `validate_schema` accepts a node with two containers and `container` on an attribute and a relationship, with no error and no warning. Run `cd python_sdk && uv run pytest tests/unit/ctl/test_schema_format.py tests/unit/test_schema_offline_validation.py`

### Implementation for User Story 5

- [X] T054 [US5] Create the SDK branch inside the submodule: `cd python_sdk && git fetch origin && git switch -c ple-field-sections-ifc-2729 origin/infrahub-develop` (never the SDK's own `develop`), then rerun `uv run invoke backend.generate` from the repository root so the regenerated `python_sdk/infrahub_sdk/schema/generated/{read,write,contract}.py` land on that branch
- [X] T055 [US5] Add the key orders in `python_sdk/infrahub_sdk/ctl/schema_format.py`: `"containers"` after `"uniqueness_constraints"` in `NODE_ORDER`, `"container"` as the last entry of `ATTRIBUTE_ORDER` and `RELATIONSHIP_ORDER` before the trailing `order_weight`, `CONTAINER_ORDER = ["name", "label", "description", "order_weight", "collapsed", "state"]`, applied to each container item in `_format_entity` the way `CHOICE_ORDER` is applied with `reorder_mapping`
- [X] T056 [US5] Re-export `ContainerSchemaRead` and `ContainerSchemaWrite` from `python_sdk/infrahub_sdk/schema/main.py` next to the `DropdownChoice` read and write imports from `.generated.read` and `.generated.write`, and add them to the module's `__all__` if one exists
- [ ] T057 [US5] Run `cd python_sdk && uv run pytest tests/unit/ctl/test_schema_format.py tests/unit/test_schema_offline_validation.py tests/unit/sdk/test_schema.py && uv run ruff check . && uv run ruff format --check .`, commit the SDK branch, push it to `origin` and open the SDK pull request on `opsmill/infrahub-sdk-python` against `infrahub-develop` with `gh pr create` (a separate deliverable; the Infrahub PR stays in draft until it merges)
- [ ] T058 [US5] After the SDK PR merges: `cd python_sdk && git fetch origin && git checkout <merged commit on origin/infrahub-develop>`, stage the pointer with `git add python_sdk` from the repository root, rerun T010's validations and `uv run pytest backend/tests/component/api/test_40_schema.py backend/tests/unit/core/schema/test_generated_visibility.py`; `git diff --cached --submodule` must show the pointer at a commit that exists on `origin/infrahub-develop`

**Checkpoint**: A client of the schema API or the SDK reads the same containers the web interface
renders.

---

## Phase 8: User Story 6 - Read how sections work (Priority: P3)

**Goal**: The schema guide explains sections and the generated reference lists both properties.

**Independent Test**: `uv run invoke docs.lint`, `uv run invoke docs.validate` and `cd docs && npm run build`
pass with the new page in the `Display & presentation` sidebar group.

### Implementation for User Story 6

- [x] T059 [P] [US6] Create `docs/docs/schema/field-sections.mdx` modeled on `docs/docs/schema/field-visibility.mdx`: the `containers` item properties, `container` on attributes and relationships, the built-in Advanced section (never declared, always accepted, always last and collapsed), the default Details section, ordering (`order_weight` first, then declaration order), inheritance (merge by name, node wins, first generic wins), reload merge with `state: absent`, the three error messages, and the LAG interface example of `models/base/dcim.yml` (`lacp`, `layer2`, `layer3`); written in the guide voice of `dev/guidelines/documentation.md`
- [x] T060 [P] [US6] Add `{ type: 'doc', id: 'schema/field-sections', label: 'Field sections' }` to the `Display & presentation` category of `docs/sidebars.ts`, next to `schema/field-visibility`
- [x] T061 [P] [US6] Link the new page from `docs/docs/schema/overview.mdx`: add `- [Field sections](./field-sections) — Group attributes and relationships into sections on the detail page and in the forms` as the last item of the list under its `In this section` heading (the list ends with the `Schema extensions` item today)
- [x] T062 [P] [US6] (done as four fragments, one per pull request: `+ifc-2729-schema-containers.added.md`, `+ifc-2729-detail-page-sections.added.md`, `+ifc-2729-form-sections.added.md`, `+ifc-2729-lag-minimum-links-label.fixed.md`) Create the towncrier fragments in `changelog/` with the `creating-changelog-entries` skill: one of type `added` stating in one sentence that a node or generic schema accepts `containers` and that attributes and relationships accept `container`, and that the detail page and the forms group the fields by section; one of type `fixed` for the user-visible label fix of T066 (the `minimum_links` attribute of `InfraLagInterface` in the demo schema is labelled `Minimum links` instead of `Mimimum links`)
- [x] T063 [US6] Run `uv run invoke docs.lint && uv run invoke docs.validate && cd docs && npm run build` and confirm the regenerated reference pages `docs/docs/reference/schema/{node,generic,attribute,relationship}.mdx` list `containers` and `container`

**Checkpoint**: All six user stories are independently functional.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: The demo schema, the end-to-end test and the repository gates.

- [ ] T064 [P] Create `tests/e2e/objects/test_object_containers.py` with `pytestmark = pytest.mark.shard_sites_a` and the branch fixture of `tests/e2e/objects/test_object_update.py`, one test `test_should_show_sections_on_the_detail_page_and_save_a_value_from_a_section_panel`: open `/objects/InfraLagInterfaceL2?branch=...`, open `port-channel1` of `atl1-leaf1`, assert the `Details`, `LACP` and `Layer 2` regions and the `Advanced` header, assert no `Layer 3` region, edit `Minimum links` inside the `LACP` panel of the edit form, save, assert the toast and the new value in the `LACP` card; then open the `InfraLagInterfaceL3` object of T065, assert the `Details`, `LACP` and `Layer 3` regions and the `Advanced` header, read `MTU` inside the `Layer 3` region and assert no `Layer 2` region
- [ ] T065 [P] Add one `InfraLagInterfaceL3` object (`port-channel3` on `atl1-leaf1`, with `mtu` left at its default) to `tests/e2e/data/sites.py` next to the `port-channel1` data, loaded by the same slice
- [ ] T066 Declare the containers in `models/base/dcim.yml` on `InfraLagInterface`: `lacp` (label `LACP`, description `Link aggregation settings`, order_weight 100), `layer2` (label `Layer 2`, description `Switching settings of the bundle`, order_weight 200), `layer3` (label `Layer 3`, description `Addressing and MTU`, order_weight 300, `collapsed: true`); fix the label of the `minimum_links` attribute from `Mimimum links` to `Minimum links` (the e2e test of T064 targets `Minimum links`); set `container: lacp` on `lacp`, `minimum_links` and `mlag`, `container: advanced` on `max_bundle`; on `InfraLagInterfaceL2` set `container: layer2` on `l2_mode`, `untagged_vlan` and `tagged_vlan`; on `InfraLagInterfaceL3` set `container: layer3` on `ip_addresses` and redeclare `mtu` (`name: mtu`, `kind: Number`, `label: MTU`, `default_value: 1500`, `container: layer3`, keeping `kind: Number` or the inheritance check fails); `members` stays ungrouped on both nodes
- [ ] T067 Check the demo schema against a running instance: `uv run invoke dev.start && uv run invoke dev.load-infra-schema && uv run infrahubctl schema check models/base/dcim.yml && uv run invoke dev.load-infra-data`, then walk the seven web UI checks of `quickstart.md` (L2 cards, collapse, edit form, L3 create form, schema viewer, an `InfraDevice` unchanged)
- [ ] T068 Add `test_object_containers.py` to the `objects/` entry of the directory layout in `tests/e2e/README.md` and note the `InfraLagInterfaceL3` object in the data description of `infrastructure_data`
- [ ] T069 Build the image from the branch with the bumped pointer of T058 and run `INFRAHUB_TESTING_IMAGE_VER=local INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/objects/test_object_containers.py tests/e2e/objects/test_object_details.py tests/e2e/objects/test_object_update.py -s --pdb`; the existing object tests must keep passing because their kinds declare no container
- [ ] T070 Run the frontend gates: `cd frontend && pnpm biome:fix && cd app && pnpm exec tsc --noEmit && pnpm knip && pnpm exec betterer ci && pnpm test`; Biome rewrites nothing on a clean tree, `knip` reports no unused export, `betterer` reports no TypeScript regression
- [ ] T071 Run the backend gates: `uv run invoke format && uv run invoke lint && uv run invoke backend.test-unit && uv run pytest backend/tests/unit/core/schema backend/tests/unit/api/test_schema_load_contract.py`
- [ ] T072 Run the whole-repository checks: `uv run ruff check . --exclude python_sdk && uv run ruff format --check --exclude python_sdk . && uv run invoke docs.validate && uv run invoke backend.validate-generated && uv run invoke schema.validate-jsonschema && uv run invoke schema.validate-graphqlschema`, then ask the user to run `/pre-ci` (only the user can start it)
- [x] T073 Update the internal knowledge files for the new pieces: in `dev/knowledge/backend/schema-definitions.md`, describe the `ContainerSchema{suffix}` family and its explicit `state` entry under `Model families` (the `Field Visibility and the Write / Read / Internal Models` section) and add `backend/infrahub/core/schema/container.py` (`ContainerSchema`, a fixed-type family of `_external_internal_kind`) and `backend/infrahub/core/validators/schema_branch/container_validator.py` (the `ContainerValidator` plug-in registered in `SchemaBranch.validators`) to the `Key Locations` table; in `dev/knowledge/frontend/shared-components.md`, add the `DynamicForm` `sections` prop to the `Form fields (react-hook-form integration)` section and `FormSectionPanel` (`shared/components/form/form-section-panel.tsx`) to the `Layout` table; follow `dev/guidelines/documentation.md` (internal docs) and run `npx --yes markdownlint-cli2 dev/knowledge/backend/schema-definitions.md dev/knowledge/frontend/shared-components.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependency; T001, T002 and T003 run in parallel
- **Foundational (Phase 2)**: depends on Setup; blocks every user story. T004 before T005 to T008;
  T005 before T006 (the definitions import the model); T006 before T009; T009 before T010 to T013;
  T012 before T013
- **User Stories (Phases 3 to 8)**: all depend on Foundational
- **Polish (Phase 9)**: depends on US1 to US4 for the e2e test (T064 to T069), on every story
  for the gates (T070 to T072) and on US1, US3 and US4 for the knowledge files (T073)

### User Story Dependencies

- **US1 (P1)**: starts after Foundational. T021 and T022 (the inheritance merge and the reset)
  land before T023, because the validator refuses the nodes' inherited references in `LAG_SCHEMA`
  until the merge exists. T023, T024 and T025 land in the same commit: profiles and templates are
  generated before the validator runs, so a profile without its containers fails the load
- **US2 (P1)**: starts after US1; it has no production task. The inherited-reference validator
  cases (T027) need the validator of T023, the reprocess cases (T028) need the reset of T022, and
  the reload test of T029 needs the reload tests of T018 in the same file
- **US3 (P1)**: starts after Foundational (T012 and T013); independent of US1 and US2 for its unit
  tests, which render schemas built by the test factories. A server rendering the sections needs
  US1 and US2
- **US4 (P2)**: starts after US3's T035, T036 and T037 (the form reuses the partition rule and
  `SectionTitle`)
- **US5 (P2)**: T051 to T057 start after Foundational (T009 produced the regenerated SDK files)
  and after US2, because T052 registers `LAG_SCHEMA` and asserts the merged containers of
  `InfraLagInterfaceL2`. T058 depends on the SDK PR of T057 being merged upstream. The
  `test_40_schema.py` cases of T052 pass only after T058, and the Infrahub PR must never point at
  an unpushed submodule commit
- **US6 (P3)**: starts after Foundational (T009 produced the reference pages); independent of the
  other stories

### Within Each User Story

- Tests are written and fail before the implementation task they precede
- Model and rule before component; component before composition
- The story's run task closes it

### Parallel Opportunities

- Setup: T001, T002, T003
- Foundational: T007 and T008 beside each other after T006
- US1 tests: T014 to T020 together; US2 tests: T027 to T029 together
- US3 tests: T031 to T034 together; US3 implementation: T037, T038 beside each other after T036;
  T041, T042, T043 beside each other after T040
- US4 tests: T045 and T046 together
- US5: T051 and T053 beside each other; T054 to T057 while US3, US4 and US6 are in progress
- US6: T059 to T062 together
- Polish: T064 and T065 together before T066; T073 beside T070 to T072

---

## Parallel Example: User Story 1

```bash
# Write every US1 test together, then confirm they fail:
Task: "T014 LoadContractCase entries in backend/tests/unit/api/test_schema_load_contract.py"
Task: "T015 update-support cases in backend/tests/unit/core/schema/test_schema_update_validation.py"
Task: "T016 inheritance cases in backend/tests/unit/core/schema/test_node_inheritance.py"
Task: "T017 validator cases in backend/tests/unit/core/schema/test_schema_branch_containers.py"
Task: "T018 reload merge and profile cases in backend/tests/component/core/schema_manager/test_manager_schema.py"
Task: "T019 round-trip fixture in backend/tests/component/core/schema/schema_branch/test_process_idempotency.py"
Task: "T020 branch merge in backend/tests/integration/schema_lifecycle/test_schema_containers_branch_merge.py"

# Then, sequentially: T021 handler merge step, T022 inherited reset, T023 validator,
# T024 profile and template copy, T025 registration, T026 run.
```

## Parallel Example: User Story 2

```bash
Task: "T027 inherited-reference cases in backend/tests/unit/core/schema/test_schema_branch_containers.py"
Task: "T028 idempotency and hash cases in backend/tests/component/core/schema/schema_branch/test_process_idempotency.py"
Task: "T029 redeclaration on reload in backend/tests/component/core/schema_manager/test_manager_schema.py"

# Then: T030 run.
```

## Parallel Example: User Story 3

```bash
Task: "T031 group-fields-by-section.test.ts"
Task: "T032 object-details-card.test.tsx"
Task: "T033 object-details.test.tsx"
Task: "T034 schema-viewer.test.tsx"

# Then T035 type, T036 rule; then together:
Task: "T037 section-title.tsx"
Task: "T038 export getRelationshipsVisibleInDataDisplay"
# Then T039 card, T040 view; then together:
Task: "T041 schema-viewer.tsx"
Task: "T042 attribute-display.tsx"
Task: "T043 relationship-display.tsx"
```

## Parallel Example: User Story 4

```bash
Task: "T045 getFormFieldsFromSchema.test.ts"
Task: "T046 dynamic-form.test.tsx"

# Then T047 panel, T048 sections prop, T049 node-form, T050 run.
```

## Parallel Example: User Story 5

```bash
Task: "T051 backend/tests/fixtures/schemas/not_valid_container_01.json"
Task: "T053 python_sdk/tests/unit/ctl/test_schema_format.py"

# Then T052, T054 to T057 (SDK branch, orders, re-export, push and PR); T058 only after the SDK PR merges.
```

## Parallel Example: User Story 6

```bash
Task: "T059 docs/docs/schema/field-sections.mdx"
Task: "T060 docs/sidebars.ts"
Task: "T061 docs/docs/schema/overview.mdx"
Task: "T062 changelog fragment"

# Then T063 lint, validate and build.
```

---

## Implementation Strategy

### MVP First (Foundational + US1 + US2 + US3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational, including the regeneration chain and its validations
3. Complete Phase 3: US1, the schema contract, the inheritance merge and the validation
4. Complete Phase 4: US2, the remaining inheritance scenarios
5. Complete Phase 5: US3, the detail view and the schema viewer
6. **STOP and VALIDATE**: load `models/base/dcim.yml` with the containers of T066 on a server built
   from the branch and open `port-channel1` of `atl1-leaf1`; the Details, LACP, Layer 2 and
   Advanced cards render (the schema API still returns the fields through the backend; only the
   SDK read models of US5 lag behind)

### Incremental Delivery

1. Setup + Foundational: the model, the properties and the generated files
2. US1 + US2: the backend contract, tested on its own
3. US3: the detail view (MVP)
4. US4: the forms
5. US5: the SDK PR, then the pointer bump once it merges; the schema API tests turn green
6. US6: the guide page, the sidebar entry and the changelog fragment
7. Polish: the demo schema, the e2e test, the gates and the knowledge files; the Infrahub PR
   leaves draft after T058

### Parallel Team Strategy

With several developers, once Foundational is done:

- Developer A: US1 then US2 (backend)
- Developer B: US3 then US4 (frontend)
- Developer C: US5 (SDK PR) then US6 (documentation)
- Together: Polish, after the SDK PR merges and the pointer is bumped

---

## Notes

- `[P]` tasks touch different files than every incomplete task they could run beside
- `[USn]` maps a task to its user story
- Verify that a test fails before implementing what it covers
- Commit after each task or logical group; T023, T024 and T025 in one commit
- The Infrahub PR must never point at an unpushed submodule commit; it stays in draft until T058
- Generated files (`backend/infrahub/core/schema/generated/`, `python_sdk/infrahub_sdk/schema/generated/`, `schema/openapi.json`, `docs/docs/reference/schema/`, `frontend/app/src/shared/api/rest/types.generated.ts`) are regenerated, never edited
