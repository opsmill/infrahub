# Implementation Plan: Export the running schema

**Branch**: `schema-export-ifc-2964` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/ifc-2964-schema-export/spec.md`, and the approved [engineering design document](https://app.notion.com/p/401228b83025812589c6e6664594db35) (decisions D1 to D13).

## Summary

The schema owner downloads the running schema from `GET /api/schema/export` as one document in the schema file format, and loads it into an empty instance without editing it. `infrahubctl schema export` calls the endpoint, and the client-side export rules in the SDK are removed.

Infrahub builds the export in two steps:

1. It writes every field of the user-defined nodes and generics that a schema file can set (the write-visible fields of the generated write models), leaving out IDs, inherited and generated elements, kinds the core schema defines in an unrestricted namespace (`IpamNamespace`), and deprecated forms of validation settings and NumberPool ranges. This is the `FULL` mode.
2. In `BRIEF` mode it then removes values and checks the result: it loads the candidate into a copy of a schema that holds only the core schema, runs the same processing as a schema load, and compares the result with the stored schema. It writes back every value whose processed result differs, and repeats until a pass writes back no value. Differences that remain are logged as a warning (research R3). Properties a node took from its generic stay on the node (D4). Fields that the schema cannot be processed without, such as `inherit_from`, carry a mark in their definition and are removed only when they hold their default value.

Because the second step uses the processing code itself, a new derived value or a change to processing does not need a new export rule. The tests in D12 check the result for every test schema, and that a test schema uses every field a schema file can set.

The work is delivered in two pull requests: the SDK change first (version field in the write models, CLI rewrite), then the Infrahub change (endpoint, export rules, tests, documentation).

## Technical Context

**Language/Version**: Python 3.14 (backend). The SDK supports Python 3.10 to 3.13.

**Primary Dependencies**: FastAPI, Pydantic 2, the generated SDK write models (`infrahub_sdk/schema/generated/write.py`), Typer for `infrahubctl`. No new dependency.

**Storage**: none added. The export reads the schema held in the schema registry for the requested branch. It does not query Neo4j.

**Testing**: pytest. Unit tests for the export rules on in-memory schemas, functional tests (`TestInfrahubApp`) for the round trip through the database, SDK unit tests for the CLI.

**Target Platform**: Infrahub API server (Linux container).

**Project Type**: web service with a CLI client.

**Performance Goals**: none set by the sources. The `BRIEF` mode processes the schema at least twice per request, which is the same work as `POST /api/schema/check` done twice or more. The functional tests record the time for `models/base/` so a regression is visible (research R4).

**Constraints**:

- The export endpoint is read-only and takes no lock.
- The document must validate against the SDK write models, because `POST /api/schema/load` validates against them (`backend/infrahub/api/schema.py::SchemaLoadAPI`).
- The new route must be registered before `GET /api/schema/{schema_kind}`, which would otherwise treat `export` as a kind (research R7).

**Scale/Scope**: the schema of one branch, all user namespaces. The largest realistic test input is `models/base/` (6 files).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Result | How the plan meets it |
| --- | --- | --- |
| I. Schema-Driven Integrity | Pass | The export reads the stored schema and changes nothing. Generated files (SDK write models, `schema/openapi.json`, frontend REST types, schema JSON schema, reference docs) are regenerated, not edited. |
| II. Branch-Safe by Default | Pass | The endpoint takes `branch` through `get_branch_dep`, as `GET /api/schema` does. No database query is added. Merge behaviour does not change. |
| III. Type Safety & Explicit Contracts | Pass | The response is a Pydantic model built on `InfrahubSchemaWrite`. The contract is in [contracts/schema-export-api.md](contracts/schema-export-api.md) before implementation. The mode is an enum. |
| IV. Test Discipline | Pass, with one justified deviation | Unit tests for the rules, functional tests for the round trip, SDK unit tests for the CLI. New inline variation schemas are needed because each covers a shape no fixture has (spec Assumptions). No E2E browser test, because no UI changes (spec Assumptions). |
| V. Query Performance | Pass | No Cypher. The export works on the in-memory schema. |
| VI. Security & Input Boundaries | Pass | Read access is the same as `GET /api/schema` (D10). `mode` and `namespaces` are validated by FastAPI. A validation error while processing a candidate is logged, and the response is the `FULL` document, so no processing error reaches the client. |
| VII. Simplicity | Pass | One new component (`SchemaExporter`). The comparison loop replaces a hand-written list of derived fields, which is the cause of the drift IFC-2964 describes. |

The deviation under IV is the E2E rule ("MUST be included for all user-facing features"). The feature has no UI; the API and CLI are covered by functional and SDK tests. The UI download is a separate card that will need an E2E test.

**Ask-first items from `AGENTS.md`** that this plan contains, all approved in the design document:

- A new REST endpoint (D11). It changes `schema/openapi.json` and the generated frontend REST types.
- A change to the schema load contract: one root field, `infrahub_version`, that the load accepts and ignores (D7, research R5).

**Re-check after Phase 1**: no change. The data model adds no stored entity and the contracts follow D6 to D11.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-2964-schema-export/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1 to R10
├── data-model.md        # Phase 1: export document, mode, field classes
├── quickstart.md        # Phase 1: validation scenarios
├── contracts/
│   ├── schema-export-api.md         # GET /api/schema/export
│   ├── schema-load-contract.md      # fields the load accepts and ignores
│   └── infrahubctl-schema-export.md # CLI options, output, errors
├── checklists/
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code

Part 1, SDK repository (`python_sdk/` submodule, branch `infrahub-develop`):

```text
python_sdk/infrahub_sdk/
├── schema/
│   ├── generated/write.py      # regenerated: InfrahubSchemaWrite gains infrahub_version
│   ├── generated/contract.py   # regenerated: constant of the fields marked keep_in_export
│   ├── export.py               # client-side rules removed; holds SchemaExportDocument and split_by_namespace
│   └── __init__.py             # InfrahubSchema.export / InfrahubSchemaSync.export call the endpoint
└── ctl/schema.py               # export: --mode, --single-file, error for older servers
python_sdk/tests/unit/
├── sdk/test_schema_export.py   # rewritten for the endpoint response
└── ctl/schema/                 # CLI tests for the options and the older-server error
```

Part 2, Infrahub repository:

```text
backend/infrahub/
├── api/schema.py               # GET /api/schema/export, registered before /{schema_kind}
├── core/schema/node_inheritance_handler.py  # property list moved to a module-level constant
├── core/schema/definitions/internal.py      # ExtraField gains keep_in_export; set on the fields the loop keeps unless they hold their default
└── schema/export/
    ├── __init__.py
    ├── models.py               # SchemaExportMode, SchemaExportDocument
    └── exporter.py             # SchemaExporter: FULL build, BRIEF reduction loop
