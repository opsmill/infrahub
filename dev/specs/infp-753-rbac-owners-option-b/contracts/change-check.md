# Change check contract

The change check is the place in a mutation where Infrahub Enterprise decides if a change is allowed (FR-042 to FR-049). Infrahub Community owns the interface and ships an implementation that allows everything. The storage option does not change this contract. The names are proposals.

## Interface

`permissions/change_check/interface.py::ChangeCheck` has four operations.

| Operation | Input | Output | Community implementation |
|---|---|---|---|
| `check` | the database handle of the transaction, the branch, the account session, a `ChangeSet` | a list of `Refusal`, empty when the change is allowed | returns an empty list, reads nothing |
| `report` | the database handle, the branch, the account session, node IDs with their kind, optional field names | one `ItemPermissions` for each node | the decision for the kind, as today |
| `validate_permission` | an object permission or a global permission that a user saves | nothing, or an error | refuses `applies_to` other than `all_objects`, the action for changing owners, and the global permission to manage ownership |
| `counted_permissions` | the permissions of an account, as loaded | the permissions that count | drops every permission that `validate_permission` refuses |

## Change set

`permissions/change_check/models.py`, frozen dataclasses.

| Type | Fields | Meaning |
|---|---|---|
| `ItemChange` | `node_id`, `kind`, `field` (optional), `action` | One node or one field that the user creates, updates or deletes |
| `LinkChange` | `relationship identifier`, and for each end: `node_id`, `kind`, `field` (optional) | One link added or removed, with both ends |
| `OwnerChange` | `node_id`, `kind`, `field` (optional) | The owners of the item change |
| `MoveChange` | `node_id`, `kind`, `old_parent_id`, `new_parent_id` | The parent of a node changes |
| `ChangeSet` | `items`, `links`, `owner_changes`, `moves`, `created_node_ids`, `cascade_node_ids` | All changes of one mutation |

Rules for the content (FR-044, FR-046):

- The set holds only what the user sent and what changed. A field that the user sent with the same value is not in the set.
- A create gives the new node. The check can read the owners that apply after the creation, because the call comes after the write.
- A delete gives every node that the cascade removes, before anything is deleted.
- A change made from the peer side of a relationship gives both ends of the link and the field on each end.
- Profile values applied to nodes, computed attributes, template components, pool allocations and merges are never in a set.

## Refusal

| Field | Meaning |
|---|---|
| `node_id`, `kind`, `node_label` | The refused node |
| `field` | The refused field, or none for the node |
| `side` | The side of a link, when the refused item is one end of a link |
| `action` | `create`, `update`, `delete` or the action for changing owners |
| `message` | The reason that the check gave |
| `data` | Optional details that the check adds to the error `extensions` |

- When `check` returns one or more refusals, the mutation writes nothing (FR-045).
- The response lists every refusal at once, as one entry in `errors` for each.
- Other mutations of the same request still run.

## Permission report

`ItemPermissions`: `node_id`, `update`, `delete`, the action for changing owners, and `fields` (a decision for each field).

- Each decision is a `PermissionDecisionFlag`, as the kind check returns today.
- `report` and `check` must use the same decision, so that the reported value matches the result of the mutation (FR-049).

## Call sites

All calls are inside the transaction of the mutation, after the write and before the commit.

| Mutation | Call site |
|---|---|
| Update, and the update of an upsert | `graphql/mutations/main.py::InfrahubMutationMixin.mutate_update_object` |
| Create, and the create of an upsert | `core/node/create.py::_do_create_node`, when the mutation passes the check |
| Relationship add and remove | `graphql/mutations/relationship.py::RelationshipAdd.mutate`, `RelationshipRemove.mutate` |
| Delete | `graphql/mutations/main.py::InfrahubMutationMixin._delete_obj` |
| IP prefix delete | `graphql/mutations/ipam.py::InfrahubIPPrefixMutation.mutate_delete` |
| Object conversion | `graphql/mutations/convert_object_type.py::ConvertObjectType.mutate` |

## Selection of the implementation

- `workers/dependencies.py` builds one change check for the process, with the `_singletons` pattern.
- Infrahub Community builds `ChangeCheckCommunity`.
- Infrahub Enterprise supplies its own class. How it replaces the Community class was not checked in the Enterprise repository.
- Tests replace the singleton with a test implementation that refuses chosen items.

## Limits that the contract sets

- `ChangeCheckCommunity.check` does no database read (FR-043, SC-008).
- The check does not change data.
- The identity of the user holds the account ID and the IDs of its groups. With the group tree setting on, it also holds the groups above them (FR-051).
