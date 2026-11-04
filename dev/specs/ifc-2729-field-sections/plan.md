# Implementation Plan: Schema-defined field sections

**Branch**: `ple-field-sections-ifc-2729` | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-2729-field-sections/spec.md`

## Summary

A schema designer declares named containers on a node or generic and assigns attributes and
relationships to them. Operators then view one collapsible card per section on the node detail page
and one bordered panel per section in the create and edit forms, and schema API clients read the
same containers. The change adds a `ContainerSchema` model and three properties to the internal
schema definitions (`containers` on nodes and generics, `container` on attributes and
relationships), merges inherited containers by name in the inheritance handler, validates container
references in a schema-branch validator plug-in, copies containers onto generated profiles and
object templates, regenerates the backend, SDK, OpenAPI, REST-type and reference-doc files, and adds
one section partition rule that the detail view and the form share. The Advanced section is
implicit (never stored, never returned) and the GraphQL schema does not change. Decisions and
rejected options: [research.md](research.md). Model and rules: [data-model.md](data-model.md).
Contracts: [contracts/schema-api.md](contracts/schema-api.md) and
[contracts/frontend-components.md](contracts/frontend-components.md).

## Technical Context

**Language/Version**: Python 3.14 (backend, `tasks/`), TypeScript 6.0 with React 19.3 and Vite 8.3
(frontend), Python for the `python_sdk` submodule (its own PR on
`opsmill/infrahub-sdk-python`, branched from `infrahub-develop`)

**Primary Dependencies**: FastAPI 0.131 and Pydantic 2.12 (schema models, schema API),
`react-aria-components` (`Disclosure` and `DisclosurePanel` for the collapsible card),
`@infrahub/ui` (`Card`, `CardHeader`, `CardContent`), react-hook-form (existing form state),
`openapi-typescript` (REST types), Docusaurus (reference docs)

**Storage**: Neo4j. The stored schema-of-the-schema (`SchemaNode`, `SchemaGeneric`,
`SchemaAttribute`, `SchemaRelationship`) gains the three properties when the internal schema is
loaded; no graph migration and no `GRAPH_VERSION` change, the same footprint as the `display`
property. Approved in the spec's clarifications.

**Testing**: pytest unit tests (`backend/tests/unit/`) for the model, the validator and the
inheritance merge; pytest component tests (`backend/tests/component/`, testcontainers) for the
reload merge, the database round trip and the schema API; Vitest for the partition rule, the detail
card, the detail view, the form and the schema viewer; pytest-playwright end-to-end test in
`tests/e2e/objects/`; SDK unit tests in `python_sdk/tests/unit/ctl/`

**Target Platform**: Infrahub server (schema API), Infrahub web UI, Python SDK and `infrahubctl`

**Project Type**: Web application: backend, frontend, SDK submodule, demo schema, documentation

**Performance Goals**: No new query and no new request. `GET /api/schema` payloads grow by the
`containers` list of each node, generic, profile and template and by one `container` key per field.

**Constraints**: The GraphQL data schema and queries must not change (FR-014). Every schema that
loads today must load unchanged and render as before (SC-003). Generated files are regenerated,
never hand-edited. The SDK PR must be merged upstream before the Infrahub PR bumps the `python_sdk`
pointer; until then `GET /api/schema` cannot return the new fields because the read models come
from `infrahub_sdk.schema.generated.read`.

**Scale/Scope**: One new backend model, one new validator, three internal schema properties and
their generated outputs; one new domain rule, one new header component, one new form panel and prop
additions on two existing components in the frontend; one SDK formatter change; three containers in
the demo schema; one documentation page; one end-to-end test. No `NEEDS CLARIFICATION` remains: the
spec's clarifications resolved the internal schema change, the demo schema, the implicit Advanced
section and the profile and template copy.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Schema-Driven Integrity | Pass | Containers are schema properties validated at load time; generated files (`core/schema/generated/`, SDK `generated/`, `openapi.json`, REST types, reference docs) are regenerated with `invoke` tasks and `pnpm codegen:openapi`, never edited. |
| II. Branch-Safe by Default | Pass | Containers are stored with the schema of each branch and reloaded with it; the schema API test covers a non-default branch and a schema lifecycle test in `backend/tests/integration/schema_lifecycle/` loads containers on a branch, merges it and reads the node on the default branch (FR-006). No new query. |
| III. Type Safety & Explicit Contracts | Pass | `ContainerSchema` is a Pydantic `HashableModel` with field constraints; the API shape is written as a contract before implementation; the frontend reads `ContainerSchema` from the generated REST types and the partition rule is generic over the item type. |
| IV. Test Discipline | Pass | Unit tests for the model, validator, inheritance merge and partition rule; component tests for reload merge, round trip and API; Vitest component tests for card, view, form and viewer; one e2e test on the demo data. Tests are written before each task's implementation. |
| V. Query Performance | Pass | No database query is added or changed. |
| VI. Security & Input Boundaries | Pass | `POST /api/schema/load` validates the new properties through the existing write contract and the validator; the three error messages name the kind, the field and the container name only. |
| VII. Simplicity | Pass with justification | Two small shared pieces are added: `SectionTitle` (label and muted description) and the section partition rule. Each has two callers that land in this change: the detail card header and the form panel header for `SectionTitle` (FR-020 requires the same header in both), the detail view and the form for the partition rule (FR-015 and FR-021 require the same order in both). The validator is a plug-in of an interface that already exists; the inheritance merge is one step in the existing handler. No new dependency: `react-aria-components` and `@infrahub/ui` are already installed. |

Re-check after Phase 1 design: unchanged, all pass. The internal schema change (three properties on
the stored schema definitions, no graph migration, no GraphQL change) is approved in the spec's
clarifications and needs no further ask.

## Design

### D1. Backend model and internal schema properties

`backend/infrahub/core/schema/container.py::ContainerSchema` is a `HashableModel` keyed on `name`
(`_sort_by = ["name"]`), patterned on `backend/infrahub/core/schema/dropdown.py::DropdownChoice`.
`backend/infrahub/core/schema/definitions/internal.py` declares `containers` (kind `List`,
`internal_kind=ContainerSchema`, empty list by default) on the base node schema and `container`
(kind `Text`, optional) on the attribute and relationship schemas, all with
`UpdateSupport.ALLOWED` and `Visibility.WRITE`. The SDK generator in `tasks/backend.py` gets a
`container_schema_fields` list of `name`, `label`, `description`, `order_weight` and `collapsed`
built with `_field`, plus `state` declared as an explicit `SchemaAttribute(name="state",
kind="Text", internal_kind=HashableModelState, enum=HashableModelState.available_types(),
enum_class="SchemaState", default_value=HashableModelState.PRESENT, optional=True, ...)` entry that
mirrors the attribute-level `state` entry of `definitions/internal.py::attribute_schema`
(`_field` is not extended, because it has no `enum_class` parameter). The list leaves out the
internal `inherited` flag, so the SDK read and write models and the OpenAPI schema never carry it.
A field left out of that list becomes read-only in the write contract and a load that sends it
drops the value with a warning, which is why `state` must be in the list for `state: absent` to
remove a container. Details: [data-model.md](data-model.md).

### D2. Inheritance merge with an internal `inherited` flag

`backend/infrahub/core/schema/node_inheritance_handler.py::NodeInheritanceHandler.inherit_from_interface`
gets a step that appends an `inherited=True` copy of each generic container whose name the node does
not already have. `SchemaBranch.process_inheritance` drops the `inherited` containers of a node
right after duplicating it, before the generic loop, so a generic that drops a container removes it
from the node on the next process, and a second process yields the same list (FR-010). Field-level
`container` needs no code: `update_from_generic` already copies it.

### D3. Validator plug-in

`backend/infrahub/core/validators/schema_branch/container_validator.py::ContainerValidator` is
registered in `SchemaBranch.validators` next to `HierarchicalNodesRestrictedWords`. It runs in
`SchemaBranch.process_validate`, after inheritance, and raises `ValueError` with one of the three
messages of [data-model.md](data-model.md#validation-rules). `evaluate_candidate_schemas` in
`backend/infrahub/api/schema.py` turns it into a 422 as today.

### D4. Profiles and object templates copy the containers

`SchemaBranch.generate_profile_from_node` and `SchemaBranch.generate_object_template_from_node` copy
`node.containers` without the `inherited` flag. Attribute copies already carry `container`. Both
generators run on every process, so the copies stay current.

### D5. Frontend partition rule and section model

`frontend/app/src/entities/nodes/object/domain/rules/group-fields-by-section.ts::groupFieldsBySection`
takes the containers, already-filtered items and a function that reads an item's container, and
returns ordered `FieldSection` values: Details first, declared containers by `order_weight` then
declaration order, Advanced last with `collapsed: true`, sections without an item dropped. The
`DETAILS_SECTION` and `ADVANCED_SECTION` constants and the `FieldSection` type live in
`entities/nodes/object/domain/model/field-section.ts`.

### D6. Detail view: one card per section

`object-details.tsx::ObjectDetails` applies the detail view's visibility filters
(`getAttributesVisibleInDetailedView` and `getRelationshipsVisibleInDataDisplay`, which
`object-data-display.tsx` keeps and exports as a named export so both can call it; the kind-based
`getRelationshipsVisibleInDetailedView` of `domain/rules/` is a different predicate that the data
display does not use), partitions the result, and renders one `ObjectDetailsCard` per section with
`objectSchema={{ ...objectSchema, attributes, relationships }}`, where `relationships` is the
section's visible relationships plus every relationship of the full schema for which
`isFromResourcePoolRelationship` is true, because the summary filter drops those before the
partition and `object-data-display.tsx` looks the `<name>_from_resource_pool` relationship up in
the schema it receives. `ObjectDetailsCard` gets `defaultCollapsed` and `description`; when
`defaultCollapsed` is undefined the header is unchanged for every existing caller. When defined,
the header DOM is `CardHeader > [h2 > Button(chevron, label)] [p.description, id=descriptionId]
[Extra button]`: the react-aria `Disclosure` trigger button carries
`aria-describedby={descriptionId}`, the region's `aria-labelledby` is the `h2` id, and the Extra
button stays a sibling of the `h2`. `SectionTitle` takes `label`, `description`, `titleId` and
`descriptionId` and renders the label slot and the description `<p>` as siblings: the detail card
passes the trigger button as the label slot and places the description after the `h2`; the form
panel passes plain text. Contract:
[contracts/frontend-components.md](contracts/frontend-components.md).

### D7. Form: one panel per section

`DynamicForm` gets an optional `sections` prop. `fields` stays the single source for default values
and submission. Without `sections`, or when only the Details section has fields, the form is the
flat list of today. Otherwise the form partitions `fields` with the same rule, passing
`(field) => "relationship" in field ? field.relationship.container : field.attribute?.container`
as the `getContainer` argument so the container is read from the schema attached to each field,
and renders one `FormSectionPanel` per section, always expanded.
`NodeForm` passes `sections={schema.containers}`; no other caller changes.

### D8. Schema viewer, demo schema, documentation

The schema viewer lists a node's containers and shows each field's container with the existing
`PropertyRow`. `models/base/dcim.yml` declares the LACP, Layer 2 and Layer 3 containers on
`InfraLagInterface` and assigns the generic's and the two implementing nodes' fields;
`InfraLagInterfaceL3` redeclares `mtu` with `container: layer3` (research R7). The same change
fixes the label of the `minimum_links` attribute (`Mimimum links` today) to `Minimum links`, a
user-visible fix that gets its own changelog fragment.
A new `docs/docs/schema/field-sections.mdx` page explains the properties, the built-in Advanced
section, the default Details section, ordering, inheritance and the three errors; the generated
reference pages come from `uv run invoke docs.generate`.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2729-field-sections/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── schema-api.md
│   └── frontend-components.md
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
backend/infrahub/core/
├── constants/__init__.py                                  # ADVANCED_CONTAINER_NAME
├── schema/
│   ├── container.py                                       # new: ContainerSchema
│   ├── __init__.py                                        # export ContainerSchema
│   ├── definitions/internal.py                            # containers, container, fixed_types entry
│   ├── node_inheritance_handler.py                        # container merge step
│   ├── schema_branch.py                                   # validator registration, inherited reset,
│   │                                                      # profile and template copy
│   └── generated/                                         # regenerated: base_node_schema,
│                                                          # attribute_schema, relationship_schema
└── validators/schema_branch/container_validator.py        # new: ContainerValidator
backend/templates/basenodeschema_imports.j2                # import of ContainerSchema
backend/tests/
├── helpers/schema/lag_interface.py                        # new shared fixture (LAG generic, L2, L3)
├── fixtures/schemas/not_valid_container_01.json           # new 422 fixture
├── unit/core/schema/test_schema_branch_containers.py      # new: validator cases
├── unit/core/schema/test_node_inheritance.py              # container merge cases
├── unit/core/schema/test_schema_update_validation.py      # no migration, no constraint
├── unit/core/schema/test_generated_visibility.py          # WRITE fields, read-only delta
├── unit/api/test_schema_load_contract.py                  # load contract cases
├── component/core/schema/schema_branch/test_process_idempotency.py
├── component/core/schema_manager/test_manager_schema.py   # reload merge, profile, template
├── component/api/test_40_schema.py                        # GET and POST cases
└── integration/schema_lifecycle/                          # merge of a branch with containers
tasks/backend.py                                           # SDK generator: container_schema_fields,
                                                           # family, internal counterpart
schema/openapi.json                                        # regenerated

python_sdk/                                                # submodule, separate PR
├── infrahub_sdk/schema/generated/{read,write,contract}.py # regenerated by backend.generate
├── infrahub_sdk/schema/main.py                            # re-export ContainerSchema
├── infrahub_sdk/ctl/schema_format.py                      # NODE_ORDER, ATTRIBUTE_ORDER,
│                                                          # RELATIONSHIP_ORDER, CONTAINER_ORDER
└── tests/unit/ctl/test_schema_format.py

frontend/app/src/
├── entities/schema/domain/model/schema.ts                 # ContainerSchema type
├── entities/schema/ui/schema-viewer.tsx                   # containers block
├── entities/schema/ui/attribute-display.tsx               # Container row
├── entities/schema/ui/relationship-display.tsx            # Container row
├── entities/nodes/object/domain/model/field-section.ts    # new: constants, FieldSection
├── entities/nodes/object/domain/rules/group-fields-by-section.ts        # new rule (+ test)
├── entities/nodes/object/ui/object-details/section-title.tsx            # new header piece
├── entities/nodes/object/ui/object-details/object-details-card.tsx      # defaultCollapsed, description
├── entities/nodes/object/ui/object-details/object-details.tsx           # one card per section
├── entities/nodes/object/ui/object-details/object-data-display/
│   └── object-data-display.tsx                            # relationship filter made callable from the view
├── shared/components/form/form-section-panel.tsx          # new: bordered panel with SectionTitle
├── shared/components/form/dynamic-form.tsx                # sections prop (+ new test)
├── shared/components/form/node-form.tsx                   # passes schema.containers
└── shared/api/rest/types.generated.ts                     # regenerated by pnpm codegen:openapi
frontend/app/tests/fake/schema.ts                          # containers and container defaults, factory

models/base/dcim.yml                                       # containers on InfraLagInterface,
                                                           # mtu redeclared on InfraLagInterfaceL3
tests/e2e/data/sites.py                                    # one InfraLagInterfaceL3 object
tests/e2e/objects/test_object_containers.py                # new e2e test
tests/e2e/README.md                                        # fixture catalog entry

docs/docs/schema/field-sections.mdx                        # new guide page
docs/docs/schema/overview.mdx                              # link to the page
docs/sidebars.ts                                           # entry under Display & presentation
docs/docs/reference/schema/{node,generic,attribute,relationship}.mdx   # regenerated
changelog/<fragment>.added.md                              # towncrier fragment
```

