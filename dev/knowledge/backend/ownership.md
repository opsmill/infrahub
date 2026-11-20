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
| `HAS_OWNER` or `HAS_NO_OWNER`, and `HAS_OWNER_SOURCE` | a copy from an object template. The state reads as `INHERIT`, the origin is `TEMPLATE` |

- Every `HAS_NO_OWNER` edge ends at the one `NoOwner` vertex (`uuid: "no-owner"`). The creation of the `Root`
  vertex (`create_root_node`) and the graph migration `m086` create it. The write query also has a `MERGE` for a
  database without it. The delete of a branch, the rebase of a branch and a rollback (`GraphRollbacker`) delete each
  vertex that keeps no edge, but not this vertex.
  `verify_graph` reports a graph that has no such vertex or more than one (`GraphCheck.NO_OWNER_VERTEX`).
- `HAS_OWNER_SOURCE` ends at the object template. Without a `HAS_OWNER` or `HAS_NO_OWNER` edge, the mark gives no
  state. The delete of the template, and the merge of a branch that deletes it, close the mark. The copied
  `HAS_OWNER` or `HAS_NO_OWNER` edges stay, so the holder then reads as its own state: `OWNERS`, or `NO_OWNER` for a
  copy of "no owner", with the origin `SELF`.
- The sources of a node are `HAS_SOURCE` edges from the `Node` vertex. Sources have no "no owner" state: an empty
  list closes all source edges.
- The `HAS_OWNER` and `HAS_SOURCE` edges of a `Relationship` vertex (the properties of one link) keep one target
  and are not part of this model.
  The merge of a branch that deletes a node closes the `HAS_OWNER` and `HAS_SOURCE` edges from a `Relationship`
  vertex to that node, and the `HAS_SOURCE` edges from an `Attribute` vertex. The `HAS_OWNER` edges from a `Node`,
  `Attribute` or `OwnerSet` vertex and the `HAS_SOURCE` edges from a `Node` vertex stay, so that a list shows a
  deleted owner or a deleted source.
- A read applies one of two rules to the `HAS_OWNER` and `HAS_SOURCE` edges of a vertex:
  - From a `Node`, `Attribute` or `OwnerSet` vertex, the read takes the latest edge for each peer, so several
    owners can be active together (`NodeOwnerStateReadQuery`, and the `owner` property in
    `NodeListGetAttributeQuery`). The `HAS_SOURCE` edges of a `Node` vertex use this rule too.
  - From a `Relationship` vertex, the read takes the latest edge for each edge type, so the link has one owner and
    one source at most (`core/query/relationship.py`). The `HAS_SOURCE` edge of an `Attribute` vertex uses this rule
    too (`NodeListGetAttributeQuery`).
- The merge copies an owner edge or a source edge of the branch also when its owner or source is deleted, so the
  default branch reads the same list as the branch and the diff. Only the `HAS_OWNER_SOURCE` mark needs a live
  template.
- The changelog of a merge records no change for an owner list or a source list that the default branch held just
  before the merge (`DiffChangelogCollector`). An attribute value and the owner of one link have no such check: the
  changelog records them also when the default branch holds the same value.
- The diff reads the default branch changes of each node whose owners or sources changed on the branch
  (`DiffCalculator`). So a delete of the node on the default branch gives a node conflict that cannot be resolved.

## Writes

`OwnerStateWriteQuery` (`core/ownership/queries.py`) replaces the state of one holder. `NodeSourcesWriteQuery`
(`core/ownership/sources.py`) is the same query for the source edges.

- The query reads the edges with the branch of the request and writes on the write branch. The write branch is the
  global branch for a branch-agnostic node. For the owners of an attribute, the branch support of the attribute
  gives the write branch, whatever the branch support of the node.
- An edge of the write branch that is no longer in the list gets a `to` time. An edge that has a `to` time keeps
  it. A branch can read a global edge that is closed after the start of the branch, and a later `to` time would
  show the old owner again on the default branch.
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
- The query writes an edge to an owner only when the branch reads an `IS_PART_OF` edge of the owner vertex. Two
  rules then apply:
  - A write of a list that a user gives also needs that edge to be active, so it skips a deleted owner. The check
    of the owner kinds refuses a deleted owner before the write (see Owner Kinds).
  - A copy of a list that the graph stores keeps a deleted owner (`keep_deleted_owners`), because a deleted owner
    stays in the list. The object conversion (`store_owner_states`), the copy from an object template
    (`copy_from_template`) and the owner resolution of a merge (`DiffMerger._apply_owner_diff_resolutions`) use
    this rule.
