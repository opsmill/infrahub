# Owners and Sources of Nodes

> Part of: `dev/knowledge/backend/` | Related: [Database Schema](database-schema.md), [Diff Conflicts](diff-conflicts.md)

How Infrahub stores, writes and reads the owners and the sources of a node and of its fields. The code is in
`backend/infrahub/core/ownership/`.

## Holders

A holder is the vertex that carries one list of owners. `HolderKind` (`core/ownership/models.py`) names each kind:

| Holder | Vertex | Reached from the node by |
|---|---|---|
| `NODE` | the `Node` vertex | the node itself |
| `ATTRIBUTE` | the `Attribute` vertex | `HAS_ATTRIBUTE` |
| `FIELD_SET` | an `OwnerSet` vertex with `identifier` and `direction` | `HAS_OWNER_SET` |
| `TARGET_SET` | an `OwnerSet` vertex | `HAS_TARGET_OWNER_SET` |
| `SOURCES` | the `Node` vertex | the node itself |

- A relationship field has no vertex of its own, so its owners go on an `OwnerSet`. The key of the set is the
  `identifier` and the `direction` of the relationship.
- A `TARGET_SET` holds the owners that a profile or an object template gives. Without a key, the owners go to the
  nodes. With `attribute`, or with `identifier` and `direction`, the owners go to that field of the nodes.

## Owner State

The active edges of a holder give its state (`StoredOwnerState`, `OwnerState`):

| Active edges of the holder | State |
|---|---|
| none | `INHERIT` |
| only `HAS_NO_OWNER` | `NO_OWNER` |
| one or more `HAS_OWNER` | `OWNERS`. They win over a `HAS_NO_OWNER` edge that a merge leaves active |
| `HAS_OWNER` and `HAS_OWNER_SOURCE` | a copy from an object template. The state reads as `INHERIT`, the origin is `TEMPLATE` |

- Every `HAS_NO_OWNER` edge ends at the one `NoOwner` vertex (`uuid: "no-owner"`). The creation of the `Root`
  vertex (`create_root_node`) and the graph migration `m086` create it. The write query also has a `MERGE` for a
  database without it. The delete of a branch, the rebase of a branch and a rollback (`GraphRollbacker`) delete each
  vertex that keeps no edge, but not this vertex.
  `verify_graph` reports a graph that has no such vertex or more than one (`GraphCheck.NO_OWNER_VERTEX`).
- `HAS_OWNER_SOURCE` ends at the object template. Without a `HAS_OWNER` edge, the mark gives no state.
  The delete of the template, and the merge of a branch that deletes it, close the mark. The copied `HAS_OWNER`
  edges stay, so the holder then reads as its own owners: the state `OWNERS` with the origin `SELF`.
- The sources of a node are `HAS_SOURCE` edges from the `Node` vertex. Sources have no "no owner" state: an empty
  list closes all source edges.
- The `HAS_OWNER` and `HAS_SOURCE` edges of a `Relationship` vertex (the properties of one link) keep one target
  and are not part of this model.
  The merge of a branch that deletes a node closes the `HAS_OWNER` and `HAS_SOURCE` edges from a `Relationship`
  vertex to that node, and the `HAS_SOURCE` edges from an `Attribute` vertex. The `HAS_OWNER` edges from a `Node`,
  `Attribute` or `OwnerSet` vertex and the `HAS_SOURCE` edges from a `Node` vertex stay, so that a list shows a
  deleted owner or a deleted source.
- The merge copies an owner edge or a source edge of the branch also when its owner or source is deleted, so the
  default branch reads the same list as the branch and the diff. Only the `HAS_OWNER_SOURCE` mark needs a live
  template.
- The changelog of a merge records no change for an owner list or a source list that the default branch held just
  before the merge (`DiffChangelogCollector`). An attribute value and the owner of one link have no such check: the
  changelog records them also when the default branch holds the same value.

## Writes

`OwnerStateWriteQuery` (`core/ownership/queries.py`) replaces the state of one holder. `NodeSourcesWriteQuery`
(`core/ownership/sources.py`) is the same query for the source edges.

- The query reads the edges with the branch of the request and writes on the write branch. The write branch is the
  global branch for a branch-agnostic node. For the owners of an attribute, the branch support of the attribute
  gives the write branch, whatever the branch support of the node.
- An edge of the write branch that is no longer in the list gets a `to` time.
- On the global branch, that edge also gets a `deleted` edge, as the delete of a node does. A branch reads a global
  edge that was open at the start of the branch, also after the global branch closes it. The `deleted` edge is later,
  so a branch made before the write reads the new state only. A later write that adds back the owner creates a new
  active edge, which is later than the `deleted` edge.
