# Internal Contract: `SchemaPlanner`

**Module**: `backend/infrahub/graph_traversal/planning/planner.py`
**Plan**: [../plan-schema-planning.md](../plan-schema-planning.md)
**Data model**: [../data-model-schema-planning.md](../data-model-schema-planning.md)

Internal API consumed exclusively by the GraphQL resolvers in `backend/infrahub/graphql/queries/path.py` and `backend/infrahub/graphql/queries/reachable.py` (which then hand the `Plan` to the Query classes). Not exposed via GraphQL, REST, or SDK.

## Surface

```text
class SchemaPlanner:
    def __init__(
        self,
        *,
        schema_branch: SchemaBranch,
        branch: Branch,
        permission_resolver: PermissionResolver,
    ) -> None: ...

    def plan(
        self,
        *,
        source_kind: str,
        terminal_predicate: TerminalPredicate,
        max_depth: int,
        user_filters: UserFilters,
    ) -> Plan: ...
```

The planner is fully synchronous from the outside: every dependency (schema view, branch, permission resolver) is injected at construction time. `plan()` is callable any number of times.

The caller is responsible for building the `PermissionResolver` before constructing the planner. This is one `await PermissionLoader.load(...)` followed by `PermissionResolver(permissions=..., default_branch_name=...)` — see the Caller Contract below.

`KindPermissionCache` is built internally by `__init__` from the injected resolver and is not part of the planner's public surface; callers neither construct nor pass it.

## Inputs

### `__init__` (constructor) — synchronous

| Parameter | Purpose | Validation |
|---|---|---|
| `schema_branch` | The schema view for the request's branch at the requested time. Obtained via `db.schema.get_schema_branch(branch=branch)` (or equivalent) in the caller before the planner is built. | Must be a populated `SchemaBranch`. |
| `branch` | Branch context. Used by the internal `KindPermissionCache` to pick the right `PermissionDecisionFlag` value (`ALLOW_DEFAULT` vs `ALLOW_OTHER`). | Must exist on `db.schema`. |
| `permission_resolver` | A pre-built `PermissionResolver` carrying the requester's loaded permissions, scoped to `branch`. The caller builds this via `PermissionLoader.load(...)` followed by `PermissionResolver(permissions=..., default_branch_name=...)`. | Must be a populated `PermissionResolver`. |

`__init__` constructs the internal `KindPermissionCache(resolver=..., branch=..., schema_branch=...)` eagerly. No I/O occurs; the resolver's permissions were already loaded by the caller.

Per-kind lookups (during `plan()`) go directly through the `schema_branch` API:

- Relationships on a concrete kind: `schema_branch.get_node(name=kind, duplicate=False).relationships`.
- Concrete kinds implementing a generic: `schema_branch.get_generic(name=kind, duplicate=False).used_by` (a direct reverse index — no `get_all()` pass is performed).
- Kind namespace: `schema_branch.get(name=kind, duplicate=False).namespace`.

The planner MAY memoize results of these lookups on the instance. The cache is bounded by the subset of kinds reachable from `source_kind` within `max_depth`, not by the whole schema. All caches are discarded when the planner instance goes out of scope.

### `plan` — synchronous

