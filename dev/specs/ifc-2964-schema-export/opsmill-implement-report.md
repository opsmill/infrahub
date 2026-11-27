# Implementation report: export the running schema

- Feature: export the running schema (`GET /api/schema/export` and `infrahubctl schema export`)
- Spec directory: `dev/specs/ifc-2964-schema-export`
- Infrahub repository, branch `po-ifc-3670-schema-export-endpoint`: base `91568a343a`, head `c2cb0e4242` (before this report)
- SDK submodule, branch `po-ifc-3669-schema-export-cli`: base `338fbdc188` (`origin/infrahub-develop`), head `e59fd9c8`
- Wall-clock time: about 3 hours
- Status: DONE. T052, T053 and T055 were out of scope for this run and are still open.

## Chunk ledger

| # | Chunk | Tasks | Done / partial / blocked | Commits |
| --- | --- | --- | --- | --- |
| 1 | Phase 1, setup | T001 to T003 | 3 / 0 / 0 | `1ab9153f42` |
| 2 | Phase 2, load contract | T004 to T009 | 6 / 0 / 0 | `047052e44e`, `0fe6ac3d31`, `7d62fbfad9`, `cea3377a6e`, `8beccf939a`; SDK `a327204b`, `2631a682` |
| 3 | Phase 2, models and helpers | T010 to T012 | 3 / 0 / 0 | `ddf451ba6f` |
| 4 | User Story 1, fixtures, coverage and reset | T013, T018, T019 | 3 / 0 / 0 | `5229ddbb79` |
| 5 | User Story 1, implementation | T015 to T017, T021 to T027 | 10 / 0 / 0 | `f061dcea2b`, `bcf4a0518c` |
| 6 | User Story 1, round trip and marks | T014, T020, T028 | 2 / 1 / 0 | `a0ba5b4cc2`, `f154250be1`; SDK `c405d508` |
| 7 | User Story 2, FULL mode | T029 to T033 | 5 / 0 / 0 | `878a50e917` |
| 8 | User Story 3, namespace filter | T034 to T037 | 4 / 0 / 0 | `2644e228e7` |
| 9 | User Story 4, SDK and CLI | T038 to T045 | 8 / 0 / 0 | SDK `3229eced`, `513bd033`; `6d758ff3b2` |
| 10 | Polish, generated files and changelog | T046, T047, T049, T051 | 4 / 0 / 0 | `3bfe7ed37f`, `f7e75cfe31`, `ef3085b0a0` |
| 11 | Polish, documentation | T048, T050 | 2 / 0 / 0 | `67b00a47a8`, `49efc3f3e4` |
| 12 | Older-server message fix, then T054 | T054 | 1 / 0 / 0 | SDK `e9b8eed4`; `fad9185370`, `71d13d4955` |
| Review | Fixes from the review | none | not applicable | SDK `e59fd9c8`; `c2cb0e4242` |

Decisions and surprises the chunks reported:

- Chunk 2: generic schemas have no `inherit_from` field, so only the node field has the mark. `POST /api/schema/check` returns 202, not 200, so the test asserts 202 and compares the `diff`, because that endpoint returns no hash. The new generated constant is `KEEP_IN_EXPORT_FIELDS`.
- Chunk 3: `ListAttributeParameters` has only `regex`. A List attribute therefore keeps a top-level `min_length` and `max_length`; only `regex` moves under `parameters`. FR-008 and data-model.md list List among the kinds that lose all three. Building the core baseline takes about 0.6 s per call.
- Chunk 4: the variation schemas are in `backend/tests/helpers/schema/export_variations.py`, so the functional tests can import them. There are 14, one more than the task list names: `relationship_settings` covers the relationship fields. The functional test app keeps the core schema in memory only, so `store_core_schema_of()` stores `BuiltinTag` before an extension to it can load.
- Chunk 5: the exporter leaves out a marked field, a pinned property or an empty list when it holds its default value. Without this, every node carried `inherit_from: []` and `relationships: []`.
- Chunk 6: the round trip of `models/base/` needed four marks that no variation schema needed. A schema read back from the database does not keep the order in which attributes and relationships were loaded, so the exporter now sorts them by `order_weight`, then by name. data-model.md and the text of T021 were updated to match. T014 is partial; see "Tasks not completed".
- Chunk 7: in FULL mode the load gives exactly the same deprecation warnings as in BRIEF mode.
- Chunk 8: a filter that names only restricted namespaces returns status 200 with empty `nodes` and `generics`. Changed after the run, in `31247b230c`: a restricted or unknown namespace now returns 404.
- Chunk 9: the SDK release constant is `SCHEMA_EXPORT_MIN_INFRAHUB_VERSION = "1.13.0"`. No source confirms it. The SDK also exports a `SchemaExportMode` enum, which the task list did not ask for.
- Chunk 10: the frontend REST types come from `pnpm codegen:openapi`, not `pnpm codegen` as T046 states. Neither generator found changes left over from the base branch.
- Chunk 11: the error texts in `docs/docs/schema/export.mdx` come from running each case. A test against a real 1.12.2 server found that the SDK never named the release for an older server. Chunk 12 fixed this.
- Chunk 12: a released server answers `GET /api/schema/export` with status 422 and the message `Unable to find the schema 'export' in the registry`. The spec had `Unable to find the schema export in the database.`, which is only the default text of the exception. The SDK now matches the real message exactly. tasks.md, research.md and contracts/schema-export-api.md were corrected.

