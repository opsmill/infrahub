# Plan synthesis

Three plans were produced in parallel from different framings — minimal-change, refactor-friendly,
test-first — against [spec.md](spec.md), [research.md](research.md) and [design.md](design.md).
This document is the merged result: where they agreed it records the decision once, where they
disagreed it picks and says why. It is the input to `/speckit-plan`.

## Corrections the three plans found in the inputs

All three verified source rather than trusting `research.md`. Four corrections, now authoritative:

1. **`renderAt` is not exported** from `frontend/app/tests/components/render.tsx`. It is a private
   helper in `src/shared/components/ui/link-tab.test.tsx:9`, and it overrides the whole wrapper —
   which drops NuqsAdapter, jotai, QueryClient and BranchContext. `research.md` §7 said otherwise
   and is wrong. URL-driven tests must instead drive `window.history` under the default
   `BrowserRouter` and reset it in `afterEach`, which is the only shape that keeps the nuqs adapter
   wired.
2. **`DataTable` renders its own count footer** whenever `count !== undefined`
   (`data-table.tsx:116-134`, rendering "N counts"). It would collide with FR-010a's window
   statement. **Do not pass `count`.**
3. **The generated gql.tada files live at** `frontend/app/src/shared/api/graphql/generated/`, and
   the **e2e suite is at repo-root `tests/e2e/`**, not under `frontend/app/`.
4. **`isOfKind(GENERIC_REPOSITORY_KIND, schema)`** already resolves both concrete repository kinds
   through `inherit_from` — the same predicate `object-details-tabs.tsx` uses for tab injection. FR-020's
   gate needs no kind list.

## Where all three agreed (settled, not revisited)

- **Row identity**: synthesise `id` from `name.value` in the mapper. The contract guarantees one row
  per branch. Do not relax `DataTable<T extends NodeCore>` or its `getRowId` — that touches every
  table in the app.
- **FR-016 is enforced structurally**: the gql.tada document simply does not declare
  `sync_status__value`, `internal_status__value` or `own_values_only`. A variable that cannot be
  expressed cannot be sent — stronger than any runtime guard.
- **`node_metadata` is not selected at all**, which is the cheapest possible guarantee for FR-006.
- **A pure partition function** decides the card split, unit-testable without rendering.
- **A new pagination component**, with the legacy one and `QSP.PAGINATION` untouched (FR-017).
- **Custom `gridTemplateColumns`** is required: the default reserves a trailing 2.5rem actions
  column this card must not have.

## The four decisions where they diverged

### D1 — How to render two cards from one attribute list → **two derived schemas** (2 of 3)

- *Minimal* and *test-first*: build two derived `ModelSchema` objects with filtered `attributes`,
  hand each to the existing `ObjectDetailsCard` / `ObjectDataDisplay` **unchanged**. No shared file
  is edited.