- The query looks for the `OwnerSet` with the same key on all branches and on each `Node` vertex of the UUID, and
  reuses it. So after a kind migration on one branch, the two branches write to the same set. It creates a set only
  for the first owner or the first "no owner". When the set goes back to inherit, its edges close and the vertex stays.
- The query compares only the key properties of a set (`owner_set_key_filter`), so another property on the vertex
  does not hide the set.
- Before the query checks that the node is active, it takes a write lock on the node vertex in the database
  (`SET n.uuid = n.uuid`), for every kind of holder. The lock lasts until the commit of the transaction. So two
  open transactions cannot both create a set with the same key, or an active edge to the same owner, on any write
  path: the owner resolution of a merge, a node create, an object conversion. `NodeSourcesWriteQuery` and
  `NodeOwnerEdgesCloseQuery` take the lock too. The copy of the owner edges of a branch in a merge
  (`BulkMergeOwnershipEdgesQuery`) takes no lock. It depends on the merge write block (`MergeWriteBlocker`, see
  [Merge Failure Recovery](merge-failure-recovery.md)), which refuses the other writes on the default branch and on
  the source branch during the merge.
  The attribute rename migration, the only other code that creates a set, takes the same lock before it reads the
  sets of the node. It looks for the set with the new key in the same way, on all branches and on each `Node` vertex
  of the UUID. After the lock, it gives no set to a node that is not active, with the same check of a later
  `deleted` `IS_PART_OF` edge as a write of owners.
- Lock order: a writer of a node locks the node vertex first, and then an attribute vertex or a set vertex. A
  write of owners, `Node._update` and `Node.delete` take the lock on the node vertex (`NodeLockQuery`, or the same
  `SET` in the query) before they write a field, on every branch. When one transaction locks a field first, it
  fails against a transaction that locks the node first:
  - On the default branch, the two transactions deadlock, and Neo4j stops one of them with
    `Neo.TransientError.Transaction.DeadlockDetected`. For example, the value write of an attribute locks the
    attribute vertex, and the write of `updated_at` on the node vertex comes later.
  - On another branch, the delete does not wait for the write, and an active value edge or owner edge stays on a
    deleted attribute.
- Two writers still lock a field before the node, so they can still deadlock against a delete of the node:
  - `Attribute.save` from a caller other than `Node._update` locks the attribute vertex before the owner write locks
    the node vertex. Only the migration `m064` calls it, and a migration runs alone.
  - On the default branch, `RelationshipDeleteQuery` sets `updated_at` on the `Relationship` vertex before the
    source and the peer node vertices, in one statement. `Relationship.delete` in the GraphQL `RelationshipRemove`
    mutation and `RelationshipManager.save` in the profile applier run it before any node lock.
- Order of the nodes: a transaction that writes several nodes locks each node vertex in turn. Two transactions
  that lock the same two nodes in the reverse order deadlock, on every branch, and Neo4j stops one of them with
  `DeadlockDetected`. The update, upsert and delete mutations retry this error (`retry_db_transaction`), so a user
  sees a delay.
  - The cascade of `NodeManager.delete`, the profile refresh and the IPAM reconciler lock their nodes in the order
    of the node IDs, so two of these writers lock their shared nodes in one order. A node delete also locks its
    peer nodes in no fixed order, so these writers can still deadlock through the peers of a deleted node. The
    cascade locks all its nodes first and then deletes them in its own order, because a delete leaves out of its
    changelog the links that an earlier delete closed.
  - A caller that saves several nodes in one transaction in another order can still deadlock against one of
    these writers or against another caller, for example two scripts that each call `node.save()` on the same two
    nodes in the reverse order.
- When the caller gives no time, `Node.delete` reads its time after the lock, so it also closes the owner edges
  that a write commits while the delete waits for the lock.
