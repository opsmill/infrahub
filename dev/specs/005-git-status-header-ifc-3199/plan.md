# Implementation Plan: Git status indicator in the app header

**Branch**: `ple-git-status-header-ifc-3199` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-git-status-header-ifc-3199/spec.md`, plus a
synthesis of three parallel plan explorations (minimal-change, refactor-friendly, test-first).

## Summary

Add a branch-scoped Git health glyph to the application header. It asks the backend for two
counts — how many Git repositories exist on the current branch, and how many of those carry
the import-error sync status — and folds them into one of five display states. It links out
to the repository list filtered to failures; it does not explain.

The technical approach is deliberately conservative: reuse the existing generic
object-count hook for both counts, extract the only genuinely new logic (five-state
derivation) into a pure function with its own unit test, and copy the existing task
indicator's structure for everything else. The single new abstraction is the derivation
function, which exists because the spec's own acceptance criteria require distinguishing
three data conditions, not because a second caller is imagined.

## Technical Context

**Language/Version**: TypeScript 5.9, React 19 (React Compiler enabled — no manual memoization)

**Primary Dependencies**: TanStack Query v5, `@infrahub/ui` (LinkButton, Tooltip), React Aria
Components, Iconify (`mdi:` set), nuqs, jotai

**Storage**: N/A — read-only counts, no client persistence

**Testing**: Vitest in browser mode (unit + component), pytest-playwright (E2E at repo root)

**Target Platform**: Infrahub web frontend

**Project Type**: Feature-Sliced React application (`entities/<slice>/{api,domain,ui}`)

**Performance Goals**: Two count requests per 10-second interval per open tab. Cost constant
in the number of repositories (SC-006).

**Constraints**: Header layout must not shift between states (SC-004). No colour-only state
distinction (FR-010). Branch name is deployment-configurable — never compare to a literal.

**Scale/Scope**: 5 new files, 4 modified, no new E2E fixture repository (status set directly).

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design. Result: PASS both times.*

| Principle | Assessment | Verdict |
|---|---|---|
| **II. Branch-Safe by Default** | Both counts pass the branch as GraphQL query context; the branch comes from `useCurrentBranch()`, never the URL (nuqs writes a render late). Default-branch detection uses `currentBranch.is_default`, never a literal name. Query keys include the branch, so a switch is a distinct cache entry. Three dedicated tests. | PASS |
| **III. Type Safety & Explicit Contracts** | Derivation function has an explicit input type and a five-member union return. No `any`, no non-null assertions, no `as`. Generated GraphQL types consumed as generated. | PASS |
| **IV. Test Discipline** | Unit test for the derivation rule; component tests for all five states plus branch/link behaviour; new header test (none exists today); E2E setting a repository's sync status to the error value and asserting the header reacts. Gaps that remain are named in "Known gaps" below rather than hidden. | PASS |
| **V. Query Performance & Efficiency** | Counts only — never repository lists. Cost is constant in repository count. Two requests per interval is the shape the user explicitly chose over one combined query. | PASS |
| **VII. Simplicity & Maintainability** | Reuses `useObjectsCount` rather than adding a second count-fetching path. One new abstraction (the derivation rule), justified by three data conditions the acceptance criteria already require. The permission-denied requirement was amended rather than met with ~4 duplicate files — recorded in the spec's Clarifications. | PASS |

**Complexity justification**: none required. No deviation from Principle VII is being requested.

## Project Structure

### Documentation (this feature)

```text
specs/005-git-status-header-ifc-3199/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source code

```text
frontend/app/src/entities/repository/
├── domain/
│   ├── model/
│   │   └── repository.ts                      # MODIFIED — add error-value constant
│   └── rules/
│       ├── derive-git-status.ts               # NEW — the five-state rule
│       └── derive-git-status.test.ts          # NEW — unit test
└── ui/
    ├── git-status.tsx                         # NEW — the glyph
    ├── git-status.test.tsx                    # NEW — component tests
    └── routing/
        └── repository-urls.ts                 # NEW — failing-repositories URL builder

frontend/app/src/entities/nodes/object/ui/queries/
└── get-objects-count.query.ts                 # MODIFIED — widen config type

frontend/app/src/entities/navigation/ui/
├── app-header.tsx                             # MODIFIED — mount <GitStatus />
└── app-header.test.tsx                        # NEW — header has no test today

tests/e2e/repository/
└── test_git_status_header.py                  # NEW — E2E

tests/e2e/conftest.py                          # MODIFIED only if a status-setting helper is shared
```

## Phase 0: Research

