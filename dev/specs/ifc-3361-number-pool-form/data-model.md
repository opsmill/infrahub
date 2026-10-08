# Data model: Number pool create and edit forms

Frontend types only. Server entities are defined in `backend/infrahub/core/schema/definitions/core/resource_pool.py` (`CoreNumberPool`, `CoreNumberPoolRange`) and are not changed.

## Form values

| Field | Type | Create | Edit (user pool) | Edit (schema pool) |
|---|---|---|---|---|
| `name` | `{ source, value }` attribute field | input | input | input |
| `description` | `{ source, value }` attribute field | input | input | input |
| `node` | node kind | input | read-only text | read-only text |
| `node_attribute` | attribute name | input | read-only text | read-only text |
| `allocation_scope` | `string[]` of bare field names | input (scope picker) | read-only badges | read-only badges |
| `ranges` | `RangeRow[]` (field array) | rows | rows | read-only text + note |

## Domain types (`domain/model/number-pool-range.ts`)

- `RangeRow`: `{ rangeId?: string; start: string; end: string; weight: string }`. Strings because they hold what the user typed; `rangeId` is set for rows that exist on the server.
- `StoredRange`: `{ id: string; start: number; end: number; weight: number | null }`.
- `RangeUpdate`: `{ id: string; start: number; end: number; weight: number | null }`.
- `RangeInput`: `{ start: number; end: number; weight: number | null }`.
- `RangeChanges`: `{ deletes: string[]; smaller: RangeUpdate[]; larger: RangeUpdate[]; creates: RangeInput[] }`.
- `RangeRowErrors`: `{ start?: string; end?: string; weight?: string; row?: string }`.
- `NumberPoolForEditing`: `{ id; name; description; node; nodeAttribute; allocationScope: string[]; poolType: "User" | "Schema"; ranges: StoredRange[] }`.

## Domain types (`domain/model/scope-candidate.ts`)

- `ScopeCandidate`: `{ name: string; label: string; type: "attribute" | "relationship"; detail: string; unavailableReason?: string }`.

## Rules

### `validateRangeRows(rows) → Record<number, RangeRowErrors>` (FR-003)

- Parsing: a value is a whole number when the trimmed string matches `^-?\d+$` and is within `Number.MAX_SAFE_INTEGER`; `"1e3"`, `"1.0"` and `""` are not.
- `start`, `end`: required, whole number (negative allowed).
- `end` lower than `start`: error on `end`.
- `weight`: empty allowed; otherwise a whole number of 0 or more.
- Overlap: two valid rows overlap when `a.start <= b.end && b.start <= a.end`; both rows get `row: "Overlaps <b.start> – <b.end>"` (identical bounds overlap).

### `getRangeClipHint(row, limits) → string | null` (FR-004)

Returns `Clipped to <max(start,min)> – <min(end,max)> by the <attribute> limits` when a valid row extends past the attribute's `min_value` or `max_value`; otherwise `null`. Non-blocking.

### `sortStoredRanges(ranges) → StoredRange[]` (FR-017)

Weight descending, `null` weight last, then start ascending. Applied only when the form loads.

### `diffRanges(stored, rows) → RangeChanges` (FR-008)

- A stored range whose id is not on any row: delete.
- A row with `rangeId` whose values differ from the stored range: update; **smaller** when `newStart >= oldStart && newEnd <= oldEnd` (includes weight-only changes), otherwise **larger**.
- A row without `rangeId`: create.
- Unchanged rows produce nothing. Empty weight becomes `null`.

### `matchRowsToStored(rows, stored) → RangeRow[]` (FR-009, FR-015)

After a refusal: a row without `rangeId` whose bounds equal a stored range not already linked gets that range's id. All other row values stay as typed.

### `getScopeCandidates(schema: ModelSchema, nodeAttribute) → ScopeCandidate[]` (FR-010, FR-016)

`schema` is the node or generic schema of the selected kind. Every attribute and relationship of the kind itself, with `unavailableReason` when:

- the field is optional;
- the attribute kind is List or JSON;
- the relationship has cardinality many;
- the attribute is `nodeAttribute` ("This is the attribute the pool allocates").

## State transitions of the form

```text
create ──save──► pool created ──ranges applied──► closed (onSuccess)
                      │
                      └─range refused──► editing created pool (createdPoolId set)
edit ──save──► pool updated (if changed) ──ranges applied──► closed (onSuccess)
                      │
                      └─range refused──► editing, stored ranges refetched, rows kept
```
