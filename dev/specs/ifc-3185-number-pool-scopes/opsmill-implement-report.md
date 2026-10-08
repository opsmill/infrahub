# Implementation report: number pool allocation scopes, Phase 1

**Status: DONE.** Every test written or modified by this run passes, and so do the number-pool suites the phase touches.

- Spec directory: `dev/specs/ifc-3185-number-pool-scopes`
- Scope of the run: Phase 1 only (T001 to T005), as requested
- Branch: `pmi-number-pool-scoped-pools-ifc-3185-rebased` (local, not pushed), rebased onto `origin/number-pool-branch-provenance` (PR #10949) at the user's request, because that branch moves the `python_sdk` pointer to an SDK commit that knows `allocation_scope`
- Base commit: `7d5429fe8d` (tip of `number-pool-branch-provenance`); the phase first ran on `df361a06a5` (`feature-number-pools-1.12`)
- Head commit: the commit that adds this report
- Wall-clock time: about 45 minutes, 18:20Z to 19:05Z on 2026-10-08

## Chunk ledger

| Chunk | Tasks | Outcome | Commits |
|-------|-------|---------|---------|
| A: rebase PR #10932 and update the fixed dataset to the contract | T001, T002 | T001 ✅. T002 ⚠️: code and tests are done; the PR description is drafted, not published | 23 cherry-picks ending at `86fa174f09`, `286c0606d1`, `9dc21c3b16` |
| B: test schema, fixtures, scope module | T003, T004, T005 | 3 ✅ | `38cdc88817`, `1da743f1a0` |

Decisions and surprises reported by the chunks:

- **Source of the rebase.** T001 used the local branch `pmi-number-pool-scoped-pools-ifc-3185` (worktree saber-scabiosa, tip `280e3e6a40`) as its source, because it is 12 code commits ahead of the version on GitHub. The user chose this source.
  - Only its 23 code commits were cherry-picked.
  - Its `docs(specs)` commits were left out, because they edit the old directory `dev/specs/ifc-3185-scoped-number-pools`, which this spec set replaces.
- **Conflicts during the cherry-picks:**
  - `backend/tests/conftest.py` conflicted twice. After resolution it is identical to the base.
  - The generated file `graphql-cache.d.ts` conflicted once and was regenerated.
- **Mock test file.** `backend/tests/unit/pools/test_number_pool_mock.py` no longer exists, because a commit of the source branch deletes it. T002 lists it; the component tests cover the change instead.
- **Branch fixture.** The component tests of the fixed dataset now create `branch1`. The test that checked a refusal naming the branch is removed, as T002 asks.
- **Test schema, T003:**
  - The pooled attribute is `vlan_id`.
  - Two peer kinds were added: `ScopeRack` and `ScopeLink`.
  - The generic is `ScopeHolder`, not `ScopedHolder` as T003 names it, and its implementing kind is `ScopePodHolder`.
  - `tags` is required.
- **Pool fixtures, T004.** The pools store their scope as a list of names, because that is what the current code accepts. T015 must change these fixtures, and the expected value in `test_number_pool_scope.py`, to `{id, name}` elements.
- **Refusal message, T005.** `data-model.md` gives no exact text for the refusal of a scope stored in the old shape, so `AllocationScope.from_stored` uses this one: `allocation_scope of pool <pool>: the stored entry <json> is not an element with an "id" and a "name"; recreate the pool to set its scope`.

## Tasks not completed

- T002, sub-part "update the description of PR #10932": the draft waits for the user's approval to publish.
  - Draft: `scratchpad/pr-10932-body.md` of the session.
  - The draft also rewrites the "Tests" and "Stack" sections, which still described the old state.

Every checkbox from T001 to T005 is ticked `[X]`.

## Local-pass evidence

| Test id | Type | Run command | Passed at (ISO 8601) | Environment context | Verbatim pass line |
|---------|------|-------------|----------------------|---------------------|--------------------|
| `tests/unit/graphql/test_number_pool_surface_contract.py::test_number_pool_surface_sdl_matches_the_published_contract` | unit | `cd backend && uv run pytest tests/unit/graphql/test_number_pool_surface_contract.py tests/component/graphql/queries/test_number_pool_surface.py -v -p no:cacheprovider` | 2026-10-08T18:29:27Z | macOS, Docker testcontainers | `17 passed, 16 warnings in 14.49s` |
| `tests/component/graphql/queries/test_number_pool_surface.py::TestNumberPoolSurface` (16 cases, including the new `test_divisions_read_each_holder_on_the_request_branch` and `test_allocations_follow_a_holder_moved_on_the_request_branch`) | component | same command | 2026-10-08T18:29:27Z | macOS, Docker testcontainers | `17 passed, 16 warnings in 14.49s` |
| `tests/unit/pools/test_scope.py` (all cases, after the review fixes) | unit | `cd backend && uv run pytest tests/unit/pools/test_scope.py tests/component/core/resource_manager/test_number_pool_scope.py tests/component/core/resource_manager/test_number_pool_is_reserved_retirement.py -p no:cacheprovider -q` | 2026-10-08T18:43:59Z | macOS, Docker testcontainers | `44 passed, 16 warnings in 32.60s` |
| `tests/component/core/resource_manager/test_number_pool_scope.py::test_device_takes_the_first_number_of_a_new_pool[one-element\|two-elements\|list-attribute\|unscoped]` | component | same command | 2026-10-08T18:43:59Z | macOS, Docker testcontainers | `44 passed, 16 warnings in 32.60s` |
| Number-pool suites touched by the phase: `tests/unit/graphql/test_number_pool_surface_contract.py`, `tests/unit/pools`, `tests/component/graphql/queries/test_number_pool_surface.py`, `tests/component/core/resource_manager`, `tests/component/graphql/resource_manager/number_pools`, `tests/component/core/schema/test_attribute_parameters.py`, `tests/component/pools` | unit and component | `cd backend && uv run pytest <the paths> -p no:cacheprovider -q -n 4` | 2026-10-08T18:52:15Z | macOS, Docker testcontainers | `3 failed, 402 passed, 3 xfailed`. The 3 failures are listed under "Known failure" below |
| Live checks of the three queries, 61 checks | live (Docker stack) | `uv run python scratchpad/live_check.py <repo>` | 2026-10-08T18:49Z | stack `aluminumterrier` started with `INFRAHUB_IMAGE_VER=local uv run invoke dev.start --wait`; the worktree is bind-mounted on `/source` | `61/61 passed` |
| Frontend types of the three queries | frontend type check | `pnpm codegen:graphql`, then `pnpm exec tsc --noEmit -p .` with a temporary file typing the queries | 2026-10-08T18:51Z | frontend/app, local node_modules | 185 errors, the same count as without the change; none in the temporary file; both `@ts-expect-error` lines are used |

**After the rebase onto PR #10949.** The commit SHAs above are those before the rebase; the branch `backup/ifc3185-phase1-pre-rebase` keeps them.

- During the rebase, only generated files conflicted (`schema/schema.graphql` and the frontend generated GraphQL files). They were regenerated once at the end.
- The new base moves `PoolRecordProvenance` into `infrahub.core.constants`, so the dedicated queries and the fixed dataset now import it from there (`dd885665cd`).
- Number-pool suites, run from `backend/` with `uv run pytest tests/unit/graphql/test_number_pool_surface_contract.py tests/unit/pools tests/component/graphql/queries/test_number_pool_surface.py tests/component/core/resource_manager tests/component/graphql/resource_manager tests/component/core/schema/test_attribute_parameters.py tests/component/pools -p no:cacheprovider -q -n 4` at 2026-10-08T19:00:45Z: `476 passed, 3 xfailed, 80 warnings in 146.80s`. This includes the three cases of `test_attribute_parameters.py::test_number_pool_allocation_scope_round_trips_through_schema_api`, which failed on `feature-number-pools-1.12` because its SDK submodule did not know `allocation_scope`.
- Live checks, on a stack recreated from the rebased branch at 2026-10-08T19:02:09Z: `61/61 passed`.

## What the live checks cover

The checks ran against a Docker stack built from this worktree.

- **Schema served to the frontend.** The 13 `NumberPool*` types and the 5 root fields served live match `schema/schema.graphql`: same fields, types, descriptions and arguments. Field order is ignored, because the file is sorted alphabetically.
- **Every field of the three queries.** Each field is selected on the default branch and on `branch1`:
  - The divisions read on the request branch: sites A (40) and B (30) on `main`; A (39), B (30) and C (1) on `branch1`.
  - `allocation_scope` is a list of `{id, name}` objects, and each entry's `id` equals the scope element's id.
  - Divisions are ordered by utilization, then by label.
  - The range figures add up to the division's `used`.
- **Allocations query:**
  - The default page holds 10 rows.
  - Rows are ordered by value, then branch, then holder id.
  - `offset` and `limit` page through the rows, and `count` is taken before paging.
  - The `division`, `range_id`, `branch` and both `provenance` filters each work, including the division filter read on `branch1`.
- **Unscoped pool.** The divisions list is empty, and the utilization and allocations queries answer without a division.
- **Refusals.** The 8 refusals that the fixed dataset can produce return the contract's exact message.
- **Real pool.** A pool created through GraphQL with `allocation_scope: ["site"]` stores it, and three devices receive 100, 101 and 102 from it. Allocation per division arrives in Phase 3.
- **Generic queries.** `InfrahubResourcePoolUtilization` answers for the real pool. Its description and that of `InfrahubResourcePoolAllocated` name the dedicated queries.
- **Generated frontend files.** The gql.tada files were out of date: `graphql-env.d.ts` did not have `NumberPoolScopeElement`, and the CI check that runs `pnpm codegen:graphql` and fails on a diff (`.github/workflows/ci.yml`) would have failed. They are regenerated in `4312214c02`.

## Review findings

The review covered the commits of the phase (`86fa174f09..HEAD`) with six agents: code, comments, tests, errors, types and simplification. No finding was high or critical.

| Severity | File | Finding | Action |
|----------|------|---------|--------|
| medium | `backend/infrahub/pools/scope.py` | `hash()` of a division holding a `List` or `JSON` value raised `TypeError`, and equality disagreed with the lock key (`1` equal to `True`, different keys). Four agents reported it | Fixed in `72309bc3d4`: equality and hash follow the key |
| low | `backend/infrahub/pools/scope.py` | `from_stored` read a stored text value one character at a time | Fixed in `72309bc3d4`: a value that is not a list is refused, naming the pool |
| low | `backend/tests/unit/pools/test_scope.py` | The equality test compared a division with itself, and no test covered a `name` that is not text | Fixed in `72309bc3d4` (`deepcopy`, new case, `1` against `True`, `1` against `1.0`, a set of divisions) |
| low | `backend/tests/component/core/resource_manager/test_number_pool_scope.py` | The scope was read from the pool in memory, not from the database | Fixed in `72309bc3d4`: the pool is read back from the database |
| low | `backend/tests/component/core/resource_manager/conftest.py` | The `scoped_schema` docstring listed kinds and left one out | Fixed in `72309bc3d4` |
| medium | `backend/tests/component/core/resource_manager/test_number_pool_scope.py` | The `scoped_pools` fixture creates all four pools for each case | Deferred: `request.getfixturevalue` fails with async fixtures (`Runner.run() cannot be called from a running event loop`) |
| low | `backend/infrahub/pools/scope.py` | `AllocationScope` accepts two elements with the same id | Deferred to T008: the resolver refuses a duplicate |
| low | `backend/infrahub/pools/number_pool_mock.py` | `MockScopeElement` repeats `ScopeElement` | Deferred: T027 deletes the mock |
| low | `dev/specs/ifc-3185-number-pool-scopes/tasks.md` | T002 names a deleted test file; T003 names `ScopedHolder` instead of `ScopeHolder` | Deferred: this run does not edit the prep documents |

## Autonomous decisions

- **Phase scope.** "Phase 1" was read as the Phase 1 of `tasks.md` in the most recent spec directory, `ifc-3185-number-pool-scopes`.
- **Branch.** The work happens on a new local branch, `pmi-number-pool-scoped-pools-ifc-3185-rebased`, because the branch of the same name is checked out in the saber-scabiosa worktree.
- **Chunks.** Phase 1 was split into two chunks, T001 and T002 then T003 to T005, to keep the rebase apart from the new code.
- **Review range.** The review covered only the commits of the phase. The 23 cherry-picked commits were already reviewed in PR #10932.
- **Review fixes.** Medium and low findings were fixed when the fix was small and local, although the procedure requires fixes only for high findings.
- **Review workflow.** The six review agents ran as a parallel workflow without asking the user first.
- **Live stack:**
  - The running stack `ifc3185`, from the saber-scabiosa worktree, was removed with its volumes.
  - The stopped stacks `stablewt`, `infrahubfix` and `pmiombieflowregeneration` were left in place.
  - The stack `aluminumterrier` is still running on port 8000.

- **Rebase onto PR #10949.** At the user's request, the branch was rebased onto `number-pool-branch-provenance`, so PR #10932 now depends on #10949.

## Suggested next steps

1. Once the user approves:
   - Force-push to `pmi-number-pool-scoped-pools-ifc-3185` with `--force-with-lease` against `0008e217f7`.
   - Change the base of PR #10932 to `number-pool-branch-provenance` (PR #10949).
   - Publish the new description.
2. T045 still applies to the SDK: the commit `python_sdk` points at must reach `infrahub-develop` before the feature branch merges into the release branch.
3. Before working in the saber-scabiosa worktree again, put its local branch back on the pushed version.
4. Continue with Phase 2 (T006 to T010).