- The check that the node is active comes after the lock, so it reads a delete of the node that another
  transaction commits while the query waits for the lock. The query then writes nothing, for every kind of holder.
  It raises `QueryError`, unless the caller sets `skip_inactive`. Only the owner resolution of a merge sets it: the
  merge skips the node and logs a warning (see Diff and Merge).
- The caller gives the write time before the query waits for the lock, so that delete can have a later time than
  the write. The check also refuses the write when the node has a `deleted` `IS_PART_OF` edge after `$at`, on a
  branch that the branch of the query reads at `$at`. An isolated branch reads its origin branch at the start of the
  branch, so a later delete on the origin branch does not stop a write on the branch. The query does not read the
  time after the lock, because each caller gives the time that its other writes use: the merge writes at the merge
  time, and a save writes the owners at the time of its other fields.
- `verify_graph` reports an open owner edge on a deleted attribute (`GraphCheck.ORPHANED_ACTIVE_EDGES`). It does not
  report a `HAS_OWNER` edge from a `Node`, `Attribute` or `OwnerSet` vertex, or a `HAS_SOURCE` edge from a `Node`
  vertex, to a deleted node, also when a write adds the edge after the delete, because a copy of a list keeps a
  deleted owner. It reports such an edge from a `Relationship` vertex, and a `HAS_SOURCE` edge from an `Attribute`
  vertex, when a write adds it after the delete (`GraphCheck.EDGES_AFTER_NODE_DELETE`): the merge does not copy a
  `HAS_SOURCE` edge of an attribute to a deleted node.
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
`deleted` edge for an edge that the branch inherits. The write branch of the owner edges of a branch-aware attribute
is the branch of the query, as for a write, also when the node is branch-agnostic. A branch-agnostic attribute of a
branch-aware node uses the branch of the node, so its global owner edges stay open until the retirement of the
branch-agnostic fields closes them. This is one more write query for each deleted node.
After the lock, the query reads no holder when the node, its attributes and its sets have no owner edge, no source
edge and no template mark, and no `HAS_OWNER_SOURCE` edge ends at the node. This check reads the edges on all
branches and at all times, so a closed edge also makes the query read the holders.

## Owner Kinds

- An owner is an account or an account group (`OWNER_KINDS` in `core/ownership/input.py`). A repository is refused.
- No code checks the kind of a source.
- The create and the update of a node check the `owner` property of each attribute and of each link before the first
  write (`check_field_owner_kinds`), so a refused owner leaves the node unchanged also outside a transaction. The
  update checks only an owner that the database does not hold yet, so an owner that was deleted later does not stop
  the update. To compare a link with the database, the update first resolves the peers of each relationship that has
  a link with an owner. So a resource pool gives the peer before the check, as in the GraphQL mutations, which
  resolve all peers before the save. An owner of another kind, or an owner that does not exist, raises `ValidationError` with the path of
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
- A change of the rules must reach three places: `core/ownership/resolution.py`, `_needed`, and the walk. The
  first two give the result. A filter on the owner list must give the same result. The walk only
  reads ahead: it copies the rules so that one query reads all the nodes. When the walk misses a node that the
  rules need, `_needed` reads that node with one more query, so a walk that does not follow a change of the rules
  costs queries but does not change the result.

The owners that apply to a node come from the first level that has a state:

1. The own state of the node (`origin: SELF`).
2. Its profiles, in the order of `profile_priority`, then profile ID: the first profile that gives owners or
   "no owner" (`PROFILE`).
3. The copy from its object template (`TEMPLATE`).
4. Its parent, with the same order on the parent (`PARENT`). The parent is the peer of the relationship of kind
   `Parent`, otherwise the peer of the hierarchy relationship `parent`.

The resolver does not resolve the owners that apply to a field, or the owners that a profile or an object template
gives.

- The walk stops after `MAX_INHERITANCE_DEPTH` parents. A node with more parents and no state below the limit
  gets no inherited owner.
- A deleted owner stays in the list.
- `state` is always what the item itself stores, whatever the origin of the owners that apply.

## Diff and Merge

Each holder is one property of the diff, and its value is the sorted list of owner IDs. The reserved field names of
the holders that are not attributes are in `core/ownership/fields.py` (see [Diff Conflicts](diff-conflicts.md)).

