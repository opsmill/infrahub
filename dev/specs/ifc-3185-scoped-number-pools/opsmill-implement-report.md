# Implementation report: number-pool GraphQL surface, first delivery

- Feature: scoped number pools (IFC-3185), first delivery limited to the GraphQL surface backed by a fixed in-memory dataset
- Spec directory: `dev/specs/ifc-3185-scoped-number-pools`
- Branch: `pmi-number-pool-scoped-pools-ifc-3185`
- Base commit: `b7cddc9bfa` (spec branch merged with `feature-number-pools-1.12`)
- Head commit: `cc3a3d3e3e`
- Status: DONE for the agreed scope (tasks for real reads are out of scope and stay open)

## Scope of this run

The user narrowed the run after chunk 3: the delivery is the GraphQL surface with mock data and no
database read, so that the frontend team can start. Chunks 1 and 2 (test schema, the
`allocation_scope` attribute) are kept. Chunk 3 (database-backed reads) is reverted. Chunk 4 was
stopped before it wrote anything and replaced by one mock-surface chunk.

## Chunk ledger

| Chunk | Tasks | Outcome | Commits | Notes |
|---|---|---|---|---|
| 1. Setup | T001-T004 | 4 done | `9cdee955c2` | Helpers later removed as unused (`7d0019563b`); `SCOPED_POOL_SCHEMA` kept |
| 2. Schema (change set A) | T005-T010 | 6 done | `d367058ec2`, `5d9bc57be7` | SDK models changed in the `python_sdk` submodule (local commit, pointer not bumped) |
| 3. Rows query, effective space, mock partition | T011-T017 | reverted | `242e86c32c`, `88410dfb12`, `7d57d68496`, reverted by `081a0ba295` | Read the database; out of the agreed scope |
| 4. Surface resolvers (database-backed) | T018-T026 | stopped | none | Stopped when the scope changed |
| 4'. Mock surface | T011, T013, T017, T018, T022, T023, T024 | done | `b31aa26de1`, `10bed88e70`, `692e7d25db` | Fixed scoped dataset for any `pool_id`, unscoped dataset for `mock-unscoped`; filters, pagination and refusals in memory |
| Review fixes | T025 + review findings | done | `4d4ac80d43`, `dbbac8412c`, `eb87ce0b04`, `7d0019563b`, `cc3a3d3e3e` | See review findings |

## Tasks not completed

Every task from T012 onward that needs real reads stays open: T012, T014-T016a, T019-T021,
T026, and Phases 4 to 13 (T027-T084). They are outside the agreed scope of this delivery.

## Local-pass evidence

| Test id | Type | Run command | Passed at | Environment | Pass line |
|---|---|---|---|---|---|
| `tests/unit/pools/test_number_pool_mock.py` (24 tests) | unit | `cd backend && uv run pytest tests/unit/pools/test_number_pool_mock.py -q` | 2026-10-06T17:45:28Z | local | part of `100 passed, 16 warnings in 143.00s` |
| `tests/component/graphql/queries/test_number_pool_surface.py::TestNumberPoolSurface` (14 tests) | component | same combined run | 2026-10-06T17:45:28Z | testcontainers | part of `100 passed` |
| `tests/unit/graphql/test_number_pool_surface_contract.py::test_number_pool_surface_sdl_matches_the_published_contract` | unit | same combined run | 2026-10-06T17:45:28Z | local | part of `100 passed` |
| `tests/component/graphql/resource_manager/number_pools/test_pool_scope.py` (3 tests) | component | same combined run | 2026-10-06T17:45:28Z | testcontainers | part of `100 passed` |
| `tests/component/core/schema/test_attribute_parameters.py::test_number_pool_allocation_scope_round_trips_through_schema_api` (3 cases) | component | same combined run | 2026-10-06T17:45:28Z | testcontainers | part of `100 passed` |
| `tests/component/graphql/queries/test_resource_pool.py` (existing, unchanged) | component | same combined run | 2026-10-06T17:45:28Z | testcontainers | part of `100 passed` |
| `tests/unit/core/schema/test_write_json_schema.py` (existing) | unit | same combined run | 2026-10-06T17:45:28Z | local | part of `100 passed` |