- An edge that the branch inherits gets a `deleted` edge on the branch, also when the branch has its own edge to the
  same owner. A read must apply the `deleted` edge, because the inherited edge stays open.
- When a write adds back an owner, or the "no owner" state, that a `deleted` edge of the branch hides, the query
  gives the `deleted` edge a `to` time and creates no edge. The branch reads the inherited edge again, and a merge
  has no edge to copy. So the owner does not come back when the default branch removed it after the start of the
  branch.
- The query looks for the `OwnerSet` with the same key on all branches and reuses it. It creates a set only for the
  first owner or the first "no owner". When the set goes back to inherit, its edges close and the vertex stays.
- The query compares only the key properties of a set (`owner_set_key_filter`), so another property on the vertex
  does not hide the set.
- Before the query checks that the node is active, it takes a write lock on the node vertex in the database
  (`SET n.uuid = n.uuid`), for every kind of holder. The lock lasts until the commit of the transaction. So two
  open transactions cannot both create a set with the same key, or an active edge to the same owner, on any write
  path: a merge, a node create, an object conversion. `NodeSourcesWriteQuery` and `NodeOwnerEdgesCloseQuery` take
  the lock too.
  The attribute rename migration, the only other code that creates a set, takes the same lock.
  The close query needs its own lock: `NodeDeleteQuery` locks the node on the default and the global branch with
  `SET n.updated_at`, but not on another branch, where it only creates an edge, and the creation of an edge does
  not wait for the lock of another transaction on the node.
- The check that the node is active comes after the lock, so it reads a delete of the node that another
  transaction commits while the query waits for the lock. The query then writes nothing and raises `QueryError`,
  for every kind of holder.
- `verify_graph` reports a node that has two sets with the same key (`GraphCheck.DUPLICATE_OWNER_SETS`). A read
  gives the owners of both sets together, so this state gives owners that no write stored.

`OwnershipWriter` (`core/ownership/writer.py`) wraps the write of one holder of a saved node:

- It writes nothing when the holder already stores the state.
- It adds the old and the new owner IDs to the changelog of the node. The reserved field names are in
  [Diff Conflicts](diff-conflicts.md). For the owners of an attribute, the write and the merge use the same rule
  (`attribute_owners_change`): a change between one owner and none gives the `owner` property with the owner IDs, as
  the save of the `owner` property does. Any other change gives the `owners` property with the owner lists.
- It records `updated_at` and `updated_by` on the node vertex only when the write branch is the default branch or
  the global branch.
- `copy_from_template` gives a new node the owners that its object template gives, with the `HAS_OWNER_SOURCE` mark.

The save of an attribute with a new `owner` property calls the same write with one owner, so it replaces all own
owners of the attribute. A cleared `owner` property gives the inherit state.

`Node.delete` closes the owner edges of the node, of its attributes and of its sets, and the edges to those sets,
with `NodeOwnerEdgesCloseQuery`. The query closes a `HAS_SOURCE` edge only when the edge starts at the node vertex:
the delete of an attribute closes the source edge of the attribute. The query also closes each `HAS_OWNER_SOURCE`
edge that ends at the node, with the branch rules of a write: a `to` time for an edge of the write branch, a
`deleted` edge for an edge that the branch inherits. This is one more write query for each deleted node.
After the lock, the query reads no holder when the node, its attributes and its sets have no owner edge, no source
edge and no template mark, and no `HAS_OWNER_SOURCE` edge ends at the node. This check reads the edges on all
branches and at all times, so a closed edge also makes the query read the holders.

## Owner Kinds

- An owner is an account or an account group (`OWNER_KINDS` in `core/ownership/input.py`). A repository is refused.
- A source is an account, an account group, a repository, a resource pool, a profile or an object template
  (`SOURCE_KINDS`).
- The create and the update of a node check the `owner` property of each attribute and of each link before the first
  write (`check_field_owner_kinds`), so a refused owner leaves the node unchanged also outside a transaction. The
  update checks only an owner that the database does not hold yet, so an owner that was deleted later does not stop
  the update. An owner of another kind, or an owner that does not exist, raises `ValidationError` with the path of
  the field, for example `color.owner`. The save of one attribute or of one link checks its own new owner too.

## Resolution

`OwnershipResolver` (`core/ownership/resolver.py`) reads the nodes, their parents and their profiles. The pure
rules are in `core/ownership/resolution.py`.

