# Data Model: Schema-defined field sections

The backend container model, the three schema properties, their inheritance, validation, copy and
reload rules, and the frontend section model. No graph migration: the properties are added to the
internal schema definitions and stored with the schema of each branch.

## ContainerSchema

`backend/infrahub/core/schema/container.py::ContainerSchema`, a `HashableModel` like
`backend/infrahub/core/schema/dropdown.py::DropdownChoice`.

| Field | Type | Default | Rule |
|---|---|---|---|
| `name` | `str` | required | `NAME_REGEX`, `DEFAULT_NAME_MIN_LENGTH` to `DEFAULT_NAME_MAX_LENGTH` characters; unique among the containers a kind declares; never `details` |
| `label` | `str` | required | Section title |
| `description` | `str \| None` | `None` | Muted text under the title |
| `order_weight` | `int \| None` | `None` | Lowest first; containers without a weight follow, in declaration order; the backend does not fill it |
| `collapsed` | `bool` | `False` | The detail card starts collapsed; the form ignores it |
| `state` | `HashableModelState` | `present` | Inherited from `HashableModel`; `absent` removes the item on reload |
| `inherited` | `bool` | `False` | `True` on a copy taken from a generic; read-only in the write contract |

- `_sort_by = ["name"]`, so the name identifies the item in a diff.
- Name format and required fields are Pydantic constraints; uniqueness and the reserved name are
  validator rules (below).
- A container name and an attribute name are separate namespaces.

## Schema properties

All three are `SchemaAttribute` entries in `backend/infrahub/core/schema/definitions/internal.py`
with `UpdateSupport.ALLOWED` and `Visibility.WRITE`, so a change needs no migration and no
constraint check (FR-005).

- `containers` on `base_node_schema` (nodes, generics, profiles, templates): kind `List`,
  `internal_kind=ContainerSchema`, `ordered=True`, empty list by default. `ordered=True` makes the
  branch diff compare the list in order, so two branches that reorder the same containers
  differently conflict on merge. `BaseNodeSchema` turns a missing stored value into an empty list,
  so a schema stored before this change loads without a migration. `ContainerSchema` is added to
  the `fixed_types` map of `SchemaAttribute` and to `backend/templates/basenodeschema_imports.j2`
  for the generated `base_node_schema.py`.
- `container` on `attribute_schema` and on `relationship_schema`: kind `Text`, optional, `None` by
  default.

Valid `container` values: a container of the kind after inheritance. `None` means the Details
section. `details` (`DETAILS_CONTAINER_NAME` in `backend/infrahub/core/constants/__init__.py`) is
not valid. `advanced` is valid only when the kind declares or inherits a container of that name.

The SDK generator in `tasks/backend.py` lists `container_schema_fields`: `name`, `label`,
`description`, `order_weight`, `collapsed`, `state` (`Visibility.WRITE`, enum class `SchemaState`,
so `state: absent` works on a load) and `inherited` (`Visibility.READ`). It produces
`ContainerSchemaRead`, which carries `inherited`, and `ContainerSchemaWrite`, which does not; a
load that sends `inherited` gets the warning
`'containers.inherited' is a read-only field, the submitted value is ignored`.

## Inheritance merge

`backend/infrahub/core/schema/node_inheritance_handler.py::NodeInheritanceHandler.inherit_containers`
runs once per node in `SchemaBranch.process_inheritance`, after the per-generic loop. It rebuilds
`node.containers` from the node's own containers (`inherited=False`) and the generics' containers:

- Inherited containers come first, in the order each generic lists them, the first generic in
  `inherit_from` first. Each is a `model_copy` with `inherited=True`.
- When two generics declare the same name, the first generic provides it.
- A node container with the same name as an inherited one replaces it whole, in the inherited
  one's position.
- The node's other containers follow in declaration order.

Because the existing `inherited=True` copies are discarded and rebuilt from the generics:

- A generic that drops a container removes it from every node that did not redeclare it; a field
  that still references it fails validation.
- Processing twice yields the same list (FR-010).
- A node whose `inherit_from` is emptied keeps only its own containers.