- `DiffOwnerHoldersQuery` (`core/diff/query/ownership.py`) lists the holders whose owner edges changed on a branch.
  A kind migration links the old and the new `Node` vertex of a UUID to the same attribute or set. So the query keeps
  the row of the vertex whose `HAS_ATTRIBUTE`, `HAS_OWNER_SET` or `HAS_TARGET_OWNER_SET` link to the holder is the
  latest on the queried branch. The kind migration copies the owner edges and the source edges of the node to the
  new vertex, so for these holders the query keeps the row of the vertex whose `IS_PART_OF` edge is the latest on
  the queried branch. So the diff gives one node for each UUID. The query skips the `HAS_OWNER` edges to a
  repository: from the upgrade (`m085`), the reads hide a repository owner, so these edges give no change on any
  branch.
- `OwnershipDiffer` (`core/diff/ownership_differ.py`) takes the field name of a set or of a node holder from the
  schema of the diff branch. For a change of the base branch, it uses the schema of the base branch when the schema
  of the diff branch does not have the kind. So after a kind migration on the base branch, different owner changes on
  both branches still give a conflict.
- `BulkMergeOwnershipEdgesQuery` (`core/diff/query/bulk_merge.py`) copies the owner edges of the branch as a set for
  each holder, edge type and owner. It writes the edges of a node to the `Node` vertex that is active on the target
  branch, which a kind migration on the target branch replaces. A `deleted` edge of the branch from a `Node` vertex
  closes the active edge on each `Node` vertex of the UUID.
- `ConflictsEnricher._have_same_value` (`core/diff/conflicts_enricher.py`) gives no conflict for an owner list or a
  source list with the same owner IDs on both branches, or with an update that keeps the same list.
- `core/graph/index.py` has a range index on `branch`, on `from` and on `to` of each of `HAS_NO_OWNER`,
  `HAS_OWNER_SOURCE`, `HAS_OWNER_SET` and `HAS_TARGET_OWNER_SET`. The diff and the merge read these edges by branch,
  and the `from` and `to` indexes serve a read of the edges that changed in a time window. The server creates each
  missing index when it starts, so they need no migration.
- `OwnerDiffResolution` (`core/diff/merger/exclusion_plan.py`) is a holder whose owner conflict the branch side won.
  `DiffMerger._apply_owner_diff_resolutions` (`core/diff/merger/merger.py`) then writes the list of the branch on the
  holder, with `keep_deleted_owners` and `skip_inactive`. When the node is not active on the target branch, the merge
  skips the holder and logs a warning.

## Schema Changes and Kind Changes

- The kind migration (`core/migrations/query/node_duplicate.py`) copies each edge type between the node and each
  other vertex, so the owner edges and the source edges follow the node.
- A rename or a removal of an attribute, and a removal of a relationship, close or move the `OwnerSet` vertices with
  that key (`OwnerSetKeyMigrationQuery`). The key is a vertex property that all branches share, so a rename gives the
  branch an edge to another set and changes no key. For an attribute of a generic, the query also reads the
  profiles and the templates of each kind that inherits the attribute (`profile_and_template_kinds`). It skips the
  template of a kind that declares its own attribute with the same name, because that template also has the label of
  the template of the generic.
  The query ends an edge of the branch of the migration. An edge of another branch, the global branch included,
  stays open and gets a `deleted` edge on the branch of the migration, as `AttributeRemoveQuery` does. So a branch
  with the schema before the change still reads the owners of the field. For a rename on the default branch, the
  new set of a branch-agnostic node gets its edges on the global branch, where a write of owners can replace them.
  On another branch, the new set gets its edges on that branch until the merge runs the migration on the default
  branch.
- The removal of a kind (`core/migrations/schema/node_remove.py`) closes the owner edges and the source edges that
  start at each node of the kind, at its attributes and at its `OwnerSet` vertices. For the edges that end at a node
  of the kind, it does what a delete of the node does: it closes each `HAS_OWNER_SOURCE` edge, and the `HAS_OWNER`
  and `HAS_SOURCE` edges from a node, an attribute or an `OwnerSet` stay, so a removed owner or source stays in the
  list. It closes the `HAS_OWNER` and `HAS_SOURCE` edges from a `Relationship` vertex.
- The attribute rename (`AttributeRenameQuery`) copies each edge type between the attribute and each other vertex,
  so an attribute keeps a source and an owner that are the same node.
