# Implementation report: number pool field tabs (IFC-3371)

- **Status**: INCOMPLETE. T025 is partial: one end-to-end case fails because of a backend bug, and the test is marked as an expected failure.
- **Spec dir**: `dev/specs/ifc-3371-number-pool-field-tabs`
- **Branch**: `ple-number-pool-field-ifc-3371`, based on `origin/feature-number-pools-1.12`, not pushed
- **Base commit**: `fbf1a81533`
- **Head commit**: `71f1d9e90b`
- **User decisions applied**:
  - The edit form opens on the From pool tab when a pool tracks the number.
  - Saving a number from the Value tab is the only way to take a number out of its pool. There is no separate button.

## 1. Chunk ledger

| # | Chunk | Tasks | Outcome | Commit | Flagged upward |
|---|---|---|---|---|---|
| 1 | Setup | T001 | 1 done | `3629b610b7` | The case where the user empties the number and keeps the same pool relies on backend contract row 7, which says the allocator returns the number it already reserved for the node. No component test covers this. |
| 2 | Foundational | T002–T004 | 3 done | `2f8c85a8c5` | The new helper is named `buildNumberPoolMutationValue`. |
| 3 | User Story 1 | T005–T009 | 5 done | `b25cbf090d` | The number input in the pool tab is `PoolNumberField`. Its help text is in a tooltip, so tests find the input by role, not by the help text. |
| 4 | User Story 2 | T010–T012 | 3 done | `c65c0e695f` | T011 needed no code. A test that a typed 0 is sent as 0 was added beyond the task list. |
| 5 | User Story 3 | T013–T014 | 2 done | `bf077f1544` | T014 is covered by an existing test, "renders without a tab strip when no pool serves this attribute". |
| 6 | User Story 4, part 1 | T015–T019 | 5 done | `633e477fe7` | T018 checked every place that reads a pool source and changed none of them. |
| 7 | User Story 4, part 2 | T020–T024 | 5 done | `c9a1e739c6` | The old test "opens on the value tab when the value came from a pool" was replaced, because it contradicts user decision 1. No test checks the new label text. |
| 8 | Polish | T025–T028 | 3 done, 1 partial | `5c43cf9e5a` | Backend bug in the detach case (see §3). The default end-to-end stack does not fit in Docker memory on this machine. |
| — | Review fixes | — | — | `71f1d9e90b` | One high-severity bug fixed (see §5). |

## 2. Tasks not completed

T025 is partial and still unticked. The end-to-end case for saving a number from the Value tab, to take it out of its pool, is marked `xfail(strict=True)`.

The form sends the right request, `{value: 7, from_pool: null}`. The backend stops counting the number in the pool. But the attribute still records the pool as its source:

- The node loaded for the update still carries the pool as its source.
- The attribute update in `backend/infrahub/core/attribute.py` therefore writes that source back.

The subagent confirmed the source edge in Neo4j and reproduced the bug with GraphQL alone, without the frontend. Moving a number to another pool probably has the same problem.

## 3. Local-pass evidence

The component and unit tests ran in Vitest browser mode (Chromium) on macOS.

