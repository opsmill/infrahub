# Data model: stored schema changes

The four records are frozen dataclasses in `backend/infrahub/core/schema_change/models.py`. The
class name is the Neo4j label. Each record has a `uuid`, a time-ordered UUID that the repository
generates and that is the ID of the record, and `created_at`; the schema change and the
application also have `created_by`, `updated_at` and `updated_by`, the operation `created_by`, and
the migration record `updated_at`. `record_serializer.py::SchemaChangeRecordSerializer` turns a
record into the properties that a query writes, and the properties that a query returns back into
a record ([research.md](research.md), R1).

The records are not versioned by branch. Their edges have no `branch` property, and no record has
an edge to `Root` ([research.md](research.md), R2). Three indexes cover the lookups: `SchemaChange`
by `uuid` and by `branch`, and `SchemaChangeApplication` by `uuid` ([research.md](research.md),
R3).

```text
(SchemaChange)-[:SCHEMA_CHANGE_HAS_OPERATION]->(SchemaChangeOperation)
(SchemaChange)-[:SCHEMA_CHANGE_HAS_APPLICATION]->(SchemaChangeApplication)
(SchemaChange)-[:SCHEMA_CHANGE_HAS_PARENT]->(SchemaChange)
(SchemaChangeApplication)-[:SCHEMA_APPLICATION_HAS_MIGRATION]->(SchemaChangeMigration)
```

## SchemaChange

One schema load, or one dropdown or enum mutation, that changed the schema of a branch.

| Field | Type | Notes |
| --- | --- | --- |
| `branch` | `str` | Name of the branch the schema change belongs to |
| `status` | `SchemaChangeStatus` | `staged`, `running`, `applied`, `failed` |
| `version` | `int \| None` | Set when the status becomes `applied`. Unique among the applied schema changes of one branch |
| `summary` | `str` | From the first operation, with a count when there are more ([research.md](research.md), R10) |
| `format_version` | `int` | Version of the operation format. `1` in this feature |
| `applied_at` | `str \| None` | Timestamp of the graph writes of the application that applied it. Set when the status becomes `applied` |

Derived, not stored:

- `name`: `<version, five digits>_<summary>`, or `summary` when `version` is `None`.

Rules:

- `applied_at` is not the time the load ended. It is the timestamp at which the schema was written
  to the branch, so a branch whose `branched_from` is at or after it started from a schema that
  holds this schema change.
- Timestamps are stored as text in the format of `Timestamp.to_string()`, which is the format of
  `Branch.branched_from`, so the two can be compared in a query.
- A schema change always has at least one operation (FR-003).
- `version` is `None` unless `status` is `applied` (FR-032).
- A schema change has at most one parent, and only when its status is `applied`. The parent is an
  applied schema change of the same branch, or of main for the first schema change of a branch
  (FR-034).
- `branch` never changes.

Status transitions in this feature:

```text
schema load:             (created) running ──► applied
                                          └──► failed
dropdown/enum mutation:  (created) applied
```

No code of this feature sets `staged`. The staging task of the same epic creates it. A `failed`
schema change is never applied again.

## SchemaChangeOperation

One change to the schema. The operations of a schema change apply in the order of `position`.

| Field | Type | Notes |
| --- | --- | --- |
| `position` | `int` | Starts at 0. Unique within one schema change |
| `operation_type` | `SchemaOperationType` | `node_add`, `node_remove`, `node_rename`, `node_property`, `element_add`, `element_remove`, `element_property` |
| `kind` | `str` | Kind of the node or generic. For a renamed kind, the kind before the operation |
| `node_type` | `SchemaOperationNodeType \| None` | `node` or `generic`. Set for `node_add` |
| `section` | `SchemaOperationSection \| None` | `attributes` or `relationships`. Set for the three element types |
| `element_name` | `str \| None` | Name of the attribute or relationship before the operation. Set for the three element types |
| `property_name` | `str \| None` | Name of the property, dotted when nested. Set for the two property types |
| `value` | JSON, stored as a string | New value for a property type; full definition for an add type. An added attribute or relationship also holds the `order_weight` that processing gave it when the file sets none ([research.md](research.md), R4) |
| `previous_value` | JSON, stored as a string | Value before the change. Set for the two property types |

Rules:

- No field holds a vertex ID. `value` for an add type has no `id` and no
  `parameters.number_pool_id` (FR-012, FR-014).
- `value` and `previous_value` are JSON so that a list, a mapping, a boolean and `null` keep their
  type. `null` as a value is different from a field that is not set.
- Both fields are always JSON-encoded text when set. A field that is not set is a property that
  is not stored, so the JSON value `null` is stored as `null`, a text value as text inside quotes,
  and the text `NULL` stays text.
- A dropdown or enum mutation stores one `element_property` operation on `choices` or `enum`,
  with the whole list in `value` and the whole list before the change in `previous_value`. Each
  dropdown choice holds every field of the choice model, including `id`, which is always `null`,
  and `state`. The choice that the mutation adds holds the fields as the mutation input gives them,
  so its `color` and `description` can be `null` where the saved schema has a value.

The in-memory form is `SchemaOperation`, a Pydantic model in
`backend/infrahub/core/schema_change/operations.py`. The builder creates it, the applier reads it,
the serializer converts it to `SchemaChangeOperation` for the repository, and back for the history
reader.

