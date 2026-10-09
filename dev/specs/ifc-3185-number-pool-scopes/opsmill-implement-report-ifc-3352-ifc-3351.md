# Implementation report: IFC-3352 and IFC-3351

- Spec directory: `dev/specs/ifc-3185-number-pool-scopes`
- Tasks: T029 to T039 (Phase 5 for IFC-3351, Phase 6 for IFC-3352)
- Base commit: `0f2713df74` (head of PR #10975, branch `ajtm-ifc-3348-scope-validation`)
- Branches, stacked on the base:
  - `pmi-number-pool-scope-checker-ifc-3352`, head `1537f1f135`
  - `pmi-number-pool-declared-scope-ifc-3351`, head `524c3f1aaf`
- 25 commits, 25 files, 3231 insertions, 30 deletions. Nothing is pushed.
- Status: complete. Two strict expected failures wait for per-division allocation (IFC-3349).

## Chunk ledger

| Chunk | Tasks | Outcome | Commits |
|---|---|---|---|
| A, schema checker | T037, T038, T034 | 3 done | `da7412577a`, `96bcc16396` |
| B, checker component tests | T035 | 1 done | `840b299ec9` |
| C, name refresh and integration tests | T039, T036 | 2 done | `3398c9cbbf`, `1537f1f135` |
| D, declared scope | T031, T032, T029 | 3 done | `5f9b4015b7`, `345580582a`, `66c3b80032` |
| E, declared scope comparison | T033, T030 | 2 done | `91fad2416b`, `974b21398c` |
| Review fixes | 10 findings | 8 fixed, 2 partly fixed | `e0dfcd97df` to `1cc88a6732` (9 commits) |
| Test gaps and spec wording | 6 test items, 1 spec item | 7 done | `5a47ebe1fc` to `524c3f1aaf` (6 commits) |

Decisions the chunks reported:

- Chunk A: for a change on a generic, the checker also loads the pools of the kinds that use the generic, because Infrahub records the change on the generic only. The constraint name `attribute.parameters.allocation_scope.update` and its identifier were added in T038, so T031 did not add them again.
- Chunk D: a field that the same schema load adds has no id yet. The declared-scope validator gives it the placeholder id `unsaved:<kind>.<name>`, which is never stored; the pool stores the saved id when it is created. The T029 refusal cases are unit tests in `backend/tests/unit/core/schema/test_schema_branch_number_pool_scope.py`.
- Chunk E: the schema-load messages follow `contracts/number-pool-parameters.md`.

## Tasks not completed

None. T029 to T039 are ticked in `tasks.md`.

## Local-pass evidence

All runs on macOS, Docker Desktop for testcontainers, working directory `backend/`.

| Tests | Type | Run command | Passed at | Pass line |
|---|---|---|---|---|
| Checker decision table, missing-schema cases, declared scope comparison | unit | `uv run pytest -q tests/unit/core/schema/test_schema_branch_number_pool_scope.py tests/unit/core/validators/` | 2026-10-09T11:06:46Z | `88 passed, 16 warnings in 2.06s` |
| Checker, synchronizer, declared scope (component) | component | `uv run pytest tests/unit/core/validators/test_number_pool_scope_checker.py tests/component/pools/test_schema_number_pool_synchronizer.py tests/component/pools/test_schema_number_pool_scope.py tests/component/core/constraint_validators/test_number_pool_scope.py -p no:warnings -q` | 2026-10-09T11:35:57Z | `78 passed, 2 xfailed in 243.57s (0:04:03)` |
| Whole `tests/component/pools/` and the checker component file | component | `uv run pytest -q tests/component/pools/ tests/component/core/constraint_validators/test_number_pool_scope.py` | 2026-10-09T11:06:59Z | `48 passed, 2 xfailed, 16 warnings in 181.43s (0:03:01)` |
| Checker and declared-scope schema lifecycle | integration | `uv run pytest tests/integration/schema_lifecycle/test_number_pool_scope_schema.py -p no:warnings -q` | 2026-10-09T11:40:06Z | `29 passed, 1 xfailed in 209.45s (0:03:29)` |
| Existing number-pool parameter lifecycle | integration | `uv run pytest -q tests/integration/schema_lifecycle/test_number_pool_scope_schema.py tests/integration/schema_lifecycle/test_number_pool_parameters_update.py` | 2026-10-09T11:10:20Z | `29 passed, 1 xfailed, 24 warnings in 201.18s (0:03:21)` |
| Existing constraint validators | component | `uv run pytest tests/component/core/constraint_validators -q` | 2026-10-09T09:04:35Z | `441 passed, 6 skipped, 16 warnings in 231.72s` |

Expected failures, both strict with `raises=AssertionError`, both waiting for per-division allocation (IFC-3349):

- `backend/tests/component/pools/test_schema_number_pool_scope.py::test_nodes_in_two_sites_each_receive_the_first_number` returns `(1, 2)` instead of `(1, 1)`.
- `backend/tests/integration/schema_lifecycle/test_number_pool_scope_schema.py`, step05 of the checker class, returns `{'site-a': 1, 'site-b': 2}`.

The third `xfailed` in the component runs is an expected failure that existed before this work.

## Review findings

| Severity | File | Finding | Outcome |
|---|---|---|---|
| High | `core/validators/schema_branch/number_pool_scope_validator.py` | A branch whose kind was removed on the default branch failed to load, which stops server startup | Fixed for an existing pool; still fails for a branch declaration whose pool does not exist yet |
| Medium | same file | Element rules were checked on the default branch's schema only, so a load could declare `site` and make it optional | Fixed |
| Medium | `pools/schema_number_pool_upserter.py` | A scope that cannot be resolved stopped pool creation for every later branch | Fixed |
| Medium | `core/validators/pool/scope.py` | A declaration whose pool is not found was not checked | Fixed |
| Medium | `pools/scoped_number_pool_reader.py` | One pool with an unreadable stored scope blocked every schema change on its kinds | Fixed by text matching on the stored value, see decisions |
| Medium | `core/schema/schema_branch.py` | `core` imported `infrahub.pools` | Partly fixed: the module moved under `core/`, it still imports `infrahub.pools.scope` |
| Medium | `number_pool_scope_validator.py` | Override of the private `_element_id` of `pools/scope.py` | `@override` added and covered by a test; a public option in `scope.py` is not added yet |
| Low | `core/validators/pool/scope.py` | A changed declaration on a generic was reported once per kind | Fixed |
| Low | `number_pool_scope_validator.py` | A path entry on an existing pool got the wrong message | Fixed |
| Low | `number_pool_scope_validator.py` | The default branch's schema is read from the global registry | Partly fixed: an error is raised when it is not loaded |
| Low | `contracts/number-pool-parameters.md` | Branch refusal wording contradicted `contracts/pool-allocation-scope.md` | Fixed in the spec; the code was right |

## Decisions to confirm

1. Leaving the `allocation_scope` key out of a schema load keeps the stored declaration, because the schema merge treats `None` as "keep the stored value". FR-026 and `contracts/number-pool-parameters.md` say that leaving it out is refused. Step03 of the declared-scope integration class records the current behaviour. Either change the merge, which also affects branch merges, or change the spec.
2. For a pool whose stored scope cannot be read, the checker refuses a change only when the stored text contains the changed field's name or id, or when the field is the tracked attribute. Refusing every change on that kind and naming the pool would be simpler.
3. Three changes from the review fixes touch the IFC-3352 checker but are on the IFC-3351 branch, so the IFC-3352 pull request alone does not contain them.
4. Changing an existing Number attribute to NumberPool in one load drops its parameters (`allocation_scope`, ranges). This was observed during the work and is outside this diff.

## Suggested next steps

1. Agree with the owner of `pools/scope.py` on a public option that accepts a field with no id, and on moving `scope.py` under `core/`.
2. Decide items 1 and 2 of "Decisions to confirm".
3. When per-division allocation lands, remove the two expected-failure markers.
4. Run `/pre-ci`, then open the two stacked pull requests.
