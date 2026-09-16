# Tasks: Repository branches card and branch-scoped details

**Feature**: IFC-3130 | **Branch**: `ple-branches-card-ifc-3130` | **Base**: `cross-branch-repo-status-infp-671`

**Input**: [plan.md](plan.md) (work units, dependency graph, reuse inventory), [spec.md](spec.md)
(32 FRs, 3 user stories), [data-model.md](data-model.md),
[contracts/repository-branch-status-ui.md](contracts/repository-branch-status-ui.md),
[critiques/critique-2026-09-16.md](critiques/critique-2026-09-16.md).

**Tests are required for this feature** — the constitution's Test Discipline principle applies, and
every FR carries a stated verification method.

---

## Rules that apply to every task in this file

Violating any of these produces work that passes review and fails its purpose. They are repeated in
the individual tasks that depend on them, but they hold everywhere.

1. **Mock at `entities/repository/api/get-repository-branch-status-from-api`, never the query hook.**
   Mocking the hook hides the request, and every request assertion degrades to asserting a mock.
2. **Every request assertion is paired, in the same test, with a rendered-output assertion from a
   different payload.** Use `expectServerDrivenChange(...)` (T006); direct `apiMock.mock.calls[...]`
   is lint-blocked in the card's test files.
3. **Never pass `count` to `DataTable`** — it renders its own "N counts" footer that collides with
   FR-010a's window statement.
4. **Define `gridTemplateColumns` at module scope**, never as an inline arrow — `DataTable` memoizes
   its grid style on that identity. (Manual memoization is forbidden in this repo; module scope is
   the compiler-independent fix.)
5. **No `useCallback` / `useMemo` / `React.memo`** — the React Compiler is enabled.
6. **Locate elements by accessible name, never by colour, class or `data-testid`** (FR-025).
7. **Refer to FRs individually.** There are **32** statements: FR-001…FR-028 plus FR-003a, FR-010a,
   FR-011a, FR-018a. A range silently omits the suffixed ones.

---

## Phase 1: Setup

- [ ] T001 Add a shared Vitest `afterEach` that resets `window.location.search` (not just
      `history.state`) in `frontend/app/tests/setup.ts`, so nuqs-driven URL state cannot leak between
      test files. `tests/components/render.tsx` mounts a real `BrowserRouter`, so without this the
      paging tests pass alone and fail in a full run. It goes in the **shared** setup file, not
      per-file, so a new test file cannot silently opt out.

---

## Phase 2: Foundational — work unit 4 (BLOCKING)

**These must land before any card test is written.** Once unpaired tests exist, the pairing helper
becomes a migration rather than a default, and that is the one decision in this plan that cannot be
retrofitted cheaply.

- [ ] T002 [P] Create row factories in `frontend/app/tests/fake/repository.ts` producing
      `InfrahubRepositoryBranchStatus` wire payloads. Cover the nullable shapes the mapper must
      survive: `is_default` and `sync_with_git` absent entirely (not merely `{value: null}`),
      `sync_status` null, `commit` null, and `ref` null for `CoreRepository`.
- [ ] T003 [P] Create `Dropdown` factories in `frontend/app/tests/fake/dropdown.ts` emitting
      `{value, label, color, description}`, including at least one **invented** value/label/colour
      triple — FR-004 is verified by asserting an invented value renders with its invented label and
      colour, which only works if the factory can produce one.
- [ ] T004 [P] Create page factories in `frontend/app/tests/fake/repository.ts` producing a
      `{count, edges}` envelope where `count` exceeds `edges.length`, so FR-009's "the total is the
      server's, not the row count" is expressible.
- [ ] T005 Write at least two **distinct** payload fixtures whose row sets do not overlap (a branch
      present in one and absent from the other), in `frontend/app/tests/fake/repository.ts`. Every
      paired assertion needs a second payload to draw its rendered-output half from; without disjoint
      fixtures the pairing rule cannot be satisfied.
- [ ] T006 Implement `expectServerDrivenChange({apiMock, callIndex, variables, payload, rowVisibleAfter})`
      in `frontend/app/tests/helpers/expect-server-driven-change.ts`. **Every argument is required** —
      the signature is the enforcement mechanism, so that omitting the rendered-output half is a type
      error rather than a reviewer's catch. It asserts the call at `callIndex` carries `variables`,
      **and** that `rowVisibleAfter` is rendered once `payload` resolves.