**Structure Decision**: Each layer changes inside its existing module: the backend schema package
and its validator plug-in directory, the frontend `entities/nodes/object` and
`shared/components/form` slices, the SDK schema package. No new directory.

## Delivery phases

Phase A is sequential. Phases C, D, E and G run in parallel once their dependency has landed. The
SDK PR (phase C) is a separate deliverable on `opsmill/infrahub-sdk-python` and must be merged
upstream before phase H bumps the submodule pointer; the Infrahub PR must never point at an
unpushed submodule commit.

- Phase A, backend core (sequential, each task test-first):
  - A1: `ContainerSchema`, the three internal definitions, the `fixed_types` entry, the template
    import, the SDK generator lists and `ADVANCED_CONTAINER_NAME`.
  - A2: shared fixture `backend/tests/helpers/schema/lag_interface.py`.
  - A3: inheritance merge in the handler and the `inherited` reset in `process_inheritance`.
  - A4: `ContainerValidator` and its registration.
  - A5: profile and template copy. A4 and A5 land together: profiles and templates are generated
    before validation, so a profile without its containers would fail the load.
- Phase B, regeneration gate (after A1, rerun after A5): `uv run invoke backend.generate`,
  `uv run invoke schema.generate-jsonschema`, `uv run invoke docs.generate`,
  `cd frontend/app && pnpm codegen:openapi`, then the validate tasks of
  [quickstart.md](quickstart.md). `schema.validate-graphqlschema` shows no diff (FR-014).
