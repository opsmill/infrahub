# Contract: the allocation scope on the number pool mutations

The generic node mutations `CoreNumberPoolCreate`, `CoreNumberPoolUpdate` and `CoreNumberPoolUpsert` (overridden by `backend/infrahub/graphql/mutations/resource_manager/number_pools/pool.py::InfrahubNumberPoolMutation`) carry the scope in the existing `allocation_scope` attribute.

## Input on create

```graphql
mutation {
  CoreNumberPoolCreate(data: {
    name: { value: "vlan-per-site" }
    node: { value: "InfraDevice" }
    node_attribute: { value: "vlan_id" }
    start_range: { value: 1 }
    end_range: { value: 100 }
    allocation_scope: { value: ["site", "role"] }
  }) { ok object { id allocation_scope { value } } }
}
```

`allocation_scope.value` accepts a list whose entries are, each, one of:

- a string holding the element's name on the pool's kind;
- a string holding the element's schema id;
- an object `{ "id": "<schema id>", "name": "<name>" }`, as returned by a read (the `id` is used, the `name` is ignored and recomputed).

An absent field, `null` or an empty list creates an unscoped pool.

## Stored and returned value

```json
[
  { "id": "17d0a4c2-…", "name": "site" },
  { "id": "3b1f90ee-…", "name": "role" }
]
```

Order is the input order. The value is returned as stored by every read of the node (generic node query, REST object read) and by the dedicated number-pool queries. Today the attribute returns the names it was given (`["site", "role"]`); this is the change of decisions 3 and 4.

## Refusals on create

Each refusal is a `ValidationError` on the `allocation_scope` field, naming the entry.

| Case | Message |
|------|---------|
| Entry resolves to nothing on the pool's kind in the default branch's schema | `allocation_scope: "<entry>" is not an attribute or a relationship of <kind> on branch <default branch>` |
| Entry is an optional attribute or an optional relationship | `allocation_scope: "<name>" is optional; a scope element must be required on <kind>` |
| Entry is a relationship of cardinality many | `allocation_scope: "<name>" has cardinality many; a scope element must be a relationship of cardinality one` |
| Entry contains `__` | `allocation_scope: "<entry>" is a path; a scope element must be an attribute or a relationship of <kind> itself` |
| Entry is the pool's tracked attribute | `allocation_scope: "<name>" is the attribute the pool allocates; it cannot divide the pool` |
| Entry appears twice | `allocation_scope: "<name>" appears more than once` |
| Pool's kind is a generic and the entry is declared on an implementing node only | `allocation_scope: "<entry>" is not declared on the generic <kind>` |
| Entry is an attribute of kind `List`, `JSON` or `Any` | `allocation_scope: "<name>" is of kind <attribute kind>; a scope element must hold a single scalar value` |
| Tracked attribute is `unique: true` | `allocation_scope: <kind>.<node_attribute> is unique; a globally unique number cannot be allocated per division` |

## Refusal on update

| Case | Message |
|------|---------|
| `allocation_scope` in the payload differs from the stored list (ids or order), or is `null` | `allocation_scope can't be changed after the pool is created` |

The same list, in any accepted input form, is not a change. The refusal applies to user-created and schema-created pools alike. Today's behaviour, where `null` on update clears the scope, goes away with its test.

## Refusal on allocation and attach

| Case | Message |
|------|---------|
| The schema of the request's branch does not define a scope element on the pool's kind | `<attribute>.from_pool: the scope element "<name>" of pool <pool name> does not exist on <kind> on branch <branch>; rebase the branch to get it` |

## Interaction with the rest of the pool

- `node` and `node_attribute` keep their existing refusal on change.
- Deleting a pool deletes its scope with it.
- A scope has no effect on `ranges`, on the shorthand bounds, or on what the pool records.
