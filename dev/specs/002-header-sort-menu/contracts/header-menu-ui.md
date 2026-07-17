# UI Contract: Column-Header Menu

**Date**: 2026-07-16 | **Plan**: [../plan.md](../plan.md) | **Data model**: [../data-model.md](../data-model.md)

The feature exposes no new API endpoints. Its external contracts are (1) the header menu's interaction surface and (2) the URL state it reads/writes. Both are testable from Playwright without implementation knowledge.

## 1. Menu structure per column type

### Sortable attribute column (e.g. Text, Number, Datetime kinds)

```text
[Header button: <icon> <label> (↑|↓ when driving custom sort) (filter icon when filtered)]
└─ Menu
   ├─ Sort ascending      (marked selected when active)
   ├─ Sort descending     (marked selected when active)
   ├─ ────────────
   └─ Filter             → closes menu, opens existing per-column filter form in popover
```

### Non-sortable attribute column (JSON / List / Any / Password kinds)

```text
└─ Menu
   └─ Filter             (no sort entries)
```

### Cardinality-one relationship column (peer schema resolvable)

```text
└─ Menu
   ├─ Sort by ▸
   │   └─ Submenu: one entry per peer attribute passing sortability,
   │      each offering ascending / descending
   ├─ ────────────
   └─ Filter
```

### Cardinality-many relationship column, or peer schema unresolvable

```text
└─ Menu
   └─ Filter             (no sort entries)
```

### Column with no sort entries and no filter

Plain, non-interactive header — no menu trigger at all.

## 2. Behavior contract

| # | Given | When | Then |
|---|---|---|---|
| B1 | Any sort state | Menu "Sort ascending/descending" selected | Entire sort replaced by that single field+direction; list refetches server-sorted; menu closes |
| B2 | Column drives the custom sort | Menu opened | Active direction is visibly selected |
| B3 | Column drives the custom sort with direction D | "Sort D" selected again | Custom sort cleared; schema default order restored; header indicator removed |
| B4 | Any | "Filter" selected | Menu closes; existing attribute/relationship filter form opens anchored to the header; applying writes the same filter state as the toolbar path |
| B5 | Filter active on column | "Filter" selected | Form opens pre-filled with current value |
| B6 | Sort applied from header | Toolbar SortPicker opened | Shows exactly that sort |
| B7 | Multi-field sort built in SortPicker | Any header sort selected | Replaced by single-field sort (B1) |
| B8 | Sort applied | — | Pagination offset unchanged |
| B9 | Keyboard user focuses header | Enter/Space, arrows | Menu opens and is fully keyboard-navigable (react-aria Menu semantics; submenu via arrow keys) |

## 3. URL state contract

| Param | Format | Written by | Read by |
|---|---|---|---|
| `?sort=` | array of `field__asc\|desc` tokens, e.g. `?sort=name__value__desc`, relationship: `?sort=site__name__value__asc` | Header menu, SortPicker (same setter) | `useSort` → validated by `getValidSorts` → `order: {by: [{field, direction}]}` GraphQL arg |
| `?filters=` | existing JSON format — unchanged | Existing filter forms (opened from header or toolbar) | `useFilters` |

Invariants: absent `?sort=` ⇒ schema default order; invalid/unsortable fields in `?sort=` are dropped silently (existing `getValidSorts` behavior); URL is shareable — loading it restores order + indicators.

## 4. Scope

Sorting applies to every table rendering the shared interactive header **with a schema wired**: object lists (`/objects/:kind`), IPAM IP-address and IP-prefix lists.

Other tables that share the interactive header component without sort wiring (role-manager lists, the branches table's filterable columns) render the menu with **"Filter" only** — their filtering behavior is unchanged in outcome, but the interaction moves under the menu like everywhere else. Sorting there is out of scope. Read-only property tables keep their plain headers.
