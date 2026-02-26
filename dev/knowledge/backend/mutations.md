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
       -> preview node (process_pools=False) for lock calculation
       -> acquire InfrahubMultiLock
       -> _do_create_node()
            -> NodeCreationContext     # tracks side-effect nodes for events
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
            -> handle_template_relationships()  # recursive template instantiation
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
                      -> recompute HFID/display_label if needs_update()
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

## Relationship Resolution During Mutations

### RelationshipManager.update()

**Location:** `backend/infrahub/core/relationship/model.py`

When updating relationships, the manager compares new data against existing relationships:

1. Fetch current relationships from DB -> `previous_relationships` dict (keyed by `peer_id`)
2. Clear `_relationships` list
3. For each new item:
   - **UUID match** (string or dict with `"id"`): Reuse existing `Relationship` object from `previous_relationships`
   - **No match** (HFID, default_filter, new UUID): Create new `Relationship` via `.new()`
4. Mark as changed if the set of peers differs

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

## Locking Strategy

1. A preview node is created with `process_pools=False` (no side effects)
2. Lock names are computed from uniqueness constraints and resource pool fields
3. `InfrahubMultiLock` acquired before the transaction
4. Actual mutation runs inside the lock

## Key Files

| File | What |
|------|------|
| `graphql/mutations/main.py` | Mutation dispatcher, create/update/upsert/delete |
| `core/node/__init__.py` | `Node.new()`, `load()`, `from_graphql()`, `_create()`, `_update()`, `save()` |
| `core/node/create.py` | `create_node()`, `_do_create_node()`, template relationship handling |
| `core/relationship/model.py` | `RelationshipManager.update()`, `resolve()`, `save()` |
| `core/constraint/node/runner.py` | `NodeConstraintRunner` for uniqueness/constraint checks |
| `core/query/node.py` | `NodeCreateAllQuery` and other DB queries |
