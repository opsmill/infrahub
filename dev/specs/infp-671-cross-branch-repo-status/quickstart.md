# Quickstart / Validation: Cross-branch Repository Status Query

**Branch**: `cross-branch-repo-status-infp-671` | **Date**: 2026-09-03

Scenarios derived from the spec's acceptance criteria and pinned behaviours. Each names the increment
in which it becomes verifiable. Contract details live in [contracts/](contracts/); shapes in
[data-model.md](data-model.md).

## Prerequisites

```bash
uv sync --all-groups
docker info                       # component tests start Neo4j via testcontainers
```

Automated runs:

```bash
uv run pytest backend/tests/unit/graphql/queries/test_repository_branch_status.py
uv run pytest backend/tests/component/graphql/queries/test_repository_branch_status.py
uv run pytest backend/tests/component/core/query/test_repository_branch_attributes.py   # increment B
uv run pytest backend/tests/query_benchmark/test_repository_branch_attributes.py         # increment B
uv run pytest backend/tests/component/git/test_utils.py                                  # increment C
uv run pytest backend/tests/component/computed_attribute/test_gather.py                  # increment C
uv run pytest backend/tests/integration_docker/test_computed_attributes.py               # increment C
uv run invoke schema.validate-graphqlschema
```

## Increment A: contract stub

### A1. The query exists and the frontend can generate types

1. `uv run invoke schema.generate-graphqlschema`; `git diff --stat schema/schema.graphql` shows the
   new root field and three types. `InfrahubBranch` is unchanged: T007 was dropped.
2. `cd frontend/app && pnpm codegen` succeeds and `git diff --stat src/shared/api/graphql/generated/`
   shows the new types.

**Expected**: the SDL matches `contracts/graphql-repository-branch-status.graphql`.

### A2. Row membership per kind

Fixture: one `CoreRepository`, one `CoreReadOnlyRepository`, branches `b-open`, `b-nosync`
(`sync_with_git=false`), `b-merged` (status `MERGED`), `b-deleting` (status `DELETING`), plus `main`.

**Expected**: for the read-write repository the rows are `main`, `b-open` and `count` is 2, every row
carrying `sync_with_git: true`; for the read-only repository the rows are `main`, `b-open`, `b-nosync`
and `count` is 3, with `b-nosync` carrying `sync_with_git: false`. The global branch never appears.

### A3. Paging, count and default order

Fixture: 12 syncing branches named out of alphabetical order plus `main`.

**Expected**: `limit: 5, offset: 0` returns `main` first then four names ascending; `count` is 13 on
every page; `offset: 10` returns the last three; `order` by `created_at` desc overrides the default.

### A4. Permission matrix (FR-012)

| Caller grant on `Core/Repository` view | Executed on `main` | Executed on a user branch |
| --- | --- | --- |
| `ALLOW_ALL` | rows | rows |
| `ALLOW_DEFAULT` + `ALLOW_OTHER` (two grants) | rows | rows |
| `ALLOW_DEFAULT` only | denied | denied |
| `ALLOW_OTHER` only | denied | denied |
| none | denied | denied |
| anonymous session, anonymous role grants `ALLOW_ALL` | rows | rows |
| anonymous session, no grant | denied | denied |

**Expected**: denial is a `PermissionDeniedError` in `errors`, with `data` null; never a trimmed set.
For the "none" row, `CountingInfrahubDatabase` records no repository lookup: denial happens before it.

### A5. Not found and argument validation

**Expected**: an unknown `id` fails like other repository lookups; the repository's `name` passed as
`id` resolves; `limit: 0` and `offset: -1` fail validation.

### A6. `ref` dispatch and no bus traffic

**Expected**: one document requesting `ref` returns null on the read-write kind and a value on the
read-only kind; `TestHelper.get_message_bus_recorder().messages` is empty after every document.

### A7. Stub visibility

**Expected**: the API log carries one warning naming the stub module when the schema is built, not
one per call; the root field description in `schema/schema.graphql` contains "preview" and names
neither a ticket nor a delivery increment; values are identical across two calls.

## Increment B: graph read

### B1. Inheritance at the fork point

1. Import commit `c1` on `main`; create `b1`; import `c2` on `main`; create `b2`.
2. Query.

**Expected**: `main` shows `c2` (own value), `b1` shows `c1` (inherited), `b2` shows `c2` (inherited).
`updated_at` on `b1` equals `main`'s write time for `c1`.

### B2. Own import and rebase

1. Continue from B1; import `c3` on `b1`; rebase `b2`.

**Expected**: `b1` shows `c3` with `own_values_only: true` keeping it; `b2` still shows `c2` unless a
newer import landed on `main` before the rebase, in which case it shows that one.

### B3. Never imported anywhere

**Expected**: a fresh repository with no import returns rows whose `commit.value` is null and
`sync_status.value` is `unknown`; no error.

### B4. Attribute filter and count (SC-003)

Fixture: 200 syncing branches, 3 with `sync_status = error-import` written on their own branch.

**Expected**: `sync_status__value: "error-import"` returns exactly those 3 rows and `count: 3` on one
page; `own_values_only: true` alone returns `main` plus the branches that wrote their own value.

### B5. Query count independent of branch count (FR-007, SC-002)

Run the same document through `CountingInfrahubDatabase` against fixtures of 5 and 200 branches.

**Expected**: `sum(counting_db.query_counts.values())` is equal for both; `rows_for("repository-branch-attributes")`
grows with the branch count while `count_for` does not.

### B6. Selection-aware attribute read (FR-008)

Request only `commit`.

**Expected**: the attribute-name set handed to `RepositoryBranchAttributesReader.read` is `{"commit"}`
and `sync_status` is absent from the statement parameters. Observed by constructing the resolver with a
recording source, not by patching.

### B6a. Differential check against the standard read

For every branch in the shared fixture, including one legacy branch saved with `is_isolated=false`,
compare the primitive's `commit` value and `updated_at` with `NodeManager.get_one(branch=...)`.

**Expected**: identical for every branch. This is the test that keeps the primitive's operators in
step with `Branch.get_query_filter_path`.

### B7. Direct primitive call (FR-009)

**Expected**: the example in `contracts/core-primitive.md` passes as a component test with two branch
names and one attribute.

### B8. Documentation

**Expected**: `uv run invoke docs.validate` passes after `uv run invoke docs.generate`; the new section
in `docs/docs/git-integration/branch-synchronization.mdx` shows the example document from the contract.

## Increment C: periodic sync

### C1. Bounded read

Fixture: one repository, 200 branches, `CountingInfrahubDatabase`.

**Expected**: `count_for("repository-branch-attributes") <= ceil(200 / 100)`; the `-global-` key is
absent from `RepositoryData.branches`; `branch_info[registry.default_branch].internal_status` and
`get_staging_branch()` behave as before; `RepositoryData.repository.default_branch`, `.location` and
`.ref` carry the default branch's values; the computed-attribute gather resolves `branches[branch.name]`
for every non-global branch, in-process and on the distributed stack.

### C2. Sync flow unchanged in outcome

Run `sync_remote_repositories` against the existing component fixtures in
`backend/tests/component/git/`.

**Expected**: the same repositories are bootstrapped and synced as before the change; only the read
path differs.

## Manual check in a dev stack (any increment)

```bash
uv run invoke dev.start
uv run invoke dev.load-infra-schema
uv run invoke dev.load-infra-data
```

Open `http://localhost:8000/graphql`, paste the example document from the contract with the id of the
demo repository, and confirm rows arrive for every branch created in the demo data. Create a branch
with `sync_with_git: false` and confirm it disappears from the rows of the read-write repository.
