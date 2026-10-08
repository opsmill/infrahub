# Implementation report: number pool allocation scopes, Phase 1

**Status: DONE.** Every test written or modified by Phase 1 passes, and so do the number-pool suites the phase touches.

- Spec directory: `dev/specs/ifc-3185-number-pool-scopes`
- Scope: Phase 1 only (T001 to T005), plus the changes that followed on the same pull request (review fixes, the shared provenance enum)
- Branch: `pmi-number-pool-scoped-pools-ifc-3185`, the head of PR #10932
- Base: `number-pool-branch-provenance` (PR #10949). PR #10932 is the bottom of stack #10973; PR #10950 (`ifc-3348-allocated-scope-validation`) sits on top of it.
- Head commit: the commit that adds this report

## History of the branch

The phase first ran on `feature-number-pools-1.12` and produced about 30 commits. Three operations then rewrote that history, so the SHAs recorded during the run no longer exist on the branch:

1. **Rebase onto PR #10949**, at the user's request. PR #10949 moves the `python_sdk` submodule to an SDK commit that knows `allocation_scope`.
   - Only generated files conflicted, and they were regenerated.
   - The new base moves `PoolRecordProvenance` into `infrahub.core.constants`, so the dedicated queries and the fixed dataset import it from there.
2. **Curation** of the 33 commits into 11, with an identical final tree.
3. **Shared provenance enum.** The dedicated queries return `PoolRecordProvenance`, the enum that `InfrahubResourcePoolAllocated` already returns, instead of a second enum `NumberPoolProvenance` with the same values. The values `ALLOCATED` and `PROVIDED` do not change. A client that names the type in a query variable must use the new name.

Commits on the branch, from the base up:

| Commit | Content | Tasks |
|--------|---------|-------|
| `8a00d115d2` | Test of the `allocation_scope` round trip through the schema API | from PR #10932 |
| `0262368806` | The fixed number-pool dataset | from PR #10932 |
| `4a908acf60` | The three dedicated queries served from the fixed dataset, with their component tests | from PR #10932 |
| `51fbf771a0` | SDL snapshot of the dedicated queries | from PR #10932 |
| `135a7a3e80` | Regenerated GraphQL schema and frontend types | from PR #10932 |
| `ed95a3b9f0` | Scope elements returned as `{id, name}`, divisions read on the request branch | T002 |
| `58fe591fe6` | Regenerated GraphQL schema and frontend types | T002 |
| `a3ff2e88c7` | `backend/infrahub/pools/scope.py` and its unit tests | T005 |
| `df61c54fac` | Scoped test schema, scoped pool fixtures, smoke test | T003, T004 |
| `ffdb00098d` | `tasks.md`, `spec.md`, `plan.md` and `quickstart.md` record what Phase 1 delivered | — |
| `5cef3a1c0f` | First version of this report | — |
| `67b607b03f` | The shared provenance enum | — |
| `a59fd8bc90` | Regenerated GraphQL schema and frontend types | — |
| `7d7e4e0c94` | The contract uses the shared provenance enum | — |

T001 has no commit of its own: the rebase of PR #10932 is the base of this table, and the deletion of `test_pool_scope.py` disappeared with the curation because the file and its deletion cancel out.

## Decisions taken during the phase

- **Source of the rebase (T001).** The local branch `pmi-number-pool-scoped-pools-ifc-3185` of the saber-scabiosa worktree was 12 code commits ahead of the version on GitHub. The user chose it as the source. Only its code commits were kept; its `docs(specs)` commits edited the old directory `dev/specs/ifc-3185-scoped-number-pools`, which this spec set replaces.
- **Mock test file (T002).** `backend/tests/unit/pools/test_number_pool_mock.py` was already deleted on the source branch. The component tests of the dedicated queries cover the fixed dataset instead.
- **Branch fixture (T002).** The component tests of the fixed dataset create `branch1`. The test of the refusal that named the branch is removed, as T002 asks.
- **Test schema (T003).**
  - The pooled attribute is `vlan_id`.
  - The peer kinds are `ScopeRack` and `ScopeLink`.
  - The generic is `ScopeHolder` (constant `SCOPED_HOLDER`), and its implementing kind is `ScopePodHolder`.
  - `tags` is required, because a scope element must be required.
- **Pool fixtures (T004).** The pools store their scope as a list of names, because the current code stores what it receives. T015 changes these fixtures, and the expected value in `test_number_pool_scope.py`, to `{id, name}` elements.
- **Refusal message (T005).** `data-model.md` gives no exact text for a scope stored in the old shape, so `AllocationScope.from_stored` uses: `allocation_scope of pool <pool>: the stored entry <json> is not an element with an "id" and a "name"; recreate the pool to set its scope`. A stored value that is not a list is refused with a message of the same form.
- **Division values (T005).** Decision 10 was revised on 2026-10-09: `List`, `JSON` and `Any` attributes are refused as scope elements, so a division holds only scalar values. `Division` is a plain frozen dataclass whose lock key hashes the values; the `List` scope fixture and smoke-test case are removed (`b5141177fc`).

## Tasks not completed

None. T001 to T005 are ticked `[X]`, and the description of PR #10932 is published with the `{id, name}` shape and the new example figures.

## Local-pass evidence

All runs are from `backend/` on macOS, with the Docker daemon up for the component tests (testcontainers).

| Tests | Type | Run command | Passed at (ISO 8601) | Verbatim pass line |
|-------|------|-------------|----------------------|--------------------|
| `tests/unit/graphql/test_number_pool_surface_contract.py`, `tests/component/graphql/queries/test_number_pool_surface.py` | unit and component | `uv run pytest tests/unit/graphql/test_number_pool_surface_contract.py tests/component/graphql/queries/test_number_pool_surface.py -p no:cacheprovider -q` | 2026-10-08T20:32:37Z | `17 passed, 16 warnings in 16.82s` |
| `tests/unit/pools/test_scope.py`, `tests/component/core/resource_manager/test_number_pool_scope.py`, and the other files of the curated tip suite | unit and component | `uv run pytest tests/unit/graphql/test_number_pool_surface_contract.py tests/unit/pools tests/component/graphql/queries/test_number_pool_surface.py tests/component/core/resource_manager/test_number_pool_scope.py tests/component/core/schema/test_attribute_parameters.py tests/component/graphql/resource_manager/number_pools -p no:cacheprovider -q -n 4` | 2026-10-08T19:20:23Z | `250 passed, 80 warnings in 107.10s (0:01:47)` |
| Number-pool suites (`tests/component/core/resource_manager`, `tests/component/graphql/resource_manager`, `tests/component/pools` and the files above) | unit and component | `uv run pytest <the paths> -p no:cacheprovider -q -n 4` | 2026-10-08T19:00:45Z | `476 passed, 3 xfailed, 80 warnings in 146.80s` |
| Backend unit suite | unit | `uv run invoke backend.test-unit` | 2026-10-08, between 19:30Z and 19:39Z | `3440 passed`; the 6 errors of `tests/unit/helpers/test_prefect_diagnostics.py` came from a local editable install of the SDK and pass after `uv sync --all-groups` (`11 passed`) |
| Live checks of the three queries, 61 checks | live | `uv run python <scratchpad>/live_check.py <repo>` against the stack `aluminumterrier` (`INFRAHUB_IMAGE_VER=local uv run invoke dev.start --wait`, worktree mounted on `/source`) | 2026-10-08T19:39:19Z, on `5cef3a1c0f` | `61/61 passed` |
| Frontend types of the three queries | frontend type check | `pnpm codegen:graphql`, then `pnpm exec tsc --noEmit -p .` with a temporary file typing the queries | 2026-10-08T18:51Z | 185 errors, the same count as on the base; none in the temporary file |

The 250-test, 476-test and live runs predate the shared provenance enum. That change touches only the dedicated queries' schema, and the 17-test run covers it.

## What the live checks cover

- **Schema served to the frontend.** The `NumberPool*` types and the 5 root fields served live match `schema/schema.graphql`: same fields, types, descriptions and arguments, field order ignored.
- **Every field of the three queries**, on the default branch and on `branch1`:
  - the divisions read on the request branch: sites A (40) and B (30) on `main`; A (39), B (30) and C (1) on `branch1`;
  - `allocation_scope` as a list of `{id, name}` objects, each entry's `id` equal to the scope element's id;
  - divisions ordered by utilization, then by label, and range figures adding up to the division's `used`.
- **Allocations query.** Pages of 10 rows by default, rows ordered by value, branch and holder id, `count` taken before paging, and the `division`, `range_id`, `branch` and `provenance` filters.
- **Unscoped pool, refusals, real pool.** The unscoped pool lists no division; the 8 refusals the fixed dataset can produce return the contract's message; a pool created with `allocation_scope: ["site"]` gives 100, 101 and 102 to three devices.

## Review findings

The phase review (six agents) and two later reviews of the pull request (cubic, `/code-review`) found no high or critical issue. Fixed during the phase:

- Division hashing and equality, the refusal of a stored scope that is not a list, and the unit tests of `scope.py`.
- The pool read back from the database in the smoke test, and the `scoped_schema` docstring.
- The duplicate provenance enum (shared enum, above).
- The stale descriptions and example figures of `contracts/graphql-number-pool-queries.md`, and the equality rule of `data-model.md`.

The findings of the two pull request reviews are fixed, one commit each:

| Commit | Finding |
|--------|---------|
| `5b92b5469c` | A stored scope entry that cannot be written as JSON raised `TypeError` instead of `ValidationError` |
| `3267062b03` | `Division.key` raised `UnicodeEncodeError` on a `JSON` value holding a lone surrogate; the key is now ASCII JSON, and ASCII values keep the same key |
| `8f7a6520e7` | `Division.key` was recomputed on every comparison |
| `e3673697e1` | In the fixed dataset, a range's size counted the values the attribute excludes |
| `2ead696d1c` | The scoped pool smoke test created all four pools for each case |
| `910af2e2d4` | The schema API scope test accepted either `null` or `[]`; an absent scope reads back as `null`, an empty one as `[]` |
| `c43f73c89b`, `759bd19efc` | Parametrized cases were tuples instead of dataclasses with a `name` field |

Suites touched by these commits, from `backend/`: `uv run pytest tests/unit/graphql/test_number_pool_surface_contract.py tests/unit/pools tests/component/graphql/queries/test_number_pool_surface.py tests/component/core/resource_manager tests/component/core/schema/test_attribute_parameters.py tests/component/graphql/resource_manager/number_pools -p no:cacheprovider -q -n 4` at 2026-10-08T21:52:36Z: `380 passed, 2 xfailed, 80 warnings in 115.33s (0:01:55)`.

Kept by design: the fixed dataset answers for any `pool_id` (IFC-3347, deleted by T027), and an unknown or repeated division path gets the one message the contract defines.

## Suggested next steps

1. Rebase PR #10950 on the head of PR #10932 and align it with the spec (see the IFC-3348 discussion).
2. T045: the SDK commit that `python_sdk` points at must reach `infrahub-develop` before the feature branch merges into the release branch.
3. Continue with Phase 2 (T006 to T010).
