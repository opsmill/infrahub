# Research: Schema-defined field sections

One entry per decision. Each states the decision, why it was taken and what was considered instead.
Code is cited as `module::Symbol`.

## R1. Container validation as a schema-branch validator plug-in

- **Decision**: A new
  `backend/infrahub/core/validators/schema_branch/container_validator.py::ContainerValidator`,
  registered in `SchemaBranch.validators` next to `HierarchicalNodesRestrictedWords`.
- **Rationale**: The plug-in loop is the first step of `SchemaBranch.process_validate`, which runs
  after `SchemaBranch.process_inheritance` (called from `process_pre_validation`), so the validator
  sees the merged containers of every node. The interface already exists, so no new abstraction is
  introduced; the cost is one file and one registration line instead of adding the logic to
  `schema_branch.py`, which already holds several thousand lines.
- **Alternatives considered**: An inline `SchemaBranch.validate_containers` method called from
  `process_validate`, the way `DisplayLabelValidator` is called. That validator is inline because
  it must run after `validate_uniqueness_constraints`; containers have no such ordering need.

## R2. Inherited containers marked with an internal `inherited` flag

- **Decision**: `ContainerSchema` carries `inherited: bool = False`. The inheritance handler appends
  `inherited=True` copies of each generic container whose name is not already on the node.
  `SchemaBranch.process_inheritance` drops the node's `inherited` containers right after
  `node.duplicate()`, before the generic loop.
- **Rationale**: "Node wins, then the first generic in `inherit_from` wins" falls out of the
  per-generic loop order with a name check. Dropping the inherited copies before the loop handles
  a generic that removes a container the node never redeclared, and makes a second process
  idempotent (FR-010). A reload that redeclares an inherited container flips the flag to `False`
  because `HashableModel.update` overwrites a bool from the write payload, whose default is
  `False`. The flag is hidden from the API and the SDK by not listing it in the generator's
  `container_schema_fields` in `tasks/backend.py`: the SDK read and write models come from that
  list only, and `backend/infrahub/schema/read_schema.py::build_read_schema` projects onto read
  models declared with `extra="ignore"`. Profile and template copies use
  `model_dump(exclude={"inherited"})`, as attribute copies exclude their own internal fields.
- **Alternatives considered**: A plain merge-by-name dictionary without a marker. It cannot tell a
  stale inherited copy from a local declaration on the next process, so it would need an
  equivalent marker anyway. Adding `containers` to the handler's `properties_to_inherit` list:
  that list copies a property only when the node has none, so a node that declares one container
  would lose every generic container. A `Visibility.INTERNAL` entry: no such entry exists for a
  hand-written fixed type.

## R3. Form grouping reads the container from the field's attached schema

- **Decision**: A small rule `getFormFieldContainer(field)` returns
  `field.relationship.container` or `field.attribute?.container`. `DynamicForm` partitions its
  `fields` with it; no new prop on the field and no name-to-container map.
- **Rationale**: `FormFieldProps.attribute` and `DynamicRelationshipFieldProps.relationship` in
  `frontend/app/src/shared/components/form/type.ts` are set by `getFormFieldFromAttribute` and
  `getFormFieldFromRelationship`, including the bulk `relationship-add` and `relationship-remove`
  pair built by `getFormFieldsFromSchema`. The data is already on the field. The field-builder
  tests assert that every schema-built field carries its schema.
- **Alternatives considered**: A `container` prop on every form field: duplicates data already on
  the field. A name-to-container map passed to the form: must strip the bulk prefixes from the
  field names before the lookup.

## R4. `SectionTitle` kept as a shared header piece; `FieldSet` move rejected

- **Decision**: `entities/nodes/object/ui/object-details/section-title.tsx::SectionTitle` renders
  the container label and, when set, the description as muted text under it. The detail card
  header and the form panel header both use it. The repository entity's `FieldSet` shape stays
  where it is.
