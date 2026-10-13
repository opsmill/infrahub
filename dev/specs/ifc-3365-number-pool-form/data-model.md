# Data Model: Number pool create and edit form

No backend entity changes. This file describes the frontend types the form reads and writes. Paths are relative to `frontend/app/src/entities/resource-manager/`.

## Domain types (`domain/model/number-pool.ts`)

| Type | Change | Shape | Used by |
|---|---|---|---|
| `NumberPoolData` | changed | adds `ranges: Array<{ start: number; end: number; allocation_weight: number \| null }>` | The edit form's initial ranges, loaded through `GET_NUMBER_POOL` |

The `allocation_scope` field of `NumberPoolData` is typed `NodeAttribute<string[]>` and its mapper reads a stored scope as empty. Neither is changed by this feature. The form reads the scope from the generic edit query instead (see `research.md`, "Scope labels in the read-only summary").

## Domain rules (`domain/rules/`)

| Rule | Input | Output | Behavior |
|---|---|---|---|
| `canNumberPoolAllocateTo` | one attribute schema | boolean | True for a `Number` attribute that is not read-only. |
| `canNumberPoolBeScopedBy` | one attribute or relationship schema | boolean | False for an optional field, a relationship with cardinality many, or an attribute of kind List, JSON or Any. The form also leaves out the allocated attribute when it filters. |
| `findOverlappingRanges` | `Array<{ key; start: number; end: number }>` | `Map<key, Array<{ start; end }>>` | For each range, the other ranges it overlaps. Two ranges overlap when each one's start is at or below the other's end. |

## Form values (`ui/number-pool/form/number-pool-form-values.ts`)

The form edits the domain type directly: `NumberPoolFormValues = Pick<NumberPoolData, "name" | "description" | "node" | "node_attribute" | "allocation_scope" | "ranges">`.
- **Create:** sends the form values as the `CoreNumberPoolCreateInput` payload, unchanged.
- **Edit:** fills the form with the loaded pool, and sends `{ id, name, description, ranges }`.

| Component | Sets |
|---|---|
| Name, Description inputs | `name.value`, `description.value` |
| `NumberPoolNodeSelect` | `node.value` |
| `NumberPoolNodeAttributeSelect` | `node_attribute.value` |
| `NumberPoolAllocationScopeSelect` | `allocation_scope.value` (field names, in the order picked) |
| `NumberPoolRangesInput` | `ranges`: `{ start, end, allocation_weight }` from number inputs |

### Field dependencies

- Changing the node clears the attribute and the scope.
- Choosing a unique attribute clears the scope and disables "Scoped by".

### Range checks before sending

A number input reports an empty field as `NaN`, and an empty weight is stored as `null`.

| Check | Message | Where |
|---|---|---|
| bound empty (`NaN`) | "Required" | under the row |
| bound or weight negative or not an integer | "Whole number" | under the row |
| value above `Number.MAX_SAFE_INTEGER` | "Too large" | under the row |
| overlaps another row | "Overlaps \<start\> – \<end\>" | under both rows |

### Stored scope

The pool mapper (`api/number-pool.mappers.ts::mapToNumberPoolData`) reads the stored `[{ id, name }]` scope entries as field names.

## State transitions

| Event | Result |
|---|---|
| Save pressed with a failing browser check | Nothing is sent. Errors show under the failing rows and fields. |
| Backend refuses the save | Sheet stays open with every value kept. The backend's message shows in the alert above the footer. |
| Backend accepts the save | The caller's `onSuccess` runs. |
