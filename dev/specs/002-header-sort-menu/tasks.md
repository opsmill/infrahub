# Tasks: Column-Header Sort & Filter Menu

**Input**: Design documents from `/specs/002-header-sort-menu/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/header-menu-ui.md, quickstart.md

**Tests**: Included — Constitution Principle IV mandates component tests and Playwright E2E for user-facing features; the critique added specific test obligations (E3, E4, E7, X2, P5).

**Organization**: Grouped by user story; IPAM wiring is a separate release-blocking phase (spec Assumptions, critique X1). All paths are repo-relative.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (header sort, P1), US2 (relationship sort, P2), US3 (filter parity, P3)

---

## Phase 1: Setup (Baseline)

**Purpose**: Confirm a green baseline so regressions are attributable.

- [X] T001 Run the existing sort and filter suites as a baseline and record they pass: `cd frontend/app && pnpm test src/entities/nodes/sort` and `pnpm test src/entities/nodes/object/ui/object-table` (component), plus confirm `tests/e2e/objects/object-sort.spec.ts` and `tests/e2e/objects/object-filters.spec.ts` are green against a local stack

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The active-sort matching rule both story phases depend on for indicators and toggle-clear.

- [X] T002 Create token-aware pure rule `getColumnActiveSort(customSort, columnSchema)` in `frontend/app/src/entities/nodes/sort/domain/rules/get-column-active-sort.ts` — returns the single active `Sort` when `customSort?.length === 1` and the field matches the column (attribute: exact `buildAttributeSortField(attr.name)` match; relationship: first `__`-token equals the relationship name — split on `__`, never raw string prefix, per critique E3), else `null`. Add colocated unit tests in `frontend/app/src/entities/nodes/sort/domain/rules/get-column-active-sort.test.ts` covering attribute match, relationship match, near-miss names (e.g. relationship `site` vs attribute `site_code`), multi-field custom sort → `null`, and `customSort = null` → `null`. Bare `// GIVEN` / `// WHEN` / `// THEN` markers, one of each per test.

**Checkpoint**: `pnpm test src/entities/nodes/sort` green — user story phases can start.

---

## Phase 3: User Story 1 — Sort a list from a column header (Priority: P1) 🎯 MVP

**Goal**: Column header opens a react-aria menu with Sort ascending / Sort descending (sortable attribute columns) and Filter… (last, after a separator). Sort replaces the whole sort, toggle-clears back to default, shows indicators, shares state with the toolbar SortPicker via `useSort`.

**Independent Test**: Quickstart scenarios 1–3 on `/objects/InfraDevice` — sort desc via header (`?sort=name__value__desc`, ↓ indicator, persists on reload), toggle-clear restores default order, header sort replaces a toolbar-built multi-sort.

- [X] T003 [US1] Rework `frontend/app/src/entities/nodes/object/ui/object-table/cells/table-column-header.tsx`: replace the Radix `Popover`/`PopoverTrigger`/`PopoverContent` with `@infrahub/ui` `MenuTrigger` + `Popover` + `Menu`/`MenuItem`/`MenuSeparator` (pattern donor: `frontend/app/src/entities/nodes/sort/ui/add-sort/add-sort-button.tsx` + `add-sort-picker.tsx`). For attribute columns passing `isSortableAttribute`, render "Sort ascending" / "Sort descending" items writing `setCustomSort([{ field: buildAttributeSortField(attr.name), direction }])` (full replace); when the selected direction equals the active sort from `getColumnActiveSort`, write `setCustomSort(null)` instead (toggle-clear); mark the active direction as selected in the menu. The header trigger stays a single button (icon + label + indicators) with no nested pressables (react-aria MenuTrigger constraint).
- [X] T004 [US1] In the same component, add the "Filter…" menu item (always last, after a `MenuSeparator`): its action closes the menu and opens a **controlled** `@infrahub/ui` `Popover` anchored to the header containing the existing form — `RelationshipFilterForm` when `"peer" in columnSchema` else `AttributeFilterForm` — with `onSuccess` closing the popover; the form must open pre-filled when a filter is active on the column (contract B5). Keep the existing active-filter icon behavior (`useFilters` + `isFieldFiltered`).
- [X] T005 [US1] Add the header sort indicator: render ↑/↓ on the header button only when `getColumnActiveSort` returns a sort (custom sort only, never for schema default). Render the plain non-interactive header (reuse `frontend/app/src/entities/nodes/object/ui/object-table/cells/table-column-header-simple.tsx`) when a column has no sort entries and no filter form (FR-008); adjust `frontend/app/src/entities/nodes/object/ui/object-table/utils/get-object-table-columns.tsx` only if header props need to change.
- [X] T006 [P] [US1] Create component tests in `frontend/app/src/entities/nodes/object/ui/object-table/cells/table-column-header.test.tsx` (vitest browser mode, `tests/components/render.tsx` helper, pattern donor `sort-editor.test.tsx`): menu structure for a sortable attribute (asc/desc + Filter… last), full-replace write, toggle-clear removes the sort (URL param gone → default order, critique E4), active direction marked, non-sortable kind (JSON) shows Filter… only, Filter… opens the existing form pre-filled when a filter is active (critique E7), applying a filter via the header writes the same `useFilters` state as the toolbar path.
- [X] T007 [P] [US1] Create E2E spec `frontend/app/tests/e2e/objects/object-header-sort.spec.ts` (pattern donor `object-sort.spec.ts`: `ACCOUNT_STATE_PATH.ADMIN`, role-based locators, `test.step`): header sort desc → row order + `?sort=name__value__desc` + ↓ indicator; reload persists; toggle-clear → `?sort=` removed, default order, indicator gone; build a two-field sort via the toolbar Sort button then header-sort → single-field sort shown in both header and SortPicker (contract B6/B7).
- [X] T008 [US1] Update `frontend/app/tests/e2e/objects/object-filters.spec.ts`: steps that drive the old header filter popover now go through the header menu's "Filter…" item, asserting the identical end state (same active-filter tags, same `?filters=` URL); toolbar-path steps stay untouched (critique X2, SC-003).