- [ ] T007 Add a lint guard forbidding direct `apiMock.mock.calls[...]` member access inside
      `frontend/app/src/entities/repository/ui/repository-branches-card/**/*.test.tsx`. A Biome
      `noRestrictedSyntax`-style rule if the config supports it; otherwise a two-line grep step in the
      `frontend-lint` CI job. Without this, T006 is a suggestion.

**Checkpoint**: T001–T007 complete. Units 1, 2, 3 and 5's tests now have the only sanctioned path.

---

## Phase 3: User Story 1 — See every branch's status from the repository page (P1) 🎯 MVP

**Goal**: A card listing each in-scope branch with its sync status and imported commit, server-paged,
without switching branches.

**Independent test**: Open a repository with more branches than one page. Assert the rendered rows
carry each branch's own values, that the stated total reflects every in-scope branch rather than the
page, and that moving to page 2 returns different rows.

### Work unit 1 — pagination (three layers)

- [ ] T008 [P] [US1] Implement pure paging arithmetic in
      `frontend/app/src/shared/utils/table-pagination.ts` — page↔offset conversion, total-page count,
      clamping, and the window statement's numbers. **No React, no URL.** Covers FR-010, FR-010a.
- [ ] T009 [P] [US1] Unit-test `table-pagination.ts` in `table-pagination.test.ts`: boundary cases at
      page 1, the last page, an exact multiple of page size, a single page, and zero rows (FR-010a
      must read correctly when the set is smaller than one page).
- [ ] T010 [US1] Implement `useTablePagination({urlKey, defaultPageSize})` in
      `frontend/app/src/shared/hooks/use-table-pagination.ts`. **`urlKey` is a required prop and is
      never defaulted** — that is the whole of FR-011's collision guarantee. Add a dev-mode warning
      when two mounted instances share a key. Covers FR-011.
- [ ] T011 [US1] Unit-test `use-table-pagination.ts` in `use-table-pagination.test.ts`: render two
      probes with **different** `urlKey`s and assert one is unmoved after the other pages. This is
      the test that proves the new hook cannot collide with the legacy global `QSP.PAGINATION`, and
      it is half of FR-017's guarantee alongside T071's zero-diff check. Covers FR-011, FR-017.
- [ ] T012 [US1] Implement the **controlled** `TablePagination` component in
      `frontend/app/src/shared/components/table/table-pagination.tsx` — props `{page, pageSize,
      totalCount, onPageChange, onPageSizeChange}`, knowing nothing about URLs. Previous/next, direct
      page selection, and a page-size selector offering 10 / 20 / 50 (default 20). Covers FR-010,
      FR-010a. Building it uncontrolled would rebuild the exact defect that makes the legacy
      component unmigratable.
- [ ] T013 [US1] Give `TablePagination` its accessible names (FR-025): `aria-current="page"` on the
      active page, named previous/next controls, a labelled page-size selector, and an announced page
      change. Three future migrations inherit whatever this ships.
- [ ] T014 [US1] Component-test `TablePagination` in `table-pagination.test.tsx` rendering it inside a
      **fixed-height card with no page-level scroll container**, asserting paging works there
      (FR-011a). Locate every control by accessible name.

### Work unit 2 — query, model, mapper, use case

- [ ] T015 [P] [US1] Write the gql.tada document in
      `frontend/app/src/entities/repository/api/get-repository-branch-status-from-api.ts`, alongside
      the api boundary. Every gql.tada document in this codebase lives in `api/*-from-api.ts`; none
      lives in `ui/queries/`, which is the react-query `queryOptions` layer. Putting it in `ui/` would
      force an `api/ → ui/` import, which `dev/knowledge/frontend/entities-structure.md` prohibits.
      Declare **only** `id`, `limit`, `offset`, `name__value`, `partial_match`, `status__value`.
      **Do not declare `sync_status__value`, `internal_status__value` or `own_values_only`** — that
      omission *is* FR-016's enforcement; the backend rejects all three with a `ValidationError`
      during the preview window. **Do not select `node_metadata`** — not asking for it is the
      structural guarantee behind FR-006 and FR-008. Select `sync_status { value label color
      description }` so FR-004's label and colour come from the schema.
