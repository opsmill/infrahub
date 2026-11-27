# Schema Export

> Part of: `dev/knowledge/backend/` | Related: [schema-definitions.md](schema-definitions.md),
> [code-generation.md](code-generation.md), [display-labels-and-hfid.md](display-labels-and-hfid.md)

How `GET /api/schema/export` builds a schema file from the stored schema of a branch, and why its output
looks the way it does. The user documentation is `docs/docs/schema/export.mdx`.

The endpoint is `backend/infrahub/api/schema.py::export_schema`. The work is in
`backend/infrahub/schema/export/exporter.py::SchemaExporter`, and the response model is
`backend/infrahub/schema/export/models.py::SchemaExportDocument`, a subclass of the SDK
`InfrahubSchemaWrite`, so a document that validates as a response also validates as a load payload.

## The route runs the export in a thread

A `BRIEF` export processes the schema twice or more, about 2 to 3 seconds of CPU for `models/base/`. The
route runs it with `asyncio.to_thread`, so the API worker keeps answering other requests. The thread reads
`SchemaBranch.duplicate_with_own_cache()` of the registry's branch schema, taken on the event loop. A copy made
with `duplicate()` would share the registry's cache dict, and `SchemaManager.purge_inactive_branches` deletes
the hashes no active branch uses from that dict when a schema change reaches this worker, so a running export
could no longer read a kind it started with.

The processed core schema is built once per process (`exporter.py::copy_core_schema_baseline`), and each pass
loads into `SchemaBranch.duplicate_with_own_cache()` of it, which takes about 1 ms instead of about 0.6 s for
a new build. The copy shares the cached schema objects, because processing replaces an object it changes
rather than changing it in place, but it has its own cache dict and kind lists, so a pass never adds to the
shared schema. `SchemaBranch.duplicate()` would share the cache dict, and every export would grow it.

## A namespace the export cannot select returns 404

`SchemaExporter.export` checks `namespaces` before any work and raises
`backend/infrahub/exceptions.py::SchemaNamespaceNotFoundError` (HTTP 404) for each namespace that does not
exist on the branch or is restricted. Each error names its namespace in `extensions.namespace`, through
`Error.error_extensions`. Infrahub's catch-all route answers an unknown `/api` URL with a 404 in the same
envelope (`backend/infrahub/api/__init__.py::not_found`), so clients recognize the namespace error by that
field, not by the status or the message. A namespace that exists but holds only kinds Infrahub defines, such
as `Ipam` on an instance with no user kinds in it, returns an empty document.

## A field's visibility decides whether the export can write it

The export writes only the fields of the generated SDK write models (`NodeSchemaWrite`,
`GenericSchemaWrite`, the `AttributeSchemaWrite` union, `RelationshipSchemaWrite` and the
attribute-parameter write models in `infrahub_sdk/schema/generated/write.py`). The exporter validates a
`model_dump()` of each stored element against its write model, and the write models ignore extra fields.

The write models are generated from the schema definitions: a field is in them when its definition has
`Visibility.WRITE` (`backend/infrahub/core/constants/schema.py::Visibility`). So:

- A new field with `WRITE` visibility reaches the export with no change to the exporter.
- A field that belongs to the source instance only, such as `parameters.number_pool_id`, gets `READ`
  visibility. Do not add an export rule to leave it out.

On top of that, both modes remove:

- `id` on every element.
- Nodes and generics in `RESTRICTED_NAMESPACES`, which also removes profile and template schemas.
- Nodes and generics whose kind the core schema definitions define (`internal_schema`, `core_models`,
  `deprecated_models`), whatever their namespace: `exporter.py::CORE_SCHEMA_KINDS`. Today this adds
  `IpamNamespace`, which is in the unrestricted `Ipam` namespace. The set is read from the definitions, so a
  kind Infrahub adds later in an unrestricted namespace is left out too. A change or an extension the
  schema owner made to one of these kinds is not exported, with no warning.
- Attributes and relationships with `inherited: true` on a node. They are written on the generic only.
- The six relationships processing adds, identified by kind, name and identifier:
  `exporter.py::GENERATED_RELATIONSHIPS`. A relationship the schema owner defined with kind `Group`,
  `Profile`, `Hierarchy` or `Template` but another name or identifier is exported. A unit test fails when
  processing adds a relationship of these kinds that the set does not hold. The schema does not record
  whether processing added a relationship, so the set is kept by hand.

Deprecated forms are converted, not removed, by `exporter.py::convert_deprecated_attribute_fields`: top-level
`regex`, `min_length` and `max_length` move under `parameters` when the parameters model of the kind has the
field (Text and TextArea have all three, List has only `regex`, so List keeps top-level `min_length` and
`max_length`), and NumberPool `start_range` and `end_range` become one `ranges` entry.

Attributes and relationships are written sorted by `order_weight`, then by name, because a schema read back
from the database does not keep the order in which they were loaded. Nodes and generics are sorted by kind.

## How `BRIEF` decides which values to leave out

`FULL` is the document described above. `BRIEF` starts from it and leaves out every value that processing
produces again on load. It does not use a list of derived fields; it asks processing
(`SchemaExporter._reduce`):

1. Build a candidate from the `FULL` document with every optional field removed, except the fields a node
   takes from its generic (see the last section), the fields marked `keep_in_export`, and the attribute and
   relationship lists.
2. Load the candidate into a copy of the core-only schema, the schema of an empty instance
   (`copy_core_schema_baseline` in the route), and run `SchemaBranch.process`, as a schema load does. When
   processing raises `ValueError`, `ValidationError`, `SchemaNotFoundError` or `AttributePathParsingError`, the
   export returns the `FULL` document and logs a warning.