- The attribute removal (`AttributeRemoveQuery`) ends each edge type between the attribute and each other vertex,
  so it ends a source and an owner that are the same node.
  On a branch, the query cannot read an owner that the default branch gave to the attribute after the start of the
  branch. So the merge of a deleted `HAS_ATTRIBUTE` edge closes each active owner edge of the attribute on the
  default branch (`BulkMergeNodeExistenceQuery`). An attribute that a kind migration of the branch moved to
  another `Node` vertex keeps its owners.
- The object conversion (`convert_object_type`) reads the owner states of the node in the transaction of the
  conversion, before the delete, and writes them on the new node. It takes the lock on the node (`NodeLockQuery`)
  before the read, so it also reads an owner write that commits while the conversion waits for the lock. The owners of an attribute or of a relationship go
  to each field of the new kind that the mapping fills from it. A field that the mapping fills with a value or with
  the default gets no owner state. The owners of a relationship that fills no field of the new kind are not copied.
  The conversion does not copy the `HAS_OWNER_SOURCE` mark, because the object template is of the old kind. So the
  new node reads the owners of a template copy as its own owners: the state `OWNERS` with the origin `SELF`, as
  after the delete of the template.

## Upgrade

| Migration | What it does |
|---|---|
| `m084` | Adds a `deleted` edge for each attribute owner of the default branch that a branch replaced, also when the default branch closed the owner edge after the start of the branch. The `deleted` edge starts at the first edge of the branch to another owner, so a read at a time between two owner writes of the branch gives one owner |
| `m085` | Closes the `HAS_OWNER` edges from attributes to repositories, on every branch. A branch still reads an edge of the default branch that was open at the start of the branch, so the migration adds a `deleted` edge for it on the branch, at the time of the upgrade. For such an edge of the global branch, the `deleted` edge goes on the global branch, as a write of owners on the global branch does. It deletes nothing, and prints the number of closed edges for each repository |
| `m086` | Creates the `NoOwner` vertex |

`infrahub db ownership-report` (`core/ownership/report.py`) reads only vertices and edges that the release before
holds, so it runs before the upgrade. When the graph version of the database is the number of `m085` or later, the
command first prints a warning: `m085` closed the owner edges from attributes to repositories, so the first section is
empty.

## Limits

- The diff and the merge of owners read branch-aware nodes, and the branch-aware attributes of all nodes. The owners
  of a relationship field (`FIELD_SET`) follow the branch support of the node, not of the relationship.
- Outside a transaction, a pool allocation for the peer of a link with an owner stays when the owner kind check
  then refuses the owner. The update resolves the peers of a relationship before the check, to compare each link
  with the database.
- The upgrade ends only the attribute owners that are repositories (`m085`). An attribute owner of another kind that
  is not an account or an account group stays readable. `infrahub db ownership-report` lists them, by kind, before
  the upgrade.
- Two transactions that write the same nodes in a different order deadlock, on every branch, because each one
  locks the nodes in its own order (see "Order of the nodes"). Only the cascade of `NodeManager.delete`, the profile
  refresh and the IPAM reconciler sort their nodes.
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
- A rebase stops on a conflict of owners or sources until both branches hold the same list. See
  [Diff Conflicts](diff-conflicts.md).
- The diff shows a holder that lost only its `HAS_OWNER_SOURCE` mark as an update with the same list at both ends.
  It cannot show that the origin of the owners changed from `TEMPLATE` to `SELF`.
  `DiffCombiner` compares only the owner IDs when it combines two diffs of one branch. So when the mark alone
  changes between the start of the first diff and the end of the second diff, and the owner IDs end the same, the
  combined diff shows no change, while a full diff of the same time range shows an update. The merge copies the
  edges of the branch, not the values of the diff, so the merge result does not change.
- An event stores the owners of an attribute as the `owner` or the `owners` property of the attribute, in its payload
  only.
- The owner of one link (the `HAS_OWNER` edge of a `Relationship` vertex) keeps the behavior before owner lists at a merge.
  Three tests in `test_ownership_scenarios.py` mark these cases as expected failures:
  - The changelog of the merge records the owner of a link also when the default branch already holds the same
    owner, for example after the same change on both branches.
  - The changelog of the merge records the branch value of a link owner when the conflict selects the default
    branch.
  - The merge does not copy the `HAS_OWNER` edge of a link to a deleted owner. The default branch then reads no
    owner on the link, and the branch reads the deleted owner.
