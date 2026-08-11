# Quickstart: Validate the `schema_differs_from_default_branch` field

Run guide to prove the feature end-to-end. Details of the contract live in
[contracts/graphql-branch-field.md](./contracts/graphql-branch-field.md); the data shape lives in
[data-model.md](./data-model.md).

## Prerequisites

- Backend deps: `uv sync --all-groups`
- Frontend deps: `cd frontend/app && pnpm install`
- Docker running (for component/integration tests via testcontainers)

## 1. Backend: parity and deprecation

Regenerate the GraphQL schema and confirm the diff is exactly the two new fields plus two
`@deprecated` annotations:

```bash
uv run invoke schema.generate-graphqlschema
git diff schema/schema.graphql
```

Run the branch GraphQL query tests (parity + field presence):

```bash
uv run pytest backend/tests/component/graphql/queries/test_branch.py -q
```

Run the schema-lifecycle integration tests that assert schema divergence after a load:

```bash
uv run pytest backend/tests/integration/schema_lifecycle -q
```

Expected: both `has_schema_changes` and `schema_differs_from_default_branch` return identical
values for every branch state (C1-C5, C7), and introspection reports `has_schema_changes` as
deprecated with a reason naming the replacement and Infrahub 1.14.0 (C6).

### Manual introspection check (optional)

Against a running instance, query:

```graphql
query {
  __type(name: "Branch") {
    fields(includeDeprecated: true) {
      name
      isDeprecated
      deprecationReason
    }
  }
}
```

Expect `has_schema_changes` with `isDeprecated: true` and the 1.14.0 reason, and
`schema_differs_from_default_branch` present and not deprecated. Repeat for `InfrahubBranch`.

## 2. Frontend: new field + copy

Regenerate types and run unit tests:

```bash
cd frontend/app
pnpm codegen
pnpm test
```

Expected: generated types carry `schema_differs_from_default_branch`; branch fixtures and tests
use the new field; no hand-written frontend code references `has_schema_changes`.

Manual UI check (branch views): load the branch list and a branch detail for a branch whose schema
differs from default. The badge and detail label appear in the same positions as before, now
reading as a difference from the default branch (e.g. "schema differs from default"), and the
underlying request selects `schema_differs_from_default_branch` (SC-003, SC-006).

## 3. Full local gate before pushing

```bash
uv run invoke format lint
uv run invoke backend.test-unit
cd frontend/app && pnpm biome:fix && pnpm test
/pre-ci
```

CI's `validate-generated-documentation` / schema-validate jobs fail if `schema/schema.graphql` or
the frontend generated types are stale, so ensure both regeneration steps above are committed.

## 4. Follow-up tickets (must exist before "done")

- SDK adoption of `schema_differs_from_default_branch` (OOS-001), shipped on a deliberate delay.
- Removal of `has_schema_changes`, pinned to the Infrahub 1.14.0 milestone (OOS-005).

## Success signals

- SC-001/SC-004: parity tests green; old field unchanged.
- SC-002: introspection shows deprecation + replacement + 1.14.0.
- SC-003/SC-006: UI uses new field, misleading copy gone.
- SC-005: changelog fragments (`.added`, `.deprecated`) present under `changelog/`.