- **Rationale**: FR-020 and FR-021 require the same header in the detail card and the form panel;
  both callers land in this change, which meets the two-callers rule of principle VII.
  `dynamic-form.tsx` already imports from `@/entities/schema`, so the form panel importing from an
  entity follows an existing direction. The section rule needs its own shape (`container` plus
  the two lists), and `entities/nodes/object` importing from `entities/repository` would be the
  wrong direction.
- **Alternatives considered**: Inline the title markup in both places: two copies that must stay
  identical. Move `partitionFieldsByBranchSupport`'s `FieldSet` to a shared place and reuse it: the
  repository entity is untouched by this feature and its shape lacks the container.

## R5. Empty-section rule applies the detail view's visibility filters

- **Decision**: The partition rule is generic over the item type and takes already-filtered items.
  The detail view filters with `getAttributesVisibleInDetailedView` and the relationship filter
  that `ObjectDataDisplay` applies today, partitions the result, and renders each section with
  `objectSchema={{ ...objectSchema, attributes, relationships }}`, the narrowing that
  `repository-object-details.tsx::RepositoryObjectDetails` already uses.
- **Rationale**: A section whose only field is not shown in the detail view (a relationship shown
  in a tab, such as `ip_addresses` or a `Component` relationship of cardinality many) must be
  dropped (FR-015, US3 scenario 5). Filtering before partitioning is the only way the rule can
  know the section is empty. `ObjectDataDisplay` re-applies the same filters, which is idempotent,
  and `hasExtraFields` evaluated on the narrowed schema scopes the Extra control to the section
  (FR-018). The relationship filter is a module-private function of the data display today and
  moves out so the view can call it.
- **Alternatives considered**: A `fields` prop on `ObjectDetailsCard` instead of the narrowed
  schema: changes the card's contract for every caller. Partitioning the full schema and letting
  each card hide its rows: an empty card would still render its header.

## R6. Placement of the Advanced and Details constants

- **Decision**: Backend: `ADVANCED_CONTAINER_NAME = "advanced"` in
  `backend/infrahub/core/constants/__init__.py` next to `NAME_REGEX`, used by the validator and
  its error message only. Frontend: `ADVANCED_CONTAINER` and `DETAILS_SECTION` in
  `entities/nodes/object/domain/model/field-section.ts`, imported by the partition rule and the
  views.
- **Rationale**: Each constant sits with the code that owns the rule it expresses. The SDK needs
  no constant: it does not validate container references.
- **Alternatives considered**: One constant shared through the OpenAPI schema: the Advanced
  section is implicit (R9), so the API carries nothing to generate from.

## R7. Demo schema assignments on the LAG interface

- **Decision**: In `models/base/dcim.yml`, `InfraLagInterface` declares `lacp` (label "LACP",
  weight 100), `layer2` (label "Layer 2", weight 200, with a description) and `layer3` (label
  "Layer 3", weight 300, `collapsed: true`). On the generic: `lacp`, `minimum_links` and `mlag` go
  to `lacp`; `max_bundle` goes to `advanced`. On `InfraLagInterfaceL2`: `l2_mode`, `untagged_vlan`
  and `tagged_vlan` go to `layer2`; `members` stays ungrouped. On `InfraLagInterfaceL3`:
  `ip_addresses` goes to `layer3`; `members` stays ungrouped. `mtu` stays ungrouped.
- **Rationale**: The LAG interface is the mockup's node and `port-channel1` of `atl1-leaf1` already
  exists in the e2e site data, so no new data is needed. The assignments exercise inheritance (the
  containers come from the generic), the Advanced section, a description, a collapsed container
  and the empty-card rule on both nodes: the L2 node has no Layer 3 field, and on the L3 node the
  only Layer 3 field is tab-only, so neither node shows a Layer 3 card. `mtu` is declared on
  `InfraInterface`, which does not own the containers, and a node cannot redeclare an inherited
  attribute to move it.
- **Alternatives considered**: A dedicated schema loaded by the e2e test through the SDK: isolates
  the test but needs its own data, catalog entry and shard, and leaves the demo without sections.
  Declaring the containers on `InfraInterface` so that `mtu` can be grouped: puts sections on every
  physical interface, which the product decision did not ask for.