- For `MAX_NODES_FOR_LINEAGE_WALK` nodes or fewer, the resolver runs one query. For more nodes, it runs one query
  for each level of parents, because the nodes of a page share their parents and the walk reads the parents again
  for each node.
- `LineageWalk` (`core/ownership/queries.py`) adds a walk to the start of `NodeOwnerStateReadQuery`. The walk goes
  from each node up to its parents. It stops at the depth limit, at a node with its own owners, and at a copy from an
  object template. It also finds the profiles of each node that takes owners from its profiles, the profiles of a
  template copy included. The query then reads the stored state of each node that the walk found.
- The walk and the read of one node find the parent with two different Cypher patterns. So the resolver checks the
  result: when a parent or a profile that the rules need is not in the result, the resolver reads it with one more
  query for each level (`_needed`). The results are then the same if the walk misses a node.
- A change of the rules must reach four places: `core/ownership/resolution.py`, the walk, `_needed`, and
  `OwnerFilter`.

The owners that apply to a node come from the first level that has a state:

1. The own state of the node (`origin: SELF`).
2. Its profiles, in the order of `profile_priority`, then profile ID: the first profile that gives owners or
   "no owner" (`PROFILE`).
3. The copy from its object template (`TEMPLATE`).
4. Its parent, with the same order on the parent (`PARENT`). The parent is the peer of the relationship of kind
   `Parent`, otherwise the peer of the hierarchy relationship `parent`.

The owners that apply to a field: the own state of the field, then the profiles that give owners to that field,
then the template copy of the field, then the owners that apply to the node (`OBJECT`).

- The walk stops after `MAX_INHERITANCE_DEPTH` parents. A node with more parents and no state below the limit
  gets no inherited owner.
- A deleted owner stays in the list.
- `state` is always what the item itself stores, whatever the origin of the owners that apply.

## List Filters

`NodeGetListQuery` handles three filters before the pagination, so the count is correct:

| Filter | Built by | Start of the query |
|---|---|---|
| `node_metadata__owners__ids` | `OwnerFilter` (`core/ownership/filter.py`) | the owners, then down to the nodes that inherit |
| `node_metadata__owners__isnull` | `OwnerFilter` | all nodes with a live owner, then the nodes of the kind that are not in that set when the value is `true` |
| `node_metadata__sources__ids` | `SourceFilter` (`core/ownership/sources.py`) | the sources |

`OwnerFilter` must give each node the answer of the resolver: the same parent for each kind, the same depth limit,
the same order of profiles, and a deleted owner does not count.

## Schema Changes and Kind Changes

- The kind migration (`core/migrations/query/node_duplicate.py`) copies each edge type between the node and each
  other vertex, so the owner edges and the source edges follow the node.
- A rename or a removal of an attribute, and a removal of a relationship, close or move the `OwnerSet` vertices with
  that key (`OwnerSetKeyMigrationQuery`). The key is a vertex property that all branches share, so a rename gives the
  branch an edge to another set and changes no key. For an attribute of a generic, the query also reads the
  profiles and the templates of each kind that inherits the attribute (`profile_and_template_kinds`).
  The query ends an edge of the branch of the migration. An edge of another branch, the global branch included,
  stays open and gets a `deleted` edge on the branch of the migration, as `AttributeRemoveQuery` does. So a branch
  with the schema before the change still reads the owners of the field. For a rename on the default branch, the
  new set of a branch-agnostic node gets its edges on the global branch, where a write of owners can replace them.
  On another branch, the new set gets its edges on that branch until the merge runs the migration on the default
  branch.
- The removal of a kind (`core/migrations/schema/node_remove.py`) closes the owner edges and the source edges that
  start at each node of the kind, at its attributes and at its `OwnerSet` vertices. It also closes the `HAS_OWNER`,
  `HAS_SOURCE` and `HAS_OWNER_SOURCE` edges that end at a node of the kind. The other node keeps the edge to its
  `OwnerSet`.
- The attribute rename (`AttributeRenameQuery`) copies each edge type between the attribute and each other vertex,
  so an attribute keeps a source and an owner that are the same node.
- The attribute removal (`AttributeRemoveQuery`) ends each edge type between the attribute and each other vertex,
  so it ends a source and an owner that are the same node.
  On a branch, the query cannot read an owner that the default branch gave to the attribute after the start of the
  branch. So the merge of a deleted `HAS_ATTRIBUTE` edge closes each active owner edge of the attribute on the
  default branch (`BulkMergeNodeExistenceQuery`). An attribute that a kind migration of the branch moved to
  another `Node` vertex keeps its owners.
