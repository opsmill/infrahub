# Quickstart: Column-Header Sort & Filter Menu

**Plan**: [plan.md](./plan.md) | **Contract**: [contracts/header-menu-ui.md](./contracts/header-menu-ui.md)

## Prerequisites

```bash
uv run invoke dev.start          # or an already-running Infrahub stack with demo data
cd frontend/app && pnpm setup    # first time: submodules + deps
cd frontend/app && pnpm dev      # dev server against the local stack
```

Load demo data if the stack is empty (`uv run invoke demo.load-infra-schema demo.load-infra-data`) so `/objects/InfraDevice` has multiple rows.

## Manual validation scenarios

1. **Header sort (Story 1)** — open `/objects/InfraDevice`, click the *Name* column header → menu shows *Sort ascending / Sort descending / Filter*. Pick *Sort descending*: rows reorder reverse-alphabetically, header shows ↓, URL contains `?sort=name__value__desc`. Reload — order and indicator persist.
2. **Toggle-clear (Story 1)** — open the *Name* menu again (descending is marked active), pick *Sort descending* again: `?sort=` disappears, default order returns, indicator gone.
3. **Replace semantics (Story 1)** — build a two-field sort in the toolbar Sort button, then header-sort any column: toolbar Sort now shows exactly that one sort.
4. **Relationship sort (Story 2)** — click the *Site* column header on the device list → *Sort by ▸* lists the site's sortable attributes; pick *Name → ascending*: devices order by site name, `?sort=site__name__value__asc`.
5. **Cardinality-many (Story 2)** — a to-many relationship column's menu has no sort entries, only *Filter*.
6. **Filter parity (Story 3)** — from the *Status* header menu pick *Filter*, apply a value: active-filter tag appears under the toolbar identical to a toolbar-applied filter; remove it from the tag → header filter indication clears.
7. **IPAM** — on the IPAM prefix list, header-sort the *Description* column and verify rows reorder and `?sort=` updates. (The *Prefix* value renders in the identifier column, which has no menu — `prefix` is excluded from list columns by design.)

## Automated validation

```bash
cd frontend/app

# Component tests (vitest browser mode)
pnpm test src/entities/nodes/object/ui/object-table/cells/table-column-header.test.tsx
pnpm test src/entities/nodes/sort   # existing sort suite must stay green

# E2E (requires running stack with demo data)
pnpm test:e2e tests/e2e/objects/object-header-sort.spec.ts
pnpm test:e2e tests/e2e/objects/object-sort.spec.ts      # toolbar sort must stay green
pnpm test:e2e tests/e2e/objects/object-filters.spec.ts   # filter regressions (SC-003)
pnpm test:e2e tests/e2e/ipam/ip-prefix-list-sort.spec.ts

# Lint/format before committing
pnpm biome:fix
```

## Expected outcomes

- All scenarios in [contracts/header-menu-ui.md §2](./contracts/header-menu-ui.md) hold.
- `object-sort.spec.ts` passes unmodified (toolbar sort intact). Toolbar-path assertions in `object-filters.spec.ts` pass unmodified; any steps that drive the old header filter popover are updated to go through the menu's "Filter" item while asserting the identical end state — same active-filter tags, same `?filters=` URL (SC-003 is outcome-level: zero filter-behavior regressions).
- No console errors from overlay/focus management when opening menu → filter popover sequences.
- A Towncrier changelog fragment exists in `changelog/` covering the new menu and the changed filter interaction.