## R8. Profiles and object templates are regenerated on every process

- **Decision**: Copy `node.containers` in `SchemaBranch.generate_profile_from_node` and
  `SchemaBranch.generate_object_template_from_node`, excluding the `inherited` flag. No other
  refresh code.
- **Rationale**: `SchemaBranch.manage_profile_schemas` and
  `SchemaBranch.manage_object_template_schemas` regenerate every profile and template from its
  node on every process, so the copy is always current. Attribute copies already carry
  `container`, so the references on the copies resolve. Profile relationships are built field by
  field and carry neither `display` nor `container`; they stay as they are.
- **Alternatives considered**: Strip `container` from the attribute copies instead: fewer lines,
  but profile and template forms stay flat and the copies diverge from the node by one more field.
  A separate refresh step: `manage_profile_relationships` updates the node's `profiles`
  relationship, not the profile, so there is no existing hook to extend.

## R9. The Advanced section is implicit

- **Decision**: `advanced` is never stored, never returned in `containers`, and always accepted as
  a `container` value. The frontend appends the Advanced section after every declared section with
  `collapsed: true`.
- **Rationale**: Materializing it would make schema load round trips, `infrahubctl schema format`
  output and schema diffs carry a container the schema designer never wrote. Confirmed in the
  spec's clarifications.
- **Alternatives considered**: A derived read-only container in the API: every consumer would
  read it, but the write contract would have to reject it on load and the formatter would have to
  drop it.

## R10. react-aria `Disclosure` for the collapsible card

- **Decision**: `ObjectDetailsCard` implements `defaultCollapsed` with `Disclosure` and
  `DisclosurePanel` from `react-aria-components`, as
  `entities/repository/ui/repository-activity-card/repository-last-runs.tsx` already does inside a
  card. The `h2` title is the trigger button; the Extra button stays its sibling in `CardHeader`.
- **Rationale**: `@infrahub/ui` already depends on `react-aria-components`, and the chevron, focus
  ring and reduced-motion behaviour can be copied from the existing use. A button cannot nest in a
  button, so the Extra control must be a sibling of the trigger.
- **Alternatives considered**: Radix `Accordion` from `shared/components/ui/accordion.tsx`: wraps
  the trigger in its own header with padding that conflicts with `CardHeader`, and `@infrahub/ui`
  has no Radix dependency. The hand-written `shared/components/display/accordion.tsx`: used by the
  schema viewer only and not meant to spread.

## R11. `UpdateSupport.ALLOWED` and `Visibility.WRITE` on the three properties

- **Decision**: `containers`, `container` on attributes and `container` on relationships are
  declared with `extra={"update": UpdateSupport.ALLOWED, "visibility": Visibility.WRITE}`.
- **Rationale**: A container only affects rendering, so changing one needs neither a migration
  nor a constraint check (FR-005), the same choice as `display` and `order_weight`. Schema designers
  set the properties, so they must be writable; without `Visibility.WRITE` the field is absent
  from the SDK models and from `GET /api/schema`, as `test_schema_read_endpoint_visibility`
  checks.
- **Alternatives considered**: `UpdateSupport.VALIDATE_CONSTRAINT`: there is no data constraint
  to check. A read-only visibility: the schema designer could not set the property.

## R12. `containers` merged by name on reload, removal with `state: absent`

- **Decision**: `ContainerSchema` sets `_sort_by = ["name"]` so that `HashableModel.update`
  merges the `containers` list by name, as it does for dropdown choices. Removing a container on
  reload requires `state: absent` on the item.
- **Rationale**: `HashableModel.update_list_hashable_model` merges list items by their
  `_sorting_id`; an item left out of the list stays (FR-007, US1 scenario 6). This is the existing
  behaviour for every item list in the schema, and the documentation already explains
  `state: absent` for dropdown choices.
- **Alternatives considered**: Replace the whole list on reload: differs from every other item
  list in the schema and would silently drop containers that another schema file declared.
