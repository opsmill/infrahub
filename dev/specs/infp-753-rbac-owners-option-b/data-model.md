# Data model: Owner and source metadata (Community side), storage option B

The names of labels, edge properties and attributes are proposals. The API review and the engineering review fix them ([research.md](research.md), R-22).

## Graph structure

### Vertices

| Vertex | Status | Properties | Branch data |
|---|---|---|---|
| `Node` | existing | as today | as today |
| `Attribute` | existing | as today | as today |
| `OwnerMarker` | new, one shared vertex | a fixed `uuid` | none |

Option B adds no vertex for each set of owners. On the data of the benchmark of 2026-11-09, it added 532,900 edges and 1 vertex.

### Edges

All edges below carry the branch and time properties of Infrahub edges (`branch`, `branch_level`, `status`, `from`, `to`).

| Edge | From | To | Extra properties | Status | Meaning |
|---|---|---|---|---|---|
| `HAS_OWNER` | `Attribute` | owner `Node` | none | existing, now several | Own owners of an attribute |
| `HAS_OWNER` | `Node` | owner `Node` | none | new use | Own owners of a node |
| `HAS_OWNER` | `Node` | owner `Node` | `field` | new | Owner of a relationship field of the node |
| `HAS_OWNER` | `Node` (profile or template) | owner `Node` | `given` | new | Owner that it gives to its nodes |
| `HAS_OWNER` | `Node` (profile or template) | owner `Node` | `given`, `field` | new, not in the engineering design | Owner that it gives to one field of its nodes |
| `HAS_OWNER` | `Node`, `Attribute` | `OwnerMarker` | the same `field` and `given` as the holder | new | The holder has its own state |
| "from template" mark | `Node`, `Attribute` | template `Node` | `field` for a relationship field | new, open | The owners are a copy from this template |
| `HAS_SOURCE` | `Node` | source `Node` | none | new use | Sources of a node |
| `HAS_OWNER`, `HAS_SOURCE` | `Relationship` | `Node` | none | existing, unchanged | Owner and source of one link (D-9) |

- `field` holds the name of the field, such as `interfaces`. The identifier and the direction of the relationship are an open alternative ([research.md](research.md), R-1).
- Two edges from a node vertex can end at the same owner vertex: one for the node, and one for each field with that owner. The properties tell them apart.

### Holders

A holder is the item that has one owner state.

| Holder | Start vertex | `field` | `given` |
|---|---|---|---|
| A node | the node | not set | not set |
| An attribute of a node | the attribute | not set | not set |
| A relationship field of a node | the node | the field | not set |
| The nodes of a profile or template | the profile or template | not set | set |
| One field of the nodes of a profile or template | the profile or template | the field | set |

### Owner state of a holder

| Active `HAS_OWNER` edges of the holder | State |
|---|---|
| none | inherit |
| only the edge to the marker | no owner |
| the edge to the marker and edges to owners | those owners |
| edges to owners and no edge to the marker, on an attribute | those owners. This is an attribute owner written before the upgrade (FR-037) |
| edges to owners and the "from template" mark | template copy: the state reads as inherit, with the origin "template" |

State changes:

| From | Input | To | Edges |
|---|---|---|---|
| any | key left out | same | no change |
| any | list of owners | own owners | add the marker edge, close the "from template" mark, close removed owners, add new owners |
| any | `[]` | no owner | close all owner edges and the "from template" mark, add the marker edge |
| any | `null` | inherit | close all owner edges, the marker edge and the "from template" mark |
| new node | created from a template that gives owners | template copy | add owner edges and the "from template" mark |

### Indexes

| Index | Status |
|---|---|
| `owner_branch` on `HAS_OWNER(branch)` | existing in `core/graph/index.py`. The diff query uses it with a hint |
| `source_branch` on `HAS_SOURCE(branch)` | existing |

### Graph migrations

The numbers are the next free numbers when the work starts.

| Migration | Requirement |
|---|---|
| Close the `HAS_OWNER` edges from attributes to repositories | FR-036 |
| Hide the attribute owner of the default branch that a branch replaced | FR-037 |
| Set `applies_to = all_objects` on every object permission and recompute its human-friendly ID | FR-047 |

The kind migration is not a graph migration, but it must change: it must keep one edge for each holder, owner and edge type, and copy `field` and `given` ([research.md](research.md), R-11).

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

A deleted owner stays in the list with `is_deleted: true` and does not count as an owner (FR-008). The marker is never an owner.

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
| `HolderKind` | same | `NODE`, `ATTRIBUTE`, `FIELD`, `TARGET` |
| `HolderKey` | same | `kind`, `field`, `given` |
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
| The marker vertex is never accepted as an owner in an input | FR-003 |
| An owner reference has an ID, or a kind with an HFID of the right length | FR-003 |
| A failed owner check refuses the whole mutation and changes nothing | FR-003 |
| `target_owners` and `target_field_owners` only on profiles and object templates | FR-012 |
| A field name in `field_owners` is an attribute or a relationship of the kind | FR-013 |
| A source is an account, an account group, a repository, a resource pool, a profile or an object template | FR-033 |
| In Community, `applies_to` is `all_objects` | FR-048 |
