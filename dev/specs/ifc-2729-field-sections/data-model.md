# Data Model: Schema-defined field sections

Backend schema model, the three new schema properties, their inheritance, validation, copy and
reload rules, and the frontend section model. No graph migration: the properties are added to the
internal schema definitions and stored with the schema of each branch.

## ContainerSchema

`backend/infrahub/core/schema/container.py::ContainerSchema`, a `HashableModel` patterned on
`backend/infrahub/core/schema/dropdown.py::DropdownChoice`.

| Field | Type | Required | Default | Constraint |
|---|---|---|---|---|
| `name` | `str` | yes | none | `NAME_REGEX` (`^[a-z0-9\_]+$`), `DEFAULT_NAME_MIN_LENGTH` to `DEFAULT_NAME_MAX_LENGTH` characters, the attribute name rules; unique within a node after inheritance; never `details` or `advanced` |
| `label` | `str` | yes | none | Shown as the section title |
| `description` | `str \| None` | no | `None` | Shown as muted text under the title when set |
| `order_weight` | `int \| None` | no | `None` | Orders sections, lowest first; a container without a weight comes after the weighted ones, in declaration order; the backend does not fill it |
| `collapsed` | `bool` | no | `False` | The detail view card starts collapsed; the form panel ignores it |
| `state` | `HashableModelState` | no | `present` | Written as `absent` on a reload to remove the item; the same field as on attributes and relationships, exposed to the SDK as `SchemaState` |
| `inherited` | `bool` | no | `False` | `True` on a copy taken from a generic; never written by a schema designer; returned by the API and present on `ContainerSchemaRead`, read-only in the write contract, as on attributes and relationships |

- `_sort_by = ["name"]`: the name is the item's `_sorting_id`, so `HashableModel.update` merges a
  `containers` list by name.
- Name format and required fields are Pydantic field constraints on the model, not branch
  validators. Uniqueness after inheritance and the reservation of `details` and `advanced` are
  validator rules (below).
- `inherited` is listed in `container_schema_fields` in the SDK generator of `tasks/backend.py`
  with `Visibility.READ`, as the attribute-level `inherited` is declared in
  `definitions/internal.py`. The read family keeps it and the write family drops it, so
  `ContainerSchemaRead` carries it, `ContainerSchemaWrite` does not, and the contract lists it as
  read-only: a load that sends it gets a read-only warning and the value is dropped. Clients use
  it to tell the containers a kind declares from the copies of its generics; the SDK schema
  export writes only the containers whose `inherited` is `false`. `state` has `Visibility.WRITE`
  so that `state: absent` works on a load.
- A container name and an attribute name are separate namespaces; both may be `mtu`.

## Schema properties and where they are declared

All three are `SchemaAttribute` entries in `backend/infrahub/core/schema/definitions/internal.py`
with `extra={"update": UpdateSupport.ALLOWED, "visibility": Visibility.WRITE}` and a `description`
(the schema documentation test requires one).

- `containers` on `base_node_schema` (so on nodes, generics, profiles and templates), next to
  `order_by`: kind `List`, `internal_kind=ContainerSchema`, optional, `ordered=True`, default an
  empty list. `ordered=True` makes the branch diff conflict detection compare the list in order,
  so two branches that reorder the same containers differently produce a conflict on merge. A node or generic stored before this change has no `containers` value in the database;
  `BaseNodeSchema` turns a missing value into an empty list when the schema is loaded, so an
  upgraded instance loads its stored schema without a migration. `ContainerSchema` is added to
  the `fixed_types` map of `SchemaAttribute._external_internal_kind` and imported in
  `backend/templates/basenodeschema_imports.j2`, so the generated `base_node_schema.py` types the
  field as `list[ContainerSchema]`.
- `container` on `attribute_schema`, next to `display`: kind `Text`, optional, default `None`.
- `container` on `relationship_schema`, next to `display`: kind `Text`, optional, default `None`.

Valid `container` values: a `name` declared in the node's `containers` after inheritance, or the
literal `advanced` (`backend/infrahub/core/constants/__init__.py::ADVANCED_CONTAINER_NAME`).
`None` means the field belongs to the Details section. `details`
(`DETAILS_CONTAINER_NAME`, the name of the frontend `DETAILS_SECTION`) is not a valid value. A field stored before this change has no
`container` value and loads as `None`.

