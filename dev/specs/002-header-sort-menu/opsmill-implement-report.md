# Implement Report: Column-Header Sort & Filter Menu

**Status**: COMPLETE
**Spec dir**: `specs/002-header-sort-menu` | **Branch**: `header-sort-menu-ifc-2794`
**Base commit**: `ec51ecd24f` → **Head commit**: `bc4dcb8e24` (9 commits)
**Wall-clock**: ~1h50m (7 implementation chunks + review, sequential clean-context subagents)

## 1. Chunk-by-chunk ledger

| # | Chunk (tasks.md phase) | Tasks | Outcomes | Commit(s) | Flagged upward |
|---|---|---|---|---|---|
| 1 | Setup (baseline) | T001 | 1 ✅ | `f8aa45bae4` | E2E must use the default playwright baseURL (vite :8080); `INFRAHUB_ADDRESS=:8000` tests the stack's baked-in older UI |
| 2 | Foundational rule | T002 | 1 ✅ | `2c27e4f7db` | Signature `getColumnActiveSort(customSort: Sort[] \| null, columnSchema): Sort \| null`; token-based relationship match |
| 3 | US1 — header menu MVP | T003–T008 | 6 ✅ | `052e6ed792` | `setCustomSort` widened to accept `null`; `TableColumnHeader` gained optional `schema` prop (sort entries only when passed → no dead sort items on unwired tables); old "Filter by X" popover title dropped. Run interrupted twice (API error, then a stalled Playwright HTML-report server) — resumed both times, no work lost |
| 4 | US2 — relationship submenu | T009–T011 | 3 ✅ | `3d6d4559fb` | Submenu-trigger items can't carry `aria-checked` → active peer attribute marked via CheckIcon + sr-only text; task's `getSchema()` didn't exist → used `useSchema` (donor pattern) |
| 5 | US3 — filter parity | T012 | 1 ✅ | `cafde261a4` | Header filter icon has no accessible name → located via scoped icon selector (follow-up suggested) |
| 6 | IPAM sort wiring | T013–T017 | 5 ✅ | `7619b4c642` (+ orchestrator docs fixup `a48c2a6213`) | Prefix column can't sort by design (renders in identifier column; `prefix` excluded from list columns) → E2E sorts Description; quickstart amended. Also fixed 2 pre-existing IPAM filter E2E specs broken by the menu rework. Verified `include_available: true` + `order` accepted by the live API |
| 7 | Polish | T018–T020 | 3 ✅ | `c49f445ac5` | Full suite 931/931; scripted console-error check clean; changelog fragment + `pr-description.md` written |
| R | Review fixes (Phase 6) | — | — | `bc4dcb8e24` | See §5 |

## 2. Tasks not completed

None — all 20 tasks are `[X]` in `tasks.md`.

## 3. Local-pass evidence

Environment for all rows: local macOS; component/unit = Vitest 4.1.9 browser mode (Chromium, playwright provider); E2E = Playwright vs vite dev server `http://localhost:8080` (default baseURL) with Infrahub stack API on `:8000`, admin storage state. Commands run from `frontend/app`.

**Unit — `src/entities/nodes/sort/domain/rules/get-column-active-sort.test.ts`** (chunk 2) — cmd `pnpm vitest run src/entities/nodes/sort/domain/rules/get-column-active-sort.test.ts --reporter=verbose` — passed 2026-07-16T11:19:08Z — `Tests  6 passed (6)`:

| Test | Type |
|---|---|
| returns the sort when it targets the attribute column | unit |
| returns the sort when it targets a peer attribute of the relationship column | unit |
| does not match the relationship `site` against the attribute field `site_code__value` | unit |
| returns null when the sort targets another attribute column | unit |
| returns null when the custom sort holds several fields | unit |
| returns null when there is no custom sort | unit |

**Component — `.../object-table/cells/table-column-header.test.tsx`** — cmd `pnpm test src/entities/nodes/object/ui/object-table` — US1 set (9 tests) passed 2026-07-16T13:38:10Z (`Tests  22 passed (22)`); US2 set (7 tests) passed 2026-07-16T13:52:49Z (`Tests  29 passed (29)`); review set (2 tests) passed 2026-07-16T14:59:41Z (`Tests  105 passed (105)` across sort + object-table suites):