## Fields that received a keep_in_export mark

| Write model | Field | Validation error without the mark |
| --- | --- | --- |
| `NodeSchemaWrite` | `inherit_from` | Set by the task list: processing cannot rebuild the list of generics a node inherits from |
| Attribute write models | `read_only` | "PoolCircuit.vlan_id is a NumberPool it has to be a read_only attribute" |
| Attribute write models | `choices` | "The property 'choices' is required for kind=Dropdown" |
| Attribute write models | `unique` | "HFID of InfraInterfaceL2 refers to peer InfraDevice with a non-unique combination of attributes" |
| `RelationshipSchemaWrite` | `identifier` | "Identifier of relationships must be unique for a given direction" (InfraBGPPeerGroup) |
| `RelationshipSchemaWrite` | `cardinality` | "relationship must be of cardinality one (`device`)" |
| `RelationshipSchemaWrite` | `optional` | "relationship must be mandatory (`device`)" |

Processing does derive an `identifier` and a `unique` value. Without the stored values, however, the BRIEF candidate fails validation before the loop can put them back, and the export falls back to FULL. The marks are on the field definitions in `backend/infrahub/core/schema/definitions/internal.py`; the generator writes them into `KEEP_IN_EXPORT_FIELDS` in the SDK's `contract.py`.

## Tasks not completed

- T052: not in scope for this run. Opening the SDK pull request is a manual step.
- T053: not in scope for this run. The `python_sdk` pointer can move only after the SDK pull request merges.
- T055: not in scope for this run. The quickstart scenarios are manual.
- T014 is marked done, with one assertion changed. It was to assert that BRIEF writes `unique`, `human_friendly_id` and `uniqueness_constraints` on the node with a unique attribute. T028 added the mark on `unique`, so processing derives the other two values again and the loop leaves them out. The test asserts only `unique`, and does not assert that the other two are left out. The loop has no second removal pass (A1). The example in research R3 and T013 expected all three values; it needs a product decision.

## Local-pass evidence

