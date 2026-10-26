# Data Model: Export the Running Schema

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

No database change. The export reads the processed schema of a branch, which the schema manager holds in
memory, and returns a document. Nothing is stored.

## Schema export document

The response body of `GET /api/schema/export` and the content of the files `infrahubctl schema export`
writes. It is an `InfrahubSchemaWrite` document, the model that `POST /api/schema/load` accepts.

| Field | Type | Rule |
|-------|------|------|
| `version` | string | Always `"1.0"`, the schema file format version (FR-001). |
| `infrahub_version` | string | The Infrahub release that produced the export (FR-010, research R7). New optional field of the write root. The load accepts and ignores it (FR-011). |
| `generics` | list of `GenericSchemaWrite` | User-defined generics of the selected namespaces, sorted by namespace and then name (research R5). |
| `nodes` | list of `NodeSchemaWrite` | User-defined nodes of the selected namespaces, sorted by namespace and then name. |

The root never contains `main`, `namespaces`, `profiles`, `templates` or `extensions`.

### Node and generic

- Fields: the write-model fields (research R2), without `id` and `state`.
- `attributes`: local attributes only (`inherited` false), sorted by `order_weight` and then name.
- `relationships`: local relationships only, without the generated `member_of_groups`,
  `subscriber_of_groups`, `profiles`, `object_template`, `parent` and `children` (research R3), sorted by
  `order_weight` and then name.
- In `BRIEF` mode, the derivable fields of research R1 are left out when processing reproduces them. On a
  node, the properties in FR-007 are kept when a generic in `inherit_from` sets them (research R4).
- `unique: true` is written on the attribute, and the matching single-attribute uniqueness constraint is
  left out (FR-008); `SchemaBranch.sync_uniqueness_constraints_and_unique_attributes` adds it again on load.

### Attribute

- Fields: the `AttributeSchemaWrite` fields, without `id` and `state`.
- `regex`, `min_length`, `max_length` only under `parameters` (FR-009).
- NumberPool `parameters`: without `number_pool_id`. `start_range` and `end_range` are written as stored
  (research R6).

### Relationship

- Fields: the `RelationshipSchemaWrite` fields, without `id` and `state`.
- In `FULL` mode, `identifier`, `branch` and `direction` are written even though Infrahub cannot update
  them (FR-015a, research R10).

## Export mode

`SchemaExportMode`, a string enum in `infrahub.core.constants`:

| Value | Meaning |
|-------|---------|
| `brief` | Default. Leaves out every value that processing reproduces on load (FR-006 to FR-009). |
| `full` | Writes every write-model field of the exported elements, defaults included (FR-015). |

Both modes leave out IDs, `state`, `number_pool_id`, read-only fields, inherited elements, generated
relationships, restricted namespaces and generated profile and template schemas.

## Schema equality used by the tests

Two schemas are equal for FR-012 when their `FULL` exports for the same namespaces are equal, ignoring
`infrahub_version`. This compares every write field of every user-defined element and leaves out IDs,
hashes, inherited and generated elements, which the spec excludes from "identical".

## Export field coverage registry

A test-only map used by the field coverage test (FR-023):

| Key | Value |
|-----|-------|
| `(model, field)` for each field of `NodeSchemaWrite`, `GenericSchemaWrite`, `AttributeSchemaWrite`, `RelationshipSchemaWrite` and the attribute parameter write models | the name of the test schema that sets the field to a non-default value, or a reason why no test is needed (for example `id`: "never exported") |

A field missing from the map fails the test.
