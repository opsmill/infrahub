# UI Contract: `getRelationshipDisplayLabel`

The single client-side interface introduced by this feature. Every relationship-label render site MUST resolve its label through this function.

## Signature

```ts
function getRelationshipDisplayLabel(
  relationshipSchema: RelationshipSchema,
  peerSchema?: ModelSchema | null,
): string;
```

- `relationshipSchema` — the relationship being rendered.
- `peerSchema` — the schema of `relationshipSchema.peer`, resolved by the caller via `useSchema` / `getSchema` / `resolveSchema`. Pass `undefined`/`null` if unresolved.

## Contract

| # | Given | Then |
|---|-------|------|
| C1 | `relationshipSchema.hierarchical` truthy **and** `peerSchema` is a concrete node with a label | returns `peerSchema.label` |
| C2 | `relationshipSchema.hierarchical` truthy **and** `peerSchema` missing or `peerSchema.label` empty | returns `relationshipSchema.label ?? relationshipSchema.name` |
| C3 | `relationshipSchema.hierarchical` falsy (any non-hierarchical relationship, including one named `parent`/`children`) | returns `relationshipSchema.label ?? relationshipSchema.name` — identical to prior inline behavior |
| C4 | children relationship (`cardinality: "many"`) with hierarchical + concrete-node peer label | returns `peerSchema.label` verbatim (no pluralization) |
| C5 | `relationshipSchema.hierarchical` truthy **and** `peerSchema` is a **generic** (`isGenericSchema`) | returns `relationshipSchema.label ?? relationshipSchema.name` — a generic's label is too broad; keep "Parent"/"Children" |

## Consumers (call sites that MUST route through this function)

| Site | File | Peer already resolved? |
|------|------|------------------------|
| A | `object-details/object-data-display/object-data-row.tsx` | no — add `useSchema(peer)` |
| B | `object-details/object-data-display/object-relationship-row.tsx` | no — add `useSchema(peer)` |
| C | `object-tabs.tsx` | no — add `useSchema(peer)` |
| D | `object-details/object-details-tab.tsx` | **yes** (`useSchema(relationship.peer)`) |
| E | `object-table/cells/table-column-header.tsx` | **yes** (`useSchema(relationshipSchema.peer)`) |
| F (consistency) | `shared/components/form/utils/getFormFieldFromRelationship.ts` | **yes** (`getSchema(relationshipSchema.peer)`) |
| G | `sort/ui/add-sort/add-sort-picker.tsx` | **yes** (`useSchema(relationship.peer)`) |
| H | `sort/ui/hooks/use-sortable-fields.ts` | **yes** (`resolveSchema(relationship.peer, ...)`) |
| I | `object/ui/filters/relationship-filter-form.tsx` | no — add `useSchema(peer)` |

## Non-goals

- Does not resolve the peer schema itself (caller's responsibility — keeps the function pure and store-free).
- Does not pluralize.
- Does not read or mutate any persisted state.