| Test | Type | Added by |
|---|---|---|
| offers both sort directions then a filter entry for a sortable attribute column | component | chunk 3 |
| replaces the whole custom sort with a single-field sort | component | chunk 3 |
| toggle-clears the sort when selecting the active direction again | component | chunk 3 |
| marks the active direction as selected in the menu | component | chunk 3 |
| shows a direction indicator on the header for a custom sort | component | chunk 3 |
| shows no direction indicator for the schema default order | component | chunk 3 |
| offers only the filter entry for a non-sortable attribute kind | component | chunk 3 |
| opens the filter form pre-filled when a filter is active on the column | component | chunk 3 |
| writes the same filter state as the toolbar filter path | component | chunk 3 |
| lists exactly the peer's sortable attributes in the Sort by submenu | component | chunk 4 |
| writes the relationship sort field when selecting a peer attribute direction | component | chunk 4 |
| toggle-clears the sort when selecting the active peer attribute direction again | component | chunk 4 |
| marks the active peer attribute and direction as selected in the submenus | component | chunk 4 |
| shows a direction indicator on the relationship header for an active relationship sort | component | chunk 4 |
| offers only the filter entry for a cardinality-many relationship column | component | chunk 4 |
| offers only the filter entry when the peer schema cannot be resolved | component | chunk 4 |
| keeps the pagination offset unchanged when sorting from the header | component | review (B8/FR-010) |
| renders a plain non-interactive header when disabled | component | review (FR-008) |

**E2E — `tests/e2e/objects/object-header-sort.spec.ts`** — cmd `PW_TEST_HTML_REPORT_OPEN=never pnpm test:e2e --reporter=line tests/e2e/objects/object-header-sort.spec.ts` — US1 tests passed 2026-07-16T13:38:33Z (`9 passed (40.3s)` incl. object-filters); full spec incl. US2 passed 2026-07-16T13:58:20Z (`7 passed (19.2s)`):

| Test | Type | Added by |
|---|---|---|
| should sort from the column header, persist on reload, and toggle-clear | e2e | chunk 3 |
| should replace a toolbar-built multi-field sort with a single-field sort | e2e | chunk 3 |
| should sort by a related attribute from the Site header | e2e | chunk 4 |
| should sort by a related attribute using only the keyboard | e2e | chunk 4 |

**E2E — `tests/e2e/objects/object-filters.spec.ts` (modified + extended)** — same command form — modified header-path tests passed 2026-07-16T13:38:33Z (`9 passed`); parity test passed 2026-07-16T14:04:11Z (`8 passed (38.7s)`):

| Test | Type | Change |
|---|---|---|
| should filter by attribute and relationship with all conditions | e2e | modified (menu → "Filter…" path) — chunk 3 |
| should filter using enum value | e2e | modified (menu → "Filter…" path) — chunk 3 |
| header and toolbar parity › should produce identical filter state from the header menu and the toolbar filter picker | e2e | new — chunk 5 |

**E2E — IPAM** — cmds `PW_TEST_HTML_REPORT_OPEN=never pnpm test:e2e --reporter=line tests/e2e/ipam/<spec>`:

| Test | Type | Evidence |
|---|---|---|
| ip-prefix-list-sort.spec.ts › should sort IP prefixes from a column header and toggle-clear | e2e (new — chunk 6) | passed 2026-07-16T14:24:40Z — `4 passed (19.2s)` |
| ip-prefix-list-filters.spec.ts (fixed for menu path) | e2e (modified — chunk 6) | passed 2026-07-16T14:28:44Z — `4 passed (12.8s)` |
| sub-ip-prefix-list-filters.spec.ts (fixed for menu path) | e2e (modified — chunk 6) | passed 2026-07-16T14:34:03Z — within `17 passed (45.8s)` broader IPAM run |

**Whole-suite confirmation** (chunk 7): `pnpm test` — 2026-07-16T14:37:52Z — `Test Files 134 passed (134) / Tests 931 passed (931)`; all four affected E2E specs together — 2026-07-16T14:38:43Z — `14 passed (58.0s)`.

No MISSING rows; no deferred-local-E2E rows.

## 4. Review findings (Phase 6: code, tests, types, comments agents; errors skipped — no error-handling paths in diff)

