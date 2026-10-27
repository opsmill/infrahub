# Implementation Plan: Export the Running Schema

**Branch**: `schema-export-infp-723` | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `dev/specs/infp-723-schema-export/spec.md`

## Summary

A schema owner downloads the user-defined schema of a branch as one schema file document and loads it into
another instance without editing it ([INFP-723](https://opsmill.atlassian.net/browse/INFP-723),
[IFC-2964](https://opsmill.atlassian.net/browse/IFC-2964)). Infrahub produces the export, and
`infrahubctl schema export` calls it instead of applying its own rules.

Technical approach:

- `GET /api/schema/export` with `branch`, `namespaces` and `mode` (`brief` by default, or `full`).
- The fields written come from the write models generated from field visibility (ADR 0010), so a new
  schema field is covered without a hand-maintained list ([research.md](research.md) R2).
- `brief` leaves out a value only when processing gives it back. The export checks this by processing the
  candidate in memory and writing back every value that differs, until nothing differs (R1).
- A new optional root field `infrahub_version`, generated into the SDK write model and accepted by the
  backend load (R7).
- The SDK client and `infrahubctl` call the endpoint. The client-side export code is removed (R12).

## Technical Context

**Language/Version**: Python 3.14 (backend); Python 3.10 to 3.13 (SDK, `python_sdk/`)

**Primary Dependencies**: FastAPI 0.131, Pydantic 2.12, Typer and `httpx` (SDK), PyYAML (SDK, already
used). No new dependency.

**Storage**: None. The export reads the processed schema held by the schema manager. No migration.

**Testing**: pytest unit tests (in-memory round trip, field coverage), component tests
(`test_40_schema.py`), functional tests (`TestInfrahubApp`, empty database per class), SDK unit tests with
`pytest_httpx` and `typer.testing.CliRunner`. See [quickstart.md](quickstart.md).

**Target Platform**: The API server (Linux container) and `infrahubctl` on the schema owner's machine.

**Project Type**: Web service (backend REST endpoint) plus a library and CLI (SDK).

**Performance Goals**: The spec sets none. An export runs `SchemaBranch.process` once per R1 pass, usually
one to three passes. The time on `models/base/` is measured in the unit tests and reported in the pull
request; no target is set.

**Constraints**: The export never writes a value the write model rejects (the response is validated
against `InfrahubSchemaWrite`). Processing runs in the request, without the database, as
`evaluate_candidate_schemas` already does for a load.

**Scale/Scope**: About 6 backend files (one new package, the API module, `SchemaRoot`, the SDK root
generator, constants), 5 test files, 4 SDK files and their tests, 2 documentation pages, 1 knowledge file,
generated files (`schema/openapi.json`, frontend REST types, SDK write models).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | Pass | The export reads the schema and changes nothing. `infrahub_version` is added through the generator (`tasks/backend.py::_sdk_root`), never by editing generated files. `schema/openapi.json`, the frontend REST types and the SDK write models are regenerated. |
| II. Branch-Safe by Default | Pass | The export reads the schema of the requested branch through `get_branch_dep`, as `GET /api/schema`. No query. |
| III. Type Safety & Explicit Contracts | Pass | `SchemaExportMode` string enum. The exporter and the SDK client return the generated `InfrahubSchemaWrite`, never an untyped `dict`; the document is serialised with the values that were set only at the HTTP and YAML boundaries. Contracts in [contracts/](contracts/) before implementation. |
| IV. Test Discipline | Pass | Unit, component, functional and one end-to-end test without a browser (R14). The rule schemas reuse existing fixtures where one covers the rule (T010). |
| V. Query Performance & Efficiency | Pass | No database query. Processing is in memory and bounded by R1. |
| VI. Security & Input Boundaries | Pass | Read-only. Same access as `GET /api/schema` (D10). `mode` is validated by the enum. A 500 from a failed self-check does not include the schema. |
| VII. Simplicity & Maintainability | Pass | Reuses `SchemaBranch.process`, the write models and the existing schema API dependencies. The remove-and-restore loop (R1) replaces a rule list that drifted; see Complexity Tracking. |
| Ask First (root `AGENTS.md`, `backend/AGENTS.md`) | Pass | A new REST endpoint is an API change, and `backend/AGENTS.md` prefers GraphQL for new SDK needs. D11 chose REST because the schema read, check and load are REST and GraphQL has no query that returns the node schema. Damien Garros approved `GET /api/schema/export` as specified in [contracts/rest-schema-export.md](contracts/rest-schema-export.md) on 2026-10-27, in the implementation session. |

Re-check after Phase 1: unchanged. The design adds no table, no query, no setting and no dependency.

## Project Structure

### Documentation (this feature)

```text
dev/specs/infp-723-schema-export/
├── spec.md
├── plan.md                         # This file
├── research.md                     # Phase 0
├── data-model.md                   # Phase 1
├── quickstart.md                   # Phase 1
├── contracts/
│   ├── rest-schema-export.md       # GET /api/schema/export, load change
│   └── cli-schema-export.md        # infrahubctl and SDK client
├── checklists/requirements.md
└── tasks.md                        # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/infrahub/
├── api/schema.py                          # GET /api/schema/export, declared before /{schema_kind}
├── core/constants/__init__.py             # SchemaExportMode
├── core/schema/__init__.py                # SchemaRoot.infrahub_version (accepted, ignored)
└── core/schema/export/                    # new package
    ├── __init__.py
    ├── serializer.py                      # FULL document of the selected kinds from a SchemaBranch (R2, R3, R4, R5)
    ├── minimizer.py                       # BRIEF: remove, process in memory, restore until stable (R1)
    └── exporter.py                        # entry point: branch schema + namespaces + mode -> document

backend/tests/
├── unit/core/schema/export/
│   ├── schemas/                           # one small YAML schema per rule
│   ├── test_round_trip.py                 # models/base, models/examples, rule schemas, both modes
│   └── test_field_coverage.py             # FR-023
├── component/api/test_40_schema.py        # endpoint parameters, access, errors
└── functional/api/test_schema_export.py   # load into an empty database, US3, FR-015a, US4

tasks/backend.py                            # _sdk_root: infrahub_version on the write root

python_sdk/                                 # separate pull request on infrahub-develop
├── infrahub_sdk/schema/__init__.py         # export() calls the endpoint; old export code removed
├── infrahub_sdk/schema/export.py           # removed
├── infrahub_sdk/schema/generated/          # regenerated from tasks/backend.py
├── infrahub_sdk/ctl/schema.py              # --mode, --single-file, split by namespace
├── infrahub_sdk/ctl/schema_format.py       # FILE_ORDER gains infrahub_version
├── infrahub_sdk/ctl/utils.py               # VersionNotSupportedError without traceback
├── tests/unit/sdk/test_schema_export.py    # rewritten
├── tests/unit/ctl/                         # CLI tests for export
└── changelog/                              # added, removed

docs/docs/schema/export.mdx                 # new page, plus sidebar entry
dev/knowledge/backend/schema-export.md      # new knowledge file
changelog/                                  # added fragment
schema/openapi.json, frontend/app/src/shared/api/rest/types.generated.ts   # regenerated
```

**Structure Decision**: The export logic is a new package under `backend/infrahub/core/schema/`, next to
the processing it depends on. Following `dev/guidelines/backend/component-design.md`:

- `SchemaExportSerializer` builds the `FULL` document; it has no collaborators.
- `BriefSchemaMinimizer` receives in its constructor the serializer and a factory that returns a new
  `SchemaBranch` loaded with the internal schema and the core models. Its entry method takes the `FULL`
  document and the other user namespaces.
- `SchemaExporter` receives both in its constructor. Its entry method takes the branch schema, the
  namespaces and the mode.
- The API handler builds the exporter once per request from the registry, as the other schema handlers do.

## Delivery order

1. Generator change in this repository (`_sdk_root`), run `uv run invoke backend.generate`, and open the SDK
   pull request against `infrahub-develop` with the regenerated models, the client and CLI changes, and
   their tests (R13). It merges first.
2. Backend pull request: the export package, the endpoint, `SchemaRoot.infrahub_version`, the tests, the
   documentation and knowledge pages, the regenerated files, the changelog, and the bump of `python_sdk` to
   the merged SDK commit.

The two pull requests are prepared together, because the SDK's generated models come from this
repository's generator.

## Spec changes made during planning

- FR-012 and SC-001: "no warnings" becomes "no warnings other than the deprecation warnings for deprecated
  fields that the source schema contains" (research R6).
- "Not decided yet": the names (`mode`, `brief`, `full`, `infrahub_version`) are fixed (R7, R8); the load
  refuses a `FULL` change of a setting Infrahub cannot update (R10); NumberPool shorthand is not converted
  and `order_weight` is restored when processing does not reproduce it (R5, R6).
- Assumptions: the empty export and the unknown branch are now decided (contract).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `BRIEF` processes the candidate in memory and repeats until stable (R1) | Some derived values depend on order or on other values (dropdown colours, `human_friendly_id`, `order_weight`), so no per-field rule reproduces them. | A fixed rule list is what IFC-2964 reports as drifting from the schema model. |
