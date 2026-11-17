# Change check contract

The change check is the place in a mutation where Infrahub Enterprise decides if a change is allowed (FR-042 to FR-049). Infrahub Community owns the interface and ships an implementation that allows everything. The storage option does not change this contract. The names are proposals.

## Interface

`permissions/change_check/interface.py::ChangeCheck` has four operations.

| Operation | Input | Output | Community implementation |
|---|---|---|---|
| `check` | the database handle of the transaction, the branch, the permissions of the request, a `ChangeSet` | a list of `Refusal`, empty when the change is allowed | returns an empty list, reads nothing |
| `report` | the database handle, the branch, the permissions of the request, node IDs with their kind, optional field names | one `ItemPermissions` for each node | the decision for the kind, as today |
| `validate_permission` | an object permission or a global permission that a user saves | nothing, or an error | refuses `applies_to` other than `all_objects`, the action for changing owners, and the global permission to manage ownership |
| `counted_permissions` | the permissions of an account, as loaded | the permissions that count | drops every permission that `validate_permission` refuses and that allows. A refused permission that denies stays, and denies for every node of its kind and action |

Decisions of the implementation (tasks T088 to T097):

- `check` and `report` get the permissions of the request, not the account session alone. This object is the `PermissionManager` that the request already loaded. It holds the account session and the permissions of the account, so `report` reads nothing from the database.
- A request without an account session has no permissions. Its mutations build no change set and call no change check. The permission checks of today also skip such a request.
- `validate_permission` raises `EnterpriseRequiredError` with the feature name `ownership_permissions`.

Decisions of the implementation (tasks T098 to T104):

- `PermissionManager.load_for_account` gets the change check as an argument, because `permissions/manager.py` cannot import `workers/dependencies.py` without an import cycle. The GraphQL context and the REST dependency pass the change check of the process. Without the argument, the Community rules apply.
- The node classes `CoreObjectPermission` and `CoreGlobalPermission` call `validate_permission` in `save`. A branch whose schema has no `applies_to` yet reads as `all_objects`.
- `PermissionResolver` does not match a permission with the `any` action when the requested action is `hand_over`.
- `node_metadata { permissions }` makes one `report` call for each page, for all fields. The `fields` argument filters the result of that call.
- The display label uses the template filter `permission_applies_to_suffix`, because the value is an enum in a node and a text in a recompute.

## Change set

`permissions/change_check/models.py`, frozen dataclasses.

| Type | Fields | Meaning |
|---|---|---|
| `ItemChange` | `node_id`, `kind`, `field` (optional), `action` | One node or one field that the user creates, updates or deletes |
| `LinkChange` | `identifier`, and for each end (`source` and `peer`, each a `LinkEnd`): `node_id`, `kind`, `field` (optional) | One link added or removed, with both ends. `source` is the end that the mutation names |
| `OwnerChange` | `node_id`, `kind`, `field` (optional) | The owners of the item change. `field` is `node_metadata__target_owners` for the owners that a profile or an object template gives |
| `MoveChange` | `node_id`, `kind`, `old_parent_id`, `new_parent_id` | The parent of a node changes |
| `ChangeSet` | `items`, `links`, `owner_changes`, `moves`, `created_node_ids`, `cascade_node_ids` | All changes of one mutation |

Rules for the content (FR-044, FR-046):

