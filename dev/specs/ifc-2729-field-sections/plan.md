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
per section). Details is the only built-in section of a node or generic and sits at order weight
0, generated profiles add a Profile section above it, generated object templates add a Template
section above it, and the GraphQL schema does not change. Only the detail cards of containers with
`collapsible: true` can be collapsed, the schema viewer lists containers in a Containers tab, and
the first tab of the object and IPAM detail pages is named Overview.

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

**Details is the only built-in section.** Fields without a `container` form Details, and
`details` cannot be declared or referenced. The first version of this plan also made `advanced`
implicit: never stored or returned, always accepted as a reference, and not declarable (rejected
alternative: a derived read-only container in the API, which the write contract and the formatter
would have to strip). The product owner reversed that decision on 2026-11-10: `advanced` is an
ordinary container name, and the frontend has no Advanced section.

**Negative weights place a container above Details.** The product owner decided on 2026-11-10 that
Details sits at order weight 0: a container with a negative `order_weight` renders before it, and
a container with a weight of 0 or more, or without a weight, after it. `groupFieldsBySection`
applies the rule, so the detail page, the IPAM detail page and the forms follow it. The backend
does not order containers and `ContainerSchema.order_weight` has no lower bound, so no backend
change was needed. Existing schemas keep their layout unless a container has a negative weight.

**The `builtin_` prefix is reserved.** The product owner decided on 2026-11-10 that a node or
generic cannot declare a container whose name starts with `builtin_`
(`BUILTIN_CONTAINER_PREFIX`), so a generated container never collides with a declared one.
`ContainerValidator` accepts `builtin_profile` only on a `ProfileSchema` and `builtin_template`
only on a kind in the `Template` namespace.

**Profiles get a generated Profile container.** The product owner asked on 2026-11-10 that a
profile show its name and priority first. `generate_profile_from_node` adds `builtin_profile`
(label Profile, order weight -100, not collapsible) before the node's copied containers and sets
`container: builtin_profile` on `profile_name` and `profile_priority`. The copied node attributes
keep the node's containers. Profiles are generated on every process and are not stored
(`SchemaManager.load_schema_to_db` stores nodes and generics), and `SchemaBranch.diff` and
`SchemaBranch.get_hash` compare nodes and generics only, so the container is never reported as a
schema change or a merge conflict.

**Object templates get a generated Template container.** Added on 2026-11-12 so that a template
shows its name first, as a profile does. `generate_object_template_from_node` adds
`builtin_template` (label Template, order weight -100, not collapsible) before the node's copied
containers and sets `container: builtin_template` on `template_name`, for both the `TemplateSchema`
of a node and the `GenericSchema` generated for a generic. Only the negative weight places it above
Details; the frontend has no rule for `builtin_` containers. Templates are generated on every
process and are not stored (`SchemaManager.load_schema_to_db` stores
`node_names + generic_names_without_templates`). `SchemaBranch.diff` compares the kinds of
`get_all_kind_id_map(nodes_and_generics_only=True)`, which leaves out the `Template` namespace, so
the container is never reported as a schema change or a merge conflict. Unlike a profile, the
template generated for a generic is stored in `SchemaBranch.generics`, so `SchemaBranch.get_hash`
includes it, together with the node containers it already copied. `ContainerValidator` identifies
templates by the `Template` namespace rather than by `TemplateSchema`, because the template
generated for a generic is a `GenericSchema`.

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

**A `collapsible` flag decides which cards collapse.** Added on 2026-11-12. `ContainerSchema`
has `collapsible` (default true) next to `collapsed`. `ObjectDetailsCard` renders a `Disclosure`
only for a section with `collapsible: true`; `collapsed` sets its initial state. A section with
`collapsible: false`, like `DETAILS_SECTION`, renders the plain header, so the Details, Profile and
Template cards are always expanded. `ContainerValidator` refuses `collapsed: true` with
`collapsible: false`, so a stored schema never asks for a collapsed card that cannot open. The
generated `builtin_profile` and `builtin_template` containers set `collapsible=False`. Rejected:
deciding collapsibility in the frontend from the `builtin_` prefix, which the API would not
expose to other clients.

**Schema viewer Containers tab.** Added on 2026-11-12. The schema viewer lists containers in
their own tab, between Properties and Attributes, with one `ContainerDisplay` accordion per
container built on `AccordionStyled`, so containers look like attributes and relationships. The
Properties tab stays as on `develop`. The accordion does not list the container's fields: the
Container row of each attribute and relationship already shows them.

**Overview tab.** Added on 2026-11-12. The first tab of the object detail page and of the IPAM
detail layout is named Overview, so it no longer shares its name with the Details card it
contains. Only the label changes; the route stays the same.

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

- Model and constants: `backend/infrahub/core/schema/container.py` (with `collapsible`),
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
  `object-details.tsx`, `object-details-tabs.tsx`, `object-data-display/object-data-display.tsx`
  under `entities/nodes/object/ui/object-details/`, `pages/ipam/ipam-details-page.tsx` and
  `pages/ipam/ipam-details-layout.tsx`.
- Forms: `shared/components/form/dynamic-form.tsx`, `form-section-panel.tsx`, `node-form.tsx`,
  `core-file-form.tsx`.
- Schema viewer: `entities/schema/ui/schema-viewer.tsx`, `schema-viewer-modal.tsx`,
  `container-display.tsx`, `attribute-display.tsx`, `relationship-display.tsx`; type in
  `entities/schema/domain/model/schema.ts`.
- Generated: `shared/api/rest/types.generated.ts`, `frontend/app/.betterer.results`.

Demo, end-to-end and documentation:

- `models/base/dcim.yml`, `tests/e2e/data/sites.py`, `tests/e2e/objects/test_object_containers.py`,
  `tests/e2e/README.md`, and `tests/e2e/ipam/test_ip_prefix_list.py` for the Overview tab.
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
- A database that loaded the demo schema of this branch before 2026-11-10 stores `max_bundle` with
  `container: advanced`. Schema loading validates the stored schema, so that database no longer
  loads; recreate it. No released version stores `container`.
