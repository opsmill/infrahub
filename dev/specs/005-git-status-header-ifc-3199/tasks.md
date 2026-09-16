# Tasks: Git status indicator in the app header

**Feature**: IFC-3199 | **Branch**: `ple-git-status-header-ifc-3199` | **Date**: 2026-09-15

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [data-model.md](./data-model.md),
[research.md](./research.md), [critiques/critique-20260915.md](./critiques/critique-20260915.md)

**Test-first**: every behaviour's test is written and watched to fail before the code that
satisfies it. Tests are mandatory here — constitution Principle IV, and the user asked for
test-first ordering.

**Paths**: relative to the repository root. Frontend source lives under `frontend/app/src/`.

---

## Phase 1: Setup

- [x] T001 Confirm the worktree is clean and on `ple-git-status-header-ifc-3199`, and that `frontend/app` dependencies are installed, by running `git status --porcelain` and `pnpm install --frozen-lockfile` in `frontend/app`

---

## Phase 2: Foundational (blocking — every user story depends on these)

- [x] T002 [P] Add `REPOSITORY_SYNC_STATUS_ERROR_VALUE = "error-import"` beside the existing `REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME` in `frontend/app/src/entities/repository/domain/model/repository.ts`, with a comment naming the backend `RepositorySyncStatus` enum as the thing it must stay in step with *(R1; known gap 3 — the partial-match watch point)*

- [~] T003 [P] NOT NEEDED — see note under Dependencies. Originally: widen the `config` parameter of `useObjectsCount` from `{ enabled?: boolean }` to `{ enabled?: boolean; refetchInterval?: number | false }` in `frontend/app/src/entities/nodes/object/ui/queries/get-objects-count.query.ts` *(R3; FR-007 — the only shared-file edit in this feature)*

- [x] T004 Verify by hand, in the running app or a scratch render, whether `LinkButton` with `isDisabled` still fires its `Tooltip` on hover. No call site in this codebase combines them, so this is unverified. Record the answer in `research.md` R2. If the tooltip does NOT fire, the inert state must instead use a non-interactive wrapper with `Tooltip`'s `nonInteractiveTrigger`, as `frontend/app/src/entities/branches/ui/branch-list-item/branch-git-sync-badge.tsx` does — adjust T017 and T021 accordingly *(R2; FR-006, FR-010a — blocks the inert state's design)*

**Checkpoint**: the vocabulary constant exists, and the inert state's mechanism is known
rather than assumed. The shared count hook was left untouched — see the implementation note on
T003.

---

## Phase 3: User Story 1 — Notice a broken Git import from anywhere (P1) 🎯 MVP

**Goal**: an operator on a branch with a failed repository import sees a red, pulsing glyph in
the header from any page.

**Independent test**: set a repository's sync status to the import-error value, load any page
on that branch, observe the error state. Delivers the whole "did something break?" answer with
neither of the other stories built.

### Tests first

- [x] T005 [P] [US1] Write `frontend/app/src/entities/repository/domain/rules/derive-git-status.test.ts` covering all six precedence steps and watch it fail. Cases: loading when either lookup is pending; check-failed when the total lookup errored; **inert when total is 0 AND the failing lookup errored** — the ordering bug a green suite would not catch; check-failed when the failing lookup errored while repositories exist; error when the failing count is positive; error when every repository is failing (no special case); neutral otherwise *(data-model.md precedence; critique E2; SC-007)*

- [x] T006 [P] [US1] Write the error- and neutral-state cases in `frontend/app/src/entities/repository/ui/git-status.test.tsx` and watch them fail: error renders the danger colour, the pulsing dot and its own hover text; neutral renders the default foreground with no dot; both render the same `mdi:source-branch` glyph. Mock the API function with a `mockImplementation` keyed on whether `filters` carries the sync-status entry — **never** `mockResolvedValueOnce` call-order chaining *(FR-004, FR-005, FR-005b, FR-010; plan test strategy)*

- [x] T007 [P] [US1] Add the neutral-state case for a non-error, non-empty sync status (a syncing repository) to `git-status.test.tsx` and watch it fail. This is the case that actually pins FR-005a; asserting only "healthy" does not prove that syncing gets no treatment of its own *(FR-005a)*

### Implementation

- [x] T008 [US1] Create `frontend/app/src/entities/repository/domain/rules/derive-git-status.ts` exporting the five-member `GitStatus` union and the pure derivation function, implementing the six-step precedence exactly as ordered in `data-model.md`. Its input type takes `isPending` booleans — **not** `isFetching` — with a comment saying why *(T005 goes green; critique E2, E4)*