tasks/backend.py                # _sdk_root adds infrahub_version to the write root; contract.py gains the keep_in_export constant
backend/tests/unit/schema/export/
├── test_field_coverage.py      # every write-visible field has a test schema or a reason (D12)
├── test_full_mode.py
├── test_brief_mode.py          # one test per variation schema
└── conftest.py                 # variation schemas, in-memory round-trip helper
backend/tests/functional/api/
└── test_schema_export.py       # round trip through the database: models/base/ and variations, both modes
docs/docs/schema/export.mdx     # new page (FR-018)
dev/knowledge/backend/schema-export.md  # new: field visibility, reduction loop, why a value is left out, pinned properties (FR-019)
changelog/                      # towncrier fragments, listed under Changelog fragments
```

Regenerated, not edited: `python_sdk/infrahub_sdk/schema/generated/write.py`, `python_sdk/infrahub_sdk/schema/generated/contract.py`, `schema/openapi.json`, `frontend/app/src/shared/api/rest/types.generated.ts`, the schema-file JSON schema built from `SchemaLoadAPI`, and the `infrahubctl` reference docs.

**Structure Decision**: the exporter goes in `backend/infrahub/schema/`, next to `read_schema.py`, which already projects the internal schema onto the published SDK models for the API. It does not go in `core/schema/`, because it is a view of the schema for the API and not part of schema processing.

## Delivery order

1. SDK pull request on `infrahub-develop`: regenerated write models, CLI rewrite, removal of the client-side rules, SDK unit tests with mocked HTTP responses. It is merged first (spec Assumptions).
2. Infrahub pull request: `tasks/backend.py` change, submodule bump to the merged SDK commit, endpoint, exporter, tests, generated files, the documentation page, `dev/knowledge/backend/schema-export.md` and an entry for it in `backend/AGENTS.md`, changelog fragments.
3. After the first release that has the endpoint: an SDK pull request that adds the integration test for `infrahubctl schema export` (research R8). It cannot pass earlier, because the SDK integration tests run against a released Infrahub image.

Rules for the order:

- The SDK pull request contains the regenerated `write.py` and `contract.py`, produced by running `uv run invoke backend.generate` on a local Infrahub branch that has the `tasks/backend.py` change and the `keep_in_export` marks in `internal.py`. The Infrahub pull request carries the same changes, so the generated-file check in CI agrees with the submodule.
- The submodule bump and the change to `SchemaLoadAPI.build_internal_schema` that drops `infrahub_version` land in the same commit. `SchemaLoadAPI` is a subclass of the SDK write root, and the internal `SchemaRoot` rejects unknown fields, so a commit with only the bump makes every load that carries the field fail.
- Between the SDK merge and the Infrahub merge, `infrahubctl schema export` from `infrahub-develop` fails against every server, because no server has the endpoint yet. Only the development SDK branch is affected.

## Changelog fragments

Infrahub repository:

- `added`: the `GET /api/schema/export` endpoint, with the `BRIEF` and `FULL` modes.
- `changed`: the schema load accepts the `infrahub_version` field and ignores it.

SDK repository:

- `changed`: `infrahubctl schema export` now uses the endpoint and needs a server that has it. The fragment lists each difference in the files it writes compared with the current version:
  - `branch` on an attribute or relationship is written when it differs from the value derived from the node or the peer;
  - values Infrahub derives, such as a `label` taken from the name, are left out;
  - `IpamNamespace` is no longer written;
  - the generated `object_template` relationship is no longer written;
  - `regex`, `min_length` and `max_length` are written under `parameters`;
  - NumberPool `start_range` and `end_range` are written as `ranges`;
  - each file has an `infrahub_version` field.
- `changed`: `InfrahubSchema.export` and `InfrahubSchemaSync.export` return the endpoint's document as a `SchemaExportDocument` instead of a `SchemaExport`; `split_by_namespace` gives one document per namespace.
- `added`: the `--mode` and `--single-file` options.
- `removed`: `schema_to_export_dict`, `RESTRICTED_NAMESPACES`, `NamespaceExport` and `SchemaExport` from `infrahub_sdk.schema`, each named in the fragment.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| No E2E browser test (Principle IV) | The feature has no UI | An E2E test would test only the API through a browser runner. Functional tests cover the API and CLI directly. |
| `BRIEF` processes the schema in a loop instead of applying a fixed list of rules | Derived values do not reduce to a fixed list (design document, estimate risks) | A fixed list is what the SDK has today, and it drifted from the schema model (IFC-2964). |