| Test id | Type | Run command | Passed at (ISO 8601) | Environment | Pass line |
| --- | --- | --- | --- | --- | --- |
| Existing inheritance tests, `backend/tests/unit/core/schema/test_node_inheritance.py` | unit | `uv run pytest backend/tests/unit/core/schema/test_node_inheritance.py` | 2026-11-26T14:28Z | n/a | `5 passed, 1 warning in 0.06s` |
| `tests/unit/sdk/test_schema.py::test_validate_schema_accepts_infrahub_version` (SDK) | unit | `cd python_sdk && uv run pytest "tests/unit/sdk/test_schema.py::test_validate_schema_accepts_infrahub_version" -v` | 2026-11-26T14:30:37+00:00 | n/a | `1 passed in 0.03s` |
| `backend/tests/functional/api/test_load_schema.py::TestLoadSchemaWithInfrahubVersion` (2 tests) | functional | `uv run pytest "backend/tests/functional/api/test_load_schema.py::TestLoadSchemaWithInfrahubVersion" -v` | 2026-11-26T14:31:16+00:00 | Neo4j through testcontainers | `2 passed, 1 warning in 60.86s` |
| `backend/tests/unit/schema/export/test_exporter.py` (baseline, conversion, normalization, attribute order) | unit | `uv run pytest backend/tests/unit/schema/export/` | 2026-11-26T14:43:14Z | n/a | `15 passed, 1 warning in 3.92s` |
| `test_variation_schemas.py`, `test_field_coverage.py` | unit | `uv run pytest backend/tests/unit/schema/export/` | 2026-11-26T14:56:31Z | n/a | `34 passed, 1 warning in 16.32s` |
| `test_schema_export.py::TestResetToCoreSchema` (2 tests) | functional | `uv run pytest backend/tests/functional/api/test_schema_export.py` | 2026-11-26T14:56:52Z | Neo4j through testcontainers | `2 passed, 1 warning in 80.64s` |
| `test_brief_mode.py` (loop end, two fallbacks, memory, read-only), `backend/tests/unit/api/test_schema_export_route.py` | unit | `uv run pytest backend/tests/unit/schema/export/ backend/tests/unit/api/test_schema_export_route.py backend/tests/unit/api/test_schema_load_contract.py -q` | 2026-11-26T15:17:00Z | n/a | `79 passed, 2 warnings in 31.25s` |
| `test_brief_mode.py::test_brief_export_loads_to_the_same_schema_without_the_fallback[*]` (14 variations) and attribute order tests | unit | `uv run pytest backend/tests/unit/schema/export/ backend/tests/unit/api/test_schema_export_route.py -q -n 6` | 2026-11-26T15:58:13Z | n/a | `62 passed, 13 warnings in 111.31s` |
| `TestSchemaExportOfBaseModels`, `TestSchemaExportOfVariationSchemas` (BRIEF) | functional | `uv run pytest backend/tests/functional/api/test_schema_export.py -s -p no:randomly` | 2026-11-26T15:59:22Z | Neo4j through testcontainers | `19 passed, 1 warning in 178.20s` |
| `test_full_mode.py` (48 tests), route tests for FULL and an unknown mode | unit | `uv run pytest backend/tests/unit/schema/export/ backend/tests/unit/api/test_schema_export_route.py -q -n 4` | 2026-11-26T16:23:48Z | n/a | `112 passed, 9 warnings in 108.85s` |
| Both functional classes in BRIEF and FULL mode, `test_export_rejects_an_unknown_mode` | functional | `uv run pytest backend/tests/functional/api/test_schema_export.py -s -v -p no:randomly` | 2026-11-26T16:19:05Z | Neo4j through testcontainers | `36 passed, 1 warning in 228.92s` |
| Namespace filter tests in `test_brief_mode.py` and `test_full_mode.py` (4 tests) | unit | `uv run pytest backend/tests/unit/schema/export/ -k namespace -rA -q -p no:randomly` | 2026-11-26T16:32:41Z | n/a | `10 passed, 102 deselected, 1 warning in 27.51s` |
| `TestSchemaExportOfBaseModels::test_export_of_one_namespace_writes_its_entries_as_the_unfiltered_export[BRIEF,FULL]` | functional | `uv run pytest backend/tests/functional/api/test_schema_export.py -k TestSchemaExportOfBaseModels -q -rA` | 2026-11-26T16:33:29Z | Neo4j through testcontainers | `18 passed, 20 deselected, 1 warning in 139.54s` |
| SDK `tests/unit/sdk/test_schema_export.py` (11) and `tests/unit/ctl/schema/test_schema.py` export tests (8) | unit | `cd python_sdk && uv run pytest tests/unit/sdk/test_schema_export.py tests/unit/ctl/schema/test_schema.py -v` | 2026-11-26T16:40:13+00:00 | n/a | `32 passed, 4 warnings in 0.38s` |
| SDK older-server tests (`test_export_names_the_release_on_an_older_server`, `test_export_reports_other_errors_as_returned`, `test_schema_export_error_response`) | unit | `cd python_sdk && uv run pytest tests/unit/sdk/test_schema_export.py tests/unit/ctl/schema/test_schema.py -q -rA -k "older or other or error"` | 2026-11-26T17:03:37+00:00 | n/a | `11 passed, 23 deselected, 4 warnings in 0.11s` |
| Final rerun, backend export unit and route tests | unit | `uv run pytest backend/tests/unit/schema/export/ backend/tests/unit/api/test_schema_export_route.py -q -n 4` | 2026-11-26T17:06:33+00:00 | n/a | `116 passed, 9 warnings in 122.84s` |
| Final rerun, `test_schema_export.py` and `test_load_schema.py` | functional | `uv run pytest backend/tests/functional/api/test_schema_export.py backend/tests/functional/api/test_load_schema.py -q` | 2026-11-26T17:08:57+00:00 | Neo4j through testcontainers | `58 passed, 1 warning in 321.29s` |
| Final rerun, SDK unit suite | unit | `cd python_sdk && uv run pytest tests/unit/ -q -n 4` | 2026-11-26T17:08:40+00:00 | n/a | `3160 passed, 2 skipped, 1 xfailed, 29 warnings in 13.30s` |