The SDK generator in `tasks/backend.py` gains `container_schema_fields`: `name`, `label`,
`description`, `order_weight` and `collapsed` built with `_field`, and `state` as an explicit
entry that mirrors the attribute-level `state` entry of `definitions/internal.py::attribute_schema`
(`_field` has no `enum_class` parameter and is not extended):

```python
SchemaAttribute(
    name="state",
    kind="Text",
    internal_kind=HashableModelState,
    description="Expected state of the container after loading the schema",
    default_value=HashableModelState.PRESENT,
    enum=HashableModelState.available_types(),
    enum_class="SchemaState",
    optional=True,
    extra={"update": UpdateSupport.NOT_APPLICABLE, "visibility": Visibility.WRITE},
)
```

The generator also gains a `ContainerSchema{suffix}` family next to `DropdownChoice{suffix}` and
the internal counterpart mapping, so `infrahub_sdk.schema.generated` gets `ContainerSchemaRead`,
`ContainerSchemaWrite` and the contract entry.

## Inheritance merge

`backend/infrahub/core/schema/node_inheritance_handler.py::NodeInheritanceHandler.inherit_containers`
runs once per node in `SchemaBranch.process_inheritance`, after the per-generic loop, with the
node's generics in `inherit_from` order. It rebuilds `node.containers` from the node's own
containers (those with `inherited=False`) and the generics' containers:

- The inherited containers come first, in the order each generic lists them, the first generic in
  `inherit_from` first. Each is a copy
  `ContainerSchema(**container.model_dump(exclude={"inherited"}), inherited=True)`.
- The node's own containers follow, in the order the node declares them.
- A node container with the same name as an inherited one replaces it in the inherited one's
  position. It is kept whole; nothing from the generic's container of the same name is merged into
  it (FR-008).
- When two generics declare the same name, the first generic in `inherit_from` provides it and
  the second generic's container of that name is ignored (FR-008).

Because the method ignores the node's existing `inherited=True` copies and rebuilds them from the
generics:

- A generic that drops a container removes it from every node that did not redeclare it on the
  next process; a field still pointing at it then fails validation.
- Processing twice yields the same list (FR-010).
- A node stored before inherited copies were left out of the database, and so loaded with
  `inherited=True` copies, is rebuilt from its generics.
- A node whose `inherit_from` is emptied on a reload loses its `inherited=True` copies on the next
  process and keeps only its own containers.
- `SchemaManager` stores only the containers whose `inherited` is `False`, as it stores only the
  node's own attributes and relationships. The processed node, and so its hash and the schema API,
  carries the inherited copies with their flag. A change on a generic does not rewrite the stored
  `containers` of the nodes that inherit it, so it causes no merge conflict on those nodes.

Field-level `container` on inherited attributes and relationships needs no new code:
`AttributeSchema.update_from_generic` and `RelationshipSchema.update_from_generic` copy every
field except their internal ones, so `container` comes from the generic on each process. A node
that redeclares an inherited field (its name is in `valid_local_names`) keeps its own `container`,
under the existing `allow_override` rules (FR-009).

`SchemaBranch.cleanup_inherited_elements` removes inherited attributes and relationships whose
generic definition is gone; it does not touch node-level lists, which the reset above covers.

## Validation rules

`backend/infrahub/core/validators/schema_branch/container_validator.py::ContainerValidator`,
registered in `SchemaBranch.validators`, runs in `SchemaBranch.process_validate` after
inheritance. For each node and generic, in this order, it raises `ValueError` with exactly:

1. Duplicate name after inheritance:
   `<Kind>.containers: container names must be unique, duplicate '<x>'`
2. Reserved name declared, `details` or `advanced` (`BUILT_IN_CONTAINER_NAMES`):
   `<Kind>.containers: '<name>' is a built-in container and cannot be declared`
3. Reference to a container the node does not have:
   `<Kind>.attributes.<name>.container: container '<x>' is not declared on <Kind>`, and
   `<Kind>.relationships.<name>.container: container '<x>' is not declared on <Kind>`. Fields a
   node inherits are skipped, so a wrong reference on a generic's field names the generic.

A field with `container: details` fails rule 3, since `details` can never be declared.

Accepted without error: `container: advanced` with no declared container of that name; a declared
container that no field references after inheritance; a container without `order_weight`; a
container named like an attribute; a reference that resolves through an inherited container.

`evaluate_candidate_schemas` in `backend/infrahub/api/schema.py` turns the `ValueError` into a
422 `SchemaNotValidError` whose body is in [contracts/schema-api.md](contracts/schema-api.md).