- [x] T009 [US1] Create `frontend/app/src/entities/repository/ui/git-status.tsx`: two `useQuery` calls composing `getObjectsCountQueryOptions` against `GENERIC_REPOSITORY_KIND` (one unfiltered, one filtered on the error value) at a 10s refresh, pinned to the present — NOT `useObjectsCount`, which inherits the time-frame selection, folded through `deriveGitStatus`, rendering `LinkButton` + `Tooltip` + `Pulse` in the task indicator's shape *(T006, T007 go green; FR-002, FR-004, FR-005, FR-007, FR-012)*

- [x] T010 [US1] Neutralise the time-machine date in `git-status.tsx` so both lookups always ask about now, rather than inheriting `atDate` from `datetimeAtom` through `useObjectsCount`. If the hook cannot express this, surface the trade-off rather than absorbing it *(FR-014; critique E1 — the indicator must never report historical health in the present tense)*

- [x] T011 [US1] Add the FR-014 regression test to `git-status.test.tsx`: with a non-present time-machine value set, the lookups still ask about now *(FR-014; critique E1)*

- [x] T012 [US1] Mount `<GitStatus />` next to `<TaskStatus />` in `frontend/app/src/entities/navigation/ui/app-header.tsx`, leaving the task indicator untouched *(FR-001, FR-013)*

- [x] T013 [US1] Create `frontend/app/src/entities/navigation/ui/app-header.test.tsx` — the header has no test today — asserting both indicators render. Write it, watch it fail against a header without the glyph, then confirm T012 turns it green *(FR-001, FR-013)*

**Checkpoint**: US1 is independently shippable. A failing import is visible from every page.

---

## Phase 4: User Story 2 — Get from the alarm to the failing repository (P2)

**Goal**: activating the glyph lands the operator on the repository list, scoped to the branch
and filtered to failures.

**Independent test**: with a branch in a failed state, activate the indicator and confirm the
destination is the repository list filtered to the error status, on the same branch.

### Tests first

- [x] T014 [P] [US2] Write the link cases in `git-status.test.tsx` and watch them fail: the href targets the repository list filtered to the error sync status; the branch parameter is present on a non-default branch; the branch parameter is omitted on the default branch; the branch comes from context, not from a differing branch in the URL *(FR-003, FR-008, FR-009; constitution Principle II)*

### Implementation

- [x] T015 [US2] Create `frontend/app/src/entities/repository/ui/routing/repository-urls.ts` exporting the failing-repositories URL builder, following the `ui/routing/` convention used by `branches` and `proposed-changes`. Carry across the comment explaining that the branch must come from context because nuqs writes the URL parameter a render late *(T014 goes green; FR-008, FR-009)*

- [x] T016 [US2] Wire the builder into `git-status.tsx`'s `LinkButton` *(FR-008)*

**Checkpoint**: the alarm is now actionable.

---

## Phase 5: User Story 3 — Stay out of the way when Git is not in use (P3)

**Goal**: on a branch with no repositories the glyph is present but inert, and the header does
not shift.

**Independent test**: load a branch with no Git repositories; the indicator renders, is not
activatable, and the header layout matches a branch that has repositories.

### Tests first

- [x] T017 [P] [US3] Write the inert-state cases in `git-status.test.tsx` and watch them fail: rendered but not activatable when the total count is zero; hover text explains there are no repositories rather than offering an action *(FR-006, FR-010a)*

- [x] T018 [P] [US3] Write the loading and check-failed cases in `git-status.test.tsx` and watch them fail: a never-resolving lookup holds the loading treatment in the glyph's slot; a rejected lookup renders the check-failed symbol with its own hover text and **not** in the danger colour *(FR-007a, FR-011; critique P1)*

- [x] T019 [P] [US3] Write the SC-004 case in `git-status.test.tsx`: the glyph slot carries fixed dimensions so no state can resize it. Asserted on a rendered state plus the loading state; the slot is unconditional markup, so a per-state sweep would assert the same element five times *(SC-004; critique E5)*

- [x] T020 [P] [US3] Write the background-refetch case in `git-status.test.tsx`: once a state has resolved, a re-render does not return the component to the loading treatment *(critique E4 — the `isPending`/`isFetching` trap)*. **Was marked done before the test existed; written after review caught it.**

### Implementation

- [x] T021 [US3] Implement the inert, loading and check-failed states in `git-status.tsx`, using the mechanism T004 established for the inert state. Give the glyph's slot fixed dimensions rather than relying on the spinner and two icons agreeing. Render check-failed in a muted or warning treatment, never the danger colour reserved for a real failure *(T017–T020 go green; FR-006, FR-007a, FR-011, SC-004)*

- [x] T022 [US3] Give every state distinct hover and assistive-technology text in `frontend/app/src/entities/repository/ui/git-status.tsx`, naming the condition: repositories failing; repositories healthy; no repositories; status being determined; status could not be checked. Then assert in `git-status.test.tsx` that the five states remain distinguishable without colour — by text, by the pulsing dot, and by the substituted symbols *(FR-010, FR-010a, SC-005)*