- The global edges of an `OwnerSet` that a schema change hides never close. The retirement of branch-agnostic data
  (`core/query/agnostic_retention.py`) reads only `Attribute` and `Relationship` vertices.
- A `HAS_OWNER_SOURCE` edge of the global branch stays open after the delete of a branch-aware object template.
  This is the mark of a branch-agnostic attribute of a branch-aware node. Its owners still read as a copy from the
  template.
- On a branch other than the default branch, an owner write does not change `updated_at` and `updated_by` on the
  node vertex. The vertex holds them for the default and the global branch only.
- The merge of a change of the owners of a node, of a relationship field or of a profile or object template target,
  or of the sources of a node, with no other change of the node, does not change `updated_at` and `updated_by` on
  the node vertex. `DiffMergeMetadataQuery` reads them only from the attributes and the relationships that have an
  edge at the time of the merge, and the owner resolution of a merge does not record them. A change of the owners of
  an attribute changes them, because the attribute has an owner edge at the time of the merge.
- After a rename of an attribute on a branch other than the default branch, a write of owners on that branch cannot
  replace the owners that a branch-agnostic profile or object template gives to the attribute. The write goes to
  the global branch and the copy of the rename is on the branch.
- A branch made before a rename of an attribute on the default branch reads the owners that a branch-agnostic
  profile or object template gives under the old name and under the new name. A branch reads the global edges at its
  start and at the current time, and the old set and the new set are two vertices. No code of this release that
  maps a holder to a field shows the new name on that branch, because the schema of the branch does not have it.
- The removal of a relationship closes only the sets whose key is the identifier of the relationship. The own set of
  the relationship on a profile or on an object template has the key `profile_<identifier>` or
  `template_<identifier>`, so it stays open. No code of this release writes such a set, and no API reads it.
- When a branch changes the kind of a node (a kind migration) and then merges, the default branch loses the owner
  changes of the node and the relationship changes that it made on the old `Node` vertex after the start of the
  branch. Three causes are older than the owner model: the kind migration copies only the open edges
  (`NodeDuplicateQuery`), the merge does not move the edges of the default branch to the new vertex, and
  `ConflictsEnricher` keys the nodes by UUID. The owners of an attribute are not affected, because the old and the
  new vertex share the attribute. `test_source_branch_migration.py` marks the node owner case as an expected
  failure.

## Key Files

| File | Content |
|---|---|
| `core/ownership/models.py` | Holders, states and the resolved result |
| `core/ownership/constants.py` | The depth limit, the node limit of the walk and the ID of the `NoOwner` vertex |
| `core/ownership/queries.py` | The read query, the write query and the close query |
| `core/ownership/repository.py` | `OwnershipRepository`: the reads and writes as one branch does them |
| `core/ownership/resolver.py`, `resolution.py` | The owners that apply |
| `core/ownership/sources.py` | The source edges |
| `core/ownership/input.py` | The kinds that can be an owner, and the checks of owner references |
| `core/ownership/writer.py` | `OwnershipWriter`: the write of one holder of a saved node |
| `core/ownership/fields.py` | The reserved field names in both directions, the value and the labels of an owner list, for the changelog and the diff |
| `core/ownership/report.py` | The data of `infrahub db ownership-report` |
| `core/diff/ownership_differ.py`, `core/diff/query/ownership.py` | The owner lists in the diff |
| `core/diff/query/bulk_merge.py` | `BulkMergeOwnershipEdgesQuery`: the merge of the owner edges |
| `core/diff/conflicts_enricher.py` | `ConflictsEnricher._have_same_value`: no conflict for the same owner list |
| `core/diff/merger/exclusion_plan.py`, `core/diff/merger/merger.py` | `OwnerDiffResolution` and `DiffMerger._apply_owner_diff_resolutions`: the owner conflicts that the branch side won |
| `core/migrations/query/owner_set_attribute.py` | `OwnerSetKeyMigrationQuery`: the `OwnerSet` keys at a rename or a removal of a field |
