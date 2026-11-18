# Contracts: Number pool create and edit form

No GraphQL or REST schema changes. This file records the existing contracts the form depends on, and the two frontend interfaces it adds.

## GraphQL mutations used (existing)

### Create

```graphql
mutation {
  CoreNumberPoolCreate(data: {
    name: { value: "subinterface-units" }
    description: { value: "Unit IDs per device" }
    node: { value: "InfraSubinterface" }
    node_attribute: { value: "unit_id" }
    allocation_scope: { value: ["device"] }
    ranges: [
      { start: 100, end: 199, allocation_weight: 10 }
      { start: 300, end: 399, allocation_weight: null }
    ]
  }) {
    object { id display_label hfid __typename }
  }
}
```

- `allocation_scope` is left out when no field is picked.
- `start_range` and `end_range` are never sent.

### Update

```graphql
mutation {
  CoreNumberPoolUpdate(data: {
    id: "<pool id>"
    name: { value: "subinterface-units" }
    description: { value: "Unit IDs per device" }
    ranges: [
      { start: 100, end: 299, allocation_weight: 10 }
      { start: 500, end: 599, allocation_weight: null }
    ]
  }) {
    object { id display_label hfid __typename }
  }
}
```

- `node`, `node_attribute` and `allocation_scope` are never sent on update.
- `ranges` is always the complete list. The backend keeps a stored range whose bounds match a sent range, and deletes the others. `ranges: []` removes every range.

### Values

- `start`, `end` and `allocation_weight` are written as bare integer literals.
- An empty weight is sent as `null`.

See `research.md`, "Payload typing and number encoding".

## Backend refusals the form shows

| Source | Example message | Shown |
|---|---|---|
| `backend/infrahub/pools/number_pool_range_validation.py` | "Range 300-450 overlaps 400-499 (\<id\>)" | alert above the footer |
| `backend/infrahub/graphql/mutations/resource_manager/number_pools/common.py::refuse_ranges_outside_attribute` | "Range 4000-5000 ends above the attribute's max_value (4094)" | alert above the footer |
| `backend/infrahub/pools/scope.py` | "\"device\" … the default branch's schema does not define the pool's kind at allocation_scope" | alert above the footer |
| Permission or uniqueness refusals | backend text | alert above the footer |

## Frontend interface: toast setting on the generic object save (changed)

`entities/nodes/object` create and update gain one optional parameter, passed through the hook, the use case and the fetcher:

```ts
// shape only; the name is decided in implementation
interface ObjectSaveErrorOptions {
  /** Receives the backend's message in place of the global error toast. */
  processErrorMessage?: (message: string) => void;
}
```

- **Callers that leave it out** behave exactly as today.
- **When it is set**, the fetcher puts it on the request `context`, and `handleGraphQLErrors` calls it in place of showing the toast.
- **Either way**, the mutation still rejects with the backend's message.

## Frontend interface: the form (replaced)

The form keeps `ObjectForm`'s props, so no caller changes:

| Prop | Use |
|---|---|
| `isUpdate` | Chooses create or edit. |
| `currentObject` | In edit, the pool loaded by the generic edit query. In create, an optional prefill. |
| `onSuccess(node)` | Called after a successful save. The caller closes the sheet and refreshes its data. |
| `onCancel()` | Called by Cancel. |

The form renders the sheet's body and footer. The caller owns the `Sheet` and its title, as today.
