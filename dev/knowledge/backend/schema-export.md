# Schema Export

> Part of: `dev/knowledge/backend/` | Related: [code-generation.md](code-generation.md), [display-labels-and-hfid.md](display-labels-and-hfid.md), [ADR 0010](../../adr/0010-generated-user-facing-schema-contract.md)

`GET /api/schema/export` returns the user-defined nodes and generics of a branch as one `InfrahubSchemaWrite`
document that `POST /api/schema/load` accepts without editing. Read this before changing schema processing,
adding a schema field, or changing what the export writes.

## Components

All in `backend/infrahub/core/schema/export/`, built by `exporter.py::build_schema_exporter` in the API handler.

| Component | Job |
|-----------|-----|
| `SchemaExportSerializer` | Writes every value of the user-defined elements (the `full` mode) |
| `BriefSchemaMinimizer` | Removes the values processing gives back (the `brief` mode) |
| `SchemaExporter` | Entry point: picks the namespaces, runs both, validates the result against `InfrahubSchemaWrite` |

The export runs in a thread (`run_in_threadpool`), because processing takes about a second per pass on
`models/base/`.

## What the serializer writes

- **Fields**: the fields of the SDK write models, which `tasks/backend.py` generates from each field's
  `visibility` (ADR 0010). A field added with `Visibility.WRITE` is exported without a change here.
  `id`, `state`, NumberPool `number_pool_id` and the deprecated top-level `regex`, `min_length`, `max_length`
  are left out; processing keeps those three in sync with `parameters`.
- **Elements**: user-defined only. Left out: restricted namespaces, kinds present in an empty instance
  (`build_base_schema_branch().all_names`, which includes core models in non-restricted namespaces such as
  `IpamNamespace`), inherited attributes and relationships, and generated relationships, recognised by name,
  kind and identifier together (`GENERATED_RELATIONSHIPS`, `VIRTUAL_RELATIONSHIPS`).
- **Order**: generics and nodes by namespace and name; attributes and relationships by `order_weight` and name.
- **Two normalisations**, so an in-memory schema and one read from the database export the same document:
  - `include_in_menu` unset is written as `true`: the database stores an unset value as `true`.
  - A deprecated `default_filter` or `display_labels` equal to the value of the first generic in
    `inherit_from` that sets it is left out: processing copies it back, and writing it adds a deprecation
    warning per node.

## How brief decides what to leave out

Derived values depend on order and on each other (dropdown colours, a human-friendly ID taken from the first
unique attribute, `order_weight` from the position), so no per-field rule reproduces them. The minimizer
removes, processes, and writes back:

1. Plan a reduction for each removable value. A value is removable when it equals the write-model default,
   when a local rule predicts it (`_PREDICTED_FIELDS`, such as a label from the name or `min_count` from
   `cardinality` and `optional`), or when processing decides it (`_SIMULATED_FIELDS`).
2. Build the candidate without those values, load it into a new base branch (internal, core and deprecated
   models) together with the `full` documents of the other user namespaces, and call `SchemaBranch.process`.
3. Serialize the result and compare it with the `full` document. Write back each value that differs, and
   repeat until nothing differs. Each pass only writes values back, so the loop ends.

Three refinements keep the loop correct:

- **Local rules before removal**: a value that processing would derive differently can change what the
  schema means (an `optional: false` relationship becoming optional fails HFID validation). Fields whose
  derived value depends only on their element are removed only when the rule predicts the stored value.
- **Dependencies**: `uniqueness_constraints` is written back only after `human_friendly_id`, which it
  derives from, stops differing.
- **Fallback**: if the candidate fails to process, every simulated reduction is written back once and the
  loop continues with the reductions that keep the meaning.

On a node, a property that a generic in `inherit_from` sets is never removed: Infrahub copies it only when
the node has none and does not record which happened, so the export writes it.

## When you change schema processing or add a field

- A new write field fails `backend/tests/unit/core/schema/export/test_field_coverage.py` until a schema in
  `backend/tests/unit/core/schema/export/schemas/` (or a listed fixture) sets it, or it is listed in
  `NOT_TESTED` with the reason.
- A new derived value needs no change when processing reproduces it from the remaining input; the round
  trip tests in `test_round_trip.py` show whether it does. If the derived value can change the meaning of
  the schema when it differs, add a local rule to `_PREDICTED_FIELDS`.
- A new value that the database stores differently from the in-memory model needs a normalisation in the
  serializer, as `include_in_menu` has; the functional tests in
  `backend/tests/functional/api/test_schema_export.py` catch the difference.
