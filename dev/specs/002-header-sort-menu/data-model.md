# Data Model: Column-Header Sort & Filter Menu

**Date**: 2026-07-16 | **Plan**: [plan.md](./plan.md)

No new persisted entities. The feature reads and writes two existing URL-state models and derives one new in-memory view model.

## Existing models (reused, unchanged)

### Sort

Source: `src/entities/nodes/sort/domain/model/sort.ts`

| Field | Type | Notes |
|---|---|---|
| `field` | `SortField` = `` `${string}__${string}` `` | `name__value` (attribute) or `site__name__value` (relationship→peer attribute), built by `buildAttributeSortField` / `buildRelationshipSortField` |
| `direction` | `OrderDirection` (`ASC` \| `DESC`) | generated GraphQL enum |

- **Persistence**: `?sort=` URL param, array of tokens `field__asc|desc` (`serializeSortToken` / `parseSortToken`), nuqs `history: "push"`.
- **Validation**: `getValidSorts(sorts, schema)` — allowlist of sortable attribute fields, relationship→peer-attribute fields, and node-metadata fields; dedupes by field. Everything the header emits must (and does, by construction) pass it.
- **State owner**: `useSort(schema)` → `{ customSort, setCustomSort, defaultSort, appliedSort }`. `customSort = null` ⇒ schema default order applies.

### Filter

Source: `src/entities/nodes/filters/` — `?filters=` URL param (JSON, zod-validated), owned by `useFilters()`. The header menu only *opens* the existing filter forms; it never constructs or writes Filter values itself.

## New derived view model (in-memory, per rendered column)

### ColumnHeaderCapabilities

Derived in the header UI from the column's `AttributeSchema | RelationshipSchema` using existing domain rules — not stored anywhere.

| Property | Derivation | Drives |
|---|---|---|
| `sortEntries` | Attribute: `isSortableAttribute(attr)` → asc/desc items with `field = buildAttributeSortField(attr.name)`. Relationship: `isSortableRelationship(rel)` (cardinality one) and peer schema resolves → submenu of peer attributes passing `isSortableAttribute`, each `field = buildRelationshipSortField(rel.name, buildAttributeSortField(peerAttr.name))`. Otherwise: none. | FR-002, FR-003 |
| `filterable` | Same availability as today's header filter popover (attribute/relationship field columns). | FR-006 |
| `activeSort` | New pure rule `getColumnActiveSort(customSort, columnSchema)`: the single `Sort` when `customSort?.length === 1` and its field is the column's attribute field, or is prefixed `` `${rel.name}__` `` for relationship columns; else `null`. | FR-004, FR-005 |
| `activeFilter` | Existing `isFieldFiltered(filter, columnSchema.name)` over `useFilters()` (already used by the current header). | Story 3 / edge case (both indicators) |

**Interactive iff** `sortEntries.length > 0 || filterable`; otherwise the plain `TableColumnHeaderSimple` renders (FR-008).

## State transitions (sort)

| Current state | Action | Next state |
|---|---|---|
| `customSort = null` (default order) | Select "Sort desc" on column A | `customSort = [{A, DESC}]`; `?sort=A__desc` pushed |
| `customSort = [{A, DESC}]` | Select "Sort asc" on column A | `customSort = [{A, ASC}]` |
| `customSort = [{A, DESC}]` | Select "Sort desc" on column A (toggle-clear) | `customSort = null`; `?sort=` removed; default order restored |
| `customSort = [{A, ASC}, {B, DESC}]` (multi, from SortPicker) | Select any header sort on column C | `customSort = [{C, dir}]` (full replace) |
| any | Sort change | Pagination offset unchanged (FR-010) |

## Invariants

1. **Single source of truth**: header menu and toolbar SortPicker both read/write `useSort` — they can never disagree (FR-007).
2. **Allowlist by construction**: every field the menu can emit is in `getValidSorts`' allowlist for the schema (FR-009).
3. **Indicator = custom sort only**: `defaultSort` never produces a header indicator (spec edge case).
4. **Filter parity**: filters applied via the header are written by the same forms/hook as toolbar filters — indistinguishable in URL, tags, and behavior (Story 3).