- The object conversion (`ConvertObjectType`) reads the owner states of the node before the delete and writes them
  on the new node. The owners of an attribute or of a relationship go to each field of the new kind that the mapping
  fills from it. A field that the mapping fills with a value or with the default gets no owner state. The owners of
  a relationship that fills no field of the new kind are not copied.

## Upgrade

| Migration | What it does |
|---|---|
| `m084` | Adds a `deleted` edge for each attribute owner of the default branch that a branch replaced, also when the default branch closed the owner edge after the start of the branch. The `deleted` edge starts at the first edge of the branch to another owner, so a read at a time between two owner writes of the branch gives one owner |
| `m085` | Closes the `HAS_OWNER` edges from attributes to repositories, on every branch. A branch still reads an edge of the default branch that was open at the start of the branch, so the migration adds a `deleted` edge for it on the branch, at the time of the upgrade. For such an edge of the global branch, the `deleted` edge goes on the global branch, as a write of owners on the global branch does. It deletes nothing, and prints the number of closed edges for each repository |
| `m086` | Creates the `NoOwner` vertex |

`infrahub db ownership-report` (`core/ownership/report.py`) reads only vertices and edges that the release before
holds, so it runs before the upgrade.

## Limits

- The diff and the merge of owners read branch-aware nodes, and the branch-aware attributes of all nodes. The owners
  of a relationship field (`FIELD_SET`) follow the branch support of the node, not of the relationship.
- The graph migration `m084` skips an attribute whose owner a branch wrote and then cleared before the upgrade.
  The release before closed the edge of the branch at the clear, and added its own `deleted` edge for the owner of
  the default branch at that time. So a read on the branch at a time between the write and the clear gives two
  owners.
- A branch made before the upgrade can read two owners on a branch-agnostic attribute when the release before
  changed its owner on the global branch after the start of the branch. That release gave the old global edge a
  `to` time and no `deleted` edge. `m084` reads only the owner edges of a branch, and `m085` only the edges to
  repositories.
- The clear of the source of a branch-agnostic attribute (`AttributeClearNodePropertyQuery`) gives the global edge
  a `to` time and no `deleted` edge. So a branch made before the clear still reads the old source. The release
  before does the same.
- The attribute rename migration (`core/migrations/query/owner_set_attribute.py`) takes the lock on the node, but
  does not then check that the node is active. When a delete of the node commits while the migration waits for the
  lock, the migration still gives the node a set with active edges.
- A rebase stops on a conflict of owners or sources until both branches hold the same list. See
  [Diff Conflicts](diff-conflicts.md).
- An event stores the owners of an attribute as the `owner` or the `owners` property of the attribute, in its payload
  only.
- The merge does not copy the `HAS_OWNER` edge of a link to a deleted owner. The default branch then reads no owner
  on the link, and the branch reads the deleted owner.
- The global edges of an `OwnerSet` that a schema change hides never close. The retirement of branch-agnostic data
  (`core/query/agnostic_retention.py`) reads only `Attribute` and `Relationship` vertices.
- A `HAS_OWNER_SOURCE` edge of the global branch stays open after the delete of a branch-aware object template.
  This is the mark of a branch-agnostic attribute of a branch-aware node. Its owners still read as a copy from the
  template.
- After a rename of an attribute on a branch other than the default branch, a write of owners on that branch cannot
  replace the owners that a branch-agnostic profile or object template gives to the attribute. The write goes to
  the global branch and the copy of the rename is on the branch.

## Key Files

| File | Content |
|---|---|
| `core/ownership/models.py` | Holders, states and the resolved result |
| `core/ownership/queries.py` | The read query, the write query and the close query |
| `core/ownership/repository.py` | `OwnershipRepository`: the reads and writes as one branch does them |
| `core/ownership/resolver.py`, `resolution.py` | The owners that apply |
| `core/ownership/filter.py`, `sources.py` | The list filters and the source edges |
| `core/ownership/input.py` | The kinds that can be an owner or a source, and the checks of owner references |
| `core/ownership/writer.py` | `OwnershipWriter`: the write of one holder of a saved node |
| `core/ownership/fields.py` | The reserved field names and the value of an owner list, for the changelog and the diff |
| `core/ownership/report.py` | The data of `infrahub db ownership-report` |
| `core/diff/ownership_differ.py`, `core/diff/ownership_fields.py` | The owner lists in the diff |