3. Compare every write-visible field of each processed element with the stored element, both normalized
   by `normalize_element_for_comparison` (IDs dropped, deprecated forms converted).
4. Copy each differing field that the candidate does not hold back from the `FULL` document.
5. Repeat from step 2 while the previous pass copied at least one field back.

The candidate is a dict at every step, so the final document's set fields are the keys the loop kept. The
route serializes with `response_model_exclude_unset=True` and the SDK writes files with
`model_dump(exclude_unset=True)`; without that, every write-model default would come back.

The loop never makes the endpoint fail:

- When processing a candidate raises `ValueError` or `ValidationError`, the exporter logs the warning
  `A schema export candidate failed validation, the export holds every value instead` with the branch and the
  error, and returns the `FULL` document.
- When differences remain that writing more values cannot remove (the candidate already holds the `FULL`
  value of each), the exporter returns the candidate and logs the warning
  `The schema export loads to values that differ from the stored schema` with each kind, element and field.
  This happens when the stored schema is not what current processing produces, for example a schema stored
  by an earlier release.

### Finding out why a value is or is not in a `BRIEF` export

A value is in a `BRIEF` export only when the loop put it back, or when step 1 kept it. Run the export with
`INFRAHUB_LOG_LEVEL=DEBUG`:

- `Schema export put back a value that processing changes` is logged once per field put back, with `kind`,
  `element` (the attribute or relationship name, `None` for a field of the node itself) and `field` (an attribute parameter
  is `parameters.<name>`).
- `Schema export built` gives the branch, mode, number of passes and duration.

A value that is absent and not in the debug log is one processing derived to the same value.

### `BRIEF` output follows schema processing

Because the loop asks processing, the `BRIEF` output of the same stored schema can change between releases
with no change to the exporter, for example when processing starts deriving a value it did not derive
before. The export still loads to the same schema. Do not treat a text difference between two exports made
on different releases as a defect on its own.

## Fields kept unless they hold their default: `keep_in_export`

A candidate without some optional fields fails validation, which sends the export to the `FULL` fallback.
This holds for fields processing never sets, such as `inherit_from`, and for fields it derives, such as a
relationship `identifier` (`SchemaBranch.generate_identifiers`) or an attribute `unique` (set from
`uniqueness_constraints`). Without `inherit_from`, a `human_friendly_id` that names an inherited relationship
no longer validates. These fields are marked in the schema definitions, next to
`visibility`, with `"keep_in_export": True` in the `extra` of the field
(`backend/infrahub/core/schema/definitions/internal.py::ExtraField`). The mark never reaches the database.

| Element | Marked fields |
|---------|---------------|
| Node | `inherit_from` |
| Attribute | `read_only`, `choices`, `unique` |
| Relationship | `identifier`, `cardinality`, `optional` |

The fields other than `inherit_from` were marked because a `BRIEF` export of `models/base/` reached the
fallback without them. A marked field is still removed when its value equals the write-model default,
because a load sets the same default (`exporter.py::_removable_fields`). Stored relationship identifiers are
never empty, so `BRIEF` writes every relationship `identifier`.

`uv run invoke backend.generate` writes the marked fields into `KEEP_IN_EXPORT_FIELDS` in
`python_sdk/infrahub_sdk/schema/generated/contract.py`, keyed by write model name, and the exporter reads that
constant. To mark a field, set the key in `internal.py` and regenerate; never add a list of fields to the
exporter.

A field that needs the mark and does not have it shows in CI as a failure of
`backend/tests/unit/schema/export/test_brief_mode.py::test_brief_export_loads_to_the_same_schema_without_the_fallback`,
which asserts that the export of each variation schema logs no fallback or difference warning. A new write
field cannot skip that test: `backend/tests/unit/schema/export/test_field_coverage.py` fails until a variation
schema in `backend/tests/helpers/schema/export_variations.py` sets the field, or the field's table entry
records why none is needed.

## A derived value can be written next to its source

Accept a `BRIEF` export that writes a derived value next to its source; do not add a second removal pass.
Step 1 removes a derived value and the value it is derived from together. After processing, both differ, so
both are put back, and the loop does not try to remove them again. Example: an attribute loaded with
`default_value: active` and no `optional` is stored with `optional: true`, which processing derives from the
default value, and `BRIEF` writes both. The export still loads to the same schema, because every value it
writes is the stored value, but it can be longer than the files the schema owner wrote. Removing the pair
again would cost one processing per attempt, and the order of the attempts would decide which value of the
pair stays.

A derived value whose source is marked `keep_in_export` is not in this case. `unique` is marked, so the
candidate keeps `unique: true`, processing derives the `human_friendly_id` and `uniqueness_constraints` again,
and `BRIEF` leaves them out.

## Properties a node keeps from its generic

Processing copies a fixed set of node properties from the first generic in `inherit_from` that sets them, to
a node that has no value of its own. The set is
`backend/infrahub/core/schema/node_inheritance_handler.py::PROPERTIES_INHERITED_FROM_GENERIC`, which both the
inheritance handler and the exporter read:

- `human_friendly_id`
- `display_label`
- `display_labels`
- `default_filter`
- `menu_placement`
- `uniqueness_constraints`
- `icon`
- `order_by`

The stored schema cannot tell a value the node took from its generic from the same value written on the node.
So on a node with `inherit_from`, `BRIEF` keeps each of these properties whose value equals the stored value of
the first generic that sets it (`SchemaExporter._pinned_properties`). A property whose value differs from the
generic's, for example `uniqueness_constraints` that processing extended with the node's own unique attribute,
goes through the loop like any other field. A property added to the constant is kept with no change to the
exporter.

Consequence: a load of the export also writes the deprecated `display_labels` and `default_filter` on each
node that took them from a generic, so the load gives a deprecation warning for each of those nodes.
