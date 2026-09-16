# Implementation Plan: Repository branches card and branch-scoped details

**Branch**: `ple-branches-card-ifc-3130` | **Date**: 2026-09-16 | **Spec**: [spec.md](spec.md)

**Base branch**: `cross-branch-repo-status-infp-671` — a feature branch, not `develop` or `stable`.
IFC-3126 is already merged into it, so the schema and the regenerated frontend types are present
and codegen regenerates to zero drift.

**Input**: [spec.md](spec.md) (28 FRs), [plan-synthesis.md](plan-synthesis.md) (the merged output of
three parallel plan framings — minimal-change, refactor-friendly, test-first),
[design.md](design.md), [research.md](research.md).

> **Precedence.** `plan-synthesis.md` outranks `research.md` wherever they disagree; it corrected
> four of research.md's claims against source. Those corrections are restated in
> [Corrections carried forward](#corrections-carried-forward) and are authoritative here.

---

## Summary

The repository page reports the default branch's Git state as though it were the repository's. This
feature adds a **Branches card** listing one row per in-scope branch with that branch's sync status
and imported commit, fed by the frozen `InfrahubRepositoryBranchStatus` query with server-side
paging, counting and filtering; and it **splits the repository details card in two** — repository-wide
attributes above, branch-scoped attributes below — with the division derived from each attribute's
schema branch-support declaration rather than from a field-name list.

The technical approach is **reuse-first**. A verified sweep against source found existing components
for every element but one; the single justified new primitive is `CommitHash`. The one substantial
new piece of machinery is a **three-layer table pagination** (pure utils / URL-scoped hook /
controlled component), built new because the legacy `Pagination` is hard-wired to a single global
`QSP.PAGINATION` key and to a page-level scroll area, and is shared by three unrelated pages.

Nothing in this feature writes. It is a read-only presentation over one GraphQL query.

## Technical Context

**Language/Version**: TypeScript 5.x (strict), React 19 with the React Compiler enabled

**Primary Dependencies**: Vite · Tailwind CSS + CVA · `@infrahub/ui` design system · TanStack Query
(react-query) · `nuqs` for URL state · `gql.tada` for typed hand-written GraphQL documents ·
jotai · React Router

**Storage**: N/A — read-only over GraphQL; no client-side cache shape beyond react-query's

**Testing**: Vitest in **browser mode** for unit and component tests; pytest-playwright for E2E at
repo-root `tests/e2e/`

**Target Platform**: Browser (the Infrahub web app at `frontend/app`)

**Project Type**: Web application frontend, Feature-Sliced architecture (`entities/` · `shared/` ·
`pages/`)

**Performance Goals**: One request per page view regardless of branch count (SC-003); rows
transferred bounded by page size (default 20), not by branch count

**Constraints**: Server-side paging, counting, filtering and ordering only — no client-side
narrowing of any kind (FR-015). The card must not blank the rest of the page on failure (FR-024).

**Scale/Scope**: Repositories with up to ~200 branches; 2 repository kinds (`CoreRepository`,
`CoreReadOnlyRepository`); 28 functional requirements; 9 work units.

### The IFC-3127 preview window

IFC-3126 ships the query with **real** rows, paging, ordering and permission denials, but the four
attribute values are **fabricated from the branch name**. They are stable across reloads and every
dropdown value appears, so the card is fully buildable and screenshottable against them.

Two consequences this plan must honour:

- `sync_status__value`, `internal_status__value` and `own_values_only` are **accepted but ignored**
  today. **FR-016 is enforced structurally**: the gql.tada document simply does not declare those
  three variables. A variable that cannot be expressed cannot be sent — stronger than any runtime
  guard, and it needs no test to keep it true (though FR-016's test pins it anyway).
- Nothing in this feature may depend on the values being real (SC-008). When IFC-3127 merges, the
  values become real **with no contract change and no code change here**.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design. Result: **PASS**, with one
justified complexity entry.*

| Principle | Applies? | How this plan satisfies it |
|---|---|---|
| **I. Schema-Driven Integrity** | Yes | The card division is derived from each attribute's `branch` support declaration (FR-019), and every label and column header comes from the schema (FR-005) — never from a field-name list held in the frontend. This is what makes SC-005 free. Generated files under `src/shared/api/graphql/generated/` are **regenerated, never hand-edited**; the base branch already carries them, so codegen must produce zero drift. |
| **II. Branch-Safe by Default** | Yes | Read-only; writes nothing, so no merge behaviour to specify. The one branch-semantics risk — a branch showing a value inherited from its **origin** branch at its fork point — is correct behaviour, pinned by acceptance scenario US1-4 and US1-7, and rendered as an ordinary value rather than as an error or an empty cell. This feature computes no inheritance itself. |
| **III. Type Safety & Explicit Contracts** | Yes | The query is typed end-to-end through gql.tada against the frozen contract. No `any`; `unknown` + type guards where a boundary is loose. The nullable contract fields (`is_default`, `sync_with_git` as `NonRequiredBooleanValueField`; `sync_status` nullable while `DropdownCell` requires non-null) are guarded **in the mapper**, not at the call site. The page window and filter set are explicit inputs, never ambient state. Errors are typed (`RepositoryBranchStatusError` with a `code` union) rather than bare `Error`. |
| **IV. Test Discipline** | Yes | Unit tests for the pure pagination arithmetic and the partition rule; component tests (Vitest browser mode) for every FR carrying a component-test verification; E2E at `tests/e2e/repository/` with the `shard_branches_repo` marker against `demo_edge_repo` (FR-026). The backend slice deferred the epic's E2E requirement to this card, so it lands here. Test files mirror source structure. **Two requirements are honestly recorded as verified by review rather than by test** — see [below](#verified-by-review-not-by-test). |
| **V. Query Performance & Efficiency** | Yes | One request per page (SC-003). Server-side count, filters and ordering; no client-side narrowing (FR-015). `node_metadata` is **not selected at all** — the cheapest possible guarantee for FR-006. Row transfer bounded by page size. |
| **VI. Security & Input Boundaries** | Partial (N/A by shape) | No user input reaches a query language here — the filter values are bound as typed GraphQL variables. Authorization is the server's: the resolver raises `PermissionDeniedError` (a `ForwardableError`, HTTP 403) and the card renders `UnauthorizedScreen` for it (FR-023), distinct from the empty state, so a denial is never mistaken for "no branches" (SC-007). No error message exposes internal detail. |
| **VII. Simplicity & Maintainability** | Yes, with one justified entry | Reuses the existing `ObjectDetailsCard`, `DataTable` and `DropdownCell` rather than adding parallel ones. D1 was decided **against** the more elegant refactor precisely to avoid touching a file every object-detail page depends on. One new shared primitive (`CommitHash`) and one new pagination trio — both justified in [Complexity Tracking](#complexity-tracking). |

**Documentation requirement** (Governance → Documentation Requirements): frontend architecture
changes must update `dev/knowledge/frontend/`. FR-028 requires a note on the new pagination
component; the repo's own anti-pattern rule additionally requires a new shared primitive to be
justified in the PR description **and** added to `dev/knowledge/frontend/shared-components.md`.
Both are folded into work unit 9.

**Changelog** (Code Quality Gates → 5): this is a user-facing change, so it needs a Towncrier
fragment in `changelog/`.

### Post-Phase-1 re-evaluation

Re-checked after the data model and contracts below were settled. **No new violations.** The
design work made two constitution positions *stronger* rather than weaker:

- Principle I: choosing derived `ModelSchema` objects (D1) over a `fieldFilter` prop means the
  schema stays the single source of the division, with no second mechanism inside `ObjectDataDisplay`.
- Principle V: deciding not to pass `count` to `DataTable` (correction 2) removes a second,
  conflicting count from the DOM — the stated total has exactly one source, the server's.

## Corrections carried forward

All three plan framings verified source rather than trusting `research.md`. These four corrections
are authoritative and override `research.md` wherever it disagrees:

1. **`renderAt` is not exported** from `frontend/app/tests/components/render.tsx`. It is a private
   helper in `src/shared/components/ui/link-tab.test.tsx` and it **overrides the whole wrapper**,
   dropping `NuqsAdapter`, jotai, `QueryClient` and `BranchContext`. `research.md` §7 is wrong.
   URL-driven tests MUST instead drive `window.history` under the default `BrowserRouter` and reset
   it in `afterEach` — the only shape that keeps the nuqs adapter wired.
2. **`DataTable` renders its own count footer** whenever `count !== undefined` (rendering "N counts"),
   which would collide with FR-010a's window statement. **Do not pass `count`.**
3. **Generated gql.tada files live at** `frontend/app/src/shared/api/graphql/generated/`, and the
   **E2E suite is at repo-root `tests/e2e/`**, not under `frontend/app/`.
4. **`isOfKind(GENERIC_REPOSITORY_KIND, schema)`** already resolves both concrete repository kinds
   through `inherit_from` — the same predicate `object-details-tabs.tsx` uses for tab injection.
   FR-020's gate needs **no kind list**.

## Architecture decisions

Four decisions where the three framings diverged. Settled; not to be revisited during implementation.

### D1 — Two derived `ModelSchema` objects, not a `fieldFilter` prop

Build two derived `ModelSchema` objects with filtered `attributes` and hand each to the **unchanged**
`ObjectDetailsCard` / `ObjectDataDisplay`.

*Rejected*: adding an optional `fieldFilter` predicate to `ObjectDataDisplay` (~8 lines, default =
today's behaviour). Both reach the same place, but the derived-schema route **touches no file that
every object-detail page depends on** — the one change in this feature that could break unrelated
pages, and the refactor framing's own risk register ranked that edit as its highest-blast-radius item.

*Cost accepted*: two `ObjectDataDisplay` instances mount two metadata `Sheet`s, both default closed —
a duplicated dialog in the tree, not a behaviour change.

### D2 — Tests mock at the API layer, never the hook

Mock `…/api/get-repository-branch-status-from-api` and let the **real** use case and react-query run.
Mocking the query *hook* hides the request, so every request assertion degrades to asserting a mock.

**The pairing rule — non-negotiable, and the single most important rule in this plan:** every request
assertion MUST be paired, *in the same test*, with a rendered-output assertion drawn from a **different
payload**. A filter change is then observable twice: `apiMock.mock.calls[1][0]` carries the new
variables, *and* the rendered rows change to a second payload containing a branch absent from the first.

This is what makes the suite non-tautological. A client-side filter would change rows without a second
call; a "call the server and ignore the response" bug would keep the old rows. Neither passes.

### D3 — Pagination in three layers

| Layer | File | Knows about |
|---|---|---|
| Pure functions | `src/shared/utils/table-pagination.ts` | arithmetic only — no React, no URL |
| Hook | `src/shared/hooks/use-table-pagination.ts` | the URL, scoped by a **required** `urlKey` |
| Component | `src/shared/components/table/table-pagination.tsx` | nothing about URLs — controlled via `page` / `onPageChange` |

The controlled component is what makes FR-011a testable with no URL at all, and what makes the three
later migrations mechanical. Building it uncontrolled — the legacy shape — would rebuild the exact
defect that makes the legacy component unmigratable.

`urlKey` is a **required** prop, never defaulted. That is the whole of FR-011's collision guarantee,
pinned by a test rendering two probes with different keys and asserting one is unmoved after the
other pages.

### D4 — A typed error from the use case

The use case throws `RepositoryBranchStatusError` carrying `code: "PERMISSION_DENIED" | "UNKNOWN"`,
derived from the error catalogue. Verified against the merged backend: the resolver raises
`PermissionDeniedError`, a `ForwardableError` with HTTP 403, and the frontend catalogue already
declares `ERROR_CODES.PERMISSION_DENIED` with typed `PermissionDeniedData`.

Without this the distinction dies at `graphqlClient.query`, which rethrows as a bare `Error` with the
detail only on `.cause`. Two independently testable levels result: a use-case unit test over the raw
`extensions` payload, and a card test over the two `code` values.

## Project Structure

### Documentation (this feature)

```text
dev/specs/ifc-3130-repository-branches-card/
├── spec.md                       # 28 FRs, 3 user stories, success criteria
├── research.md                   # Phase 0 — codebase and toolchain facts (superseded in 4 places)
├── plan-synthesis.md             # Merged output of three parallel plan framings
├── design.md                     # Verbatim transcription of the design canvas
├── plan.md                       # This file
├── data-model.md                 # Phase 1 output
├── quickstart.md                 # Phase 1 output
├── contracts/
│   └── repository-branch-status-ui.md   # Phase 1 output — the UI-side contract
├── checklists/
│   └── requirements.md
└── tasks.md                      # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
frontend/app/src/
├── shared/
│   ├── utils/table-pagination.ts                      # NEW — pure paging arithmetic
│   ├── hooks/use-table-pagination.ts                  # NEW — URL-scoped, required urlKey
│   └── components/
│       ├── table/
│       │   ├── data-table.tsx                         # REUSED UNCHANGED (do not pass `count`)
│       │   └── table-pagination.tsx                   # NEW — controlled, card-safe
│       └── display/commit-hash.tsx                    # NEW — the one justified new primitive
│
└── entities/
    ├── repository/
    │   ├── api/get-repository-branch-status-from-api.ts        # NEW — the mock boundary (D2)
    │   ├── domain/
    │   │   ├── model/repository-branch-status.ts               # NEW — row model + typed error
    │   │   ├── use-cases/get-repository-branch-status.ts       # NEW
    │   │   └── rules/partition-attributes-by-branch-support.ts # NEW — pure, unit-testable
    │   └── ui/
    │       ├── queries/get-repository-branch-status.query.ts   # NEW — gql.tada document
    │       ├── repository-branches-card/
    │       │   ├── repository-branches-card.tsx                # NEW
    │       │   ├── columns.tsx                                 # NEW
    │       │   ├── cells/                                      # NEW
    │       │   └── use-repository-branch-filters.ts            # NEW
    │       └── repository-object-details.tsx                   # NEW — the two-card split
    │
    └── nodes/object/ui/object-details/
        └── object-details.tsx                          # EDITED — the isOfKind gate only

frontend/app/tests/
├── fake/repository.ts                                  # NEW — row factories
└── fake/dropdown.ts                                    # NEW

tests/e2e/repository/
└── test_repository_branches_card.py                    # NEW — marker: shard_branches_repo

dev/knowledge/frontend/
├── table-pagination.md                                 # NEW (FR-028)
└── shared-components.md                                # EDITED — CommitHash + drift fixes

changelog/                                              # NEW Towncrier fragment
```

**Structure Decision**: Feature-Sliced, following the repository's existing `entities/<slice>/{api,domain,ui}`
layout exactly. The branches card is **inside the repository entity** because it is repository-scoped
presentation; the pagination trio is in **`shared/`** because FR-028 declares it the intended
successor for every future table. `object-details.tsx` is the **only** shared file edited, and only
to add the kind gate.

**The card stays inside the detail route's outlet**, never replacing the page shell — IFC-3150 adds
its Commits tab as a sibling route on the same page.

## Reuse inventory

Verified against source and against `dev/knowledge/frontend/shared-components.md`. The three framings
each assumed more had to be built than actually does.

| Need | Use | Verdict |
|---|---|---|
| Card header: title + count pill + caption | `Content.CardTitle` — `{title, description, end, badgeContent, reload, isReloadLoading}` (`shared/components/layout/content.tsx`) | **USE WITH PROPS** — `badgeContent` is the count; caption goes in `end`. Live example: `entities/branches/ui/branches-list.tsx` |
| `default` row marker | `BranchDefaultBadge` (`entities/branches/ui/branch-list-item/branch-default-badge.tsx`) — already renders the literal `default` | **USE AS-IS** |
| Branch link target | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` (`entities/branches/ui/routing/branch-urls.ts`) | **USE AS-IS** |
| Branch link cell | Compose `Tooltip` + `LinkButton href={getBranchDetailsUrl(name)}`, following `branches-table/cells/branch-name-cell.tsx` | **EXTEND, do not reuse** — that cell hard-depends on `useAuth()`, `StickyLeftCell` and a selection checkbox |
| Search field | `SearchInput` — `{value, onChange, placeholder, onPressReset, …}` (`shared/components/inputs/search-input.tsx`), pure and controlled, plus `useDebounce` (`shared/hooks/useDebounce.ts`) | **USE AS-IS** |
| Branch-status filter | `BranchStatusEnum` — `{value, onChange, defaultOpen?}` (`entities/branches/ui/filters/branch-status-enum.tsx`), fully controlled | **USE AS-IS** with card-scoped state |
| Empty state | `NoDataFound` — `{message?, icon?}` (`shared/components/errors/no-data-found.tsx`), already `col-span-full py-12` | **USE AS-IS** — card-safe |
| Permission-denied state | `UnauthorizedScreen` — `{className?, message?, icon?}` (`shared/components/errors/unauthorized-screen.tsx`) | **USE WITH PROPS** — page-shaped `flex-1 p-8`, needs a `className` override |
| Error state | `ErrorScreen` — `{className?, message?, icon?, hideIcon?}` (`shared/components/errors/error-screen.tsx`) | **USE WITH PROPS** — same override |
| Loading state | `ObjectTableSkeleton` — `{headerCount: number}` (`entities/nodes/object/ui/object-table/object-table-skeleton.tsx`) | **USE AS-IS** — emits bare grid cells, valid only inside the grid table |
| Info icon beside a value | `Tooltip` from `@infrahub/ui` with `nonInteractiveTrigger` + `InfoIcon`, per `entities/branches/ui/branch-details/branch-attributes.tsx` | **USE AS-IS** |
| Copy affordance (full hashes, details card only) | `CopyToClipboardButton` — `{data, …AriaButtonProps}` (`shared/components/buttons/copy-to-clipboard-button.tsx`), already wrapped in a `Copied!`/`Copy` Tooltip | **USE AS-IS** |

**`UnauthorizedScreen` existing is what makes FR-023's denied-vs-empty distinction cheap** — the two
states differ by *component*, not by a hand-written string.

### The one new primitive: `CommitHash`

Nothing in the app renders a monospace, truncating, short-form hash. The only `font-mono` usage is
`entities/path-traversal/ui/infra-node.tsx`, and there is no short-hash helper anywhere.
`src/shared/components/display/commit-hash.tsx` is justified.

It **composes** `CopyToClipboardButton` rather than reimplementing copying, and takes `copyable` as a
prop: the design places copy affordances **only** on the full hashes in the details card, never in
table cells.

### Reuse traps — do not walk into these

1. **`FilterSearchInput`** (`entities/nodes/object/ui/filters/filter-search-input.tsx`) is the obvious
   grab: it is already used with the exact placeholder `"Search branches"` at `branches-list.tsx`.
   It writes **global `QSP.FILTER`** via `useSearch` → `useFilters`. Use the underlying `SearchInput`.
2. **`useFilters()`** (`entities/nodes/filters/ui/hooks/use-filters.ts`) infects `FilterSearchInput`,
   `BranchesEmpty`, `BranchStatusFilterForm`, `BranchStatusHeader` **and `BranchesTable` itself**.
3. **`BranchesTable` takes zero props** — filters, columns and empty state are all hardcoded, so it
   cannot be reused in a card. `BranchesDataTable` *is* prop-driven but mounts `BranchesToolbar`,
   which renders a **`fixed bottom-10` viewport-anchored** toolbar and needs a Router. **Use
   `DataTable` directly.**
4. **`BranchStatusFilterForm` cannot be reused** — it writes through `useFilters()`'s single global
   `QSP.FILTER` key and would collide exactly as `usePagination` does. Use `BranchStatusEnum` with
   card-scoped state.
5. **Test-provider requirements**: `DataTable` and `BranchesDataTable` call `useAuth()`;
   `useCurrentBranch` needs the jotai provider; any `nuqs` state needs `NuqsAdapter`. All are in
   `tests/components/render.tsx` — which is precisely why copying `link-tab.test.tsx`'s private
   `renderAt` would break them (correction 1).

## Design-to-spec reconciliation

The design canvas shows a **six-column** grid. The spec removes three of those columns. The columns
actually built are:

| Design column | Built? | Why |
|---|---|---|
| `Branch` | ✅ | Row identity; name links to the branch detail page (FR-003a) |
| `Import status` | ✅ | Rendered by `DropdownCell`, label and colour from the schema (FR-004, FR-005) — **not** renamed from `sync_status` |
| `Commit` | ✅ | `CommitHash`, non-copyable in table cells |
| `Ref` (read-only kind only) | ✅ | The ref that branch tracks (FR-002) |
| `Upstream` | ❌ | FR-006 — epic IFC-3101, separate data path |
| `Last import` | ❌ | FR-006, including any `updated_at` substitute |
| Row-menu (40px) | ❌ | FR-003a — the design does not specify its contents, so it is not invented |
| `3 behind` pills | ❌ | FR-006 |
| `Showing 5 of 12 · Load more` footer | ❌ | Replaced by page controls (clarification + FR-011) |

**Custom `gridTemplateColumns` is required**: `DataTable`'s default reserves a trailing 2.5rem
actions column this card must not have.

**The one knowing divergence from the canvas** is paging: page controls with the position in the URL,
not "Load more". A "load more" affordance cannot express a position in the URL (incompatible with
FR-011) and cannot serve the "jump to the failing branch among 200" journey. **Raise this on T094 in
IFC-3101**, the existing forum for unresolved canvas decisions — not in a separate conversation.

## Accessibility mechanics (FR-025) — adopt before the card is written, not after

`DataTable` emits `data-testid="data-table-row"`, and the path of least resistance is `getByTestId`,
which defeats FR-025. Two changes make the requirement reachable:

- Each row carries `role="row"` with an accessible name including the branch name, so
  `getByRole("row", { name: /feat\/bgp-policies/ })` works and cells can be scoped with `within(row)`.
  **Without this, FR-003 can only be written as a whole-table text assertion, which passes whenever
  *any* row carries the default marker.**
- The default marker is `<Badge aria-label="Default branch">default</Badge>`.

**FR-004 and FR-025 conflict on their face**, and the resolution must be written into both tests:
colour may never be used to *locate* an element, but asserting a chip's `backgroundColor` **after**
locating it by accessible name is a data-flow assertion, not a colour dependency. Assert
`backgroundColor` **only** — never the derived text colour, which `DropdownCell` computes with
`lch(from …)` and which serialises inconsistently.

## Verified by review, not by test

Two requirements cannot be honestly verified by test. Recording them as such is deliberate: a green
test that proves nothing is worse than an honest note.

- **FR-008** ("no row value may depend on data outside the graph read") is unfalsifiable in a test
  that mocks the only source it has. Nearest honest substitute: assert the api mock is called
  **exactly once per render**, in a file that mocks nothing else.
- **FR-017** (the three legacy paginated pages behave as today) would need three regression files for
  three pages that have **no tests at all** — more cost than the requirement buys, and the resulting
  tests would be the only coverage those files have. The honest guarantee is **zero diff**:
  `git diff --exit-code` on `pagination.tsx` and `usePagination.ts`, plus the FR-011 key-scoping unit
  test proving the new hook *cannot* collide with `QSP.PAGINATION`.

## Work units

Parallel groups separated by `───`. Units within a group share no file and have no sequential
dependency.

| # | Unit | Key files | FRs |
|---|---|---|---|
| 1 | Pagination utils + hook + component | `shared/utils/table-pagination.ts`, `shared/hooks/use-table-pagination.ts`, `shared/components/table/table-pagination.tsx` | 010, 010a, 011, 011a, 017 |
| 2 | Query, model, mapper, use case | `entities/repository/{api,domain/model,domain/use-cases,ui/queries}/…` | 001, 008, 009, 013, 016, 023 |
| 3 | Partition rule | `entities/repository/domain/rules/partition-attributes-by-branch-support.ts` | 019, 022 |
| 4 | Test factories | `tests/fake/repository.ts`, `tests/fake/dropdown.ts` | — |
| ─── | | | |
| 5 | Columns, cells, filters | `…/repository-branches-card/columns.tsx`, `cells/`, `…/use-repository-branch-filters.ts` | 002–006, 012–015 |
| ─── | | | |
| 6 | The branches card | `…/repository-branches-card.tsx` | 007, 023, 024, 025, 027 |
| 7 | The details split | `…/repository-object-details.tsx` + the kind gate in `object-details.tsx` | 018, 018a, 020, 021, 022 |
| ─── | | | |
| 8 | E2E | `tests/e2e/repository/test_repository_branches_card.py` | 026 |
| 9 | Knowledge note + `shared-components.md` + changelog fragment | `dev/knowledge/frontend/table-pagination.md`, `dev/knowledge/frontend/shared-components.md`, `changelog/` | 028 |

**Dependencies**: 1–4 are fully independent. 5 depends on 2 and 4. 6 depends on 1, 4, 5. 7 depends
on 3. 8 depends on 6 and 7. 9 depends on 1 and 6.

## Risks, ranked by likelihood of actually biting

1. **Tautological request assertions.** Mitigated by D2, but only if the pairing rule is followed in
   *every* test. This is the failure that would make the whole suite decorative.
2. **URL bleed between tests.** `render.tsx` uses `BrowserRouter`, so nuqs writes to real
   `window.location`. Without an `afterEach` history reset, paging tests become order-dependent — the
   classic "passes alone, fails in a full run".
3. **`DataTable` geometry inside a `Card`.** `min-w-max` plus a sticky first cell inside a rounded
   card will overflow unless an explicit `gridTemplateColumns` is passed and the body scrolls
   horizontally *within* the card.
4. **Nullable contract fields.** `is_default` and `sync_with_git` are `NonRequiredBooleanValueField`;
   `sync_status` is a nullable `Dropdown` while `DropdownCell` requires non-null. Guard in the mapper;
   likely to appear during the preview window.
5. **Filter/page coupling (FR-014).** With independent URL keys, resetting the page on a filter change
   is a manual call, easy to forget on one of the two filters. Put the reset inside a single
   `setFilters` wrapper.
6. **E2E cost and flake.** Ten `sync_with_git=True` branches each trigger real git-worker branch
   creation; the card can render before all rows exist, so a total assertion races. **Poll the
   heading total** rather than asserting once.
7. **FR-006 asserted by absence.** `not.toHaveTextContent("ago")` passes for a card rendering nothing.
   Pair it with a positive assertion in the same test.
8. **Row identity.** The contract guarantees one row per branch, so synthesise `id` from `name.value`
   **in the mapper**. Do **not** relax `DataTable<T extends NodeCore>` or its `getRowId` — that
   touches every table in the app.

## Deliberately not doing

Each argued and then cut by the refactor-friendly framing:

- Making `RelationshipTable` accept an injected query — the most visible rough edge, the most
  expensive, and no FR needs it.
- Relaxing `DataTable`'s generic or `getRowId`.
- Migrating the three legacy `Pagination` call sites (FR-017 and spec Out of Scope).
- Converting `BranchesTable` off `InfiniteScroll`, or fixing `infinite-scroll.tsx`'s observer-root
  problem — we avoid infinite scroll entirely.
- Building the drift provider or a fifth card state. Build the **column slot**, not the machinery;
  the fifth state is IFC-3101's to specify.
- A dedicated repository route shell — IFC-3150 adds its tab as a sibling route the router already
  supports.
- Renaming `sync_status` to "Import status" (design canvas) — out of scope in the PRD; labels follow
  the schema (FR-005).

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
|---|---|---|
| **A second pagination mechanism** alongside the legacy `Pagination` / `usePagination` | The legacy component is hard-wired to a single global `QSP.PAGINATION` key, so two paginated tables on one route move together — which this card would immediately break (FR-011). It also assumes the table is the page-level scroll area, which is false inside a card (FR-011a). | Generalising the legacy component in place would put this feature's regression risk on **three unrelated pages that have no tests at all**. The duplication is temporary and signposted: FR-028's knowledge note names the new component as the intended successor, and migrating the three call sites is tracked as follow-on work. |
| **A new shared primitive `CommitHash`** | Nothing in the app renders a monospace, truncating, short-form hash; the only `font-mono` usage is unrelated and there is no short-hash helper. Two call sites exist on arrival (table cells, non-copyable; details rows, copyable), satisfying Principle VII's two-caller bar. | Inlining the mono/truncate/short-form logic in both call sites would duplicate the hash-shortening rule — the exact thing that later drifts between the two. It composes `CopyToClipboardButton` rather than reimplementing copying. |
| **Two `ObjectDataDisplay` instances** mounting two metadata `Sheet`s (D1) | The alternative edits a file every object-detail page depends on. | See D1 — the refactor framing's own risk register ranked that edit as its highest-blast-radius item. A duplicated closed dialog in the tree is not a behaviour change. |

## Phase 0 — Research

**Status: complete.** [research.md](research.md) covers where repositories live in the frontend, why
`RelationshipTable` cannot be reused, why infinite scroll breaks inside a card, why the existing
pagination is not extended, the gql.tada (not codegen-document) approach, the attribute `branch`
support metadata, the testing patterns a new test must follow, and the backend contract summary.

**Four of its claims are superseded** by [Corrections carried forward](#corrections-carried-forward).
`research.md` is left as written — the corrections are recorded here rather than by rewriting history
in a document three plan framings were run against.

**No `NEEDS CLARIFICATION` remain.** The spec's Clarifications section settled six questions on
2026-09-10 (new paging component; page controls over "load more"; default size 20 from 10/20/50;
"On this branch" title with a branch-name caption; placement below the details card and above the
branches card; branch name links, no row-action menu).

## Phase 1 — Design & Contracts

**Status: complete.** Generated alongside this plan:

- **[data-model.md](data-model.md)** — the three key entities (repository branch status row,
  branch-support declaration, page window), their fields, nullability, and the mapper's guards.
- **[contracts/repository-branch-status-ui.md](contracts/repository-branch-status-ui.md)** — the
  UI-side contract: the exact gql.tada variable set (and the three variables deliberately **not**
  declared), the typed error shape, and the four card states. The backend contract itself is frozen
  and lives at `dev/specs/infp-671-cross-branch-repo-status/contracts/`.
- **[quickstart.md](quickstart.md)** — how to run and validate this feature locally.

**Agent context update: deliberately skipped.** `CLAUDE.md` in this repository is hand-maintained and
delegates to `AGENTS.md`; it carries no `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` markers, so
there is no managed block to refresh. Running `/speckit-agent-context-update` here would clobber a
hand-written file. This is a standing project decision, not a one-off omission.

## Phase 2 — Tasks

Not produced by this command. `/speckit-tasks` generates [tasks.md](tasks.md) from the work units,
dependency graph and FR mapping above.
