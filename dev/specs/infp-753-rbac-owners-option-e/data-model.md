# Data model: Owner and source metadata (Community side), storage option E

The names of labels, edge types and attributes are proposals. The API review and the engineering review fix them ([research.md](research.md), R-22).

## Graph structure

### Vertices

| Vertex | Status | Properties | Branch data |
|---|---|---|---|
| `Node` | existing | as today | as today |
| `Attribute` | existing | as today | as today |
| `OwnerSet` | new | `attribute`, or `identifier` and `direction`, or none | none |
| `NoOwner` | new, one shared vertex | `uuid: "no-owner"` | none |

Key of an `OwnerSet`:

| Set | Reached by | Key |
|---|---|---|
| Owners of a relationship field of a node | `HAS_OWNER_SET` from the node | `identifier` and `direction` of the relationship |
| Owners that a profile or template gives to its nodes | `HAS_TARGET_OWNER_SET` from the profile or template | no key |
| Owners that a profile or template gives to an attribute | `HAS_TARGET_OWNER_SET` | `attribute` |
| Owners that a profile or template gives to a relationship field | `HAS_TARGET_OWNER_SET` | `identifier` and `direction` |

- Infrahub creates an `OwnerSet` at the first owner or the first "no owner" of the set.
- A write first reuses a vertex with the same key under the same node, created by any branch.
- When the set goes back to inherit, its edges close and the vertex stays.

### Edges

All edges below carry the branch and time properties of Infrahub edges (`branch`, `branch_level`, `status`, `from`, `to`). No edge has another property.

| Edge | From | To | Status | Meaning |
|---|---|---|---|---|
| `HAS_OWNER` | `Attribute` | owner `Node` | existing, now several | Own owners of an attribute |
| `HAS_OWNER` | `Node` | owner `Node` | new use | Own owners of a node |
| `HAS_OWNER` | `OwnerSet` | owner `Node` | new | Owners of the set |
| `HAS_NO_OWNER` | `Node`, `Attribute`, `OwnerSet` | `NoOwner` | new | The holder is set to "no owner" |
| `HAS_OWNER_SET` | `Node` | `OwnerSet` | new | Owner state of one relationship field |
| `HAS_TARGET_OWNER_SET` | `Node` (profile or template) | `OwnerSet` | new | Owners that it gives |
| `HAS_OWNER_SOURCE` | `Node`, `Attribute`, `OwnerSet` | template `Node` | new | The owners are a copy from this template |
| `HAS_SOURCE` | `Node` | source `Node` | new use | Sources of a node |
| `HAS_OWNER`, `HAS_SOURCE` | `Relationship` | `Node` | existing, unchanged | Owner and source of one link (D-9) |

No two edges from a node vertex end at the same vertex, because the owners of fields and the given owners start at an `OwnerSet`.

### Owner state of a holder

A holder is a node vertex, an attribute vertex or an `OwnerSet` vertex.

| Active edges of the holder | State |
|---|---|
| none | inherit |
| only `HAS_NO_OWNER` | no owner |
| one or more `HAS_OWNER` | those owners. They win over a `HAS_NO_OWNER` edge that a merge leaves active |
| `HAS_OWNER` edges and `HAS_OWNER_SOURCE` | template copy: the state reads as inherit, with the origin "template" |

State changes:

| From | Input | To | Edges |
|---|---|---|---|
| any | key left out | same | no change |
| any | list of owners | own owners | close `HAS_NO_OWNER` and `HAS_OWNER_SOURCE`, close removed owners, add new owners |
| any | `[]` | no owner | close all `HAS_OWNER` and `HAS_OWNER_SOURCE`, add `HAS_NO_OWNER` |
| any | `null` | inherit | close all `HAS_OWNER`, `HAS_NO_OWNER` and `HAS_OWNER_SOURCE` |
| new node | created from a template that gives owners | template copy | add `HAS_OWNER` and `HAS_OWNER_SOURCE` |

A write on a branch hides each owner edge that the branch inherits with a `deleted` edge, also when the branch has its own edge to the same owner.

### Indexes