- [ ] T016 [P] [US1] Define the row model and `RepositoryBranchStatusError` (with
      `code: "PERMISSION_DENIED" | "UNKNOWN"`) in
      `frontend/app/src/entities/repository/domain/model/repository-branch-status.ts`.
- [ ] T017 [US1] Implement the mapper in the same module. **Guard every nullable field in the mapper,
      never at the call site**: `is_default?.value ?? false`, `sync_with_git?.value ?? false`,
      `commit?.value ?? null`, `ref?.value ?? null`, and `sync_status` → `null` when the `Dropdown` or
      its `value` is absent (`DropdownCell` requires non-null). **Synthesise `id` from `name.value`** —
      do not relax `DataTable<T extends NodeCore>` or its `getRowId`.
- [ ] T018 [US1] Implement the api boundary
      `frontend/app/src/entities/repository/api/get-repository-branch-status-from-api.ts`. **This
      module is the mock point for every test in this feature** — keep it thin and free of logic worth
      testing.
- [ ] T019 [US1] Implement the use case in
      `frontend/app/src/entities/repository/domain/use-cases/get-repository-branch-status.ts`, throwing
      the typed error. **Compose the existing `hasCatalogueCode` from
      `shared/api/graphql/error-handling.ts`** (which itself calls `parseCatalogueError` from
      `shared/api/errors/`) rather than re-reading `extensions` by hand.
- [ ] T020 [US1] Unit-test the use case's error mapping over a raw `extensions` payload in
      `get-repository-branch-status.test.ts`: a `PERMISSION_DENIED` payload yields `code:
      "PERMISSION_DENIED"`, anything else yields `"UNKNOWN"`.
- [ ] T021 [US1] Unit-test the mapper in `repository-branch-status.test.ts` against T002's nullable
      fixtures — each guard exercised, with the field **absent** as well as null.

### Work unit 5a — the new primitive and the display columns