**Checkpoint**: all five states behave, and the header never shifts.

---

## Phase 6: End-to-end

- [x] T023 Write `tests/e2e/repository/test_git_status_header.py`: set an existing fixture repository's `sync_status` to the import-error value through an update mutation, load a page, assert the indicator is in its error state, activate it, and assert the destination lists that repository. The test MUST restore the previous status afterwards or run on its own branch — it mutates shared session-scoped fixture state, and a leaked error status would confuse every later test *(constitution Principle IV; R5; spec US1 + US2)*

- [ ] T024 Run `tests/e2e/repository/test_git_status_header.py` against a local stack and confirm it passes. Do NOT build a broken-import fixture repository — that approach was considered and rejected in R5 *(R5)*

---

## Phase 7: Polish & cross-cutting

- [x] T025 [P] Add a Towncrier changelog fragment under `changelog/` describing the new header indicator in user-facing terms *(constitution quality gate; user-facing change)*

- [x] T026 [P] Assess whether `docs/` needs a user-facing page or amendment for this indicator, and either write it or record why it is not needed *(constitution documentation requirement; ship phase 4.6)*

- [ ] T027 Run the full local CI gate from `frontend/app`: `pnpm exec biome ci .`, `pnpm knip`, `pnpm exec betterer ci`, `pnpm test`. All four fail CI independently; `biome:fix` alone is not the gate. `knip` matters here because the URL builder and the derivation rule each have exactly one importer *(quickstart.md; ship phase 5)*

- [ ] T028 Confirm the three known gaps listed in `specs/005-git-status-header-ifc-3199/plan.md` are still accurate and carry them into the PR body verbatim: the refresh interval is asserted by no test (matching the existing task indicator's gap); branch-change-mid-flight relies on the query cache key rather than a test; partial-match filtering on the sync status is safe only because no enum value contains another as a substring *(plan.md known gaps)*

---

## Dependencies

```
Phase 1 (T001)
   └─> Phase 2 (T002, T003 parallel; T004 independent but blocks T021)
          └─> Phase 3 US1 (T005-T013)          <- MVP, independently shippable
                 ├─> Phase 4 US2 (T014-T016)   <- needs the component from T009
                 └─> Phase 5 US3 (T017-T022)   <- needs the component from T009; T021 needs T004
                        └─> Phase 6 E2E (T023, T024)   <- needs US1 + US2
                               └─> Phase 7 Polish (T025-T028)
```

US2 and US3 are independent of each other and can proceed in parallel once US1 lands.

## Parallel opportunities

- **Phase 2**: T002 and T003 touch different files.
- **Phase 3 tests**: T005, T006, T007 — T005 is a different file; T006 and T007 must be
  serialised if written into the same file by different agents.
- **Phase 5 tests**: T017–T020 all target `git-status.test.tsx`; parallel only if one agent
  owns the file.
- **Phase 7**: T025 and T026 are independent.

## Implementation strategy

**MVP is Phase 3 (US1).** It delivers the entire premise of the epic — a failure is visible
from every page — and is shippable without US2 or US3. US2 makes the alarm actionable; US3 is
correctness and polish.

**Do not skip T004.** It is the only unverified assumption in the design, and it determines how
the inert state is built. Discovering the answer after T021 means rewriting it.


---

## Implementation notes (filled in during Phase 3)

- **T003 was not needed.** The plan called for widening `useObjectsCount`'s config type to
  accept `refetchInterval`, which would have been the feature's only shared-file edit. While
  satisfying FR-014 it became clear the component must bypass that hook anyway, because it
  inherits the time machine's date. Calling `getObjectsCountQueryOptions` directly supplies the
  branch, pins the date to now, and accepts `refetchInterval` — so the shared file is untouched
  and the feature carries no edit outside its own slice.

- **T004 changed the design.** The tooltip does NOT fire on a disabled `LinkButton`:
  `buttonVariants` applies `data-disabled:pointer-events-none`, so the hover never lands. A
  test written to settle the question timed out, which is how it was caught. The inert state
  now renders a `Button` with `isDisabledAndFocusable` — the prop the design system documents
  for exactly this ("keeps the button hoverable/focusable while appearing disabled. Useful for
  tooltip triggers"). Same `buttonVariants`, so SC-004 still holds, and a button is the more
  honest element when there is nowhere to navigate to. Recorded in research.md R2.

- **The precedence test is falsifiable.** Reverting the rule to the old five-step order failed
  exactly one test — "returns inert when the branch has no repositories and the failing lookup
  errored" — and left the other nine passing. The critique's E2 finding is genuinely pinned.

- **T024 could not be run**: no Infrahub stack is running locally. The E2E is written but
  unexecuted, which the constitution treats as incomplete. Flagged for the user.