- The set holds only what the user sent and what changed. A field that the user sent with the same value is not in the set.
- A create gives the new node. The check can read the owners that apply after the creation, because the call comes after the write.
- A delete gives every node that the cascade removes, before anything is deleted.
- A change made from the peer side of a relationship gives both ends of the link and the field on each end.
- Profile values applied to nodes, computed attributes, template components, pool allocations and merges are never in a set.
- An owner change is in the set only when the user sent owners and the stored owners changed. The copy of the owners of an object template at a create is not in the set.
- A change of the sources of a node is an update of the node (D-10). It gives one `ItemChange` for the node with the update action and no field, only when the user sent sources and the stored sources changed. It is not an `OwnerChange`. A create already gives the `ItemChange` of the new node. This rule is a decision of the implementation (task T137). No source sets it.
- A create gives one `ItemChange` for the node, and one for each field that the user sent.
- A `MoveChange` is in the set when a link to the parent that passes owners down is added or removed, from the side of the child or from the side of the parent. The parent of a new node is not a move.
- The kind of a link end comes from the changelog of the node. The relationship mutations give the kind of each peer that they read. For a peer that a write did not read, the changelog can hold the peer kind of the relationship, which can be a generic.

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
- Each entry has the code `PERMISSION_DENIED`. Its `extensions.data` keeps the two fields of the error catalogue: `action` and `resource_kind`. The other fields of the refusal are in `extensions.refusal`: `node_id`, `kind`, `node_label`, `field`, `side`, `action` and `data`.
- The mutation raises `ChangeRefusedError`, which is a `PermissionDeniedError`. Outside the GraphQL response, it is one error with every reason in its message.
- Other mutations of the same request still run.

## Permission report

`ItemPermissions`: `node_id`, `update`, `delete`, the action for changing owners, and `fields` (a decision for each field).

- Each decision is a `BranchRelativePermissionDecision`, as the permission report of a kind returns today. The GraphQL contract uses the same type.
- In Infrahub Community, the decision for the action for changing owners is the decision for `update`, because a change of owners needs the update permission only.
- `report` and `check` must use the same decision, so that the reported value matches the result of the mutation (FR-049).

## Call sites

All calls are inside the transaction of the mutation, after the write and before the commit. A delete is the exception: its call comes before the write, so that the owners of the nodes can still be read.

| Mutation | Call site |
|---|---|
| Update, and the update of an upsert | `graphql/mutations/main.py::InfrahubMutationMixin.mutate_update_object` |
| Create, and the create of an upsert | `core/node/create.py::_do_create_node`, when the mutation passes the check |
| Relationship add and remove | `graphql/mutations/relationship.py::RelationshipAdd.mutate`, `RelationshipRemove.mutate` |
| Delete | `graphql/mutations/main.py::InfrahubMutationMixin._delete_obj` |
| IP prefix delete | `graphql/mutations/ipam.py::InfrahubIPPrefixMutation.mutate_delete` |
| Object conversion | `graphql/mutations/convert_object_type.py::ConvertObjectType.mutate` |

Call sites of the implementation that the table does not name:

- Every create goes through `graphql/mutations/main.py::create_node_with_owners`, which passes the check to `create_node`. This covers the generic create, the create of an upsert, the repository create, and the creates of IP addresses and IP prefixes.
- Every update goes through `mutate_update_object`. This covers the update of an upsert, the repository update, and the updates of IP addresses and IP prefixes. The call comes before the IP address management reconciliation, so the parent that the reconciliation sets is not in the set.
- The delete of a number pool and the delete of a number pool range do not use the generic delete. Each one gives the check to `NodeManager.delete` through the argument `before_delete`.
- The object conversion makes two calls in its transaction. The first call comes before the delete of the old node, and its set holds that delete. The second call comes after the new node is saved, and its set holds the create of the new node. At the second call, the new node has the owners of the old node.
- These mutations make no call: the update of a computed attribute, of a display label and of a human-friendly ID, the allocation from a resource pool, and the mutations of an account on its own profile and tokens.

## Selection of the implementation

- `workers/dependencies.py` builds one change check for the process, with the `_singletons` pattern.
- Infrahub Community builds `ChangeCheckCommunity`.
- Infrahub Enterprise supplies its own class. How it replaces the Community class was not checked in the Enterprise repository.
- Tests replace the singleton with a test implementation that refuses chosen items.

## Limits that the contract sets

- `ChangeCheckCommunity.check` does no database read (FR-043, SC-008).
- The check does not change data.
- The identity of the user holds the account ID and gives the IDs of its groups through `get_group_ids`, which reads them at its first call. With the group tree setting on, it also gives the groups above them (FR-051).