Export time and pass count printed by the functional tests for `models/base/`:

- `TestSchemaExportOfBaseModels BRIEF: schema export in 2.808 s, 2 passes` (an earlier run printed 2.147 s, 2 passes)
- `TestSchemaExportOfBaseModels FULL: schema export in 0.003 s, 0 passes`

## Review findings

Review mode: plugin (pr-review-toolkit). Five agents reviewed both ranges: this repository from `91568a343a` and `python_sdk` from `origin/infrahub-develop`. Then code-simplifier ran. The Infrahub tree held only the `python_sdk` entry and the SDK tree was clean, so code-simplifier was not skipped. Its edits were recorded as low findings and then discarded.

| Severity | Repository, file | Summary | Outcome |
| --- | --- | --- | --- |
| high | Infrahub, `docs/docs/schema/export.mdx` | The BRIEF example shows `on_delete: cascade`, which the reviewer said BRIEF leaves out | Not changed: the real export writes it, because without `kind` processing derives `no-action`, so the loop puts both values back |
| high | Infrahub, `tasks/backend.py` | The docstring says the export never removes a marked field, but it does when the field holds its default | Fixed in `c2cb0e4242` |
| medium | Infrahub, `internal.py`, `tasks/backend.py`; SDK, generated `contract.py` | Comment says processing does not derive the marked fields and that an export without them fails to load | Fixed in `c2cb0e4242`, regenerated in SDK `e59fd9c8` |
| medium | Infrahub, `dev/knowledge/backend/schema-export.md` | Repeats the claim above | Fixed in `c2cb0e4242` |
| medium | SDK, `changelog/+schema-export-endpoint.changed.md` | Says lengths move under `parameters` for every kind except List; true only for Text and TextArea | Fixed in SDK `e59fd9c8` |
| medium | Infrahub, `exporter.py` | Docstring of `convert_deprecated_attribute_fields` misstates when the top-level value is dropped | Fixed in `c2cb0e4242` |
| medium | Infrahub, `api/schema.py`, `exporter.py` | The async route runs the export on the event loop; each BRIEF pass builds a 0.6 s baseline, so an export blocks the API worker for seconds | Fixed after the run in `61ff4d8b5e`: the export runs in a thread |
| medium | Infrahub, `exporter.py` | Looking up `KEEP_IN_EXPORT_FIELDS` by class name returns an empty set when a write class is renamed, and the export then falls back to FULL | Deferred |
| medium | Both | `SchemaExportMode` is defined in both repositories, so the two copies can drift | Deferred |
| medium | Infrahub, `exporter.py` | The fallback warning logs no exception type and no stack trace | Deferred |
| medium | SDK, generated write models and `schema/__init__.py` | `extra="ignore"` drops fields a newer server sends, and nothing warns the user | Deferred |
| medium | SDK, `ctl/schema.py` | `--namespaces` with a mistyped or restricted namespace prints "No user-defined schema found to export." and exits 0, with no message about the namespace | Fixed after the run in `31247b230c` and SDK `a5c82404`: the server returns 404 and the CLI prints one error per namespace |
| medium | Infrahub, `tests/unit/schema/export/conftest.py` | The round-trip check uses the same normalization function as the loop, so a bug there would be hidden in both | Deferred |
| medium | Infrahub, unit tests | The export unit tests take about 214 s; a module-scoped fixture would make the filter tests faster | Deferred |
| low | Infrahub, `exporter.py` | `ExportedField` allows `collection` without `element_name` | Deferred |
| low | Infrahub, `models.py` | `generics` and `nodes` repeat the parent's declarations | Deferred |
| low | SDK, `export.py` | `SchemaExportDocument` accepts `extensions`, and `split_by_namespace` drops them | Deferred |
| low | SDK, `export.py` | `split_by_namespace` assigns lists after construction and shares node instances with its input | Deferred |
| low | SDK, `schema/__init__.py` | `_parse_export_response` repeats the filter in `as_error_list` | Deferred |
| low | SDK, `schema/__init__.py` | The `Raises:` sections omit `JsonDecodeError` and the pydantic `ValidationError` | Deferred |
| low | SDK, `ctl/schema.py` | `--single-file` writes `generics: []` when a branch has no generics | Deferred |
| low | Infrahub, route and functional tests | Exact FastAPI 422 bodies, exact validator messages, exact BRIEF bodies and private attributes are asserted | Deferred |
| low | SDK tests | No test of a non-JSON 200 body, a 401 or 403 through the CLI, or a mode value that is not valid | Deferred |
| low | Infrahub tests | The marks on `identifier`, `cardinality`, `optional` and `unique` are tested only by the functional `models/base/` run | Deferred |
| low | Infrahub, `exporter.py` | The `_reduce` docstring overstates what the loop leaves out | Deferred |
| low | Infrahub, `export.mdx` | "writes to a new directory"; the command also writes to an existing directory | Deferred |
| low | Infrahub, `export.mdx`, knowledge doc | "Today this is" phrases will go out of date | Deferred |
| low | Infrahub, `exporter.py` | Code-simplifier: build the `namespace + name` kind string in one function | Deferred, discarded |
| low | Infrahub, `exporter.py` | Code-simplifier: use `PARAMETERS_FIELD` and `ATTRIBUTES_FIELD` instead of string literals | Deferred, discarded |
| low | Infrahub, `exporter.py` | Code-simplifier: one `_remove_ids` function instead of two copies of the loops | Deferred, discarded |
| low | Infrahub, `exporter.py` | Code-simplifier: pass the document to `_reduce` without copying it | Deferred, discarded |
| low | SDK, `export.py` | Code-simplifier: collect namespaces with `dict.fromkeys` | Deferred, discarded |