| Index | Status |
|---|---|
| `owner_branch` on `HAS_OWNER(branch)` | existing in `core/graph/index.py` |
| `source_branch` on `HAS_SOURCE(branch)` | existing |
| `HAS_NO_OWNER(branch)` | new, to measure ([research.md](research.md), R-9) |
| An index for the lookup of an `OwnerSet` by key | to decide in the spike |

### Graph migrations

The numbers are the next free numbers when the work starts.

| Migration | Requirement |
|---|---|
| Close the `HAS_OWNER` edges from attributes to repositories | FR-036 |
| Hide the attribute owner of the default branch that a branch replaced | FR-037 |
| Set `applies_to = all_objects` on every object permission and recompute its human-friendly ID | FR-047 |

The kind migration is not a graph migration, but it must change: it must keep one edge for each edge type between the node and each other vertex, and copy the owner and source edges that start at the node ([research.md](research.md), R-11).

## Resolution order

Owners that apply to a node (FR-004):

1. The own state of the node: own owners, or no owner.
2. Its profiles, by profile priority: the first profile that gives owners to its nodes.
3. The template copy on the node.
4. Its parent: the peer of the Parent relationship, else the hierarchy parent. Then the same order on the parent.

Owners that apply to a field (FR-005):

1. The own state of the field.
2. The owners that its profiles give to the field, by profile priority.
3. The template copy on the field.
4. The owners that apply to its node.

A deleted owner stays in the list with `is_deleted: true` and does not count as an owner (FR-008).

## Core schema changes

### `CoreObjectPermission` (changed)

| Attribute | Type | Default | Note |
|---|---|---|---|
| `namespace`, `name`, `action`, `decision` | as today | as today | `action` gets one new value: the action for changing owners |
| `applies_to` | Text enum | `all_objects` | `all_objects`, `owned_objects`, `objects_without_owners` |

- The human-friendly ID and the uniqueness constraint include `applies_to`.
- The display label adds `applies_to` only when it is not `all_objects`.
- Community accepts only `all_objects`, and refuses the action for changing owners.

### `CoreGlobalPermission` (changed)

- `action` gets one new choice: manage ownership. Community refuses to save it.

### Configuration

- One new setting on `SecuritySettings`: the account group tree, off by default.

## Domain model (Python)

| Type | Module | Fields |
|---|---|---|
| `OwnerState` | `core/ownership/models.py` | `INHERIT`, `OWNERS`, `NO_OWNER` |
| `OwnerOrigin` | same | `SELF`, `PROFILE`, `TEMPLATE`, `PARENT`, `OBJECT` |
| `HolderKind` | same | `NODE`, `ATTRIBUTE`, `FIELD_SET`, `TARGET_SET` |
| `HolderKey` | same | `kind`, `attribute`, `identifier`, `direction` |
| `StoredOwnerState` | same | `owner_ids` (None is inherit, empty is no owner), `template_id` |
| `StoredNodeOwnership` | same | `node_id`, `kind`, `holders`, `parent_id`, `profiles` with priority |
| `ResolvedOwnership` | same | `state`, `owner_ids`, `origin`, `origin_node_id` |
| `OwnerReference` | same | `id`, `kind`, `display_label`, `hfid`, `is_deleted` |
| `PermissionAppliesTo` | `core/constants/__init__.py` | `ALL_OBJECTS`, `OWNED_OBJECTS`, `OBJECTS_WITHOUT_OWNERS` |
| `ObjectPermission` (changed) | `core/account.py` | adds `applies_to`, default `all_objects` |
| `ChangeSet` | `permissions/change_check/models.py` | see [contracts/change-check.md](contracts/change-check.md) |
| `Refusal` | same | see the contract |
| `ItemPermissions` | same | see the contract |

## Validation rules

| Rule | Requirement |
|---|---|
| An owner is an account or an account group | FR-003, D-4 |
| An owner reference has an ID, or a kind with an HFID of the right length | FR-003 |
| A failed owner check refuses the whole mutation and changes nothing | FR-003 |
| `target_owners` and `target_field_owners` only on profiles and object templates | FR-012 |
| A field name in `field_owners` is an attribute or a relationship of the kind | FR-013 |
| A source is an account, an account group, a repository, a resource pool, a profile or an object template | FR-033 |
| In Community, `applies_to` is `all_objects` | FR-048 |
