# Implementation Plan: GraphQL Query Report Introspection

**Branch**: `ifc-2504-graphql-query-report` | **Date**: 2026-04-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/ifc-2504-graphql-query-report/spec.md`

## Summary

Add `InfrahubGraphQLQueryReport` to the root GraphQL query schema. It accepts a raw GraphQL query string and synchronously returns `targets_unique_nodes: bool` — a flag indicating whether `InfrahubGraphQLQueryAnalyzer.query_report.only_has_unique_targets` is true for the submitted query. This allows users to determine artifact regeneration behavior without understanding Infrahub internals. The feature is purely additive: no new storage, no new schema nodes, no new external dependencies.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: graphene (existing), graphql-core (existing via infrahub_sdk)
**Storage**: N/A — report is computed on-the-fly, no persistence
**Testing**: pytest, component tests with TestContainers (Neo4j)
**Target Platform**: Backend GraphQL API layer
**Performance Goals**: Response in < 500ms under normal load (analysis is in-memory, no DB queries in the hot path)
**Constraints**: Must follow the `InfrahubStatus` pattern exactly; no new dependencies
**Scale/Scope**: Single new file + 3 targeted edits to existing files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Schema-Driven Integrity | ✓ PASS | No new graph schema nodes. No generated files touched. |
| II. Branch-Safe by Default | ✓ PASS | Branch resolved from `info.context` via existing `GraphqlContext.branch` — same path as all other queries. No branch-unsafe assumptions. |
| III. Type Safety & Explicit Contracts | ✓ PASS | graphene `ObjectType` with `required=True` field; resolver carries full type hints. |
| IV. Test Discipline | ✓ PASS | Component tests required for all acceptance scenarios and error edge cases (per FR-005 and spec). |
| V. Query Performance & Efficiency | ✓ PASS | No new database queries. Analysis runs in-memory on the parsed document. |
| VI. Security & Input Boundaries | ✓ PASS | User-supplied query string validated via `is_valid` before any analysis. Parse errors from malformed input caught at construction time. Error messages must not expose stack traces. |
| VII. Simplicity & Maintainability | ✓ PASS | Follows established `InfrahubStatus` pattern. Single responsibility, no abstractions beyond what two existing callers would justify. |

**Verdict**: All gates pass. No complexity justification required.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2504-graphql-query-report/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── graphql_query_report.graphql
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── infrahub/
│   └── graphql/
│       └── queries/
│           ├── graphql_query_report.py    # NEW — resolver + ObjectType
│           ├── __init__.py                # EDIT — export InfrahubGraphQLQueryReport
│           └── [existing files unchanged]
│   └── graphql/
│       └── schema.py                      # EDIT — register in InfrahubBaseQuery
└── tests/
    └── component/
        └── graphql/
            └── queries/
                └── test_graphql_query_report.py  # NEW — component tests

changelog/
└── [IFC-2504-number].added.md             # NEW — changelog fragment
```

**Structure Decision**: Backend-only, single project. Follows Option 1 (single project). All source changes are within `backend/infrahub/graphql/queries/`. Tests mirror the source structure under `backend/tests/component/graphql/queries/`.
