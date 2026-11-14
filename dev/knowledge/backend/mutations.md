# Mutations

> Part of: `dev/knowledge/backend/` | Related: [display-labels-and-hfid.md](display-labels-and-hfid.md), [architecture.md](architecture.md)

GraphQL mutations for creating, updating, upserting, and deleting nodes. All mutations are transaction-wrapped and use locking for constraint safety.

## Mutation Dispatch

**Location:** `backend/infrahub/graphql/mutations/main.py`

`InfrahubMutationMixin.mutate()` dispatches based on class name:

| Suffix | Method | Flow |
|--------|--------|------|
| `Create` | `mutate_create()` | `create_node()` -> `Node.new()` -> `Node.save()` |
| `Update` | `mutate_update()` | `Node.load()` -> `Node.from_graphql()` -> `Node.save()` |
| `Upsert` | `mutate_upsert()` | Find-or-create, then create or update path |
| `Delete` | `mutate_delete()` | Load -> delete |

## Create Flow

```
mutate_create()
  -> create_node()                    # create.py
       -> preview node (process_pools=False) for lock calculation, with the id of the node to create
       -> read_template_components()   # template only: the subtemplates, read a level at a time
       -> get_template_pool_lock_names()  # template only: the pool locks of the object and its components
       -> acquire InfrahubMultiLock
       -> _do_create_node()
            -> NodeMutationContext     # records the other nodes the mutation writes, for events
            -> Node.new()
                 -> _process_fields()  # validates, hydrates attrs & rels
                 -> _process_macros()  # evaluates mandatory computed attrs
            -> NodeConstraintRunner.check()
            -> Node.save()
                 -> resolve_relationships()  # loads peers with extra_filters
                 -> _create()
                      -> add_human_friendly_id()
                      -> add_display_label()
                      -> NodeCreateAllQuery  # bulk Neo4j insert
            -> create_components()  # template instantiation, created depth first
       -> apply profiles if applicable
  -> emit NodeCreatedEvent
```

## Update Flow

```
mutate_update()
  -> NodeManager.find_object()       # by id or hfid
  -> _call_mutate_update()
       -> preview object for lock calculation
       -> acquire InfrahubMultiLock
       -> mutate_update_object()
            -> Node.from_graphql()    # applies new data to loaded node
                 -> attribute.from_graphql()  # update attrs in-place
                 -> RelationshipManager.update()  # see below
            -> NodeConstraintRunner.check(updated fields only)
            -> Node.save(fields=[changed fields])
                 -> resolve_relationships()
                 -> _update()
                      -> attr.save() for each changed attribute
                      -> rel.save() for each changed relationship
                      -> _recompute_local_jinja2()  # Jinja2 computed attrs (dependency-ordered, skips on upstream failure)
                      -> _recompute_hfid()           # if needs_update()
                      -> _recompute_display_label()  # if needs_update()
  -> emit NodeUpdatedEvent
```

## Upsert Flow

```
mutate_upsert()
  -> identify node by (in priority order):
       1. "id" in data -> load by UUID
       2. default_filter (no HFID) -> MutationNodeGetterByDefaultFilter
       3. "hfid" in data -> load by human_friendly_id
  -> if found: _call_mutate_update()
  -> if not found:
       -> mutate_create()
       -> on HFIDViolatedError (concurrent create race):
            -> load node by ID from exception
            -> _call_mutate_update(skip_uniqueness_check=True)
            -> handle file idempotency (checksum comparison)
```

## Nodes a mutation writes besides its main node

