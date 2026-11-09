# Phase 0 Research: Rename the misleading `has_schema_changes` branch field

All spec items were fully specified; there were no `NEEDS CLARIFICATION` markers. Research
here grounds the plan in the actual code so Phase 1 and tasks reference real locations.

## Decision 1: Where the value is computed (backend model property)

- **Decision**: Add a new `schema_differs_from_default_branch` `@property` to the `Branch`
  model that contains the computation, and rewrite the existing `has_schema_changes` property
  to delegate to it (`return self.schema_differs_from_default_branch`).
- **Rationale**: FR-009 requires a new backend property returning the same value, the old one
  retained delegating to the same computation. Delegation keeps a single source of truth
  (Constitution VII) and guarantees parity (FR-002/SC-001) by construction.
- **Location**: `backend/infrahub/core/branch/models.py:119-131`. The property compares
  `self.schema_hash.main` against `origin_branch.schema_hash.main`, returning `False` when
  either hash is missing - this exactly matches the spec edge cases (default branch, no schema
  hash, origin unresolved all return `False`).
- **Alternatives considered**: Rename the property outright and alias the old name - rejected
  because FR-003 requires the old name to keep working unchanged through the deprecation window,
  and the spec forbids logic changes (OOS-003).

## Decision 2: Internal backend consumers

- **Decision**: Repoint the two internal readers to the new property name.
- **Rationale**: FR-009 requires Infrahub's own backend consumers to read through the new name.
- **Locations**: `backend/infrahub/core/branch/tasks.py:204` and `:232` (both in the
  `rebase_branch()` flow, gating schema validation and migration). Semantics are identical since
  both properties return the same value.

## Decision 3: GraphQL exposure and deprecation

- **Decision**: On both `BranchType` (legacy `Branch`) and `InfrahubBranch`, add a new graphene
  field `schema_differs_from_default_branch` matching the existing shape (`Boolean(required=False)`
  on `BranchType`; `Field(NonRequiredBooleanValueField, required=False)` on `InfrahubBranch`), and
  add `deprecation_reason=...` to the existing `has_schema_changes` fields on both types.
- **Rationale**: FR-001 requires the field on both query types and in mutation payloads; FR-004
  requires the deprecation on both types. Graphene resolves each field from a same-named model
  property via `to_graphql_flat`/`to_graphql`, so the new graphene field name must match the new
  model property name (Decision 1) - this is exactly why FR-009 says renaming the GraphQL field
  alone is insufficient.
- **Locations**: `backend/infrahub/graphql/types/branch.py:32` (BranchType field) and `:83`
  (InfrahubBranch field). Mutation payloads (`BranchCreate`, `BranchRebase`, `BranchValidate`,
  `BranchMerge` in `graphql/mutations/branch.py`) all return the shared `BranchType` and serialize
  via `to_graphql_flat(fields=...)`, so they pick up the new field with no edit to the mutation code.
- **Deprecation pattern**: Copy the existing `is_isolated` pattern
  (`backend/infrahub/graphql/types/branch.py:31` and `:80-82`):
  `Field(..., deprecation_reason="...")`. The surfaced string is `@deprecated(reason: "...")` in
  the introspectable schema (SC-002).

## Decision 4: Deprecation-reason wording (removal version)

- **Decision**: Use a single deprecation reason that both names the replacement and states the
  removal version, e.g.:
  `"Use schema_differs_from_default_branch instead. has_schema_changes is scheduled for removal in Infrahub 1.14.0."`
  Define it once as a module-level constant in `graphql/types/branch.py` and apply it to both types.
- **Rationale**: FR-005 mandates the removal version be part of this single message, not a separate
  notice. Existing Infrahub deprecations do not usually carry explicit versions, but the spec
  explicitly requires it here; the metadata-field pattern (a shared `_DEPRECATION` constant reused
  across types) is the precedent for keeping the string identical on both types.
- **Alternatives considered**: Two separate strings on the two types - rejected (drift risk,
  FR-004/FR-005 want a consistent single message).

## Decision 5: Frontend migration and copy

