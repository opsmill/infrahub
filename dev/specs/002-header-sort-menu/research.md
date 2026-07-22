# Research: Column-Header Sort & Filter Menu

**Date**: 2026-07-16 | **Plan**: [plan.md](./plan.md)

All findings verified against the codebase on branch `header-sort-menu-ifc-2794` (from `develop`).

## R1 — Menu primitives for the header

**Decision**: Use `@infrahub/ui` react-aria-components wrappers: `MenuTrigger` + `Popover` + `Menu`/`MenuItem`/`MenuSeparator`, with `SubmenuTrigger` for the relationship "Sort by ▸" submenu. Copy the canonical two-level pattern from `src/entities/nodes/sort/ui/add-sort/add-sort-button.tsx` (MenuTrigger > Button + Popover > picker) and `add-sort-picker.tsx` (Menu > SubmenuTrigger > MenuItem + nested Popover/Menu), which is the repo's established example of exactly this shape — including relationship submenus built from peer sortable attributes.

**Rationale**: The sort entity already renders field+direction menus with these primitives; reusing the pattern keeps one menu idiom in the app (Constitution VII). `MenuItem` auto-renders the submenu chevron; `Menu` supports `emptyMessage`.

**Alternatives considered**:
- *Keep the Radix popover currently in `table-column-header.tsx`* — rejected: it has no menu/submenu semantics; we'd hand-roll keyboard navigation and mixed idioms would persist (the sort UI is react-aria, the header would stay Radix).
- *Radix DropdownMenu* — rejected: introduces a second menu system alongside `@infrahub/ui` Menu for no gain.

**Known pitfalls to respect** (from prior work in this repo):
- react-aria `MenuTrigger` captures all pressable descendants — the header trigger must be a single button with no nested links/pressables.
- Bind popover/menu open state via props (`isOpen`), never conditionally render the overlay, or exit animations break.
- The header cell is currently the popover trigger (icon + label + filter icon); it becomes the menu trigger button.

## R2 — Opening the existing filter form from a menu item

**Decision**: The "Filter…" `MenuItem`'s action closes the menu (react-aria default on action) and sets local state that opens a **controlled react-aria Popover** anchored to the header, containing the existing `AttributeFilterForm` / `RelationshipFilterForm` (branching on `"peer" in columnSchema`, exactly as today at `table-column-header.tsx:49-52`). The form's `onSuccess` closes the popover. Forms remain untouched; they already write filters through `useFilters` (nuqs `QSP.FILTER`).

**Rationale**: Keeps a single filtering implementation (spec Story 3 / FR-006). Menu-then-popover is simpler and more robust than embedding a form inside a menu (react-aria menus manage focus/typeahead and fight embedded inputs).

**Alternatives considered**:
- *Embed the filter form in a submenu* — rejected: react-aria Menu intercepts keyboard events; form inputs inside menus are an accessibility trap.
- *Route to the toolbar FilterPicker opened-and-scoped* — rejected: more cross-component coupling than opening the same form in place; identical end state either way.

## R3 — Sort write semantics (replace, toggle-clear, indicators)

**Decision**:
- "Sort ascending/descending" on attribute column `a` → `setCustomSort([{ field: buildAttributeSortField(a.name), direction }])` — full replacement (FR-002).
- Relationship submenu selection → `setCustomSort([{ field: buildRelationshipSortField(rel.name, buildAttributeSortField(attr.name)), direction }])`.
- Toggle-clear (FR-004): if `customSort` is exactly `[{field: thisField, direction: selected}]`, call `setCustomSort(null)` — nuqs removes `?sort=` and `useSort` falls back to `defaultSort` (schema default).
- Active state: a column is "driving the sort" when `customSort?.length === 1` and its field equals the column's attribute field, or starts with `` `${relationshipName}__` `` for relationship columns. Implemented as a small pure rule in `sort/domain/rules/` (e.g. `get-column-active-sort.ts`) so the header and menu share it and it's unit-testable.
- Header indicator: ↑/↓ rendered only for a user-applied (custom) sort — never for `defaultSort` (edge case locked in spec).