Record each node the mutation writes outside the main node's save on the node the mutation returns,
with the action applied, so it gets its own event (see [Events](events.md#events-a-mutation-sends)):

- `create_node()` records template components and resource pool allocations itself.
- Any other write calls `Node.record_mutation_write(node, action)`, as the number pool and range
  mutations do for the ranges and the pool they write.

The records live on the returned node, so a retried attempt discards the records of a failed one
along with its node.

## Number pool values for existing nodes

A schema change that adds a NumberPool attribute, and the repair of missing number pool rows, give
existing nodes their numbers through `pools/existing_node_numbers.py`. It reads each node's division
with `NodeNumberPoolDivisionReader`, the reader the create path uses, so an existing node gets the
number a create would give it. It loads the nodes with only their id, the numbered attribute and the
fields that hold the pool's scope elements, so the peers of a relationship element are read once for
the whole set of nodes rather than once per node. The pre-load check that refuses a pool smaller than the kind's node
count skips scoped pools, because their limit applies to each division; the allocation raises when
one division runs out.

## Transaction Retry

`retry_db_transaction` (in `backend/infrahub/database/__init__.py`) replays the *entire* wrapped
function when Neo4j raises a `TransientError` — or a `ClientError` coded
`Neo.ClientError.Statement.EntityNotFound`. Its placement is therefore semantics-bearing, not
decoration:

- Wrap only a scope whose writes are fully contained in a transaction the retry can roll back. The
  create path is the trap: `create_node()` commits its own transaction and then does post-commit
  work (profiles, response reads), so a decorator on the whole mutation replays a commit that
  already succeeded and creates a duplicate node. The update path keeps its response build inside
  `db.start_transaction()`, which is what makes it replay-safe.
- Skip the retry when `db.is_transaction` — a caller-supplied transaction is already failed after a
  `TransientError`, and replaying inside it raises instead of recovering; the caller owns the retry.
- Check whether an already-retried caller reaches the code: nested retries multiply attempts.
  Upsert is the case to watch, and today it is safe — it reaches only the undecorated
  `mutate_create` and `_call_mutate_update`, never the decorated `mutate_update`, so it is the
  single retry point. Routing it through a decorated method would start multiplying attempts.

## Relationship Resolution During Mutations

### RelationshipManager.update()

**Location:** `backend/infrahub/core/relationship/model.py`

When updating relationships, the manager compares new data against existing relationships:

1. Fetch current relationships from DB -> `previous_relationships` dict (keyed by `peer_id`)
2. Clear `_relationships` list
3. For each new item:
   - **UUID match** (string or dict with `"id"`): Reuse existing `Relationship` object from `previous_relationships`. If that peer was sourced from a Profile, its source is cleared (`is_from_profile = False`, `clear_source()`) — see "Profile-sourced relationships" below.
   - **No match** (HFID, default_filter, new UUID): Create new `Relationship` via `.new()`
4. Mark as changed if the set of peers differs

### Profile-sourced relationships

A relationship's peers are all-or-nothing with respect to Profile sourcing: either every peer is sourced from a Profile or none are. Any user modification to a Profile-sourced relationship turns the whole relationship into a user-defined one, with the peers kept but their Profile source cleared:

- `RelationshipManager.update()` clears the source from reused peers (above), so an object update detaches the relationship from its Profile.
- The `RelationshipAdd` and `RelationshipRemove` GraphQL mutations call `_detach_relationship_from_profiles()` after a successful, modifying change to clear the source from the surviving peers. `_collect_current_peers()` requests `MetadataOptions.SOURCE` so those peers can be identified without re-reading the relationship. A failed or no-op mutation leaves the sourcing untouched (the detach runs inside the mutation transaction, after validation).

`NodeProfilesApplier` then treats such a relationship as user-defined and does not re-apply Profile peers to it.

### UUID vs HFID References

This distinction matters for display_label/HFID computation:

| Reference type | RelationshipManager.update() behavior | Peer data |
|----------------|---------------------------------------|-----------|
| UUID | Reuses old `Relationship` object | Peer already resolved with attributes |
| HFID / default_filter | Creates new `Relationship` object | Peer needs fresh resolution |

New `Relationship` objects require `resolve()` to load the peer. The `extra_filters` in `resolve_relationships()` ensure the peer's attributes needed by display_label/HFID templates are loaded during resolution.

### RelationshipManager.save()

After resolution, `save()` reconciles local state with the database:

- Peer in both local and DB: compare properties, update if different
- Peer only in local: create new relationship in DB
- Peer only in DB: delete orphaned relationship

### When the peers are read from the database

One mutation applies the payload, checks the constraints and saves, and each of those steps
compares the local relationships against the stored peers. The comparison is recomputed from the
peers the manager already read rather than reading them again:

- `fetch_relationship_ids()` reads the peers and records them; `refresh_update_details()` only
  recomputes the comparison, reading again when the manager has not read under the same conditions
  or has written to the relationship since. Any write through the manager discards the record.
- A node that has never been written is not read at all: it cannot have any relationship edge, and
  creating it writes the edges without going through the manager, so that answer is never recorded.
- A read with `prefetch_relationships` resolves every relationship in one query, so a relationship
  that came back without a peer is marked as read too. That read covers the relationships the
  schemas of the nodes declare, and `NodeManager.prefetch_relationships()` narrows it further to the
  relationships the caller names — reading a node's every edge would pull in the relationships that
  point *at* it, such as the objects created from an object template or the nodes using a profile.
- The peers of a prefetched relationship come back as nodes rather than ids, so a caller that
  prefetched walks them without reading them back. Applying an object template leans on this: each
  level of subtemplates arrives with the read of the level above it (see
  [Object Templates](templates.md)).

### The peers a mutation already holds

A payload names a peer by id, but a caller that already holds the peer can pass the node itself, and
the mutation then works from it rather than reading it back:

- the grouped uniqueness constraint asks the relationship for the peer id
  (`RelationshipManager.get_peer_id()`) and reads the peer only when it is named by a
  human-friendly id or a default filter value, which reading is the only way to resolve;
- the peer-kind constraint trusts the kind a peer states, and reads only the peers named by an id;
- the create query reads the peers of a relationship of cardinality many in one call, and only those
  held by id (`RelationshipManager.read_peers_not_in_hand()`); `Relationship.get_create_data()` then
  writes the edge from the peer it holds. Before that, the create query batched every peer of such a
  relationship through `get_peers()`, which reads whatever it is given — a component created from a
  template read back, once per component, a peer the template read had already brought back.

Passing a node keeps the rest of the payload for that relationship (its source, its owner) only if
the node replaces the `id` inside it rather than the payload itself.

## RelationshipAdd and RelationshipRemove

These mutations change one relationship of an existing node, so they refuse a change that would break the schema on either side of it:

| Refused when | Mutation |
|--------------|----------|
| the relationship is `read_only` | both |
| a peer is not of the relationship's peer kind | both |
| a peer is already linked to another node on a cardinality-one side of its own | both |
| the relationship is cardinality one and would receive more than one peer | `RelationshipAdd` |
| the peers do not share the parent named by `common_parent` | `RelationshipAdd` |
| the relationship is mandatory and would be left with no peer | `RelationshipRemove` |
| a removed peer's own side of the relationship (same identifier, mirrored direction) is mandatory with cardinality one, so the peer would be left without its peer | `RelationshipRemove` |

A peer that must keep its relationship, such as a component under a mandatory parent or a number pool range under its pool, therefore changes through a mutation on the peer itself: update its relationship to another node, or delete it.

## Locking Strategy

1. A preview node is created with `process_pools=False` (no side effects); a create gives it the id of
   the node it creates
2. Lock names are computed from uniqueness constraints and resource pool fields; for a create from a
   template they also include the pool locks of its components
3. `InfrahubMultiLock` acquired before the transaction
4. Actual mutation runs inside the lock

The update path builds its preview by reading the node and applying the payload through
`apply_payload_for_lock_names()`, which leaves the stored peers unread: the relationship lock names
come from the peers the payload sets. The node itself is still read, because the uniqueness
constraint hashes cover attributes the payload may not carry.

IP prefix and IP address mutations (`graphql/mutations/ipam.py`) take an IPAM lock before the
object locks, because the IPAM reconciliation that follows rewrites parent relationships:

- A prefix mutation locks its namespace, on every branch. Reconciling a prefix can move other
  prefixes and addresses under it.
- An IP address mutation on the default branch locks each address value it touches: one lock per
  namespace and host address, covering every prefix length of that host. An update locks the stored
  address and the address it has after the update, whose namespace and host each default to the
  stored ones. Reconciling an address writes only that address's own parent relationship, so
  mutations of different addresses do not wait for each other. On other branches an IP address
  mutation takes no IPAM lock, because reconciliation runs again at merge.

### Number pool locks

A change to a number pool's ranges and a write that checks a number against those ranges must not
overlap: otherwise the write can commit a number from a range the change just removed. Every such path
goes through the `NumberPoolLocker` protocol, which `NumberPoolLock` in `pools/number_pool_locker.py`
implements with two locks:

| Lock | Taken by | Mode |
|------|----------|------|
| `resource_pool.<pool id>` | range create, update and delete, pool delete, pool updates that send `start_range`, `end_range` or `ranges`, the schema-pool synchronizer's range, scope and deletion changes to existing pools, the schema migration that adds a NumberPool attribute | exclusive (`changing`) |
| `resource_pool.<pool id>` | allocation that picks a new number, attaching a supplied number, editing a tracked number | shared (`holding`) |
| `resource_pool.<pool id>.<division key>`, or `.all` without a scope | allocation, also in the mutation's lock names | mutex (`picking`) |

Pool create and update, and range create and update, also take `number_pool_target.<kind>.<attribute>`
before the pool's exclusive lock, so two pools on the same unique attribute cannot gain overlapping ranges
at the same time. Allocations never take it. Pool create takes only this lock: no other request can read
the new pool before its transaction commits, so no write can hold it.

- **Shared holders run in parallel.** Each one records an entry that expires, at
  `lock.shared.<lock name>.<holder id>`, adds its id to the set `lock.shared.<lock name>`, and renews
  the entry while it holds the lock, so allocations in different divisions never wait for each other.
  Checking for holders reads that set and the entries of the ids in it, and drops the ids whose entries
  expired.
- **A hold lasts until the commit.** Inside a transaction, `holding` and `changing` hand their release
  to `InfrahubDatabase.hold_until_transaction_end`, because a number or a range only becomes visible to
  other writes once it is committed. This also covers allocations that run inside a transaction outside
  the mutation lock, such as migrations.
- **An exclusive request waits for the shared holders.** It takes the mutex, so new shared requests
  queue behind it, then waits until no entry remains. After `INFRAHUB_CACHE_EXCLUSIVE_LOCK_WAIT_SECS`
  it releases the mutex and the range change fails with a retry message. The lock error, which names
  the setting, is logged as a warning, so that the API message does not name a server setting.
- **The division's lock comes before the pool's shared hold.** A write that holds the pool until its
  commit and then waits for a division's lock can wait on an allocation that is itself queued behind a
  range change, so allocations take `picking` first. A create from a template takes it before its
  transaction, with the exceptions listed in
  [Pool locks of a create from a template](#pool-locks-of-a-create-from-a-template).
- **A task that holds the pool exclusively skips `picking`.** Every other allocation picks inside its
  shared hold, so none can pick while the pool is held exclusively, and skipping the division's lock keeps
  the exclusive holder from waiting on an allocation that is itself queued behind it.
- **The schema migration that adds a NumberPool attribute holds the pool exclusively until its commit.**
  It allocates a number to every existing node in one transaction, and holds `changing` from before its
  first allocation until the commit, so that no other allocation picks a number the migration drew but
  has not committed yet, and no range changes under it. When writes still hold the pool after
  `INFRAHUB_CACHE_EXCLUSIVE_LOCK_WAIT_SECS`, the migration fails. The Prefect task that runs it retries it
  up to 3 times, and the schema update is rolled back only when the last attempt also fails. A kind with
  no nodes allocates nothing and takes no pool lock.
- **A dead worker makes range changes fail until its entry expires**, after
  `INFRAHUB_CACHE_SHARED_LOCK_TTL_SECS`.
- **An allocation that returns its identifier's reservation does not hold the pool.** The reserved
  number is already tracked, so the range check already counts it.
- **The schema-pool synchronizer locks only the pools it changes.** It runs on every schema load and
  every merge, so it first reads a pool's ranges and shorthand without the lock, and skips the pool when
  both match the declaration.
- **The schema-pool synchronizer reports a range change it could not apply** and moves on to the other
  pools; the flow raises the refusals once every pool was processed.
- **Not covered:** the IP prefix and IP address pool `GetResource` mutations run without a transaction,
  so a number drawn by the IP node they create is released before its write.

### Pool locks of a create from a template

A create from a template draws from pools inside its transaction: the pools the template names for the
object, and the pools its components draw from. The query that creates a node with a number that a
number pool tracks locks that pool's vertex in Neo4j until the commit, for every division. A write that
waits for a division's lock inside its transaction, after it wrote such a number, can therefore wait on
an allocation that holds that lock and itself waits for the vertex. Neither wait has a time limit, and
Neo4j does not detect the cycle. So `create_node()` adds the division locks and the IP pool locks of the
create to the mutation's lock names, which it takes before it opens its transaction; the allocations
inside the transaction take them again without waiting. The pool's shared hold is still taken inside the
transaction. The exceptions are listed below.

`get_template_pool_lock_names()` in `core/node/create.py` returns the names the preview of the object
does not already hold:

| Draws from | Object created from the template | Component created from a subtemplate |
|------------|----------------------------------|--------------------------------------|
| Number pool the template names, with a scope | preview of the object | `resource_pool.<pool id>.<division key>` |
| Number pool the template names, without a scope | `resource_pool.<pool id>.all` | `resource_pool.<pool id>.all` |
| `NumberPool` attribute of the schema | preview of the object | `resource_pool.<pool id>.<division key>`, or `.all` without a scope |
| IP address or IP prefix pool the template names | `resource_pool.<pool id>` | `resource_pool.<pool id>` |

- **Each pooled component is built twice.** `create_node()` builds an unsaved preview of each component
  that draws from a pool, and of each component above one, to read its division. A component draws from a
  pool when its subtemplate names one or its kind has a `NumberPool` attribute. A preview of a component in
  a scoped number pool reads the pool once more, and the peers or the profiles that hold a scope element
  when the preview does not hold them. A template whose components draw from no pool builds no preview.
- **The preview and the object created share one id.** `create_node()` generates the id of the object
  before it builds the preview, unless the payload sets one, and each `TemplateComponent` holds the id of
  the component it describes. So a lock name that holds the id of a new object, such as the division of a
  component whose scope names its new parent, or `relationship_count.<identifier>.<node id>`, names the
  object created. An id that `create_node()` generated is not checked against the database; an id the
  payload sets is.
- **The subtemplates are read before the locks, as the template is.** A subtemplate that another write
  changes or deletes while the create waits for a lock is applied as it was read.
- **A validation error of a component that draws from a pool, or holds one that does, is raised before the
  object's own checks**, because its preview is built before the locks. Other components are validated
  after them.
- **Not covered: a scope element that a pool fills.** When a pool fills a field that another pool's scope
  names, on the object or on a component, the preview reads that element as empty. The create takes the
  lock of that empty division (`.all` when the scope has one element), and takes the lock of the real
  division inside the transaction.
- **Not covered: an IP pool whose address or prefix kind has a `NumberPool` attribute.** The IP node is
  created inside the transaction, where it takes the lock of that number pool. A create that names the IP
  pool with `from_pool` on a relationship does the same.
- **Not covered: a caller that passes a database with a transaction already open.** `create_node()` then
  takes the locks inside that transaction.

`backend/tests/component/core/node/test_template_pool_lock_order.py` covers every cell of the table, a
nested component, a payload that sets the `id`, and a division that holds the object created.

## Key Files

| File | What |
|------|------|
| `graphql/mutations/main.py` | Mutation dispatcher, create/update/upsert/delete |
| `core/node/__init__.py` | `Node.new()`, `load()`, `from_graphql()`, `_create()`, `_update()`, `save()` |
| `core/node/create.py` | `create_node()`, `_do_create_node()`, `read_template_components()`, `get_template_pool_lock_names()`, `create_components()` |
| `core/node/lock_utils.py` | `get_lock_names_on_object_mutation()`, `get_pool_lock_names()`, `ip_pool_lock_name()` |
| `core/relationship/model.py` | `RelationshipManager.update()`, `resolve()`, `save()` |
| `core/constraint/node/runner.py` | `NodeConstraintRunner` for uniqueness/constraint checks |
| `core/query/node.py` | `NodeCreateAllQuery` and other DB queries |
