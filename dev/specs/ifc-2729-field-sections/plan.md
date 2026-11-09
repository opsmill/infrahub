# Implementation Plan: Schema-defined field sections

**Branch**: `ple-field-sections-ifc-2729` | **Spec**: [spec.md](spec.md) | **Model**:
[data-model.md](data-model.md) | **Contracts**: [schema API](contracts/schema-api.md),
[frontend components](contracts/frontend-components.md)

## Summary

A `ContainerSchema` model and three properties of the schema-of-the-schema (`containers` on nodes
and generics, `container` on attributes and relationships) let a schema designer group fields into
sections. The inheritance handler merges a node's containers with its generics' by name, a
schema-branch validator checks names and references, and generated profiles and templates copy the
containers. The backend, SDK, OpenAPI, REST type and reference doc files are regenerated. In the
frontend, one partition rule feeds the detail page (one card per section) and the forms (one panel
per section). The Advanced section is implicit and the GraphQL schema does not change.

## Design decisions

**Validator plug-in.** `ContainerValidator` is a `SchemaBranchValidator` registered next to
`HierarchicalNodesRestrictedWords`; the plug-in loop runs after inheritance, so it sees the merged
containers. Rejected: an inline `SchemaBranch` method, which would add to a file of several thousand
lines with no ordering need.

**Inherited copies carry an `inherited` flag and are not stored.** `inherit_containers` discards the
node's `inherited=True` copies and rebuilds them from the generics on every process, so a generic
that drops a container updates its nodes and a second process gives the same list.
`SchemaManager` stores only the node's own containers, as for inherited attributes and
relationships. The API returns the flag; the write contract treats it as read-only. Rejected: a
merge by name without a marker, which cannot tell a stale copy from a local declaration; adding
`containers` to `properties_to_inherit`, which copies a property only when the node has none.

**Reload merge keeps the file order.** `BaseNodeSchema._merge_containers` replaces the generic list
merge for `containers`: incoming order first, left-out containers kept after, `state: absent`
removes. The node hash and diff include the container order, and `ordered=True` makes two
branches that reorder differently conflict on merge. Rejected: replacing the whole list on reload,
which differs from every other item list in the schema.

**Advanced is implicit.** `advanced` is never stored or returned and is always accepted as a
reference, and `details` and `advanced` cannot be declared. Rejected: a derived read-only container
in the API, which the write contract and the formatter would have to strip.

**No migration.** The three properties use `UpdateSupport.ALLOWED` and `Visibility.WRITE`, as
`display` and `order_weight` do: sections only affect rendering. A schema stored before the change
loads with an empty `containers` list and `container: null`.

**Profiles and templates copy containers.** The profile and template generators copy
`node.containers` and each relationship's `container`, so references on the copies resolve. They run
on every process, so no refresh code is needed. Rejected: stripping `container` from the copies,
which leaves profile and template forms flat.

**One partition rule for the detail view and the form.** `groupFieldsBySection` takes items already
filtered by the caller, so a section whose fields are all hidden (for example a relationship shown
in its own tab) is dropped. The form reads the container from the schema attached to each field.
Rejected: a `container` prop on form fields or a name-to-container map, which duplicate data the
field already holds.

**Collapsible card with react-aria `Disclosure`.** `@infrahub/ui` already depends on
`react-aria-components`, and the repository activity card uses `Disclosure`. The Extra button stays
a sibling of the trigger because a button cannot nest in a button. Rejected: the Radix accordion,
whose header padding conflicts with `CardHeader`.

**Demo schema on the LAG interface.** `InfraLagInterface` declares `lacp`, `layer2` and `layer3`;
`InfraLagInterfaceL3` redeclares `mtu` with `container: layer3`. The L2 node shows no Layer 3 card
and the L3 node no Layer 2 card, which tests the empty-section rule. Rejected: containers on
`InfraInterface`, which would put sections on every physical interface.

## Files touched