**Rationale**: `useSort` (nuqs `QSP.SORT`, tokens `field__asc|desc` via `serializeSortToken`/`parseSortToken`) is already the single source of truth consumed by `object-table.tsx` and `SortPicker` — writing through it guarantees FR-007 (header and toolbar never disagree) with zero synchronization code. `getValidSorts` already allowlists sort fields per schema on read, satisfying FR-009 without new validation.

**Alternatives considered**:
- *Local header sort state synced to SortPicker* — rejected: duplicate state, sync bugs; FR-007 free via shared hook.
- *A "Clear sort" menu item* — rejected during idea grilling; toggle-clear chosen by the user.

## R4 — Sortability/filterability per column

**Decision**: Reuse existing domain rules verbatim:
- Attribute columns: sort entries iff `isSortableAttribute(attr)` (excludes JSON/List/Any/Password kinds).
- Relationship columns: "Sort by ▸" submenu iff `isSortableRelationship(rel)` (cardinality one) and the peer schema resolves; submenu lists peer attributes passing `isSortableAttribute`. Cardinality-many → no sort entries.
- Filter entry: same availability as today (all attribute/relationship field columns get the filter form).
- Columns with neither capability render `TableColumnHeaderSimple` (already exists, plain div).

**Rationale**: These rules are exactly what `getValidSorts` accepts, so the menu can never offer a sort the validator would drop.

## R5 — IPAM sort wiring (verified missing)

**Decision**: IPAM IP-address and IP-prefix tables currently pass **no** order argument: `__args` in `get-ip-address-list-from-api.ts:39-45` / `get-ip-prefix-list-from-api.ts` contain only `limit, offset, include_available, kinds, filters`; use-cases and query hooks accept no sort; tables don't call `useSort`. Wire them the same way the object list is wired (`object-table.tsx:11-25` → `get-objects-from-api.ts:51`):
1. API files: accept `sort` and spread `addOrderByToRequest(sort)` (`shared/api/graphql/utils.ts:169`) into `__args`.
2. Use-cases: accept and thread a `sort: Sort[]` param.
3. Query hooks: include sort in the query key + pass through.
4. Tables (`ip-address-table.tsx:29-33`, `ip-prefix-table.tsx:37-41`): call `useSort(schema)` and pass `customSort`.

This lands as the final implementation phase; the header menu itself works on IPAM immediately (shared component), so without this phase headers would offer sorts that don't take effect — therefore the IPAM phase is **required before release**, not optional (supersedes the spec's fast-follow assumption).

**Rationale**: Mirrors an existing, proven wiring; purely additive.

## R6 — Testing approach

**Decision**:
- **Component tests** (vitest browser mode, playwright provider): new colocated `table-column-header.test.tsx` using `tests/components/render.tsx`, locator style `component.getByRole(...)` + `await expect.element(...)`, bare `// GIVEN/WHEN/THEN` markers. Pattern donors: `sort-editor.test.tsx`, `add-sort-picker.test.tsx`. (Untracked `__screenshots__` dirs for a drafted `table-column-header.test.tsx` already exist locally — the test file will now exist for real.)
- **E2E** (Playwright): new `tests/e2e/objects/object-header-sort.spec.ts` modeled on `object-sort.spec.ts` (role-based locators, `ACCOUNT_STATE_PATH.ADMIN`, asserts `?sort=name__value__desc` and row order); new `tests/e2e/ipam/ip-prefix-list-sort.spec.ts` (IPAM has filter specs but no sort spec today). Filter-parity assertions extend `object-filters.spec.ts` coverage.
- **Unit tests** for any new pure rule (e.g. `get-column-active-sort`) beside the rule file.

**Rationale**: Constitution IV requires E2E for user-facing features; component tests cover menu structure/toggle logic cheaply.