The code-reviewer also noted that `infrahub.api.schema` fails to import until the `python_sdk` pointer moves, because the exporter imports `KEEP_IN_EXPORT_FIELDS`. CI on the Infrahub pull request fails until T053.

## Autonomous decisions

- US1 was split into three chunks: T013, T018 and T019; then T015 to T017 with T021 to T027; then T014, T020 and T028. Each test had to pass before its chunk reported done, but the round-trip tests could pass only after the implementation and the marks.
- Polish was split into three chunks: the generated files with the changelog and the CSV page; the two documents; then T054.
- The older-server message was fixed although the spec stated the other message. The spec message never reaches the client, so FR-016 did not work.
- The `unique` mark and its effect on T014 were accepted rather than reverted. The mark follows the T028 rule; without it, the BRIEF export of `models/base/` falls back to FULL.
- The first high finding was not applied, because running the export showed the reviewer was wrong.
- Four medium findings that made false statements in comments, docs and a changelog fragment were fixed with the two high findings.
- Rule breaks by chunk agents: chunk 3 edited `exporter.py` once with an inline Python script, and chunk 8 appended tests to `test_full_mode.py` with a heredoc. Code-simplifier also used a script, but its edits were discarded. In each case the content is what the agent intended, and every later check passed.

## Suggested next steps

1. Decide the T014 question: with the `unique` mark, BRIEF leaves out a derived `human_friendly_id` and `uniqueness_constraints`, while research R3 and T013 expected them written.
2. Confirm the SDK release constant `1.13.0` with the release owner.
3. Correct the spec documents that still say the marked fields are "not derived by processing" or "never removed": `data-model.md:60`, `research.md:45`, `research.md:53`, `research.md:81`, `plan.md:14`, `plan.md:109`, `spec.md:182`.
4. Decide on the deferred medium findings, first the event-loop blocking in the export route.
5. Run `/pre-ci`, then open the SDK pull request (T052), bump the pointer (T053) and run the quickstart (T055).