- **Decision**: Point all four branch GraphQL operations at `schema_differs_from_default_branch`,
  rename the field through the mappers and domain models, and update the two UI strings.
- **Rationale**: FR-006, SC-003, SC-006 require the UI to consume the new field and drop the
  misleading copy while keeping the same badge/label positions.
- **Locations & current copy**:
  - Queries/mutations: `entities/branches/api/{get-branches,get-branch-details,create-branch,rebase-branch}-from-api.ts`.
  - Mappers: `entities/branches/api/branch.mappers.ts:44,65`.
  - Domain models: `entities/branches/domain/model/branch.ts:26,35`; use-case default
    `domain/use-cases/create-branch.ts:31`; select options `ui/branches-to-select-options.ts:11`.
  - Badge current text: `ui/branch-list-item/branch-schema-changes-badge.tsx` renders literal
    `schema updated`. Used from `branch-list-item.tsx:46` and `branches-table/cells/branch-name-cell.tsx:51`.
  - Detail label current text: `ui/branch-details/branch-attributes.tsx:58` renders `Has schema changes`.
- **Proposed copy** (short, fits existing badge/label layout per FR-006): badge
  `schema differs from default`; detail label `Schema differs from default branch`. Final wording
  is a small product-copy choice, not a blocker.

## Decision 6: Generated artifacts

- **Decision**: Regenerate rather than hand-edit.
- **Backend**: `uv run invoke schema.generate-graphqlschema` runs
  `uv run infrahub dev export-graphql-schema --out schema/schema.graphql`. Current field locations:
  `schema/schema.graphql:238` (Branch), `:8832` (InfrahubBranch). `schema/openapi.json` has no
  reference (branch schema-divergence is GraphQL-only) - no OpenAPI regen needed for this field.
- **Frontend**: `cd frontend/app && pnpm codegen` regenerates
  `src/shared/api/graphql/generated/types.ts` (Branch at ~L278, InfrahubBranch at ~L18156) and the
  companion `.d.ts` files. CI (`validate-generated-documentation` / `docs.validate` and the schema
  validate task) fails if these are stale.

## Decision 7: Changelog

- **Decision**: Add two towncrier fragments under `changelog/`: one `.added` (new field) and one
  `.deprecated` (old field deprecated + 1.14.0 removal). Naming: `+<identifier>.<type>.md`
  (`orphan_prefix = "+"`), e.g. `+schema-differs-from-default-branch.added.md` and
  `+schema-differs-from-default-branch.deprecated.md`. Fragment content must not reference ticket IDs.
- **Rationale**: FR-007/SC-005. Towncrier config in `pyproject.toml` supports both `added` and
  `deprecated` types.

## Decision 8: Tests

- **Decision**: Update existing assertions to the new field and add a parity assertion that both
  fields return identical values while both exist.
- **Locations**:
  - Backend component: `backend/tests/component/graphql/queries/test_branch.py:101,120,129`.
  - Backend integration (schema lifecycle): `test_migration_relationship_branch.py:289`,
    `test_schema_migration_branch.py:238`, `test_migration_attribute_branch.py:266`,
    `test_unique_field_updates.py:308,404`, plus fixtures in `backend/tests/conftest.py`.
  - Frontend fixtures/tests: `tests/fake/branch.ts:12` and
    `src/shared/components/form/utils/getFormFieldsFromSchema.test.ts:503,555,607,659`.
- **Rationale**: FR-010, SC-001/SC-004.

## Decision 9: Out-of-scope confirmation

- **Confirmed separate**: `MergeSchemaAnalyzer.has_schema_changes()` in
  `backend/infrahub/core/merge/schema_analyzer.py:82-92` (consumed by `graph_merger.py:122` and
  `orchestrator.py:119`) is a diff-based async method, unrelated to the branch property. Per
  OOS-004 it MUST NOT be renamed.
- **SDK**: `infrahub_sdk/branch.py` / `ctl/branch.py` consume `has_schema_changes` but are OOS-001;
  a follow-up ticket must exist before this feature is done.
- **Removal ticket**: OOS-005 requires a separate 1.14.0-pinned removal ticket to exist before done.