**Checkpoint**: US1 fully functional on object lists — MVP deliverable.

---

## Phase 4: User Story 2 — Sort by a related object's attribute (Priority: P2)

**Goal**: Cardinality-one relationship columns get a "Sort by ▸" submenu of the peer's sortable attributes with direction; cardinality-many or unresolvable-peer columns get Filter… only.

**Independent Test**: Quickstart scenarios 4–5 — Site column "Sort by ▸ Name ↑" orders devices by site name (`?sort=site__name__value__asc`); a to-many relationship column offers no sort entries.

- [X] T009 [US2] In `frontend/app/src/entities/nodes/object/ui/object-table/cells/table-column-header.tsx`, add the "Sort by" `SubmenuTrigger` for relationship columns passing `isSortableRelationship` (cardinality one) whose peer schema resolves via `getSchema(relationship.peer)`: submenu lists peer attributes passing `isSortableAttribute`, each selecting a direction and writing `setCustomSort([{ field: buildRelationshipSortField(rel.name, buildAttributeSortField(peerAttr.name)), direction }])` (pattern donor: relationship submenu in `add-sort-picker.tsx:104-116`). Cardinality-many or unresolvable peer → no sort entries (Filter… only). Active state via `getColumnActiveSort` marks the submenu entry + direction.
- [X] T010 [P] [US2] Extend `frontend/app/src/entities/nodes/object/ui/object-table/cells/table-column-header.test.tsx`: submenu lists exactly the peer's sortable attributes, selection writes the relationship sort field, cardinality-many column has no sort entries, unresolvable peer schema has no sort entries, relationship column indicator reflects active relationship sort.
- [X] T011 [P] [US2] Extend `frontend/app/tests/e2e/objects/object-header-sort.spec.ts`: relationship sort via Site header → row order + `?sort=site__name__value__asc` + indicator on the Site header; drive the same path once via keyboard only (Enter/arrow keys through menu and submenu — contract B9, critique P5).

**Checkpoint**: US1 + US2 deliver the full sorting surface on object lists.

---

## Phase 5: User Story 3 — Filter parity lock-in (Priority: P3)

**Goal**: Header-originated filtering is indistinguishable from toolbar filtering — same tags, same URL, editable and removable from either place.

**Independent Test**: Quickstart scenario 6 — filter from Status header menu → identical tag/URL as toolbar path; removing from the tag clears the header indication.

- [X] T012 [US3] Extend `frontend/app/tests/e2e/objects/object-filters.spec.ts` with explicit parity assertions: apply a filter via header menu "Filter…" and capture `?filters=` + active-filter tag; remove it via the tag and assert the header's active-filter icon clears; apply the same filter via the toolbar FilterPicker and assert the identical `?filters=` value; re-open the header "Filter…" on an actively-filtered column and assert the form is pre-filled (contract B4/B5, spec Story 3 scenarios).

**Checkpoint**: All three user stories complete on object lists.

---

## Phase 6: IPAM Sort Wiring (Release-Blocking — critique X1)

**Purpose**: The shared header ships on IPAM tables (FR-001); without this wiring its sort items would silently do nothing. Mirrors the object-list wiring (`get-objects-from-api.ts:51`).