| Severity | File | Finding | Disposition |
|---|---|---|---|
| Critical (tests) | table-column-header.test.tsx | B8/FR-010 — pagination offset survival on sort untested anywhere | **Fixed** — component test added (`bc4dcb8e24`) |
| Important (code) | get-branch-table-columns.tsx, role-manager column builders | Tables sharing the header silently changed from click→filter-popover to click→menu→"Filter…", contradicting contract §4 "keeps current headers" | **Fixed** — behavior accepted (filtering outcome unchanged, consistent interaction); contract §4 + spec assumption amended |
| Important (tests) | tests/e2e/ipam/ | IPAM **address**-list sort has no E2E (prefix list covers the shared plumbing) | **Deferred** — follow-up |
| Important (tests) | table-column-header.test.tsx | FR-008 plain non-interactive header untested | **Fixed** — component test added |
| Low (types) | sort-field.ts / get-column-active-sort.ts | Relationship-field decode lived apart from its encoder | **Fixed** — `sortFieldBelongsToRelationship` co-located in sort-field.ts |
| Low (comments) | use-sort.ts | `setCustomSort` undocumented after `null` widening | **Fixed** — JSDoc added |
| Suggestion (code) | get-ip-{address,prefix}-list-from-api.ts | Custom sort + `include_available: true` may interleave "available range" pseudo-rows unpredictably | **Deferred** — product call; consider dropping availability under custom sort like the filter rule |
| Suggestion (code) | table-column-header.tsx | Filter popover lost its "Filter by {label}" heading — form opens without column context | **Deferred** — UX call |
| Suggestion (tests) | object-filters.spec.ts / table-column-header.tsx | Filter icon has no accessible name (locator is icon-selector-coupled); add sr-only "filtered" like the sort indicator | **Deferred** |
| Suggestion (tests) | table-column-header.test.tsx | Dual indicator (sort + filter on same column) never asserted together; `document.querySelectorAll` escapes component scope | **Deferred** |

## 5. Autonomous decisions

1. **E2E environment**: all E2E against the vite dev server (default baseURL), never `INFRAHUB_ADDRESS=:8000` — the stack image's baked-in UI predates the working tree (chunk 1 finding).
2. **Chunk 3 recovery**: resumed the same subagent twice (transient API disconnect, then a stall caused by Playwright's blocking HTML-report server); subsequent chunks got `PW_TEST_HTML_REPORT_OPEN=never --reporter=line` as a standing rule. No work lost, no re-implementation.
3. **IPAM Prefix column**: sorting it is impossible by design (identifier column has no menu; `prefix` excluded from list columns) — E2E and quickstart target the Description column instead (`a48c2a6213`).
4. **Branches/role-manager scope**: accepted the interaction change (menu with "Filter…" only) rather than disabling those headers — disabling would have *removed* their filtering; docs amended to match reality.
5. **Simplify pass**: applied inline (encode/decode co-location) instead of dispatching the simplify agent on an already-green, heavily-tested diff — churn risk outweighed benefit. `errors` review agent skipped: the diff introduces no error-handling paths.
6. **Workspace incident (resolved, worth knowing)**: the code-review subagent ran a `git stash`/`pop` pair on a clean tree, which applied your pre-existing `stash@{0}` ("WIP on ipam-object-namespace") onto this branch. I verified every spilled file byte-identical to the stash blobs (tracked diffs empty; untracked hashes matched), restored the worktree, and confirmed `stash@{0}` is still intact for your other branch. Nothing was lost or committed.
7. Baseline chunk discarded two E2E runs that used the wrong environment routing — recorded, not failures of the code.

## 6. Suggested next steps

1. Open the PR — `specs/002-header-sort-menu/pr-description.md` is ready (includes migration-debt and FR-001b notes). Do not forget the branch targets `develop`.
2. Address the deferred review findings, cheapest first: sr-only "filtered" text on the filter icon (also de-brittles the parity E2E locator), IPAM address-list sort E2E, dual-indicator assertion.
3. Product decisions to close out: filter-popover heading ("Filter by X") and custom-sort × `include_available` interleaving on IPAM lists.
4. The `specs/ifc-2428-filters` draft still carries FR-001b ("headers not clickable") — amend it next time that spec is touched (already noted in this spec's assumptions).