Combined command, from `backend/`: `uv run pytest tests/component/graphql/resource_manager/number_pools/test_pool_scope.py "tests/component/core/schema/test_attribute_parameters.py::test_number_pool_allocation_scope_round_trips_through_schema_api" tests/component/graphql/queries/test_resource_pool.py tests/component/graphql/queries/test_number_pool_surface.py tests/component/pools/test_number_pool_repository.py tests/unit/pools/test_number_pool_mock.py tests/unit/core/schema/test_write_json_schema.py tests/unit/graphql/test_number_pool_surface_contract.py -q -p no:randomly`

## Review findings

| Severity | File | Finding | Status |
|---|---|---|---|
| Important | `python_sdk` submodule | SDK model changes are a local submodule commit; the parent pointer is not bumped | Fixed: the surface builds on the `allocation_scope` change of [#10917](https://github.com/opsmill/infrahub/pull/10917), which bumps the SDK |
| Important | `attribute_parameters.py`, `resource_pool.py`, `tasks/backend.py` | `allocation_scope` description promised behaviour nothing applies | Open: the description comes from [#10917](https://github.com/opsmill/infrahub/pull/10917) |
| Important | contract | SDL snapshot test missing | Fixed (T025) |
| Important | tests | Unused helpers and their test file after the revert | Fixed: removed |
| Important | tests | Refusal branch name never varied | Fixed |
| Important | `number_pool_mock.py` | Empty division list raised `IndexError` | Fixed: refused at construction |
| Suggestion | `number_pool_mock.py` | Negative `offset` / `limit` | Fixed: refused, added to the contract |
| Suggestion | `number_pool.py` | `provenance` typed `PoolRecordProvenance \| str` | Fixed |
| Suggestion | `number_pool_mock.py` | Docstring described a plan; list fields in frozen dataclasses | Fixed |
| Suggestion | `test_attribute_parameters.py` | No test of updating `allocation_scope` on an existing schema attribute | Deferred |
| Suggestion | `number_pool_mock.py` | Multi-entry division filters untested (dataset has a one-entry scope) | Deferred |
| Suggestion | `number_pool_mock.py` | `division: []` on the unscoped dataset is treated as no filter | Deferred |
| Suggestion | `attribute_parameters.py` | No validation of scope entries (duplicates, empty strings) | Deferred to the validator tasks |

## Autonomous decisions

- Merged `feature-number-pools-1.12` into the branch before implementing, because the spec branch predated m080/m081 and the IFC-3214 mutations; three conflicts in the P2 spec files resolved by keeping both sides.
- Reverted chunk 3 and stopped chunk 4 after the scope change, keeping chunks 1 and 2.
- The scoped dataset holds no excluded value inside a range, so the contract's scoped example (40 of 100) stays exact; the unscoped dataset carries one (size 99).
- Test branch names are at least three characters (`branch1`, `feature-scope`).

## Suggested next steps

1. Open the infrahub-sdk-python PR for the submodule commits (`a5e760f`, `939bff1`), then bump the `python_sdk` pointer.
2. Push the branch and open a PR to `feature-number-pools-1.12` so the frontend team can start.
3. Plan the real reads (Phases 4 to 13) as their own delivery.

## Erratum (2026-10-07)

- The SDK submodule commits are carried by
  [infrahub-sdk-python#1402](https://github.com/opsmill/infrahub-sdk-python/pull/1402); the
  `python_sdk` pointer moves to the merged commits in IFC-3356.
- The real reads (listed above as "Phases 4 to 13") are the Jira tickets of `tasks.md`: IFC-3348,
  IFC-3352, IFC-3349, IFC-3353, IFC-3351, IFC-3329 (the reads and the dataset removal), IFC-3357,
  IFC-3355, IFC-3354 and IFC-3356. T016a is obsolete: `pools/number_ranges.py::EffectiveSpace` is
  the shared effective-space calculation.
