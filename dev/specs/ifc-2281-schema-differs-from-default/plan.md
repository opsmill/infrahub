# Implementation Plan: Rename the misleading `has_schema_changes` branch field

**Branch**: `schema-differs-from-default-ifc-2281` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/ifc-2281-schema-differs-from-default/spec.md`

## Summary

Introduce a clearly named branch field, `schema_differs_from_default_branch`, that
returns exactly the value the existing `has_schema_changes` field returns (whether a
branch's schema hash differs from its origin/default branch), deprecate the old field
with a machine-readable reason naming the replacement and the 1.14.0 removal version,
and migrate Infrahub's own backend and frontend consumers onto the new name. This is a
naming, deprecation, and first-party consumer-migration change: the underlying
divergence computation is unchanged, both fields coexist through the deprecation window,
and the SDK is deliberately deferred to a follow-up ticket.

Technical approach: add a delegating `schema_differs_from_default_branch` property to the
`Branch` model (old property kept, delegating to it), expose it as a new graphene field
on both the legacy `Branch` type and the `InfrahubBranch` type (which resolve fields from
same-named model properties), add `deprecation_reason` to the existing `has_schema_changes`
graphene fields, repoint the two internal backend readers and all frontend queries/UI copy,
update tests for parity, regenerate `schema/schema.graphql` and the frontend generated types,
and add changelog fragments plus follow-up tracking tickets (SDK adoption, 1.14.0 removal).

## Technical Context

**Language/Version**: Python 3.14 (backend), TypeScript 5.9 / React 19.2 (frontend)

**Primary Dependencies**: graphene (GraphQL), FastAPI; frontend uses Apollo/urql generated
types via `pnpm codegen`

**Storage**: Neo4j. No schema, migration, or query changes - the field reads a value already
computed from cached schema hashes on the branch model.

**Testing**: pytest (backend unit/component/integration), Vitest (frontend unit), Playwright
(frontend E2E)

**Target Platform**: Linux server backend + web frontend

**Project Type**: Web application (backend + frontend), monorepo

**Performance Goals**: No change. The new field delegates to the existing property; no new
database access is introduced.

**Constraints**: Non-breaking during the deprecation window - `has_schema_changes` must keep
returning identical values for as long as both fields exist (SC-001, SC-004). Removal is
pinned to Infrahub 1.14.0 (against the current 1.11 dev line).

**Scale/Scope**: Small, well-bounded. One model property, two graphene types, four mutation
payload types (via shared `BranchType`), two internal backend readers, ~4 frontend GraphQL
operations, 2 UI copy strings, and their tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Schema-Driven Integrity**: PASS. Generated artifacts (`schema/schema.graphql`, frontend
  `src/shared/api/graphql/generated/`) are regenerated via `uv run invoke schema.generate-graphqlschema`
  and `cd frontend/app && pnpm codegen`, never hand-edited. No data-schema change.
- **II. Branch-Safe by Default**: PASS. No new queries; the underlying property is already
  branch-aware and unchanged. No merge/rebase behavior change (the two internal readers in
  `core/branch/tasks.py` keep identical semantics, only the property name they read changes).
- **III. Type Safety & Explicit Contracts**: PASS. New property is typed `-> bool`; the GraphQL
  contract is defined before implementation (see `contracts/`); frontend consumes generated types.
- **IV. Test Discipline**: PASS with note. Existing backend GraphQL/lifecycle tests and frontend
  fixtures are updated; a parity test asserting both fields agree is added. US3 is user-facing
  (UI copy), so frontend unit/component coverage is updated; an E2E is added only if an existing
  branch-view Playwright spec covers this indicator (no behavior change, copy + field source only).
- **V. Query Performance & Efficiency**: PASS. No new or modified queries.
- **VI. Security & Input Boundaries**: PASS. No new input boundary; read-only field.
- **VII. Simplicity & Maintainability**: PASS. Old property delegates to the new one (single
  source of computation, no duplication). Follows the existing `is_isolated` deprecation pattern
  rather than introducing new deprecation infrastructure.

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/ifc-2281-schema-differs-from-default/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── graphql-branch-field.md
├── checklists/
│   └── requirements.md  # Pre-existing
└── tasks.md             # Phase 2 output (/speckit-tasks - NOT created here)
```

### Source Code (repository root)

```text
backend/infrahub/
├── core/branch/
│   ├── models.py                       # Add schema_differs_from_default_branch property (delegates); keep has_schema_changes
│   └── tasks.py                        # Repoint the two internal readers (lines ~204, ~232) to the new property
└── graphql/
    ├── types/branch.py                 # Add new field on BranchType + InfrahubBranch; add deprecation_reason to has_schema_changes
    ├── queries/branch.py               # No change expected (field selection is generic)
    └── mutations/branch.py             # No change expected (payloads use shared BranchType.to_graphql_flat)

frontend/app/src/entities/branches/
├── api/
│   ├── get-branches-from-api.ts        # Request new field
│   ├── get-branch-details-from-api.ts  # Request new field
│   ├── create-branch-from-api.ts       # Request new field
│   ├── rebase-branch-from-api.ts       # Request new field
│   └── branch.mappers.ts               # Map new field
├── domain/model/branch.ts              # Rename field on BranchListItem / BranchDetail
├── domain/use-cases/create-branch.ts   # Default value key rename
└── ui/
    ├── branch-list-item/branch-schema-changes-badge.tsx   # Copy: "schema updated" -> differs-from-default wording
    ├── branch-list-item/branch-list-item.tsx              # Field reference
    ├── branches-table/cells/branch-name-cell.tsx          # Field reference
    ├── branches-to-select-options.ts                      # Field reference
    └── branch-details/branch-attributes.tsx               # Copy: "Has schema changes" label -> differs-from-default wording

schema/schema.graphql                   # Regenerated (Branch + InfrahubBranch types)
frontend/app/src/shared/api/graphql/generated/   # Regenerated (types.ts et al.)
changelog/                              # +schema-differs-from-default-branch.added.md, .deprecated.md
```

**Structure Decision**: Web application (Option 2). The change threads through the existing
backend branch model + GraphQL layer and the frontend `entities/branches` feature slice; no new
directories or modules are introduced.

## Complexity Tracking

> No Constitution Check violations. Section intentionally empty.
