# Data Model: Allocation scope table for scoped number pools

Frontend domain types in `entities/resource-manager/domain/model/number-pool.ts`. No backend or stored data changes.

## Existing types, unchanged

- **`NumberPoolData`**: `allocation_scope: NodeAttribute<string[]>` holds the field names of the allocation scope, in order. An empty list means the pool is unscoped.
- **`NumberPoolUsage`**: `size`, `used`, `usedDefaultBranch`, `usedBranches`, `utilization`.
- **`NumberPoolUtilization`**: `{ usage, ranges }`. On the page of one allocation scope, every figure counts that allocation scope only.
- **`NumberPoolAllocationFilters`**: `{ branch?, provenance? }`.

## New types

### `NumberPoolDivisionValue`

```ts
type NumberPoolDivisionValue = string | number | boolean;
```

The value of one field of the allocation scope, with the type the backend uses:

- a relationship: the peer's ID
- a Number, NumberPool or Bandwidth attribute: a number
- a Boolean or Checkbox attribute: a boolean
- any other attribute: a string
- an empty string: the holding object has no value for the field

### `NumberPoolDivisionEntry`

| Field | Type | Source |
|---|---|---|
| `path` | `string` | `NumberPoolDivisionEntry.path`, the field name |
| `value` | `NumberPoolDivisionValue` | `NumberPoolDivisionEntry.value` |
| `label` | `string` | `NumberPoolDivisionEntry.display_label`; the peer's ID when the peer cannot be read |
| `peerKind` | `string \| null` | `NumberPoolDivisionEntry.peer_kind` |

### `NumberPoolDivision`

| Field | Type | Source |
|---|---|---|
| `label` | `string` | `NumberPoolDivision.display_label` |
| `entries` | `NumberPoolDivisionEntry[]` | one per field, in the order of the pool's allocation scope |
| `usage` | `NumberPoolUsage` | `NumberPoolDivision.figures`, mapped by the existing usage mapper |

### `NumberPoolDivisions`

| Field | Type | Source |
|---|---|---|
| `fields` | `string[]` | `NumberPoolDivisions.allocation_scope[].name` |
| `divisions` | `NumberPoolDivision[]` | in backend order: usage, highest first, then label |

### `NumberPoolDivisionSelector`

```ts
type NumberPoolDivisionSelector = Array<{ path: string; value: NumberPoolDivisionValue }>;
```

Identifies one allocation scope in a request. It is sent as `division` to the utilization, allocations and allocation count queries. It is built from the URL values and the pool's `allocation_scope` names (see [contracts/url.md](contracts/url.md)).

## UI-only types and helpers

These serve the display, so they live in `ui/`, each in the one file that uses it (research R7). This feature adds no `domain/rules` file.

| Name | File | Input → output | Requirement |
|---|---|---|---|
| Table sort type | `ui/hooks/use-number-pool-division-table-state.ts` | `{ by: "usage" \| <field name>, direction: "ascending" \| "descending" }` | FR-006 |
| Search filter | `ui/number-pool/details/number-pool-divisions-card.tsx` | `(divisions, search)` → the divisions with an entry label that contains `search`, ignoring case; every division when `search` is blank | FR-005 |
| Sort | `ui/number-pool/details/number-pool-divisions-card.tsx` | `(divisions, sort)` → sorted copy; labels compared with `numeric: true`; ties keep the input order | FR-006 |
| Selector from the URL | `ui/hooks/use-number-pool-division.ts` | `(fields, values)` → a selector, or a mismatch when the lengths differ | FR-009, edge case "does not match" |
| Lookup of the open allocation scope | `ui/number-pool/details/number-pool-division-summary.tsx` | `(divisions, values)` → the division whose entry values equal `values`, or none | FR-010, R4 |

## States of the scoped body

```text
pool scoped?
├─ no  → current body (ranges + allocations)
└─ yes → URL has allocation_scope?
         ├─ no  → allocation scopes card
         │        ├─ loading → skeleton rows
         │        ├─ fields wider than the card → horizontal scroll, usage pinned right
         │        ├─ list empty → "No numbers allocated yet…"
         │        ├─ search matches nothing → "No allocation scope matches"
         │        └─ rows
         └─ yes → selector built?
                  ├─ no  → "This link does not match the pool's allocation scope (…)"
                  └─ yes → summary + ranges card + allocations card, filtered to the selector
```