- *Refactor-friendly*: add an optional `fieldFilter` predicate to `ObjectDataDisplay` (~8 lines,
  default = today's behaviour).

**Picked: derived schemas.** Both reach the same place, but the derived-schema route touches no file
that every object-detail page depends on, which is the one change in this feature that could break
unrelated pages. The refactor plan's own risk register ranks that edit as its highest-blast-radius
item. Cost accepted: two `ObjectDataDisplay` instances mount two metadata `Sheet`s, both default
closed — a duplicated dialog in the tree, not a behaviour change.

### D2 — Where tests mock → **at the API layer** (test-first's strongest insight)

Mocking the query *hook* hides the request, so every request assertion degrades to asserting a mock.
Mock `…/api/get-repository-branch-status-from-api` instead and let the real use-case and react-query
run. A filter change is then observable twice: `apiMock.mock.calls[1][0]` carries the new variables,
**and** the rendered rows change to a second payload containing a branch absent from the first.

This is what makes the tests non-tautological. A client-side filter would change rows without a
second call; a "call the server and ignore the response" bug would keep the old rows. Neither passes.
**Every request assertion must be paired, in the same test, with a rendered-output assertion drawn
from a different payload.**

### D3 — Pagination shape → **three layers** (test-first, with refactor-friendly's controlled API)

| Layer | File | Knows about |
|---|---|---|
| Pure functions | `src/shared/utils/table-pagination.ts` | arithmetic only — no React, no URL |
| Hook | `src/shared/hooks/use-table-pagination.ts` | the URL, scoped by a required `urlKey` |
| Component | `src/shared/components/table/table-pagination.tsx` | nothing about URLs — controlled via `page` / `onPageChange` |

The controlled component is what makes FR-011a testable with no URL at all, and what makes the three
later migrations mechanical. Building it uncontrolled — the legacy shape — would rebuild the exact
defect that makes the legacy component unmigratable.

`urlKey` is a **required** prop, never defaulted: that is the whole of FR-011's collision guarantee,
and it is pinned by a test rendering two probes with different keys and asserting one is unmoved
after the other pages.

### D4 — Error handling → **a typed error from the use case**

The use case throws `RepositoryBranchStatusError` carrying `code: "PERMISSION_DENIED" | "UNKNOWN"`,
derived from the catalogue. Verified against the merged backend: the resolver raises
`PermissionDeniedError`, a `ForwardableError` with HTTP 403, and the frontend catalogue already
declares `ERROR_CODES.PERMISSION_DENIED` with typed `PermissionDeniedData`. Without this the
distinction dies at `graphqlClient.query`, which rethrows as a bare `Error` with the detail only on
`.cause`.

Two independently testable levels result: a use-case unit test over the raw extensions payload, and
a card test over the two `code` values.

## Accessibility mechanics (FR-025) — adopt before the card is written, not after

`DataTable` emits `data-testid="data-table-row"`, and the path of least resistance is `getByTestId`,
which defeats FR-025. Two changes make the requirement reachable:

- Each row carries `role="row"` with an accessible name including the branch name, so
  `getByRole("row", { name: /feat\/bgp-policies/ })` works and cells can be scoped with `within(row)`.
  **Without this, FR-003 can only be written as a whole-table text assertion, which passes whenever
  *any* row carries the default marker.**
- The default marker is `<Badge aria-label="Default branch">default</Badge>`.

**FR-004 and FR-025 conflict on their face** and the resolution must be written into both tests:
colour may never be used to *locate* an element, but asserting a chip's `backgroundColor` *after*
locating it by accessible name is a data-flow assertion, not a colour dependency. Assert
`backgroundColor` only — never the derived text colour, which `DropdownCell` computes with
`lch(from …)` and which serialises inconsistently.

## Two requirements that cannot be honestly verified by test

- **FR-008** ("no row value may depend on data outside the graph read") is unfalsifiable in a test
  that mocks the only source it has. Nearest honest substitute: assert the api mock is called exactly
  once per render, in a file that mocks nothing else.
- **FR-017** (the legacy paging pages behave as today) would need three regression files for three
  pages that have no tests at all — more cost than the requirement buys, and the resulting tests
  would be the only coverage those files have. The honest guarantee is **zero diff**:
  `git diff --exit-code` on `pagination.tsx` and `usePagination.ts`, plus the FR-011 key-scoping unit
  test proving the new hook cannot collide with `QSP.PAGINATION`.

Both should be recorded in the spec as *verified by review, not by test*. A green test that proves
nothing is worse than an honest note.

## Reuse inventory (verified against source)

The three plans each assumed more had to be built than actually does. A dedicated reuse sweep
against `dev/knowledge/frontend/shared-components.md` and the source found existing components for
almost every element. **Only one new primitive is justified.**

| Need | Use | Verdict |
|---|---|---|
| Card header: title + count pill + caption | `Content.CardTitle` — `{title, description, end, badgeContent, reload, isReloadLoading}` (`shared/components/layout/content.tsx:63`) | USE WITH PROPS — `badgeContent` is the count; caption goes in `end` for right alignment. Live example: `entities/branches/ui/branches-list.tsx:23` |
| `default` row marker | `BranchDefaultBadge` (`entities/branches/ui/branch-list-item/branch-default-badge.tsx:4`) — already renders the literal `default` | USE AS-IS |
| Branch link target | `getBranchDetailsUrl(branchName, tab?, overrideParams?)` (`entities/branches/ui/routing/branch-urls.ts:5`) | USE AS-IS |
| Branch link cell | Compose `Tooltip` + `LinkButton href={getBranchDetailsUrl(name)}` — the pattern at `branches-table/cells/branch-name-cell.tsx:39-50` | EXTEND, do not reuse the cell: it hard-depends on `useAuth()`, `StickyLeftCell` and a selection checkbox |
| Search field | `SearchInput` — `{value, onChange, placeholder, onPressReset, ...}` (`shared/components/inputs/search-input.tsx:80`), pure and controlled, plus `useDebounce` (`shared/hooks/useDebounce.ts`) | USE AS-IS |
| Branch-status filter | `BranchStatusEnum` — `{value: BranchStatus \| null, onChange, defaultOpen?}` (`entities/branches/ui/filters/branch-status-enum.tsx:14`), fully controlled | USE AS-IS with card-scoped state |
| Empty state | `NoDataFound` — `{message?, icon?}` (`shared/components/errors/no-data-found.tsx:12`), already `col-span-full py-12` | USE AS-IS — card-safe |
| Permission-denied state | `UnauthorizedScreen` — `{className?, message?, icon?}` (`shared/components/errors/unauthorized-screen.tsx:15`) | USE WITH PROPS — page-shaped `flex-1 p-8`, needs a `className` override |
| Error state | `ErrorScreen` — `{className?, message?, icon?, hideIcon?}` (`shared/components/errors/error-screen.tsx:15`) | USE WITH PROPS — same override |
| Loading state | `ObjectTableSkeleton` — `{headerCount: number}` (`entities/nodes/object/ui/object-table/object-table-skeleton.tsx:12`) | USE AS-IS — emits bare grid cells, valid only inside the grid table |
| Info icon beside a value | `Tooltip` from `@infrahub/ui` with `nonInteractiveTrigger` + `InfoIcon` — pattern at `entities/branches/ui/branch-details/branch-attributes.tsx:47` | USE AS-IS |
| Copy affordance, full hash in a details row | `CopyToClipboardButton` — `{data, ...AriaButtonProps}` (`shared/components/buttons/copy-to-clipboard-button.tsx:11`), already wrapped in a `Copied!`/`Copy` Tooltip | USE AS-IS |

**`UnauthorizedScreen` existing is what makes FR-023's denied-vs-empty distinction cheap** — the
states differ by component, not by a hand-written string.

### The one new primitive: `CommitHash`

Nothing in the app renders a monospace, truncating, short-form hash. The only `font-mono` usage is
`entities/path-traversal/ui/infra-node.tsx:91`, and there is no short-hash helper anywhere.
`src/shared/components/display/commit-hash.tsx` is justified, and per the repo's own anti-pattern
rule a new shared primitive **must be justified in the PR description and added to
`shared-components.md`** — folded into FR-028's documentation requirement.

It composes `CopyToClipboardButton` rather than reimplementing copying, and takes `copyable` as a
prop: the design places copy affordances **only** on the full hashes in the details card, never in
table cells.

### Reuse traps found (beyond the two already known)

1. `FilterSearchInput` (`entities/nodes/object/ui/filters/filter-search-input.tsx:15`) — the
   component already used with the exact placeholder `"Search branches"` at `branches-list.tsx:40`,
   and therefore the obvious thing to grab. It writes global `QSP.FILTER` via `useSearch` →
   `useFilters`. Use the underlying `SearchInput` instead.
2. `useFilters()` (`entities/nodes/filters/ui/hooks/use-filters.ts:8`) infects `FilterSearchInput`,
   `BranchesEmpty`, `BranchStatusFilterForm`, `BranchStatusHeader` **and `BranchesTable` itself**.
3. `BranchesTable` takes **zero props** — filters, columns and empty state are all hardcoded, so it
   cannot be reused in a card. `BranchesDataTable` *is* prop-driven, but mounts `BranchesToolbar`,
   which renders a **`fixed bottom-10` viewport-anchored** toolbar and needs a Router. Use
   `DataTable` directly.
4. Test-provider requirements: `DataTable` and `BranchesDataTable` call `useAuth()`; `useCurrentBranch`
   needs the jotai provider; any `nuqs` state needs `NuqsAdapter`. All are in
   `tests/components/render.tsx` — which is precisely why copying `link-tab.test.tsx`'s private
   `renderAt` (which overrides the whole wrapper) would break them.

### Documentation drift found

`shared-components.md` disagrees with source in five places, all worth capturing in phase 4.5: it
lists `Pagination` as a plain primitive without noting it is hard-wired to global `QSP.PAGINATION`;
lists `SearchInput` without distinguishing it from the URL-writing `FilterSearchInput`; omits
`CountBadge` and `Content.CardTitle` entirely; misfiles `Badge` under "Layout"; and has **no entry at
all** for `shared/components/errors/` or for skeletons. The first two are exactly the traps that
would mislead the next reader.

## Work units

Parallel groups separated by `───`.

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
| 9 | Knowledge note | `dev/knowledge/frontend/table-pagination.md` | 028 |

Units 1–4 are fully independent. 5 depends on 2 and 4. 6 depends on 1, 4, 5. 7 depends on 3. 8
depends on 6 and 7.

## Risks, merged and ranked by likelihood of actually biting

1. **Tautological request assertions.** Mitigated by D2, but only if the pairing rule is followed in
   every test. This is the failure that would make the whole suite decorative.
2. **URL bleed between tests.** `render.tsx` uses `BrowserRouter`, so nuqs writes to real
   `window.location`. Without an `afterEach` history reset, paging tests become order-dependent —
   the classic "passes alone, fails in a full run".
3. **`DataTable` geometry inside a `Card`.** `min-w-max` plus a sticky first cell inside a rounded
   card will overflow unless an explicit `gridTemplateColumns` is passed and the body scrolls
   horizontally within the card.
4. **Nullable contract fields.** `is_default` and `sync_with_git` are `NonRequiredBooleanValueField`;
   `sync_status` is a nullable `Dropdown` while `DropdownCell` requires non-null. Guard in the
   mapper; likely to appear during the preview window.
5. **Filter/page coupling (FR-014).** With independent URL keys, resetting the page on a filter
   change is a manual call that is easy to forget on one of the two filters. Put the reset inside a
   single `setFilters` wrapper.
6. **E2E cost and flake.** Ten `sync_with_git=True` branches each trigger real git-worker branch
   creation; the card can render before all rows exist, so a total assertion races. Poll the heading
   total rather than asserting once.
7. **FR-006 asserted by absence.** `not.toHaveTextContent("ago")` passes for a card rendering
   nothing. Pair it with a positive assertion in the same test.
8. **`BranchStatusFilterForm` cannot be reused** — it writes through `useFilters()`, a single global
   `QSP.FILTER` key, and would collide exactly as `usePagination` does. Use the underlying
   `BranchStatusEnum` with card-scoped state.

## Deliberately not doing

Carried from the refactor-friendly plan, which argued each case and then cut them:

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