Backend:

- Model and constants: `backend/infrahub/core/schema/container.py`,
  `backend/infrahub/core/schema/__init__.py`, `backend/infrahub/core/constants/__init__.py`.
- Schema definitions: `backend/infrahub/core/schema/definitions/internal.py`,
  `backend/templates/basenodeschema_imports.j2`.
- Inheritance, merge, storage, copy: `node_inheritance_handler.py`, `basenode_schema.py`,
  `schema_branch.py`, `manager.py` under `backend/infrahub/core/schema/`.
- Validator: `backend/infrahub/core/validators/schema_branch/container_validator.py`.
- SDK generator: `tasks/backend.py`.
- Generated: `backend/infrahub/core/schema/generated/`, `schema/openapi.json`,
  `docs/docs/reference/schema/`.

Backend tests:

- Unit: `test_schema_branch_containers.py`, `test_node_inheritance.py`,
  `test_schema_update_validation.py`, `test_generated_visibility.py` under
  `backend/tests/unit/core/schema/`, and `backend/tests/unit/api/test_schema_load_contract.py`.
- Component: `backend/tests/component/api/test_40_schema.py`,
  `backend/tests/component/core/schema_manager/test_manager_schema.py`,
  `backend/tests/component/core/schema/schema_branch/test_process_idempotency.py`,
  `backend/tests/component/core/diff/test_ordered_attribute_conflicts.py`.
- Integration: `backend/tests/integration/schema_lifecycle/test_schema_containers_branch_merge.py`.
- Fixtures: `backend/tests/helpers/schema/lag_interface.py`,
  `backend/tests/fixtures/schemas/not_valid_container_01.json`.

SDK (`python_sdk` submodule, separate PR): `infrahub_sdk/ctl/schema_format.py`,
`infrahub_sdk/schema/export.py`, `infrahub_sdk/schema/main.py`, the generated
`infrahub_sdk/schema/generated/`, and their tests.

Frontend (`frontend/app/src/`):

- Section model and rule: `entities/nodes/object/domain/model/field-section.ts`,
  `entities/nodes/object/domain/rules/group-fields-by-section.ts`.
- Detail view: `object-details-sections.tsx`, `object-details-card.tsx`, `section-title.tsx`,
  `object-details.tsx`, `object-data-display/object-data-display.tsx` under
  `entities/nodes/object/ui/object-details/`, and `pages/ipam/ipam-details-page.tsx`.
- Forms: `shared/components/form/dynamic-form.tsx`, `form-section-panel.tsx`, `node-form.tsx`,
  `core-file-form.tsx`.
- Schema viewer: `entities/schema/ui/schema-viewer.tsx`, `attribute-display.tsx`,
  `relationship-display.tsx`; type in `entities/schema/domain/model/schema.ts`.
- Generated: `shared/api/rest/types.generated.ts`, `frontend/app/.betterer.results`.

Demo, end-to-end and documentation:

- `models/base/dcim.yml`, `tests/e2e/data/sites.py`, `tests/e2e/objects/test_object_containers.py`,
  `tests/e2e/README.md`.
- `docs/docs/schema/field-sections.mdx`, `docs/docs/schema/overview.mdx`, `docs/sidebars.ts`.
- `dev/knowledge/backend/schema-definitions.md`, `dev/knowledge/frontend/shared-components.md`.
- Changelog fragments `changelog/+ifc-2729-*.md`.

## Known gaps

- Merge validation builds its candidate schema with a two-way update, so a branch that adds a
  field to a container that the default branch removed can pass validation. This belongs to the
  merge schema validation work in `dev/specs/006-merge-schema-validation`.
- An inherited field can be placed in a section only by redeclaring it on the node, as
  `InfraLagInterfaceL3` does for `mtu`. The redeclaration must keep the generic's `kind`.
- The end-to-end test `tests/e2e/objects/test_object_containers.py` has not been run locally; it
  runs in CI.