| Parameter | Purpose | Validation |
|---|---|---|
| `source_kind` | Starting kind. | Must exist in the schema view; otherwise raise `ValueError("source kind not in schema")`. |
| `terminal_predicate` | `TerminalById` or `TerminalByKinds`. | `TerminalById.node_id` is a UUID string; `TerminalByKinds.kinds` is non-empty and every kind exists in the schema view. |
| `max_depth` | Cap on path length. | `1 ≤ max_depth ≤ 20`. Raise `ValueError` otherwise. |
| `user_filters` | Plan-level filtering. | See [data-model-schema-planning.md §UserFilters](../data-model-schema-planning.md#userfilters). |

## Output

A `Plan` as defined in the data model. Always returned (never raises for "no path found" — `plan.is_empty` is the legitimate signal).

## Behavior — required

1. **Source permission gate**: validate `max_depth`, `source_kind`, and (for both terminal-predicate variants) terminal kinds exist in `schema_branch`. Then check `permission_cache.can_view(source_kind)` — if denied, return a `Plan` with empty `adjacency` without running BFS. Every viable path would start at the source, so a forbidden source has no possible plan.
2. **Forward BFS with inline pruning**: iteratively expand from `source_kind` kind-by-kind up to `max_depth`. For each candidate hop `(current_kind, identifier, peer_kind)` the planner evaluates the following filters in order and drops the hop (no entry in the forward adjacency, no frontier extension) on the first violation:
   - **Permission**: `permission_cache.can_view(peer_kind)` must be `True`. The cache memoizes per kind, so repeated checks are O(1).
   - **`excluded_kinds`**: peer must not be in the set. No exemption.
   - **`excluded_namespaces`**: `schema_branch.get(peer_kind).namespace` must not be in the set. No exemption.
   - **`relationship_filter`**: when non-empty, the hop's `relationship_identifier` must be in the set. No exemption.
   - **`kind_filter`**: when non-empty, the peer must be in the set OR match the terminal predicate. A peer that matches the terminal predicate but is not in the filter is *recorded as a hop* (terminal exemption) but is not extended (it would become an intermediate of any longer path, which the filter forbids).

   Cycles are bounded by `max_depth` alone; kinds may repeat in the adjacency. The rendered Cypher's QPP only enforces per-hop legality from the adjacency map and cannot enforce schema-uniqueness on the matched path, so planner-side revisit pruning would be invisible to query results.

3. **Schema walking**:
   - For each candidate `peer_kind`, enumerate all `RelationshipSchema` on the current kind whose `peer` matches the candidate, expanding generic peers to concrete inheritors.
   - Direction (`OUTBOUND`/`INBOUND`/`BIDIR`) is not tracked in the plan output: the Cypher renderer uses undirected QPP arrows, so direction has no downstream consumer.
   - Schema-walking is bidirectional: a `RelationshipSchema` declared on kind A with peer B is considered traversable from A→B *and* from B→A during enumeration (the reverse walk is sourced from the inverse index).
4. **Generic expansion**: A `RelationshipSchema` whose `peer` is a generic is expanded to one `(start, identifier, concrete_peer)` hop per concrete implementor before filter/permission checks. The generic kind itself never appears as an `end_kind` in the adjacency.
5. **Terminal back-pass and depth bound**: after forward BFS, walk the forward adjacency backwards from terminal-matching `end_kind`s to compute `min_depth_to_terminal` for every reachable kind. Then keep only edges `(s, r, e)` where `min_depth_from_source[s] + 1 + min_depth_to_terminal[e] ≤ max_depth`. This is the tightening pass that matches the route-based planner's output exactly: only hops on some viable ≤`max_depth` source→terminal path appear in the final adjacency.
   - For `TerminalById`: an `end_kind` matches the terminal iff it equals `TerminalById.kind`. The caller resolves the destination's kind once via `NodeManager.get_one(...).get_kind()` and passes it on the predicate so the planner does not need to load the destination node.
   - For `TerminalByKinds`: an `end_kind` matches the terminal iff it is in `kinds`.
6. **Determinism (FR-016)**: when assembling the final adjacency, iterate `start_kind`s in sorted order and `relationship_identifier`s in sorted order; each inner `frozenset[str]` of `end_kind`s is converted to a sorted list at Cypher render time. Cache builds iterate `schema_branch.nodes` in sorted order so the inverse-relationship index is deterministic.
7. **Diagnostic logging**: emit one `traversal_plan_computed` INFO event per call recording the adjacency size; emit `traversal_plan_hop` DEBUG events per `(start_kind, rel, end_kind)` triple if and only if DEBUG is enabled. Fields per spec FR-014.

**No pruned-hop accounting**: the planner does not record what was dropped. Because filter and permission checks run during BFS expansion, an excluded subtree's would-be hops are never constructed in the first place — there's nothing to report. The `Plan` carries only the surviving `adjacency` plus the input echo (`source_kind`, `terminal_predicate`, `max_depth`).

## Behavior — forbidden

- Must not perform any data-graph reads (no `MATCH (n:Node {uuid: ...})` calls inside the planner). Permission and schema lookups only.
- Must not mutate any input. Must not mutate any cache outside its own instance.
- Must not include object UUIDs in log fields (Constitution VI).
- Must not emit or import any Cypher-generation code (separation of concerns — the Query class owns Cypher).

## Caller Contract

The **GraphQL resolver** orchestrates planning and only constructs the `Query` if a non-empty plan exists. The Query class is a pure consumer of an already-built `Plan` — it does not call the planner. This eliminates pointless Cypher execution (FR-004) at a single, clean control point.

```python
# backend/infrahub/graphql/queries/path.py — top-of-file imports
from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.graph_traversal.path import PathTraversalQuery
from infrahub.graph_traversal.planning import (
    SchemaPlanner,
    TerminalById,
    UserFilters,
)
from infrahub.permissions.loader import PermissionLoader
from infrahub.permissions.resolver import PermissionResolver

async def path_traversal_resolver(root, info, data):
    graphql_context = info.context
    db, branch, at = graphql_context.db, graphql_context.branch, graphql_context.at

    # 1. Resolve source/destination objects and their kinds
    source = await NodeManager.get_one(db=db, branch=branch, at=at, id=data.source_id)
    destination = await NodeManager.get_one(db=db, branch=branch, at=at, id=data.destination_id)
    # (existence/identity errors handled here, same as today)

    # 2. Build the permission resolver and the planner.
    #    The caller does the one `await` on the permission load itself, so the
    #    planner can stay fully synchronous after construction.
    permissions = await PermissionLoader(account_session=graphql_context.account_session).load(
        db=db, branch=branch,
    )
    resolver = PermissionResolver(
        permissions=permissions,
        default_branch_name=registry.default_branch,
    )
    planner = SchemaPlanner(
        schema_branch=db.schema.get_schema_branch(branch=branch),
        branch=branch,
        permission_resolver=resolver,
    )
    plan = planner.plan(
        source_kind=source.get_kind(),
        terminal_predicate=TerminalById(node_id=data.destination_id, kind=destination.get_kind()),
        max_depth=data.max_depth or 5,
        user_filters=UserFilters.from_graphql_input(data),
    )

    # 3. Short-circuit at the caller level. No pointless Query.execute().
    if plan.is_empty:
        return _empty_result(source=source, destination=destination)

    # 4. Construct and execute the Query with the plan
    query = PathTraversalQuery(
        plan=plan,
        source_id=data.source_id,
        branch=branch,
        at=at,
        max_paths=data.max_paths or 10,
    )
    await query.execute(db=db)
    return _shape_result(query=query, source=source, destination=destination)
```

The Query class itself becomes minimal:

```python
# backend/infrahub/graph_traversal/path.py — top-of-file imports
from infrahub.core.query import Query
from infrahub.graph_traversal._cypher import render_plan_to_cypher
from infrahub.graph_traversal.planning import Plan, TerminalById

class PathTraversalQuery(Query):
    def __init__(self, *, plan: Plan, source_id: str, branch: Branch, at: Timestamp, max_paths: int):
        if plan.is_empty:
            raise ValueError("PathTraversalQuery requires a non-empty plan; caller must short-circuit upstream")
        self.plan = plan
        self.source_id = source_id
        self.branch = branch
        self.at = at
        self.max_paths = max_paths
        super().__init__(...)

    def query_init(self, ...):
        max_results = self.max_paths if isinstance(self.plan.terminal_predicate, TerminalById) else self.max_results
        rendered = render_plan_to_cypher(
            plan=self.plan,
            source_id=self.source_id,
            branch=self.branch,
            at=self.at,
            max_results=max_results,
        )
        self.query_lines = [rendered.text]
        self.params.update(rendered.params)
        self.return_labels = list(rendered.return_labels)
```

Responsibilities:

1. **GraphQL resolver** resolves source/destination objects and their kinds via `NodeManager.get_one(...)`. Same existence-error handling as today.
2. **GraphQL resolver** builds the `PermissionResolver` (`PermissionLoader.load(...)` → `PermissionResolver(...)`), constructs the `SchemaPlanner` with it, and calls `plan()`. It then constructs `TerminalById(node_id=destination_id, kind=destination_kind)` so the planner can match terminal kind without re-loading the destination node.
3. **GraphQL resolver** is responsible for the empty-plan short-circuit (FR-004): if `plan.is_empty`, return an empty GraphQL result without instantiating or executing the Query class. No pointless Cypher reaches the database.
4. **GraphQL resolver** authorizes the source object via `NodeManager.get_one` (existing behavior). The planner does its own `can_view` pass over every kind in the adjacency — including the source — and the cache makes the duplication trivially cheap.
5. **Query class** takes a non-empty `Plan` in `__init__` and emits Cypher in `query_init` via `render_plan_to_cypher`. It does not call the planner. It does not contain a short-circuit path. Module-top imports only — no in-function imports.
6. **Planner package** must not import or call anything from `graph_traversal/_cypher.py`; **Query class** must not import or call anything from `graph_traversal/planning/`'s planner (the data models are fine to import — `Plan`, `TerminalPredicate`).

## Errors

| Condition | Behavior |
|---|---|
| `source_kind` not in schema | Raise `ValueError`; caller surfaces as `GraphQLError`. |
| `max_depth` out of bounds | Raise `ValueError`. |
| Terminal kind not in schema (for `TerminalByKinds` or `TerminalById`) | Raise `ValueError`. |
| No viable hops after all pruning | Return `Plan` with empty `adjacency`. Not an error. |
| Permission resolver fails to load (in the caller, before construction) | Caller's exception; planner never reached. |

## Tests required

- `test_planner.py`
  - Empty adjacency when source and target kinds are disconnected at the schema level.
  - Generic expansion produces one `(start, identifier, concrete_inheritor)` hop per concrete kind.
  - `max_depth` cap respected (no hop appears in the adjacency that can't be on a ≤`max_depth` source→terminal path).
  - `excluded_namespaces` defaults applied when input is `None`.
  - Adjacency is deterministic across two invocations with identical inputs.
- `test_permissions_filter.py`
  - Hops through a forbidden intermediate are excluded.
  - Adjacency retained when alternate hops avoid the forbidden kind.
  - A forbidden source kind short-circuits the whole plan (empty `Plan.adjacency`).
  - A forbidden terminal kind drops the only paths through it.
- All tests use schema fixtures only; no DB required.

The planner doesn't expose what was pruned — filter and permission checks happen during BFS expansion (see [Behavior — required](#behavior--required)), so dropped subtrees are never enumerated. Tests assert on `plan.adjacency` only.