- Phase C, SDK submodule (after B, parallel with D and E): branch the SDK from
  `origin/infrahub-develop`, commit the regenerated `generated/*.py`, the `main.py` re-export, the
  `schema_format.py` key order and its tests, push, open the SDK PR.
- Phase D, backend persistence and API tests (after A5 and B, parallel with C and E): reload merge
  cases, database round trip, an assertion that `get_hash()` is equal after two `process()` calls
  on a schema with inherited containers, `GET /api/schema/{kind}` and `POST /api/schema/load` cases
  including a non-default branch, a `POST /api/schema/load` case that sends `state: absent` on a
  container item and asserts the container is gone and no read-only warning is returned, and a
  schema lifecycle test in `backend/tests/integration/schema_lifecycle/` that loads containers on a
  branch, merges it and reads the node on the default branch.
- Phase E, frontend (after B, parallel with C and D): E1 types, fixtures, model and partition rule
  first; then E2 detail view (with the Vitest case "a pool-allocated attribute inside a section
  shows its pool row"), E3 form and E4 schema viewer in parallel; E5 the frontend gates.
- Phase F, demo schema and end-to-end (after A5, E2 and E3; the e2e run needs the image built from
  the bumped pointer of phase H): F1 `models/base/dcim.yml`, where `InfraLagInterfaceL3`
  redeclares `mtu` with `container: layer3`; F2 one `InfraLagInterfaceL3` object in
  `tests/e2e/data/sites.py`, `tests/e2e/objects/test_object_containers.py` asserting the L2 and
  the L3 layouts, and its catalog entry.
- Phase G, documentation (after B, parallel with C to F): the guide page, the sidebar entry, the
  overview link, the changelog fragment.
- Phase H, pointer bump and repository gates: after the SDK PR merges, pin `python_sdk` to the
  merged commit, rerun the phase B validations and the schema API visibility test, then the format,
  lint and whole-repository ruff checks, then `/pre-ci`.

## Risks

1. Reload merge and the `inherited` flag: a reload that redeclares an inherited container relies on
   `HashableModel.update` overwriting the bool from the write payload (default `False`), and nodes
   loaded from the database carry `inherited=True` copies that the reset in `process_inheritance`
   must drop. Guarded by the reload test that asserts `inherited` is `False` after the redeclaration
   and by `test_reload_matches_saved_schema`.
2. Nested interactive elements: the Extra button must not sit inside the Disclosure trigger button.
   It stays a sibling of the trigger in `CardHeader`.
3. Validator order with profiles: profiles and templates are generated before `process_validate`,
   so a profile missing its containers fails the load. A4 and A5 land in the same commit.
4. Demo schema change: every e2e shard that loads `dcim.yml` is affected. Check the file with
   `uv run infrahubctl schema check models/base/dcim.yml` against a running instance before pushing.
5. SDK sequencing: the schema API tests fail until the SDK PR merges and the pointer is bumped;
   the Infrahub PR stays in draft until then.
6. Demo schema `mtu` redeclaration: `mtu` is declared on `InfraInterface`. `InfraLagInterfaceL3`
   redeclares it (`name: mtu`, `kind: Number`, `label: MTU`, `default_value: 1500`,
   `container: layer3`): the inheritance handler skips a generic attribute whose name is local, and
   `validate_inheritance` only requires the same kind because `allow_override` defaults to `any`.
   The L3 node shows the Layer 3 card and exercises US2 scenario 3; the L2 node shows no Layer 3
   card and exercises the empty-card rule. The redeclaration must keep `kind: Number`, or the load
   fails the inheritance check.

## Complexity Tracking

No constitution violation. The two shared pieces under principle VII each have two callers in this
change; the justification is in the Constitution Check.