Changing a container or moving a field between containers produces no migration and no constraint
check: all three properties are `UpdateSupport.ALLOWED` (FR-005).

## Profile and object template copy

`SchemaBranch.generate_profile_from_node` and `SchemaBranch.generate_object_template_from_node`
set `containers=[ContainerSchema(**c.model_dump(exclude={"inherited"})) for c in node.containers]`
on the profile and on the template. Attribute copies already carry `container`, and the
relationship copies built field by field in `add_relationships_to_profile` and
`add_relationships_to_template` set `container=relationship.container`, so every reference on a
profile or template resolves. Both generators run inside `process_pre_validation` on every
process, before the validator, so the copies are regenerated whenever the node changes (FR-011).

## Reload merge

`SchemaBranch.load_schema` merges a node loaded again onto the existing node with
`HashableModel.update`. For `containers`, `BaseNodeSchema` replaces the generic list merge by
`_sorting_id` with a merge that keeps the order of the schema file:

- The containers of the incoming list come first, in the order the incoming list gives them.
- A container with a new name takes its place in that order.
- A container with an existing name has its fields overwritten by the payload; a `description`
  or `order_weight` the payload leaves out keeps its previous value.
- A container that replaces an inherited copy (`inherited=True`) is taken whole from the payload:
  a field the payload leaves out is `None` or its default, exactly as on a first load, and the
  node owns the container from then on.
- A container left out of the incoming list stays, after the incoming containers, in its previous
  order relative to the other containers left out (FR-007).
- A container with `state: absent` is removed; a field still referencing it fails validation.
  On a first load, `SchemaBranch.process_containers_state` drops containers with `state: absent`
  before inheritance and validation, so they are not stored, inherited or accepted as a reference.

The `container` of an attribute or relationship follows the rule for optional text properties: a
reload that leaves out `container`, or sets it to `null`, keeps the stored value, and a reload that
sets `container: ""` moves the field back to the Details section.
`SchemaBranch.process_cleared_container_references` turns `""` into `None` before inheritance and
validation, on a reload and on a first load. A container can therefore be removed with
`state: absent` in the same load that sets `container: ""` on its fields.

Other item lists, such as attributes, relationships and dropdown choices, keep the generic merge
by `_sorting_id`.

The schema hash and the schema diff of a node or generic include the order of its container names,
because the generic list hash ignores item order. A reload that only reorders containers is
therefore a schema change: Infrahub writes the new order to the database and other workers load it.
Because `containers` is `ordered=True`, a merge of two branches that reorder the containers of the
same kind differently reports a conflict on `containers` instead of applying one order silently.

Containers and container assignments are stored with the schema and returned unchanged after a
reload, on the default branch and on any other branch (FR-006).

## Frontend section model

`frontend/app/src/entities/nodes/object/domain/model/field-section.ts`:

```typescript
export const DETAILS_SECTION = { name: "details", label: "Details", collapsed: false };
export const ADVANCED_SECTION = { name: "advanced", label: "Advanced", collapsed: true };

export type FieldSection<T> = {
  container: Pick<ContainerSchema, "name" | "label" | "collapsed"> &
    Partial<Pick<ContainerSchema, "description" | "order_weight">>;
  items: T[];
};
```

`ContainerSchema` is `components["schemas"]["ContainerSchemaRead"]` from the generated REST
types, exported from `entities/schema/domain/model/schema.ts`. `DETAILS_SECTION` and
`ADVANCED_SECTION` are never part of a schema's `containers`; the partition rule adds them.

`groupFieldsBySection(containers, items, getContainer)` in
`entities/nodes/object/domain/rules/group-fields-by-section.ts` returns `FieldSection<T>[]`:

1. Details first, with every item whose container is `null`, `undefined` or a name that no
   declared container has (the backend rejects the last case; the rule places it in Details so a
   field is never lost).
2. One section per declared container, containers with an `order_weight` first by ascending
   weight, then containers without a weight in declaration order; items in their input order (the
   caller sorts them by `order_weight`).
3. Advanced last, with the items whose container is `advanced`, `collapsed: true`.
4. Sections with no item are dropped. A schema without containers and without `advanced` fields
   yields one Details section.

The detail view passes items already filtered by the detail view's visibility rules; the form
passes the fields that `getFormFieldsFromSchema` built. Both pass a `getContainer` that reads the
item's `container`.