`SchemaManager` stores only the containers with `inherited=False`
(`SchemaManager._dump_node_properties`), as it stores only a node's own attributes and
relationships. A change on a generic therefore does not rewrite the stored `containers` of the
nodes that inherit it. The processed node, its hash and the schema API carry the inherited copies.

Field-level `container` needs no new code: `update_from_generic` copies it to inherited
attributes and relationships. A node that redeclares an inherited field keeps its own
`container`, under the existing `allow_override` rules (FR-009).

## Validation rules

`backend/infrahub/core/validators/schema_branch/container_validator.py::ContainerValidator` is
registered in `SchemaBranch.validators` and runs in `SchemaBranch.process_validate`, after
inheritance. For each node and generic, in this order, it raises `ValueError` with:

1. A name declared twice among the kind's own containers:
   `<Kind>.containers: container names must be unique, duplicate '<x>'`
2. A declared container named `details` (`DETAILS_CONTAINER_NAME`):
   `<Kind>.containers: 'details' is a built-in container and cannot be declared`
3. A field that references a container the kind does not have:
   `<Kind>.attributes.<name>.container: container '<x>' is not declared on <Kind>`, or the same with
   `relationships`. Inherited fields are skipped, so a wrong reference on a generic's field names
   the generic. `container: details` fails this rule, and so does `container: advanced` on a kind
   without a container of that name.

`evaluate_candidate_schemas` in `backend/infrahub/api/schema.py` turns the `ValueError` into a
422; the bodies are in [contracts/schema-api.md](contracts/schema-api.md).

## Profile and object template copy

`SchemaBranch.generate_profile_from_node` and `SchemaBranch.generate_object_template_from_node`
copy `node.containers` without the `inherited` flag (`SchemaBranch._copy_containers`). Attribute
copies already carry `container`; `add_relationships_to_profile` and
`add_relationships_to_template` set `container=relationship.container`. Both generators run in
`process_pre_validation` on every process, before the validator, so the copies follow the node
(FR-011).

## Reload merge

`SchemaBranch.load_schema` merges a reloaded node onto the stored one with `HashableModel.update`.
For `containers`, `BaseNodeSchema._merge_containers` keeps the order of the schema file:

- The incoming containers come first, in the incoming order.
- An incoming container with an existing name updates the stored one; a `description` or
  `order_weight` the payload leaves out keeps its previous value.
- An incoming container that replaces an inherited copy is taken whole from the payload.
- A container with `state: absent` is removed.
- Stored containers left out of the incoming list follow, in their previous order (FR-007).

On every process, `SchemaBranch.process_containers_state` drops containers with `state: absent`
before inheritance and validation, so they are not stored, inherited or accepted as a reference.

The `container` of a field follows the rule for optional text properties: a reload that leaves it
out, or sends `null`, keeps the stored value. `SchemaBranch.process_cleared_container_references`
turns `container: ""` into `None` before inheritance and validation, so one load can remove a
container with `state: absent` and clear the references to it.

The node hash and the node diff include the order of the container names, because the generic list
hash ignores item order. A reload that only reorders containers is therefore a schema change.

## Frontend section model

`frontend/app/src/entities/nodes/object/domain/model/field-section.ts`:

```typescript
export const DETAILS_SECTION = { name: "details", label: "Details", collapsed: false } as const;

export type FieldSection<T> = {
  container: Pick<ContainerSchema, "name" | "label" | "collapsed"> &
    Partial<Pick<ContainerSchema, "description" | "order_weight">>;
  items: T[];
};
```

`ContainerSchema` is the generated `ContainerSchemaRead` REST type, exported from
`entities/schema/domain/model/schema.ts`.

`groupFieldsBySection(containers, items, getContainer)` in
`entities/nodes/object/domain/rules/group-fields-by-section.ts` returns `FieldSection<T>[]`:

1. Details first, with every item whose container is unset or names no declared container (the
   backend rejects the second case; the rule keeps the field visible).
2. One section per declared container: containers with an `order_weight` by ascending weight, then
   the others in declaration order. A declared container named `details` is ignored. Items keep
   their input order; callers sort them by `order_weight`.
3. Sections without an item are dropped.

The rule does not filter or sort items. The detail view passes the fields its visibility rules
show; the form passes the fields `getFormFieldsFromSchema` built.