- [ ] T013 [P] Add ordering to the IP-address list API call: in `frontend/app/src/entities/ipam/ip-addresses/api/get-ip-address-list-from-api.ts`, accept a `sort: Sort[]` param and spread `addOrderByToRequest(sort)` (from `frontend/app/src/shared/api/graphql/utils.ts`) into the query `__args`.
- [ ] T014 [P] Add ordering to the IP-prefix list API call: same change in `frontend/app/src/entities/ipam/ip-prefixes/api/get-ip-prefix-list-from-api.ts`.
- [ ] T015 Thread `sort` through the IP-address path: use-case `frontend/app/src/entities/ipam/ip-addresses/domain/use-cases/get-ip-address-list.ts` accepts and forwards `sort`; the query hook (`get-ip-address-list.query.ts`) includes `sort` in its query key and passes it through; `frontend/app/src/entities/ipam/ip-addresses/ui/ip-address-table.tsx` calls `useSort(schema)` and passes `customSort`.
- [ ] T016 Thread `sort` through the IP-prefix path: same three-layer wiring for `frontend/app/src/entities/ipam/ip-prefixes/` (`get-ip-prefix-list.ts`, `get-ip-prefix-list.query.ts`, `ip-prefix-table.tsx`).
- [ ] T017 [P] Create E2E spec `frontend/app/tests/e2e/ipam/ip-prefix-list-sort.spec.ts` (conventions from `tests/e2e/ipam/ip-prefix-list-filters.spec.ts`): header-sort the Prefix column → row order changes and `?sort=` updates; toggle-clear restores default order.

**Checkpoint**: Header menu fully functional everywhere it renders — feature is releasable.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T018 [P] Add Towncrier changelog fragment `changelog/+header-sort-menu.changed.md` (naming per existing `changelog/+*.{changed,fixed}.md` fragments): user-facing description of column-header sorting and the changed filter interaction (header click now opens a menu; filtering is under "Filter…") — critique E8/P4.
- [ ] T019 Run `cd frontend/app && pnpm biome:fix`, the full unit/component suite (`pnpm test`), and the affected E2E specs (`object-header-sort.spec.ts`, `object-sort.spec.ts`, `object-filters.spec.ts`, `ip-prefix-list-sort.spec.ts`); walk the quickstart manual scenarios 1–7 against the dev stack; confirm no console errors from overlay/focus management in the menu → filter-popover sequence.
- [ ] T020 Draft the PR description noting the accepted migration debt: `TableColumnHeader` remains under `entities/nodes/object/` while imported by `entities/ipam/` (critique E2), and referencing the softened FR-001b of `specs/ifc-2428-filters` (spec Assumptions).

---

## Dependencies

```text
T001 (baseline)
  └─ T002 (foundational rule)
       ├─ Phase 3 (US1): T003 → T004 → T005 → {T006 [P], T007 [P], T008}
       │     └─ Phase 4 (US2): T009 → {T010 [P], T011 [P]}
       │           └─ Phase 5 (US3): T012
       └─ Phase 6 (IPAM): {T013 [P], T014 [P]} → T015, T016 → T017
             (independent of US2/US3; requires US1's header menu for E2E)
Phase 7: T018 [P] anytime; T019 after all implementation; T020 last
```

- **US1 → US2 → US3**: sequential (same component file for T003/T004/T005/T009; parity tests assume the menu exists).
- **Phase 6** can start any time after US1 (T013/T014 even earlier — they don't touch the header), but T017's E2E needs US1 merged.
- Story labels: US1 = T003–T008, US2 = T009–T011, US3 = T012.

## Parallel Execution Examples

- **Within US1**: after T005 lands, T006 (component tests), T007 (new E2E) and T008 (filter E2E update) touch three different files — run in parallel.
- **Within US2**: T010 and T011 in parallel after T009.
- **IPAM**: T013 and T014 in parallel (different entities); then T015 and T016 in parallel; T018 (changelog) in parallel with anything.

## Implementation Strategy

**MVP = Phase 1–3 (US1)**: header sort on object lists with filter preserved — demoable and shippable behind nothing (no flags needed; behavior is additive except the menu-instead-of-popover interaction).

Incremental delivery: US1 → US2 (relationship submenu) → US3 (parity lock) → IPAM wiring (release gate) → polish. Each checkpoint leaves the app releasable except that a release must not go out between "header menu on IPAM" and "IPAM wiring" — in practice all phases land in one PR on `header-sort-menu-ifc-2794`.

**Total: 20 tasks** — Setup 1, Foundational 1, US1 6, US2 3, US3 1, IPAM 5, Polish 3.