- [ ] T022 [P] [US1] Implement `CommitHash` in
      `frontend/app/src/shared/components/display/commit-hash.tsx` — monospace, truncating, short-form
      (7 characters, git's own default abbreviation and what the design uses), with a `copyable` prop
      that **composes `CopyToClipboardButton`** rather than reimplementing copying. The full hash goes
      on `title`, **not** `aria-label`: ARIA forbids naming a role-less element and Biome's
      `a11y/useAriaPropsSupportedByRole` rejects it. Copy affordances appear only on full hashes in the
      details card, never in table cells.
- [ ] T023 [P] [US1] Component-test `CommitHash` in `commit-hash.test.tsx`: truncation, the full value
      in the accessible name, and `copyable` on/off.
- [ ] T024 [US1] Implement the branch-name cell in
      `frontend/app/src/entities/repository/ui/repository-branches-card/cells/branch-name-cell.tsx`.
      **Compose `Tooltip` + `LinkButton href={getBranchDetailsUrl(name)}`; do not reuse
      `branches-table/cells/branch-name-cell.tsx`**, which hard-depends on `useAuth()`,
      `StickyLeftCell` and a selection checkbox. Use `BranchDefaultBadge` as-is for the default
      marker, with `aria-label="Default branch"`. Covers FR-003, FR-003a.
- [ ] T025 [US1] Define the columns in
      `frontend/app/src/entities/repository/ui/repository-branches-card/columns.tsx` — Branch,
      `sync_status` (via the existing `DropdownCell`), Commit, plus **Ref on the read-only kind only**.
      `DropdownCell` currently types its prop as the **full** generated `Dropdown` but reads only
      `color`, `label` and `value`; the query selects a four-field subset. Widen its prop to
      `Pick<Dropdown, "value" | "label" | "color">`. This is a **type-only** widening of a shared file —
      strictly more permissive, no runtime change, and it makes the signature honest about what the
      component uses.
      **Every header text comes from the schema** (FR-005): do not hardcode the canvas's `Import
      status` or `Git state`. Declare `gridTemplateColumns` **at module scope** — `DataTable`'s default
      reserves a trailing 2.5rem actions column this card must not have. **No row-action menu column**
      (FR-003a). Covers FR-002, FR-004, FR-005.
- [ ] T026 [US1] Give each row `role="row"` with an accessible name including the branch name, so
      `getByRole("row", {name: /…/})` works and cells can be scoped with `within(row)`. Without this,
      FR-003 can only be written as a whole-table text assertion, which passes whenever **any** row
      carries the default marker. **This cannot be done from the card's own files** — the row wrapper
      lives in `shared/components/table/data-table.tsx`. Add `role="row"` there **and `role="table"`
      on its grid container**: an orphan `row` is invalid ARIA and reads inconsistently. Biome's
      `useFocusableInteractive` fires on `row` regardless and needs a one-line suppression (a wrapped
      two-line `biome-ignore` is not honoured). Covers FR-025.

### Work unit 6 — the card

- [ ] T027 [US1] Implement `RepositoryBranchesCard` in
      `frontend/app/src/entities/repository/ui/repository-branches-card/repository-branches-card.tsx`.
      Use `DataTable` **directly** — not `BranchesTable` (zero props, hardcoded filters) and not
      `BranchesDataTable` (mounts a `fixed bottom-10` viewport-anchored toolbar). **Do not pass
      `count`.** Title `Branches` on the read-write kind, `Infrahub branches` on the read-only kind,
      with the total in the count badge. Covers FR-001, FR-007, FR-009.
- [ ] T028 [US1] Wire the card header: the count goes in `badgeContent`; give the header an explicit
      `aria-label` and **assert the count by the badge's own accessible name, not the heading's** —
      `Content.CardTitle` renders its title as `<h1>` with the badge as a sibling, so the count is not
      part of the heading's accessible name.
- [ ] T029 [US1] Implement the four card states (FR-023) using the strings pinned in
      [contracts/repository-branch-status-ui.md](contracts/repository-branch-status-ui.md) §4:
      `NoDataFound` for both empty cases (filtered vs none-in-scope — **different strings**),
      `UnauthorizedScreen` for `PERMISSION_DENIED`, `ErrorScreen` otherwise (both need a `className`
      override; their defaults are page-shaped `flex-1 p-8`). Both are **default** exports.
- [ ] T030 [US1] Implement the loading state. `ObjectTableSkeleton` **cannot be used as-is**: it
      hardcodes 20 rows and a disabled `Checkbox` in column 0. Add optional `rowCount` /
      `showSelection` props (additive, defaulting to today's behaviour) or render a local skeleton.
      As-is it ships a phantom checkbox and a guaranteed layout jump at page size 10 — what FR-023's
      loading clause forbids.
- [ ] T031 [US1] Implement the card-scoped `ErrorBoundary` in
      `frontend/app/src/entities/repository/ui/repository-branches-card/repository-branches-card-boundary.tsx`
      and wrap the card in it. Without it a **render-time** failure — a mapper crash on an unexpected
      preview-window shape, a null reaching `DropdownCell` — propagates to `error-boundary-router` and
      blanks the whole route. Covers FR-024's render-time half.
- [ ] T032 [US1] Component-test the card's row rendering in `repository-branches-card.test.tsx` using
      `expectServerDrivenChange`. Assert one request produced the rendered rows **and** the stated
      total (FR-001), and that the total exceeds the row count when the set is larger than a page
      (FR-009).
- [ ] T033 [US1] Component-test paging: a page change and a page-size change each issue a new request
      with the corresponding window, **and** the previous page's rows are no longer rendered — rows are
      replaced, not accumulated (FR-010). Use `expectServerDrivenChange` for both halves.
- [ ] T034 [US1] Component-test FR-010a's window statement for a set larger than one page and for one
      smaller, asserting the **full visible text**.
- [ ] T035 [US1] Component-test FR-004 and FR-025 together: locate the chip by accessible name with
      `within(row).getByText(...)` — `DropdownCell` is a bare `<span>` with no role, so `getByRole`
      will not find it — then assert **`element.style.backgroundColor`** (not
      `getComputedStyle(...)`, which normalises hex to `rgb(…)` and breaks equality against the
      fixture). Assert `backgroundColor` **only**; never the derived text colour, which `DropdownCell`
      computes with `lch(from …)`.
- [ ] T036 [US1] Component-test FR-005: vary the schema-supplied label and assert the rendered header
      follows it.
- [ ] T037 [US1] Component-test FR-006 given a payload carrying `updated_at` values: assert no
      upstream column, no "N behind" indicator and no timestamp is rendered — **paired with a positive
      assertion in the same test**, because `not.toHaveTextContent("ago")` passes for a card that
      renders nothing.
- [ ] T038 [US1] Component-test each of the four states (FR-023), asserting the full user-visible
      message. **The empty and denied states must not render the same text**, and the two empty cases
      must differ from each other.
- [ ] T039 [US1] Component-test the read-only kind (FR-027): the row set includes branches with Git
      sync disabled, the `Ref` column is present, and the title is `Infrahub branches`. This kind gets
      **no** e2e coverage, so these are its only end-to-end-shaped guarantee.

**Checkpoint**: US1 is independently shippable. An operator can find the failing branch of a large
repository from the repository page.

---

## Phase 4: User Story 2 — Tell repository-wide values from branch-scoped ones (P2)

**Goal**: Two details cards, the branch-scoped one naming its branch, divided by the schema.

**Independent test**: Open a repository page, assert two distinct cards, assert a known
repository-wide attribute is in the first and a known branch-scoped one in the second, then switch
branch and assert only the second card's values change.

### Work unit 3 — the partition rule

- [ ] T040 [P] [US2] Implement `partitionFieldsByBranchSupport(schema)` in
      `frontend/app/src/entities/repository/domain/rules/partition-fields-by-branch-support.ts`, a
      **pure function** returning `{repositoryWide, branchScoped}` each with `{attributes,
      relationships}`. The rule is
      **`branchScoped ⇔ (field.branch ?? node.branch) ∈ {"aware", "local"}`**.

      `BranchSupportType` has **three** values. `local` counts as branch-scoped: on `CoreRepository`,
      `commit` and `sync_status` are both declared `local`, so treating only `aware` as branch-scoped
      would file the two values this feature exists to disambiguate under repository-wide — SC-004
      false, with every read-only test still green. Covers FR-019.
- [ ] T041 [US2] Partition **relationships** as well as attributes, and set `relationships: []` on the
      branch-scoped side. `ObjectDataDisplay` renders relationships alongside attributes, so two
      derived schemas each keeping the full array would render `credential`, `tags`,
      `transformations`, `queries` and `checks` **twice**.
- [ ] T042 [US2] Unit-test the rule in `partition-fields-by-branch-support.test.ts` with **one case per
      `BranchSupportType` value** — `aware`, `agnostic`, `local` — plus a case exercising the
      node-level fallback for a field that declares no `branch`. Node-level `branch` is required on
      every `ModelSchema` member, so the fallback is total. Covers FR-019.

### Work unit 7 — the details split

- [ ] T043 [US2] Implement `RepositoryDetailsCard` in
      `frontend/app/src/entities/repository/ui/repository-details-card.tsx` — a thin wrapper composing
      `Card` + `CardHeader` + the **existing, unchanged** `ObjectDataDisplay`, taking `title`,
      `caption` and `testId` props. **Do not reuse `ObjectDetailsCard`**: it hardcodes the literal
      `Details` in its `CardHeader` and hardcodes `data-testid="object-details"`, with no title prop,
      so it cannot render "On this branch" and two instances would collide on test id.
- [ ] T044 [US2] Implement `RepositoryObjectDetails` in
      `frontend/app/src/entities/repository/ui/repository-object-details.tsx`: build two derived
      `ModelSchema` objects from T040's partition and render each through `RepositoryDetailsCard` —
      repository-wide first, then `On this branch` with **the branch name as a caption beneath the
      title**. Pass it as `RepositoryDetailsCard`'s `caption` prop; there is no `description` slot to
      look for — that belongs to `Content.CardTitle`, which T043 deliberately does not use.
      Covers FR-018.
- [ ] T045 [US2] Render nothing at all for a partition with no attributes **and** no relationships — a
      card with nothing to show must not appear as an empty titled box (FR-022).
- [ ] T046 [US2] Add the kind gate in
      `frontend/app/src/entities/nodes/object/ui/object-details/object-details.tsx` using
      `isOfKind(GENERIC_REPOSITORY_KIND, schema)`, which already resolves **both** concrete repository
      kinds through `inherit_from` — **no kind list is needed**. This is the feature's only
      *behavioural* shared-file edit, and reverting it is the entire rollback path (T025's
      `DropdownCell` widening is type-only and harmless on its own). Covers FR-020.
- [ ] T047 [US2] Place the three cards in the main column in document order: repository-wide details,
      then branch-scoped details, then the branches card (FR-018a).
- [ ] T048 [US2] Component-test FR-018: both card titles as complete strings, the caption's branch
      name, and which attribute lands in which card.
- [ ] T049 [US2] Component-test FR-018a: the document order of all three cards.
- [ ] T050 [US2] Component-test FR-019 with a schema carrying an **invented** attribute, asserting it
      lands in the card its declared branch support dictates.
- [ ] T051 [US2] Component-test that each relationship label appears **exactly once** on the page.
- [ ] T052 [US2] Component-test FR-020: a non-repository kind renders exactly one details card,
      unchanged from today.
- [ ] T053 [US2] Component-test FR-021 on the read-only kind: an attribute that kind does not define
      produces **no row**, rather than an empty one.
- [ ] T054 [US2] Component-test FR-024: both details cards render while the branches query is in a
      failed state, **and** a second test asserting they still render when the branches card throws
      during render (T031's boundary).
- [ ] T055 [US2] Component-test FR-025 across both details cards: every value, state and marker is
      locatable by accessible name, and the branch-name caption is part of the branch-scoped card's
      accessible name rather than decorative text.

**Checkpoint**: US2 complete and independently verifiable.

---

## Phase 5: User Story 3 — Isolate the branch you care about (P3)

**Goal**: Narrow the list by name fragment or branch status, server-side, with the total narrowing too.

**Independent test**: Type a fragment matching a known subset; assert both the rows **and the stated
total** narrow — proving the narrowing happened before the page boundary, not after.

- [ ] T056 [US3] Implement `useRepositoryBranchFilters` in
      `frontend/app/src/entities/repository/ui/repository-branches-card/use-repository-branch-filters.ts`,
      holding name-fragment and branch-status state **card-scoped**. **Put the page reset inside a
      single `setFilters` wrapper** — with independent URL keys the FR-014 reset is a manual call, and
      splitting it across two filters' call sites is how one of them gets forgotten.
- [ ] T057 [US3] Wire the search field using **`SearchInput`** (pure, controlled) plus `useDebounce`.
      **Do not use `FilterSearchInput`** — it is the obvious grab, already used with the exact
      placeholder "Search branches", but it writes the **global** `QSP.FILTER` via `useSearch` →
      `useFilters`. Covers FR-012.
- [ ] T058 [US3] Wire the status filter using **`BranchStatusEnum`** with card-scoped state. **Do not
      use `BranchStatusFilterForm`** — it writes through `useFilters()`'s single global key. Pass an
      `aria-label` and a placeholder: it renders **nothing in its trigger when `value === null`**, an
      empty unnamed button that FR-025 forbids. Restrict its options to the five **returnable**
      statuses — the contract guarantees `MERGED` and `DELETING` are never returned, so offering them
      yields a permanently empty result.
- [ ] T059 [US3] Send the schema's own wire values (FR-013): the branch status enum is **`BranchStatus`**
      on the wire even though the backend symbol is `InfrahubBranchStatus`, and `sync_status` values
      are **hyphenated** (`in-sync`, `error-import`) even though their labels are title-cased and the
      backend enum members are underscored. A re-cased or underscored form must not be sent.
- [ ] T060 [US3] Component-test FR-012 with `expectServerDrivenChange`: the request carries the
      fragment **and** `partial_match: true`, **and** the rendered rows change to a second payload's
      row set, **and** the displayed total follows the server's count.
- [ ] T061 [US3] Component-test FR-013 twice: the request carries the status and the total follows the
      server's count; and a chip whose visible label is title-cased sends the **hyphenated** wire
      value.
- [ ] T062 [US3] Component-test FR-014: the request after a filter change carries a zero offset.
- [ ] T063 [US3] Component-test FR-015: a filter change issues a **new request** rather than reducing
      the rendered rows in place. This is the test that catches a client-side filter.
- [ ] T064 [US3] Component-test FR-016: `sync_status__value`, `internal_status__value` and
      `own_values_only` are absent from **every** request the feature makes. The gql.tada document
      cannot express them (T015), so this pins a structural fact rather than guarding a runtime one.
      **`expectServerDrivenChange` cannot carry this assertion** — it matches variables with
      `toMatchObject`, which is partial and passes when an extra argument is present. Assert absence
      explicitly against each recorded call.

**Checkpoint**: All three user stories complete.

---

## Phase 6: Polish & cross-cutting

### Work unit 8 — end to end

- [ ] T065 Write the e2e test at repo-root
      `tests/e2e/repository/test_repository_branches_card.py`, asserting rendered row data, a page
      change and a name filter. It MUST carry a **module-level `pytestmark`** with
      `shard_branches_repo` — `tests/e2e/conftest.py`'s collection hook runs *before* the `-m` filter,
      so a file with no shard marker (or two) fails CI in every shard job. Run against the
      `demo_edge_repo` fixture. Covers FR-026.
- [ ] T066 **Poll the heading total; never assert it once.** Ten `sync_with_git=True` branches each
      trigger real git-worker branch creation, and the card can render before all rows exist — a
      single assertion races the worker. Poll the **count badge** by its own accessible name, not the
      heading: the badge is a sibling of the `<h1>`, not part of its accessible name. Covers FR-026.

### Work unit 9 — documentation and changelog

- [ ] T067 [P] Write `dev/knowledge/frontend/table-pagination.md` covering the new component's URL-key
      scoping, its use inside a card, the requirement that `urlKey` never be defaulted, and that it is
      the **intended successor** to the legacy paging component, which is not to be used for new
      tables. A reader choosing paging for a new table must reach the new one from it. Covers FR-028.
- [ ] T068 [P] Add `CommitHash` to `dev/knowledge/frontend/shared-components.md`. The repo's
      anti-pattern rule requires a new shared primitive to be justified in the PR description **and**
      added to this inventory.
- [ ] T069 [P] Fix the five documented drifts found during the reuse sweep in
      `dev/knowledge/frontend/shared-components.md`: `Pagination` is listed without noting it is
      hard-wired to global `QSP.PAGINATION`; `SearchInput` is listed without distinguishing it from
      the URL-writing `FilterSearchInput`; `CountBadge` and `Content.CardTitle` are missing entirely;
      `Badge` is misfiled under "Layout"; and there is **no entry at all** for
      `shared/components/errors/` or for skeletons. The first two are exactly the traps that would
      mislead the next reader.
- [ ] T070 [P] Add the Towncrier fragment `changelog/3130.added.md` describing the user-facing change.

### Verification and gates

- [ ] T071 Add the FR-017 zero-diff check to CI as a step in the `frontend-lint` job, diffing against
      the merge base over `frontend/app/src/shared/components/**ui**/pagination.tsx` and
      `frontend/app/src/shared/hooks/usePagination.ts`. **Note the `ui/` segment** — an earlier
      revision named the path one directory up, and `git diff --exit-code` over a pathspec matching
      nothing exits 0, so that check passed unconditionally. Verify the new step **fails** when it
      should by touching one file deliberately.
- [ ] T072 Verify FR-008 by review against two structural facts: the card imports exactly one api
      module, and the selection set omits `node_metadata` entirely. Record the verification in the PR
      body. Do **not** substitute a call-count assertion — it measures render-loop stability, not data
      provenance, and breaks the first legitimate refetch.
- [ ] T073 Run `pnpm codegen` and confirm `git diff --exit-code src/shared/api/graphql/generated/` is
      clean. The base branch already carries the regenerated types, so any drift means the base moved.
- [ ] T074 Run the full CI gate locally — `pnpm exec biome ci .`, `pnpm knip`, `pnpm exec betterer ci`,
      `pnpm test`. All four fail CI independently; `pnpm biome:fix` alone is not the gate. Note that
      `frontend-lint` has **no path filter** and runs on every PR.
- [ ] T075 Walk [quickstart.md](quickstart.md)'s manual validation scenarios for both repository kinds.
      These double as IFC-3131's instructions, which have not been written (open question Q3).
- [ ] T076 Raise the **divergence register** from [plan.md](plan.md) on **T094 in IFC-3101** — all six
      divergences as one conversation, not just paging. Do this **before T012**: pagination is built
      first and would otherwise be rejected last. Note the register's largest item is the two-card
      split, which the canvas explicitly ruled against.
- [ ] T077 Note the missing `CoreReadOnlyRepository` e2e fixture on **IFC-3153**, so its owner inherits
      the gap rather than it living only in this spec (FR-027).

---

## Dependencies

> **Unit 5 is split across two phases here.** [plan.md](plan.md) treats it as one unit ("columns,
> cells, filters"); this file splits it into **5a** (the display columns and cells, which US1 needs)
> and **5b** (the filters, which are US3's whole content). The split exists so each user story stays
> independently shippable — US1 must not wait on filtering it does not use. The files and FRs are
> unchanged; only the sequencing differs.

```text
Phase 1 (T001)
      │
Phase 2 — unit 4 (T002–T007)          BLOCKING: no card test may precede T006/T007
      │
      ├───────────────┬───────────────┐
      ▼               ▼               ▼
  unit 1           unit 2          unit 3
 T008–T014       T015–T021       T040–T042
      │               │               │
      │               ▼               │
      │          unit 5a  T022–T026   │        (needs units 2 and 4 — NOT unit 1)
      │               │               │
      └───────┬───────┘               │
              ▼                       │
         unit 6   T027–T039           │        (needs units 1, 4, 5a)
              │                       │
              ├───────────────────────┘
              ▼
         unit 7   T043–T055                    (needs BOTH unit 3 and unit 6)
              │
              ├──────────────▶ unit 5b (filters) T056–T064   (needs units 2, 4, 6)
              ▼
         unit 8   T065–T066
              │
              ▼
         unit 9   T067–T070  +  gates T071–T077
```

**Parallel groups** — safe to run concurrently, no shared file:

| Group | Tasks |
|---|---|
| A | T002, T003, T004 (distinct factory files/exports) |
| B | T008/T009 (pagination utils), T015/T016 (query + model), T040 (partition rule) |
| C | T022/T023 (`CommitHash`) alongside any of group B |
| D | T067, T068, T069, T070 (four separate documentation files) |

**Serial by necessity**: T006 before every `*.test.tsx` in the branches card. T040 before T044.
T031 before T054. T012 before T027. T076 before T012.

---

## Implementation strategy

**MVP = User Story 1** (T001–T039). It is independently shippable and removes the "open 200 pages"
problem on its own: an operator can see every branch's import status and imported commit from the
repository page.

**Increment 2 = User Story 2** (T040–T055). Resolves the second half of the reported confusion and is
valuable even without the table.

**Increment 3 = User Story 3** (T056–T064). What makes US1 usable at real scale rather than merely
correct.

**Then Phase 6.** T076 is the exception to the ordering — raise the divergence register early, because
pagination is the first thing built.

## Coverage — all 32 requirement statements

| FR | Tasks | | FR | Tasks |
|---|---|---|---|---|
| FR-001 | T027, T032 | | FR-015 | T063 |
| FR-002 | T025 | | FR-016 | T015, T064 |
| FR-003 | T024, T026 | | FR-017 | T071 |
| FR-003a | T024 | | FR-018 | T044, T048 |
| FR-004 | T025, T035 | | FR-018a | T047, T049 |
| FR-005 | T025, T036 | | FR-019 | T040, T042, T050 |
| FR-006 | T015, T037 | | FR-020 | T046, T052 |
| FR-007 | T027, T028 | | FR-021 | T053 |
| FR-008 | T015, T072 | | FR-022 | T045 |
| FR-009 | T027, T032 | | FR-023 | T029, T030, T038 |
| FR-010 | T008, T012, T033 | | FR-024 | T031, T054 |
| FR-010a | T008, T012, T034 | | FR-025 | T013, T022, T026, T035, T055 |
| FR-011 | T010, T011 | | FR-026 | T065, T066 |
| FR-011a | T014 | | FR-027 | T039, T077 |
| FR-012 | T057, T060 | | FR-028 | T067 |
| FR-013 | T059, T061 | | | |
| FR-014 | T056, T062 | | | |

**77 tasks.** Setup 1 (T001) · foundational 6 (T002–T007) · US1 32 (T008–T039) · US2 16 (T040–T055)
· US3 9 (T056–T064) · polish and gates 13 (T065–T077).