| Test id | Type | Run command | Passed at | Environment | Pass line |
|---|---|---|---|---|---|
| `buildFromPoolMutationValue.test.ts > buildNumberPoolMutationValue > sends the entered number with the pool`, `sends a null value when the number was cleared`, `sends a null value when no number was entered`, `keeps zero as an entered number` | unit | `pnpm vitest run src/shared/components/form/utils/mutations/buildFromPoolMutationValue.test.ts` | 2026-10-09T09:09:19Z | Vitest browser mode, Chromium | `Tests  14 passed (14)` |
| `getCreateMutationFromFormData.test.ts > Number attribute served by a number pool > asks the picked pool for its next free number when no number is typed`, `asks for the next free number when the number input was cleared`, `sends nothing after the pool tab was visited and left without picking` | unit | `pnpm vitest run …getCreateMutationFromFormData.test.ts …number.field.test.tsx` | 2026-10-09T09:11:57Z | same | `✓ \|chromium\| … 0ms` (each) |
| `number.field.test.tsx > NumberField > offers a number input only once a pool is picked`, `offers no number input for a pool that comes from a template` | component | same as the row above | 2026-10-09T09:11:57Z | same | `Tests  52 passed (52)` |
| `getCreateMutationFromFormData.test.ts > … > sends the typed number with the picked pool so the pool records it`, `sends a typed 0 rather than treating it as empty`; `number.field.test.tsx > stores the number typed in the pool tab alongside the picked pool` | unit and component | `pnpm vitest run …getCreateMutationFromFormData.test.ts …number.field.test.tsx` | 2026-10-09T09:15:36Z | same | `Tests  55 passed (55)` |
| `getCreateMutationFromFormData.test.ts > … > sends only the typed number when no pool is picked`; `getUpdateMutationFromFormData.test.ts > … > sends only the typed number when no pool tracks it`; `number.field.test.tsx > renders without a tab strip when no pool serves this attribute` | unit and component | `pnpm vitest run` on the create, update and number-field test files | 2026-10-09T09:17:36Z | same | `Tests  85 passed (85)` |
| `getUpdateMutationFromFormData.test.ts > Number attribute served by a number pool` (cases E2 to E10, plus the template check) | unit | `pnpm vitest run …getUpdateMutationFromFormData.test.ts -t "Number attribute served by a number pool"` | 2026-10-09T09:22:20Z | same | `Tests  12 passed \| 28 skipped (40)` |
| `getFieldDefaultValue.test.ts > current number when a number pool …` | unit | `pnpm vitest run …getFieldDefaultValue.test.ts -t "current number when a number pool"` | 2026-10-09T09:22:22Z | same | `Tests  1 passed \| 24 skipped (25)` |
| `updateFormFieldValue.test.ts > updateNumberPoolFieldValue` (5 tests); `number.field.test.tsx` (5 tests on edit-form behaviour) | unit and component | `pnpm vitest run …updateFormFieldValue.test.ts …number.field.test.tsx` | about 2026-10-09T09:28Z | same | `✓ \|chromium\| …` (each) |
| `number.field.test.tsx > keeps the default intact when a number is typed after re-picking the original pool`; `updateFormFieldValue.test.ts > restores the node's value when its own pool is picked again` | unit and component | `pnpm vitest run …number.field.test.tsx …updateFormFieldValue.test.ts` | 2026-10-09T10:09:38Z | same | `Tests  38 passed (38)` |
| `test_number_pool.py::test_create_node_with_typed_number_recorded_in_pool[chromium]`, `test_edit_node_opens_pool_tab_with_pool_and_number[chromium]` | e2e | `INFRAHUB_TESTING_API_SERVER_COUNT=1 INFRAHUB_TESTING_WEB_CONCURRENCY=2 INFRAHUB_TESTING_TASK_WORKER_COUNT=1 INFRAHUB_TESTING_IMAGE_VER=ifc3371 INFRAHUB_TESTING_DOCKER_PULL=false uv run pytest -c tests/e2e/pytest.ini tests/e2e/resource-manager/test_number_pool.py` | 2026-10-09T10:04:14Z | testcontainers stack `infrahub-test-*`, image built from this branch, Chromium | `PASSED` (each); `8 passed, 1 xfailed in 287.29s` |
| `test_number_pool.py::test_typed_value_takes_number_out_of_pool[chromium]` | e2e | same as the row above | expected failure | same | `XFAIL` (backend bug, §2) |
| Whole `src/shared/components/form` and `src/shared/components/inputs` folders | regression run | `pnpm vitest run src/shared/components/form src/shared/components/inputs` | 2026-10-09T10:09:15Z | Vitest browser mode, Chromium | `Tests  384 passed (384)` |

The test commands above run from `frontend/app`. Test file paths are abbreviated with `…`.

Other checks on the head commit:

| Check | Result |
|---|---|
| `biome ci .` | Passed |
| `pnpm knip` | Passed |
| `pnpm betterer ci` | Passed, 176 issues, the same count as before |
| `tsc --noEmit` | 185 errors, the same as before this change |
| `ruff check` and `ruff format` on the end-to-end test file | Passed |

## 4. Review findings

| Severity | Location | Summary | Status |
|---|---|---|---|
| High | `updateFormFieldValue.ts:115` | On an edit form, picking the original pool again stored the form's default value object itself. A number typed after that was written into the default, so saving dropped it. | Fixed in `71f1d9e90b` |
| Medium | `getUpdateMutationFromFormData.ts:93` | On the Value tab, clearing a number that a pool tracks sends `{value: null}` without `from_pool: null`. The form contract does not cover this case. | Deferred |
| Medium | `pool-allocation-panel.tsx:28` | The docstring says the From pool tab never shows an allocated value, but it now does on an edit form for a number pool. | Deferred |
| Medium | `test_number_pool.py:179-186` | The expected-failure marker covers the whole test, so a frontend failure before the backend step would also count as the expected failure. | Deferred |
| Medium | `number.field.test.tsx` | No component tests for saving from the Value tab over a tracked number, for changing a tracked number, or for rejecting a decimal. | Deferred |
| Low | `updateFormFieldValue.ts:106` | A number the user cleared comes back when they pick another pool. | Deferred |
| Low | `getFormFieldFromAttribute.ts:95` | The form does not check a number typed in the pool tab against the attribute's minimum and maximum. The backend rejects it instead. | Deferred |
| Low | `pool-backed-field.tsx:69` | The starting tab is read only on the first render. | Deferred |
| Low | `pool-select.tsx:349,403` | The comment points to another override instead of giving its own reason. | Deferred |

## 5. Autonomous decisions

- US4 (10 tasks) was split into two chunks: T015–T019 for the default value and the request, and T020–T024 for the interface.
- The review subagent tested the reviewer's first medium finding, found that it loses user input, and fixed it as high severity.
- The end-to-end case affected by the backend bug is marked as an expected failure instead of being left out, so it fails once the backend is fixed.
- The end-to-end tests ran on a smaller stack (one API server, one task worker), because the default stack ran out of Docker memory on this machine.

## 6. Suggested next steps

1. Fix the backend bug in §2 under IFC-3184, then remove the `xfail` marker and tick T025.
2. Decide on the deferred medium findings. The first one, clearing a tracked number on the Value tab, changes what the backend receives.
3. Restart the local dev database. `infrahub-database-1` exited with code 137 while the test stack was running.
4. Open a PR against `feature-number-pools-1.12`.