## SchemaChangeApplication

One time a schema change was applied to a branch.

| Field | Type | Notes |
| --- | --- | --- |
| `branch` | `str` | Name of the branch the schema change was applied to. Equal to the schema change's branch in this feature |
| `status` | `SchemaChangeApplicationStatus` | `running`, `applied`, `failed`, `rolled_back`, `skipped` |
| `at` | `str` | Timestamp of every graph write of this application |
| `error` | `str \| None` | Set when the status is `failed` |

Status transitions in this feature:

```text
schema load:             (created) running ──► applied
                                          └──► failed
dropdown/enum mutation:  (created) applied
```

No code of this feature sets `rolled_back` or `skipped` on an application. The task that applies
schema changes in order at rebase and merge sets them. The source design writes the first one
`rolled back`; the stored value has an underscore.

## SchemaChangeMigration

One migration that an application ran.

| Field | Type | Notes |
| --- | --- | --- |
| `position` | `int` | Index of the migration in the migrations of the application sorted by schema path, then by migration name, so it is the same each time a load runs ([research.md](research.md), R9) |
| `migration_name` | `str` | For example `node.attribute.add` |
| `path_type` | `SchemaPathType` | `node`, `attribute` or `relationship`. The existing enum in `core/constants`, which `core/path.py::SchemaPath.path_type` uses |
| `schema_kind` | `str` | Kind in the schema path |
| `field_name` | `str \| None` | Attribute or relationship in the schema path |
| `property_name` | `str \| None` | Property in the schema path |
| `status` | `SchemaChangeMigrationStatus` | `waiting`, `running`, `applied`, `failed`, `rolled_back`, `cancelled` |
| `nbr_migrations_executed` | `int \| None` | Result that the migration returned. Stored, and not returned by the history query |
| `errors` | `list[str]` | Errors that the migration returned |

- The path is stored as its parts, without `schema_id`, which is a vertex ID. The query also
  returns the text form that `core/path.py::SchemaPath.get_path` builds.
- The time of the record is `updated_at`, the time of its last status change.
- A record is identified inside its application by `position`, because two migrations of one
  application can have the same name and the same path.

Status transitions in this feature:

```text
(created) waiting ──► running ──► applied ──► rolled_back   (the load failed later)
   │                     │   └──► failed
   │                     └──► failed, with the error of the load   (the load failed while it ran)
   └──► cancelled   (the load failed before the migration started)
```

`mark_failed` closes the records of a failed load in one statement: `applied` becomes
`rolled_back`, `waiting` becomes `cancelled`, `running` becomes `failed` with the error of the load
added to its errors, and `failed` stays. `mark_failed_if_running`, for a cancelled load, leaves
the records as they are, because the migrations keep running and write their own statuses (spec,
decision 11).

`running` means that the task of the migration started. The records report progress and are best
effort: a record whose write fails after the retries keeps its earlier status, also when the load
succeeds.

## What the repository and the history reader offer

`SchemaChangeRepository(db, serializer)` in `backend/infrahub/core/schema_change/repository.py`,
with its `Query` classes, for the recorder, the version resolver, the migration recorder and the
branch deletion:

| Method | Purpose |
| --- | --- |
| Create a schema change with its operations and one application | The start of a load, and a mutation |
| Create the migration records of an application | The migration flow, in one query |
| Set the status of the migration records of an application by position | The migration flow, when a migration starts and when it returns |
| Mark a schema change and its application applied, with version, parent and time | The end of a load |
| Mark a schema change and its application failed, with the error, and close its migration records | The end of a failed load |
| Mark a running schema change and its application failed, with the error, and leave its migration records | The end of a cancelled load |
| Get the highest applied version of a branch, and the highest version of main applied at or before a timestamp, each with the ID of its schema change | `SchemaChangeVersionResolver` ([research.md](research.md), R10) |
| Delete the schema changes of a branch with all their records | `BranchDataDeleter` ([research.md](research.md), R13) |

`SchemaChangeHistoryReader(db, serializer)` in `backend/infrahub/core/schema_change/history_reader.py`, for
the history query:

| Method | Purpose |
| --- | --- |
| List the schema changes of a branch in pages, and count them | The page of the query |
| Count the schema changes of a branch, without reading a page | The query when it selects `count` and not `edges` |
| List operations in pages for a set of schema changes, with their counts | The operations loader |
| List applications in pages for a set of schema changes, with their counts | The applications loader |
| List migration records in pages for a set of applications, with their counts | The migrations loader |

Each read returns a typed result built by its `Query` class. No method returns a raw database
record. Both classes convert records with `SchemaChangeRecordSerializer`.

## Enumerations and constants

In `backend/infrahub/core/schema_change/enums.py`:

- `SchemaChangeStatus`, `SchemaChangeApplicationStatus`, `SchemaChangeMigrationStatus`,
  `SchemaOperationType`, `SchemaOperationNodeType`, `SchemaOperationSection`;
- `SchemaChangeEdgeType`, the four edge type names.

In `backend/infrahub/core/schema_change/constants.py`:

- the operation format version, `1`;
- the number of digits of the version in a name, `5`;
- the page sizes of the history query ([research.md](research.md), R12).
