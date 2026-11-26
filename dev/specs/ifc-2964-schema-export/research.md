# Research: Export the running schema

Decisions D1 to D13 come from the approved [design document](https://app.notion.com/p/401228b83025812589c6e6664594db35) and are not reopened here. This file records the implementation choices the design document leaves to the plan. Each entry gives the decision, the reason and the alternatives considered.

## R1. Which fields a schema file can carry

**Decision**: the export writes only the fields of the generated SDK write models (`NodeSchemaWrite`, `GenericSchemaWrite`, `AttributeSchemaWrite`, `RelationshipSchemaWrite` and the attribute-parameter write models in `infrahub_sdk/schema/generated/write.py`). The exporter builds each element by validating the stored element's dump against its write model, which drops every field the write model does not have, because the write models use `extra="ignore"`. `AttributeSchemaWrite` is an `Annotated` union of five attribute models that Pydantic selects by `kind`, so an attribute is validated with `TypeAdapter(AttributeSchemaWrite)`.

**Rationale**: the write models are generated from the schema definitions, using the `visibility` of each field (`backend/infrahub/core/constants/schema.py::Visibility`, `WRITE` level). They are what `POST /api/schema/load` and `infrahubctl schema load` validate against (`backend/infrahub/api/schema.py::SchemaLoadAPI`, `infrahub_sdk/schema/validate.py::validate_schema`). A field added to the schema definitions with `WRITE` visibility reaches the export with no change to the exporter.

**Alternatives considered**:

- Dumping the internal models and removing a hand-maintained list of fields. This is the current SDK approach (`infrahub_sdk/schema/export.py::_SCHEMA_EXPORT_EXCLUDE`) and the source of the drift.
- Using the read models and removing read-only fields. Same problem, from the other side.

## R2. What the export leaves out in both modes

**Decision**: after R1, the exporter removes:

- `id` on every element. The write models have it because a load uses it to detect renames, but IDs match nothing on another instance (D6).
- Nodes and generics whose namespace is in `backend/infrahub/core/constants/__init__.py::RESTRICTED_NAMESPACES`. This removes profile and template schemas too, because their namespaces are restricted.
- Nodes and generics whose kind the core schema definitions define (`core_models`, `deprecated_models` and `internal_schema`, the definitions the baseline in R4 loads), whatever their namespace. Today this adds one kind, `IpamNamespace`, which Infrahub defines in the `Ipam` namespace, which is not restricted (`backend/infrahub/core/schema/definitions/core/ipam.py`). The set is read from the definitions, not kept as a list, so a kind Infrahub adds later in an unrestricted namespace is left out with no change to the exporter. The exporter reads the kinds from the definitions without processing them, so `FULL` mode needs no baseline.
- Attributes and relationships with `inherited: true` (FR-004).
- Relationships of kind `Group`, `Profile`, `Hierarchy` and `Template` (`backend/infrahub/core/constants/__init__.py::RelationshipKind`), which processing generates (`SchemaBranch.add_groups`, `manage_profile_relationships`, `manage_object_template_relationships`, `add_hierarchy_node`).

The deprecated forms of validation settings and NumberPool ranges are not removed but converted, as listed in [data-model.md](data-model.md#conversions) (D5, FR-008, FR-009).

A field that belongs to the source instance only, such as `parameters.number_pool_id` (the ID of the provisioned pool), is not in this list because its definition already has `Visibility.READ` (`tasks/backend.py`), so R1 never writes it. A new field of that sort is handled the same way: by its visibility, not by an export rule.

**Rationale**: FR-003 and FR-004. The kind list replaces `_AUTO_GENERATED_REL_KINDS` in the SDK and adds `Template`, whose absence today keeps `object_template` in the export (design document, section 2). The round-trip tests in R8 fail if processing generates a relationship of another kind.

Without the rule for kinds the core schema defines, an export from an empty instance would hold `IpamNamespace`, and every load of an export would give a `default_filter` deprecation warning for it, which breaks SC-002. A namespace filter cannot separate it from user kinds, because `models/base/` also uses the `Ipam` namespace. The rule leaves out any change the schema owner made to `IpamNamespace` on the source, with no warning. This extends D2 from restricted namespaces to every kind Infrahub defines, and needs the feature owner's agreement (decided in planning on 2026-11-26, not yet agreed).

**Alternatives considered**:

- Removing every relationship the baseline processing would add, found by comparison. Rejected because a relationship the user defined with the same name as a generated one would then disappear silently.
- A hand-kept list of reserved kinds that holds `IpamNamespace`. It gives the same result today, but a kind Infrahub adds later in an unrestricted namespace would be exported until someone adds it to the list.
- Moving `IpamNamespace` to a restricted namespace. It is the clean fix, but renaming the kind changes stored data, the GraphQL API and users' queries, so it needs a migration and a deprecation plan. It is a separate issue (spec Follow-ups).

## R3. How `BRIEF` mode decides which values to leave out

**Decision**: a reduction loop in `SchemaExporter`:

1. Start from the `FULL` document of all user namespaces (R1, R2).
2. Build a candidate by removing every optional field of each element, except the pinned properties in R9, the fields the write model requires, and the fields the schema definitions mark as never removed (see "Fields the loop never removes" below).
3. Load the candidate into a copy of the baseline schema (R4) with `SchemaBranch.load_schema`, and run `SchemaBranch.process` with validation, as `backend/infrahub/api/schema.py::evaluate_candidate_schemas` does.
4. For each exported element, compare every write-visible field of the processed result with the stored element, ignoring IDs. Both sides are compared after the conversions in [data-model.md](data-model.md#conversions), so a NumberPool stored with `start_range` and `end_range` equals a processed attribute that holds the same bounds in `ranges`.
5. Put back into the candidate every field whose processed value differs and that the candidate does not hold, taking the value from the `FULL` document.
6. Repeat from step 3 while the previous pass put back at least one field.

The candidate is a dict at every step, built from the `FULL` document's `model_dump(exclude_unset=True)`, and removals delete keys from it. It becomes a `SchemaExportDocument` only at the end, by validating the dict, so the document's set fields are exactly the keys the loop kept. The endpoint serializes the document with `exclude_unset=True` (`response_model_exclude_unset=True` on the route), and the SDK writes files with `model_dump(exclude_unset=True)`. Without this, the write models would write every field with its default value and a `BRIEF` export would be as long as a `FULL` one. A test checks the HTTP response body, not only the document object (R8).

**Fields the loop never removes.** Some optional fields are not derived by processing, and removing them makes the candidate fail validation, which sends the export to the `FULL` fallback. `inherit_from` is one: without it, a `human_friendly_id` that names an inherited relationship no longer validates. These fields are marked in the schema definitions, next to `visibility`, with a new key in `backend/infrahub/core/schema/definitions/internal.py::ExtraField` (working name `keep_in_export`). The definition of a field never reaches the database, so the mark does not change the stored schema. `uv run invoke backend.generate` writes the marked fields into a new constant in `infrahub_sdk/schema/generated/contract.py`, keyed by write model name as `READ_ONLY_FIELDS` is, and the exporter reads that constant. The fields marked first are `inherit_from` and every field whose removal makes a variation schema fail validation, found by running the R8 tests. A field that needs the mark and does not have it makes a test schema reach the fallback, and the R8 tests fail on any fallback, so CI shows it. A field added later that needs the mark is found the same way, because the field coverage test (R10) requires a variation schema that sets it.

**A derived value and its source can both be written.** The first pass removes a derived value and the value it is derived from together. Both then differ after processing, and both are put back. Example: removing `unique: true` from `NetworkDevice.name` means processing derives no `human_friendly_id`, so `unique`, `human_friendly_id` and `uniqueness_constraints` all come back, although processing would derive the last two from `unique`. Other pairs of this kind are `optional` with `default_value`, and `min_count` and `max_count` with `cardinality: one`. The loop does not try to remove these values again. The export still loads to the same schema, because every value it writes is the stored value. This writes values that D3 says to leave out, and the design document example where `NetworkDevice` has no `human_friendly_id` does not match the output. It needs the feature owner's agreement (decided in planning on 2026-11-26, not yet agreed).

The loop ends when a pass finds no difference, or when every field that differs is already in the candidate, so a further pass would process the same candidate again. The second case happens when the stored schema is not what processing produces from the `FULL` document, for example a schema stored by an earlier release whose processing set a value differently. Each pass that continues puts back at least one of the fields step 2 removed, so the loop runs at most that many passes plus one.

When differences remain at the end, the exporter returns the candidate as it is and logs a warning with the branch and the kind, attribute or relationship name and field of each remaining difference. Writing more values cannot remove these differences, because the candidate already holds the `FULL` value of each one. The R8 tests assert that no difference remains for any test schema, and a unit test uses a stored schema that processing changes to check that the loop ends.

At debug level, the exporter logs each field the loop put back, with its kind and element name. A reader who wants to know why a value is or is not in a `BRIEF` export finds the answer there: a value is written only when processing produced a different value without it.

Because the loop follows processing, the `BRIEF` output can change between releases with no change to the exporter, for example when processing starts deriving a value it did not derive before. The export still loads to the same schema. A text comparison of two exports made on different releases can show the difference.

The candidate always holds every user namespace, so the namespace filter (R6) is applied after the loop and the result for a node does not depend on the filter.

The export never returns an error because a candidate fails to process. When processing a pass raises the validation errors a schema load raises (`ValueError` and `infrahub.exceptions.ValidationError`, as caught in `backend/infrahub/api/schema.py::evaluate_candidate_schemas`), the exporter stops the loop and returns the `FULL` document, which needs no processing. It logs a warning with the branch and the error message. Two cases lead there:

- A removal breaks a validation rule that links a removed field to one the candidate keeps. This is a defect in the export rules. The schema owner gets a longer file that still loads. The R8 tests assert that no test schema reaches the fallback.
- The stored schema no longer passes the current validators, for example a schema stored by an earlier release. The `FULL` document then fails to load on the target with the same validation error, and the source instance's own next schema load fails the same way, because a load processes the whole branch schema. How the loader reports it is out of scope (spec Edge Cases).

A unit test covers each case (R8). In both, `export` returns the `FULL` document without raising, so the endpoint answers with status 200.

**Rationale**: FR-006 asks to leave out a value "when processing would produce the same value on load", with the exception for a derived value written next to its source. The loop tests that statement directly with the processing code, so it covers `label`, `order_weight`, `branch`, `identifier`, a `human_friendly_id` or `uniqueness_constraints` derived from a value the export keeps, and any value processing derives later, with no list of derived fields. It also covers values that equal the write-model default, because removing them leaves processing to set the same default.

**Alternatives considered**:

- A fixed list of derivation rules, one per field. The design document lists this as a risk to the estimate ("The rules for leaving out derived values do not reduce to a fixed list"), and it is the drift the story is about.
- Removing one field at a time and processing after each removal. Correct, but processes the schema once per field, which is several hundred times for `models/base/`.
- After the loop, trying to remove each field it put back, one at a time, and keeping the removal when processing gives the same result. It leaves out a derived value written next to its source, as D3 says, but the order of the attempts decides which value of a pair stays, and each attempt costs one processing of the schema.
- Putting removed fields back one at a time when the candidate fails validation, instead of marking the fields the loop never removes. It needs no mark, but costs one processing per field it tries.
- Storing only the values the schema owner set, and deriving the rest when the schema is read. This would remove most of the loop, because the stored schema would show which values are derived. It changes how Infrahub stores the schema, and the design document lists recording the source of each value as deferred.

## R4. The baseline schema for the comparison, and its cost

**Decision**: the baseline is a `SchemaBranch` that holds `internal_schema`, `core_models` and `deprecated_models`, processed, as built by `backend/infrahub/core/initialization.py::first_time_initialization`. It is the schema of an empty instance.

An export keeps no object after the response is sent:

- Each export builds its own baseline with a new schema cache, and drops it at the end of the request. Nothing is cached between requests, in the exporter or in a module.
- Each pass of the loop builds its schema from the export's baseline with a new schema cache. `SchemaBranch.duplicate` is not used, because the copy it returns shares the original's `_cache` dictionary (`backend/infrahub/core/schema/schema_branch.py::SchemaBranch.duplicate`), and `SchemaBranch.set` adds every schema it stores to that dictionary.
- The `FULL` build gets the branch schema with `registry.schema.get_schema_branch`, which returns the registry's own `SchemaBranch`, not a copy (`backend/infrahub/core/schema/manager.py::SchemaManager.get_schema_branch`). It reads the nodes and generics from it without copying them, and never calls `SchemaBranch.set` on it, so the registry's schema caches do not change.
- The exporter therefore holds the registry's own node, generic, attribute and relationship objects. It treats them as read-only: it takes `model_dump()` of each one, which returns new containers at every level, and does every removal and conversion on that data or on the write models. It never changes a stored element and never uses `model_copy()` on one, because that copy is shallow and shares nested lists and parameter objects with the registry. A change to a stored element would change the branch schema in memory for every later request until the next reload.

A unit test runs several exports and checks that the size of the registry's schema cache for the branch is the same before and after, and that the exporter instance holds no schema after `export` returns. A second test checks that `SchemaBranch.get_hash()` and a `model_dump()` of every user node and generic are the same before and after an export in each mode, on the variation schemas that hold the deprecated forms the export converts.

The exporter runs on the request's event loop, as `POST /api/schema/load` and `POST /api/schema/check` run `SchemaBranch.process` today. The exporter logs the number of passes and the export time at debug level with the branch name. The functional test for `models/base/` prints both. An export is expected to be rare, and the API runs several workers, so the export stays on the event loop until these numbers show that it delays other requests. Moving it to a thread is decided from the numbers, not in this plan.

**Rationale**: D1 defines the promise against an empty instance. Using the source instance's core schema would carry extensions of Core kinds into the comparison, which D2 excludes. Building the baseline for each export costs one processing of the core schema per request, and in exchange the memory used by the server does not depend on whether or how often anyone exports.

**Alternatives considered**:

- Caching the baseline for the life of the process. It saves one processing of the core schema per export, but the server then keeps the baseline after the first export, and every copy made with `SchemaBranch.duplicate` adds its schemas to the baseline's cache, which grows with each export.
- Copying the baseline's cache dictionary for each pass. Smaller, but processing steps that read schemas with `duplicate=False` could change the cached baseline objects, and a shared baseline would carry the change into later exports.

## R5. The Infrahub version field and the load contract

**Decision**:

- The working name of the field is `infrahub_version`, at the root of the document, next to `version: "1.0"` (D7). Its value is `infrahub.__version__`.
- `tasks/backend.py::_sdk_root` adds `infrahub_version: str | None = None` to the generated `InfrahubSchemaWrite` only. `uv run invoke backend.generate` writes the change into the SDK.
- `backend/infrahub/api/schema.py::SchemaLoadAPI.build_internal_schema` excludes the field when it builds `SchemaRoot`, which forbids unknown fields (`backend/infrahub/core/schema/__init__.py::SchemaRoot`). `SchemaRoot` does not change.
- `infrahub_sdk/schema/validate.py::validate_schema` accepts the field with no change of its own, because it reports only fields the write model does not have.

**Rationale**: the write model is the single contract for both the server and the offline SDK validation, so FR-012 is met by one generated change. Keeping the field out of `SchemaRoot` means schema processing, merging and hashing never see it. Git repositories load schema files through `sdk.schema.load` (`backend/infrahub/git/integrator.py`), so they take the same path.

**Alternatives considered**: adding the field to `SchemaRoot`. It would put export metadata into every internal schema object and into `SchemaRoot.merge`.

## R6. Namespace filter

**Decision**: the reduction loop runs on all user namespaces, and the exporter then keeps only the selected ones (FR-011). The export does not name the kinds outside the selection that it references. The feature owner left that out of the first version on 2026-11-23 (spec Out of Scope), so the document has no field for it.

**Rationale**: running the loop on the whole user schema gives each node the same values with or without the filter, because processing a node can depend on its peers and generics in other namespaces.

**Alternatives considered**: running the loop on the selected namespaces only. Processing would fail or derive different values for nodes whose peers or generics are outside the selection.

## R7. The endpoint and older servers

**Decision**:

- `GET /api/schema/export` is declared in `backend/infrahub/api/schema.py` before `get_schema_by_kind`. FastAPI matches routes in the order they are declared, and `/{schema_kind}` would otherwise match `export`.
- On a server without the endpoint, `GET /api/schema/export` reaches `/{schema_kind}`, which raises `SchemaNotFoundError` (`backend/infrahub/exceptions.py::SchemaNotFoundError`, HTTP 422) from the schema registry lookup (`backend/infrahub/core/schema/manager.py` and `schema_branch.py`) with the message `Unable to find the schema 'export' in the registry`. Every release since 0.16 sends this message; the `in the database.` text is only the default of the exception and never reaches this route. The SDK treats only a 422 whose error message names the schema `export` as not found as "endpoint missing", and raises an error that names the first release with the endpoint (FR-016). Any other error response is reported as the server returned it.
- A server with the endpoint never returns that response from this URL. The export has no error responses of its own (R3): it returns the errors `GET /api/schema` returns for an unknown branch or a missing login, and FastAPI's request validation error for an unknown `mode`, whose body has a different shape.
- The release is held in one SDK constant. Its value is set to the release that ships the endpoint. The design document example uses `1.13.0`; the release is not confirmed by the sources.

**Rationale**: D8. The SDK cannot ask the server for its version in the same request, and `client.get_version()` adds a request that older servers answer differently.

**Alternatives considered**: comparing `client.get_version()` with the constant before the call. It adds a request on every export and fails on development builds whose version is not a release number.

## R8. Test layout

**Decision**:

- **Unit tests** (`backend/tests/unit/schema/export/`), no database:
  - An in-memory round trip helper: process a test schema on the baseline (source), export it, load the export into a new baseline copy (target), process, and compare the user-defined schema of both, ignoring IDs. It compares both sides after the conversions in [data-model.md](data-model.md#conversions), as the loop does (R3), because the target stores NumberPool ranges as `ranges` where the source may hold `start_range` and `end_range`. It also exports the target and compares the two documents apart from `infrahub_version` (SC-003).
  - One variation schema per export rule, each run in `BRIEF` and `FULL` mode (D12). One of them has a node that inherits `human_friendly_id` from a generic and also has its own `unique: true` attribute. Processing adds that attribute to the node's `uniqueness_constraints`, so the node's value differs from the generic's and is not pinned (R9). The test checks that the reduction loop still gives the same schema on the target.
  - A variation schema with a node that has no generic and a `unique: true` attribute, from which processing derives `human_friendly_id` and `uniqueness_constraints`. The test checks that `BRIEF` writes all three values and that the export loads to the same schema (R3, a derived value and its source).
  - A test that every round trip in `BRIEF` mode ends without the fallback, so a field that needs the `keep_in_export` mark and does not have it fails CI (R3).
  - A test that an export of a schema with only the core schema has no nodes and generics, and that an export of a user node in the `Ipam` namespace holds that node and not `IpamNamespace` (R2).
  - The field coverage test (R10).
  - A `FULL` check that reads the exported file alone and finds every write-visible field with a value, except the ones R2 removes and the deprecated forms that the conversions replace (SC-005, [data-model.md](data-model.md#conversions)).
  - A loop-termination test (R3): a stored schema that processing changes, so differences remain. The test checks that the loop ends, that `export` returns the candidate, and that the remaining differences are logged as a warning.
  - Two fallback tests (R3): a candidate that a validator rejects, and a stored schema that the current validators reject. Each checks that `export` returns the same document as `FULL` mode, raises nothing, and logs a warning with the branch and the error message.
  - A memory test (R4): several exports in a row leave the size of the registry's schema cache for the branch unchanged, and the exporter holds no schema after `export` returns.
  - A read-only test (R4): the branch schema hash and a `model_dump()` of every user node and generic are the same before and after an export in each mode.
- **Functional tests** (`backend/tests/functional/api/test_schema_export.py`, `TestInfrahubApp`), with the database:
  - One test class for `models/base/` and one for all variation schemas loaded together, each in its own namespace. Each class loads the schema through the API, exports it in both modes, returns the database to an empty instance with a reset helper, loads the export, and compares the schema read back from `GET /api/schema`.
  - The reset helper deletes only the user-defined schema and the objects of those kinds, then reloads the schema registry from the database. It keeps the root, the branches, the core schema and the accounts, API tokens, groups and permissions that the class fixtures created, so the SDK client stays logged in. It does not remove all nodes, which would delete those accounts and tokens. The test asserts after each reset that `GET /api/schema` holds only the nodes and generics the core schema defines, which includes `IpamNamespace` in the unrestricted `Ipam` namespace (R2). The exact queries are chosen in the tasks.
  - Checks that the load gives no warning other than the `display_labels` and `default_filter` deprecation warnings (SC-002), and that a NumberPool loaded with `start_range` and `end_range` gives the same ranges with no warning (SC-006).
  - The endpoint's `branch` and `namespaces` parameters.
  - The JSON body of a `BRIEF` response holds no key the loop removed, for example no `label` on an attribute whose label is derived from its name, and no key with a default value that the stored schema did not need (R3, serialization with `exclude_unset`).
  - The export time and pass count for `models/base/`, printed in the test output. They are the numbers for deciding whether the export needs to run outside the event loop (R4).
- **SDK unit tests** (`python_sdk/tests/unit/`), with the HTTP responses mocked by `httpx_mock` as the existing SDK tests do:
  - `export` returns the endpoint's document as a `SchemaExportDocument`, and `split_by_namespace` gives one document per namespace with the same `version` and `infrahub_version`;
  - the CLI options and the file split by namespace;
  - a file written by the CLI holds only the keys of the endpoint's response, and no field the response left out appears with its default value (R3);
  - a 422 with the message `Unable to find the schema 'export' in the registry` gives the error that names the first release with the endpoint (R7);
  - a 422 with any other message, and a 500, are reported as the server returned them and do not mention the release.
- **SDK integration test** (`python_sdk/tests/integration/`): runs `infrahubctl schema export` against an Infrahub container. It can only pass against a released image that has the endpoint, so it is added after that release (plan, delivery order). Until then the functional tests in this repository cover the export end to end.

**Rationale**: the design document lists as a risk that "the load tests cannot run on an in-memory schema and need a database for each variation". Running every variation through the database would add one empty-instance reset per variation and mode. The in-memory round trip uses the same `load_schema` and `process` as the API. The database tests then cover what memory does not: storing the schema and reading it back, which the D4 check on 2026-11-20 showed can matter. Loading all variations together in one class keeps the number of resets at four (two classes, two modes).

**Alternatives considered**: one functional test class per variation. Correct, but each class resets the database and loads the core schema, which makes the suite slower as variations are added.

## R9. Properties a node took from its generic (D4)

**Decision**: on a node with `inherit_from`, each property that processing copies from a generic is pinned in `BRIEF` mode when its value equals the stored value of the first generic in `inherit_from` that sets it. A pinned property is never removed by the reduction loop. A property whose value differs from the generic's is treated like any other field by R3.

The list of these properties is kept once. Today it is a local variable, `properties_to_inherit`, inside `NodeInheritanceHandler.inherit_from_interface`. This work moves it to a module-level constant in `backend/infrahub/core/schema/node_inheritance_handler.py`, used by both the inheritance handler and the exporter. Today it holds `human_friendly_id`, `display_label`, `display_labels`, `default_filter`, `menu_placement`, `uniqueness_constraints`, `icon` and `order_by`. A property added to it is pinned by the export with no change to the exporter.

**Rationale**: this is how processing copies these properties (`backend/infrahub/core/schema/node_inheritance_handler.py`): from the first generic that sets them, whole, and only to a node that has no value. A node whose value equals the generic's is the case the stored schema cannot tell apart. In the design document example, `NetworkPhysicalInterface` gets the six properties its generic sets. `NetworkDevice` has no generic, so nothing is pinned on it; its `human_friendly_id` and `uniqueness_constraints` are written only because the reduction loop writes them next to `unique: true` (R3), which differs from the design document example.

**Alternatives considered**:

- A copy of the property list in the exporter. A property added to the inheritance handler would then not be pinned, and the export would leave it out of nodes that took it from a generic.
- Pinning the properties on every node. A node with no generic would then get each of these properties written even when processing derives it from a value the export keeps, for example `uniqueness_constraints` generated from a `human_friendly_id` the schema owner wrote (design document, section 2).

## R10. Field coverage test (D12, SC-004)

**Decision**: the test lists the `model_fields` of every write model a schema file can contain below the root, and compares them with a table in the test module. It collects the models by walking the field annotations of `NodeSchemaWrite` and `GenericSchemaWrite` and opening unions and lists, so a nested model added later is found with no change to the test. `AttributeSchemaWrite` is an `Annotated` union, not a model, so the walk reaches its members (`TextAttributeWrite`, `NumberAttributeWrite`, `ListAttributeWrite`, `NumberPoolAttributeWrite`, `GenericAttributeWrite`). Today the walk also reaches `RelationshipSchemaWrite`, the attribute-parameter write models, `DropdownChoiceWrite`, `NumberPoolRangeWrite` and the computed-attribute write models.

Each table entry names the variation schema that covers the field, or marks the field as not needing a test with a reason. The test fails on:

- a field missing from the table;
- a table entry for a field that no longer exists;
- a table entry whose named variation schema does not set the field on at least one element of that model (SC-004: "until a test schema uses it").

The table records test coverage only. It does not say how the export treats a field, because that is decided elsewhere: whether a field can be written by its `visibility` (R1), whether `BRIEF` writes it by the reduction loop and the `keep_in_export` mark (R3), and whether it stays on a node by the inheritance constant (R9). The rules are kept once, in those places.

**Rationale**: the write models are the set of fields an export can contain (R1). A field added to the schema definitions with `WRITE` visibility appears in the regenerated write models and fails the test until someone adds a test schema that uses it, or states why none is needed.

**Alternatives considered**: listing the fields of the internal models. They include internal fields that never reach the export, so the table would mostly hold "not needed" entries.