See [research.md](./research.md). All unknowns resolved; no NEEDS CLARIFICATION remain.

Summary of what research settled:

1. **Data source** — `InfrahubRepositoryBranchStatus` (IFC-3126) is a contract stub keyed by
   repository, returning rows per branch, with hash-derived values and a resolver that rejects
   sync-status filtering. Rejected. Generic-kind counts used instead.
2. **`isDisabledAndFocusable` is not available on `LinkButton`** — it exists only on
   `ButtonProps` (`packages/ui/src/components/button/button.tsx::ButtonProps`). The inert
   state uses `isDisabled` on `LinkButton`. Whether hover still fires the `Tooltip` under
   `isDisabled` has **no existing call site in this codebase** and must be verified during
   implementation; if it does not, the fallback is a non-interactive wrapper with
   `Tooltip`'s `nonInteractiveTrigger`, as `branch-git-sync-badge.tsx` already does.
3. **`useObjectsCount`'s config type blocks `refetchInterval`** — widening required.
4. **`getObjectsCount` discards GraphQL error codes**, which is why permission-denied renders
   as check-failed rather than inert. Spec amended.
5. **No E2E fixture seeds an error sync status**, but `sync_status` is an ordinary writable
   Dropdown attribute, so the test sets it directly on an existing repository rather than
   engineering a genuine import failure. This removed what had been the ticket's largest cost.

## Phase 1: Design

### Data flow — two counts

Both counts go through the existing `useObjectsCount`, distinguished only by `filters`:

```ts
const total = useObjectsCount(
  { objectKind: GENERIC_REPOSITORY_KIND },
  { refetchInterval: 10_000 }
);

const failing = useObjectsCount(
  {
    objectKind: GENERIC_REPOSITORY_KIND,
    filters: [{ name: `${REPOSITORY_SYNC_STATUS_ATTRIBUTE_NAME}__value`, value: REPOSITORY_SYNC_STATUS_ERROR_VALUE }],
  },
  { refetchInterval: 10_000 }
);
```

`useObjectsCount` supplies `branchName` from `useCurrentBranch()` internally, so branch-safety
is inherited rather than re-implemented.

**It also supplies `atDate` from `datetimeAtom`, and that must be neutralised (FR-014).** The
time-machine control sits in this same header; letting it re-scope the indicator would make it
report historical health in the present tense and poll every ten seconds for an answer that
cannot change. The existing task indicator takes only the branch and is already unaffected, so
this keeps the pair consistent. Implementation must pass an explicit present-time date rather
than inheriting the atom; if `useObjectsCount` cannot express that, this is the one place a
narrow bespoke query is warranted — and that trade-off should be surfaced, not absorbed
silently.

Query keys come from the existing `objectQueryKeys.count(params)` and differ naturally by
`filters` — distinct cache entries, no collision, no new key builder.

### Five-state derivation

`entities/repository/domain/rules/derive-git-status.ts` — a pure function, no React, no
query library types beyond plain booleans and numbers:

```
1. either pending   -> "loading"        never present an unconfirmed state (isPending, NOT isFetching)
2. total errored    -> "check-failed"   nothing is known
3. total === 0      -> "inert"          failing is a subset of empty; the failed lookup is irrelevant
4. failing errored  -> "check-failed"   repositories exist, health genuinely unknown (SC-007)
5. failing > 0      -> "error"
6. otherwise        -> "neutral"

### Link construction

`entities/repository/ui/routing/repository-urls.ts` exports a single builder, following the
`ui/routing/` convention already used by `branches` and `proposed-changes`:

```
constructPath(`/objects/${GENERIC_REPOSITORY_KIND}`, [
  currentBranch.is_default
    ? { name: QSP.BRANCH, exclude: true }
    : { name: QSP.BRANCH, value: currentBranch.name },
  { name: QSP.FILTER, value: JSON.stringify([errorImportFilter]) },
])
```

The branch must come from context rather than the URL — nuqs writes the param one render
later, so a URL-derived value still points at the previous branch. The existing task
indicator carries this same comment; it is repeated at the new call site.

### Rendering

Single `mdi:source-branch` glyph across `inert`, `neutral` and `error`; `Spinner` substitutes
for `loading`; `mdi:error-outline` substitutes for `check-failed`, in a muted/warning
treatment rather than the danger colour (FR-011 — a permission-limited operator sees this
state permanently). `Pulse` renders only in `error`. `LinkButton` with
`shape="square" variant="outline" size="sm"`, matching the task indicator so the two controls
sit as a pair. `isDisabled` in the `inert` state.

Because three different pieces of content occupy the glyph's slot, the slot itself is given
fixed dimensions rather than relying on the spinner and two icons happening to agree. SC-004
is a stated requirement, so those dimensions are asserted in the component test instead of
left to manual inspection.

Each state carries distinct hover and assistive text naming the condition (FR-010a).

### Test strategy per layer

| Layer | File | Covers |
|---|---|---|
| Unit | `derive-git-status.test.ts` | Each of the five states; precedence (loading beats everything; a failed total beats all); **total=0 with a failed failure-lookup yields inert, not check-failed**; a failed failure-lookup with repositories present yields check-failed; all-failing is ordinary error |
| Component | `git-status.test.tsx` | Five rendered states; pulse present only in error; single glyph across resolved states; link filter and branch param; default-branch omission; branch from context not URL; inert not activatable; per-state hover text; **the glyph slot's dimensions are constant across states** (SC-004); **a resolved state survives a background refetch** (the `isPending`/`isFetching` trap); **the time-machine date does not change what is asked** (FR-014) |
| Component | `app-header.test.tsx` | Indicator mounts alongside the task indicator, both present (FR-013) |
| E2E | `test_git_status_header.py` | A real failed import turns the indicator red and its activation lands on the failing repository |

**Mocking rule for the two counts** — mock the API function with a `mockImplementation` keyed
on whether `filters` carries the sync-status entry, *not* `mockResolvedValueOnce` call-order
chaining. Call order is an implementation detail that a later refactor would silently
invalidate, and an order-keyed mock fails on the wrong line when it does.

### E2E fixture work

No fixture seeds an error sync status today; `tests/e2e/conftest.py`'s `demo_edge_repo` treats
`error-import` as a hard failure to raise on.

**Approach: set `sync_status` directly on an existing repository.** It is an ordinary Dropdown
attribute with no read-only flag, so the test reuses the existing repository fixture, sets its
status to the import-error value through a normal update mutation, and asserts the header
reacts. The indicator reads `sync_status` and nothing else, so this exercises the entire
contract the feature depends on.

**Rejected: a purpose-built repository that genuinely fails to import.** It would additionally
prove that a real failure *produces* that status — but that is the importer's behaviour, owned
by backend tests and unchanged by this ticket. It would have cost a second session-scoped
import fixture in the slowest shard tier, and would have been the suite's only test depending
on an import failing by design, re-verifiable whenever the importer's error handling moved.
Chosen against once `sync_status` was confirmed writable.

Remaining cost: the test must restore the status afterwards, or run on its own branch, so it
does not leave a poisoned repository for other tests in the same session-scoped fixture.

## Known gaps carried to the PR body

These are deliberate, not oversights, and must survive into the pull request description:

1. **The 10-second refetch is not asserted by any test.** No test in this codebase asserts a
   `refetchInterval` fires — the existing task indicator has the same gap. A regression
   changing `10_000` would not be caught. Fake-timer coverage is buildable if a reviewer
   wants it, but would be the first of its kind here.
2. **Branch-change-mid-flight is untested.** It is a TanStack Query cache-key guarantee
   rather than application logic; testing it would test the library. The guarantee holds only
   while the query stays keyed on the branch.
3. **The control changes element type between states.** Inert renders a `Button`; every other
   state renders a `LinkButton`. React therefore remounts the subtree when a branch's
   repository count crosses zero with the page open — dropping focus if the control happened
   to be focused, and changing the accessible role from button to link with no announcement.
   Accepted deliberately: the spec requires the inert state to be disabled, a disabled
   `LinkButton` cannot show a tooltip (see research R2), and a `role="link"` that leads nowhere
   is worse semantics than a disabled button. The transition is rare — it needs a repository
   added to, or removed from, an otherwise empty branch while the operator watches. The
   alternative, overriding the design system's `data-disabled:pointer-events-none` with an
   arbitrary variant, trades a rare focus loss for a permanent fight with the component library.

4. **Partial-match filtering is safe incidentally, not structurally.** `addFiltersToRequest`
   sets `partial_match: true` for any `__value` filter. No current sync-status enum value
   contains `error-import` as a substring, so the count is exact today. A future enum value
   that did would silently inflate it. A comment at the filter construction site points at
   the enum as the thing to watch.

## Agent context update — declined

Phase 1 step 4 of the plan workflow asks for the plan reference to be written into
`CLAUDE.md` between SPECKIT markers. **Not performed.** This project's `CLAUDE.md` is
hand-maintained and delegates to `AGENTS.md`; the generated block clobbers it. Declined
deliberately and recorded here so the omission is visible rather than looking like a miss.
