# feat(frontend): column-header sort & filter menu [IFC-2794]

Closes [IFC-2794](https://opsmill.atlassian.net/browse/IFC-2794)

Spec: `specs/002-header-sort-menu/` (spec.md, plan.md, contracts/header-menu-ui.md)

## Summary

Column headers in object lists and IPAM IP address/prefix lists now open a react-aria menu instead of directly opening the per-column filter popover. The menu offers:

- **Sort ascending / Sort descending** on sortable attribute columns — selecting one replaces the entire active sort with a single-field sort on that column; selecting the already-active direction again toggle-clears back to the schema default order.
- **Sort by ▸** submenu on cardinality-one relationship columns, listing the peer's sortable attributes with a direction choice (e.g. sort devices by their site's name).
- **Filter…** (always last, after a separator) — opens the existing per-column filter form in a controlled popover, pre-filled when a filter is active on the column.

The header shows an ↑/↓ indicator when it drives the active user-applied sort (never for the schema default). Sort state is shared with the toolbar Sort control through the existing `?sort=` URL param via `useSort`, so both surfaces always agree and sorted views survive reload and link-sharing. Cardinality-many or unresolvable-peer relationship columns offer Filter… only; columns that are neither sortable nor filterable keep their plain non-interactive header.

The IPAM IP-address and IP-prefix lists previously ignored sorting entirely; this PR wires `sort` end-to-end (API call → use-case → query hook → table) so the shared header's sort actions work there too (release-blocking per spec Assumptions).

## User-facing interaction change

Clicking a column header previously opened the filter form directly. It now opens the menu, and filtering sits under **Filter…** — one click further. The filter experience itself is unchanged and remains fully consistent with the toolbar path: same form, same active-filter tags, same `?filters=` URL, editable/removable from either place (spec Story 3).

A Towncrier fragment covers this: `changelog/+header-sort-menu.changed.md`.

## Implementation notes

- New pure domain rule `getColumnActiveSort(customSort, columnSchema)` (`src/entities/nodes/sort/domain/rules/get-column-active-sort.ts`) decides when a column drives the active sort — token-aware matching (split on `__`), so relationship `site` never matches attribute `site_code`.
- `TableColumnHeader` reworked from a Radix popover to `@infrahub/ui` `MenuTrigger` + `Menu`, with a controlled popover for the filter form (pattern donor: the toolbar sort picker).
- IPAM API calls spread `addOrderByToRequest(sort)` into the GraphQL `__args`, mirroring the object-list wiring.

## Accepted migration debt

- **`TableColumnHeader` location (critique E2)**: the component stays under `entities/nodes/object/ui/object-table/` while now also imported by `entities/ipam/` tables. Moving it to a shared location is deliberate follow-up work outside this PR's scope; the cross-entity import is the accepted interim state.
- **Softened FR-001b of `specs/ifc-2428-filters`** (spec Assumptions): that Draft spec's FR-001b ("column headers are no longer clickable filter triggers") is softened, not contradicted — headers now reuse the unified filter flow as a second entry point. The Draft spec should be amended when next worked on; `specs/002-header-sort-menu/spec.md` is the current source of truth for header behavior.

## IPAM Prefix-column caveat

On the IPAM prefix list, the prefix value renders in the identifier column, which has no header menu (`prefix` is excluded from the list columns by design). Sorting the prefix list therefore goes through the other columns (e.g. Description), which is what the E2E spec exercises.

## Test coverage

- **Unit/domain**: `get-column-active-sort.test.ts` — attribute/relationship match, near-miss names, multi-field sort → null.
- **Component** (vitest browser mode): `table-column-header.test.tsx` — menu structure, full-replace write, toggle-clear, active direction marked, non-sortable kinds, relationship submenu contents, cardinality-many/unresolvable peer → Filter… only, filter form pre-fill and state parity.
- **E2E** (Playwright): new `objects/object-header-sort.spec.ts` (sort, persistence, toggle-clear, toolbar replace semantics, relationship submenu incl. keyboard-only path) and `ipam/ip-prefix-list-sort.spec.ts`; `objects/object-filters.spec.ts` extended with header-menu paths and explicit header/toolbar parity assertions; `objects/object-sort.spec.ts` (toolbar sort) passes unmodified.
- Full frontend unit suite green (134 files / 931 tests); the four affected E2E specs green (14 tests); a scripted browser pass over the quickstart flows confirmed no console errors from overlay/focus management in the menu → filter-popover sequence.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
