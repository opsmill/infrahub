# Query Pattern

> Part of: `dev/knowledge/backend/` | Related: [Architecture](architecture.md)

All database access in Infrahub goes through Query classes that encapsulate Cypher queries with proper parameterization, branch-awareness, and temporal versioning. Queries return typed dataclass results for type safety and clear API contracts.

## Query Lifecycle

### Initialization

```python
query = await MyQuery.init(db=db, branch=branch, **kwargs)
```

The `init()` classmethod calls `query_init()` for async initialization (schema lookups, etc.).

### Building

Queries are built by adding Cypher clauses:

```python
def __init__(self, node_id: str, **kwargs):
    super().__init__(**kwargs)
    self.params["node_id"] = node_id
    self.add_to_query("MATCH (n:Node { uuid: $node_id })")
    self.add_to_query("WHERE n.status = 'active'")
    self.add_to_query("RETURN n.uuid AS node_uuid, n.name AS node_name")
    self.update_return_labels(["node_uuid", "node_name"])
```

| Method | Purpose |
|--------|---------|
| `add_to_query(str)` | Append Cypher clause(s) |
| `add_subquery(str, alias)` | Wrap in `CALL (alias) { }` block |
| `update_return_labels(list)` | Add labels to RETURN clause |

### Execution

```python
await query.execute(db=db)

# Use typed results
for item in query.get_data():
    print(item.uuid)  # IDE autocomplete works
```

### Query Preview

Useful for debugging:

```python
query = await MyQuery.init(db=db, branch=branch, node_id="abc123")
print(query.get_query())  # Preview generated Cypher
print(query.get_query(var=True, inline=True))  # With variables substituted
await query.execute(db=db)  # Execute when ready
```

## Reads must not write

Neo4j routing is selected by the **database session**, not by `QueryType`: `db.start_session(read_only=True)` opens a session with `READ_ACCESS` (which a clustered deployment can route to any replica), while a normal session uses `WRITE_ACCESS` (the primary). `QueryType.READ` / `QueryType.WRITE` drives Query execution behavior and metrics, not server selection.

Because a read-shaped operation may run inside a read-only session, it must never write. This is a separate invariant that holds at every layer: a method named `get_*` (or any read-shaped accessor) must not create or mutate as a side effect — e.g. a `get_global()` that lazily materializes a missing row. Return a "not set" sentinel or `None`, and let the dedicated write path (a mutation, a `Repository.save`) be the only thing that creates.

## Core Patterns

### Query Naming

Each query must have a unique `name` attribute, using lowercase with dashes:

```python
class MyCustomQuery(Query):
    name = "my-custom-query"  # Unique, lowercase, dash-separated
    type = QueryType.READ
```

### Parameter Binding

All user input must be parameterized to prevent Cypher injection and enable query caching:

```python
# Good: Parameterized
self.params["uuid"] = user_provided_id
self.add_to_query("MATCH (n { uuid: $uuid })")

# Bad: String interpolation (security risk)
self.add_to_query(f"MATCH (n {{ uuid: '{user_provided_id}' }})")
```

### Keep Cypher readable inline

Readability of the raw query outranks deduplication. Do not extract repeated Cypher blocks into shared Python string-building helpers or fragment formatters just to avoid duplication — a query assembled from indirected fragments is much harder to read, review, and paste into a Neo4j console. Duplicating a few similar Cypher blocks inline is the accepted trade-off.

### Return Labels

The RETURN clause is automatically generated from `return_labels`. Call `update_return_labels()` to specify what to return.

**Never assign a shared module-level list to `return_labels`.** `update_return_labels()` *appends* to `self.return_labels`, so assigning a module-level constant (`self.return_labels = _RETURN_LABELS`) makes every instance mutate the same list and leak labels across queries. Assign a copy: `self.return_labels = list(_RETURN_LABELS)`.

**Important:** Only return the specific properties you need, not entire nodes or relationships. This reduces data transfer and memory usage.

```python
# Good: Return only needed properties
self.add_to_query("MATCH (n:Node)-[r:REL]->(p:Peer)")
self.add_to_query("RETURN n.uuid AS node_uuid, r.branch AS rel_branch, p.uuid AS peer_uuid")
self.update_return_labels(["node_uuid", "rel_branch", "peer_uuid"])

# Avoid: Returning entire nodes transfers unnecessary data
self.update_return_labels(["n", "r", "p"])  # Returns all properties of n, r, p
```

To write the RETURN clause directly in your query, set `insert_return = False`:

```python
class MyQuery(Query):
    name = "my-query"
    type = QueryType.READ
    insert_return = False  # Disable automatic RETURN generation

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_to_query("MATCH (n:Node)")
        self.add_to_query("RETURN n.uuid AS uuid, n.name AS name")  # Only needed properties
        self.updated_return_labels(["uuid", "name"])
```

### Pagination

Pagination (`LIMIT`/`OFFSET`) is automatically appended based on constructor parameters. Pass `limit` and `offset` through to `super().__init__()` — a subclass that keeps its own copies leaves the base `self.limit`/`self.offset` at `None`, and `execute()` reads those to decide how to run: with both unset it takes the `query_with_size_limit()` path, which re-runs the query in `query_size_limit` chunks with offsets of its own. The subclass then pages twice, against itself.

To write pagination directly in your query, set `insert_limit = False`:

> **List reads default to a page limit (e.g. `Branch.get_list` defaults to `limit=1000`).** Any check that must reason over *all* matching rows — "is any branch merging?", "are there duplicates?" — must not rely on an unbounded read of a default page. Narrow the query with a filter (a status/kind predicate) or paginate explicitly; otherwise the check silently ignores everything past the first page once the table grows.
>
> Two corollaries:
>
> - **Never derive a count with `len()` on a list read.** `len(Branch.get_list(...))` caps at the page limit and silently under-reports. Use the dedicated count method (`Branch.get_list_count`) or add one — a count query is also far cheaper than materializing the rows.
> - **A "pick the newest/best from a filtered list" reduction must page through *all* results first.** This applies to any paginated API, not just our Query classes (e.g. Prefect artifact listings): reducing over only the first page silently returns a stale or missing winner once results exceed the page size.

```python
class MyQuery(Query):
    name = "my-query"
    type = QueryType.READ
    insert_limit = False  # Disable automatic LIMIT/OFFSET

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_to_query("MATCH (n:Node)")
        self.add_to_query("RETURN n.uuid AS uuid, n.name AS name LIMIT 100")  # Manual pagination
```

Two failure modes on READ queries:

- `insert_limit = False` without a `LIMIT` of your own is not "no pagination" — `execute()` still
  takes the chunked `query_with_size_limit()` path, every chunk re-reads the full result set, and
  the loop (which stops on a short page) never advances once results reach `query_size_limit`.
- An auto-paginated query needs an `ORDER BY` over a total order (a unique key). Without one, Neo4j
  does not guarantee pages are disjoint, so rows can be skipped or repeated across chunks.

### Branch-Aware Edge Resolution

Every edge in the graph has branch/temporal properties (`branch`, `branch_level`, `from`, `to`, `status`). When traversing multiple edges in a single query, filter each edge independently to resolve the correct active version:

```cypher
MATCH (n:Node)-[:HAS_ATTRIBUTE]->(attr:Attribute)
CALL (n, attr) {
    MATCH (n)-[r:HAS_ATTRIBUTE]->(attr)
    WHERE %(branch_filter)s
    RETURN r
    ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
    LIMIT 1
}
WITH n, attr, r
WHERE r.status = "active"
```

Each subquery:

1. Re-matches the edge with branch filter applied
2. Orders by `branch_level DESC, from DESC, status ASC` to prefer the most specific, most recent, active edge
3. `LIMIT 1` picks the winning edge
4. Outer `WHERE r.status = "active"` excludes soft-deleted edges

Get `branch_filter` via `self.branch.get_query_filter_path(at=self.at)`. For queries filtering multiple edges with different variable names, use `variable_name="r_custom"` to generate a filter bound to a specific variable.

Example: `NodeGetListByAttributeValueQuery` and `NodeGetByHFIDQuery` chain three such subqueries (`IS_PART_OF`, `HAS_ATTRIBUTE`, `HAS_VALUE`) to resolve the active attribute value for the requested branch/time.

### Cypher Variable Shadowing (Neo4j 5+)

Inside `CALL (var1, var2) { ... }` subqueries, Neo4j 5+ rejects re-declaring an imported variable:

```cypher
// ERROR: "Variable `r` already declared in outer scope"
CALL (r) {
    MATCH (a)-[r:REL]->(b)  // r is shadowed
    RETURN r
}
```

Either use different variable names inside the subquery, or return a fresh reference:

```cypher
CALL (attr) {
    MATCH (attr)-[r:HAS_VALUE]->(av)
    RETURN r
}
```

Similarly, `CALL ... IN TRANSACTIONS` requires the `MATCH` to be outside the subquery — transform the input first with `MATCH`, then `CALL` only the write operations:

```cypher
UNWIND $updates AS update
MATCH (attr:Attribute)-[old_r:HAS_VALUE]->(old_av)
WHERE elementId(old_av) = update.element_id
CALL (update, attr, old_r, old_av) {
    // write operations here
} IN TRANSACTIONS OF 500 ROWS
```

## Result Dataclass Pattern

All queries must expose results through frozen dataclasses. This provides type safety, IDE autocompletion, and a clear API contract between queries and callers.

### Basic Structure

```python
from typing import Generator
from dataclasses import dataclass
from infrahub.core.query import Query, QueryResult, QueryType

@dataclass(frozen=True)
class MyQueryResult:
    """Result from MyQuery."""
    uuid: str
    name: str

class MyQuery(Query):
    name = "my-query"
    type = QueryType.READ

    def __init__(self, node_id: str, **kwargs):
        super().__init__(**kwargs)
        self.params["node_id"] = node_id
        self.add_to_query("MATCH (n:Node { uuid: $node_id }) RETURN n.uuid AS node_uuid, n.name AS node_name")
        self.update_return_labels(["node_uuid", "node_name"])

    def get_data(self) -> Generator[MyQueryResult, None, None]:
        """Yield results as typed dataclass instances."""
        for result in self.get_results():
            node_uuid = result.get_as_type("node_uuid", str)
            node_name = result.get_as_type("node_name", str)
            yield MyQueryResult(uuid=node_uuid, name=node_name)
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Result dataclass | `{QueryName}Result` | `NodeGetListQueryResult` |
| Query method | `get_data()` | Yields typed results as a Generator |

### Reading values out of a result

Every shape follows the same `get_data()` loop; only the accessor changes. Pick it by the column's
shape and let it do the typing, rather than indexing the raw record and casting:

| Column shape | Accessor |
|---|---|
| A scalar | `get_as_type("uuid", str)` |
| A scalar that may be absent | `get_as_optional_type("description", str)` |
| A string (shorthand, returns `str | None`) | `get_as_str("node_uuid")` |
| A `collect(...)` list | `get_as_list_of_type("related_uuids", str)` |
| A whole node or relationship | `get("n")` |

```python
@dataclass(frozen=True)
class NodeWithPeers:
    uuid: str
    description: str | None
    peer_uuids: tuple[str, ...]  # tuple, so the dataclass can stay frozen

def get_data(self) -> Generator[NodeWithPeers, None, None]:
    for result in self.get_results():
        yield NodeWithPeers(
            uuid=result.get_as_type("uuid", str),
            description=result.get_as_optional_type("description", str),
            peer_uuids=tuple(result.get_as_list_of_type("peer_uuids", str)),
        )
```


For a query expected to yield at most one row, return `MyQueryResult | None` from a
`self.get_result()` check instead of a generator.

### Guidelines

- **Return only necessary data:** Never return entire nodes (`RETURN n`) when you only need specific properties (`RETURN n.uuid AS uuid`). This significantly reduces data transfer and memory usage.
- Use `@dataclass(frozen=True)` for immutability and hashability (NOT Pydantic)
- Flatten aggressively: replace `node.get("prop")` chains with simple attributes
- Only include fields actually used by callers
- Use tuples instead of lists for collection fields (frozen dataclass requirement)
- Use `get_as_str()`, `get_as_type()` for scalars, `get_as_optional_type()` for nullable values
- Use `Generator` return type since `get_results()` returns a generator

Use `elementId(n) AS db_id` when you need the database ID, rather than returning the full node just
to access `node.element_id` (see [Return Labels](#return-labels) for why whole-node returns waste
bandwidth and memory).

## Internals

This section documents internal implementation details. External callers should use the typed dataclass pattern above.

### Query Base Class

**Location:** `backend/infrahub/core/query/__init__.py`

```python
class Query:
    name: str = "base-query"
    type: QueryType  # READ or WRITE

    def __init__(
        self,
        branch: Branch | None = None,
        at: Timestamp | str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: list[str] | None = None,
        branch_agnostic: bool = False,
        user_id: str = SYSTEM_USER_ID,
    ) -> None:
        self.params: dict = {}
        self.query_lines: list[str] = []
        self.return_labels: list[str] = []
        self.results: list[QueryResult] = []
```

| Attribute | Purpose |
|-----------|---------|
| `query_lines` | List of Cypher clauses being built |
| `params` | Dictionary of parameterized values (`$name` → value) |
| `return_labels` | Labels to include in RETURN clause |
| `results` | List of `QueryResult` after execution |
| `branch` | Branch context for the query |
| `at` | Timestamp for time-travel queries |

### QueryResult (Internal)

> **Note:** QueryResult is for internal query implementation. Use it only inside `get_data()` methods. External callers must use typed dataclass results.

Wraps Neo4j records and provides typed access methods:

| Method | Returns | Purpose |
|--------|---------|---------|
| `get(label)` | `Neo4jNode \| Neo4jRelationship` | Get item by label |
| `get_node(label)` | `Neo4jNode` | Get node with type checking |
| `get_rel(label)` | `Neo4jRelationship` | Get relationship with type checking |
| `get_as_type(label, type)` | `type` | Get scalar as specific type |
| `get_as_optional_type(label, type)` | `type \| None` | Get optional scalar |
| `get_nodes()` | `Generator[Neo4jNode]` | Iterate all nodes |
| `get_rels()` | `Generator[Neo4jRelationship]` | Iterate all relationships |
| `get_node_collection(label)` | `list[Neo4jNode]` | Get collected nodes |

### Query Element Builders

Helper dataclasses for building Cypher patterns:

```python
# Node pattern: (n:Label { uuid: $uuid })
QueryNode(name="n", labels=["Label"], params={"uuid": "$uuid"})

# Relationship pattern with direction: -[r:IS_PART_OF]->
QueryRel(name="r", labels=["IS_PART_OF"], direction=QueryRelDirection.OUTBOUND)
```

### Query Types

| Type | Enum Value | Purpose |
|------|------------|---------|
| READ | `QueryType.READ` | Select-like operations, no side effects |
| WRITE | `QueryType.WRITE` | Create/Update/Delete operations |

### Domain-Specific Queries

Specialized base classes for different domains:

| Base Class | Location | Purpose |
|------------|----------|---------|
| `NodeQuery` | `node.py` | Node CRUD with node resolution |
| `RelationshipQuery` | `relationship.py` | Relationship operations |
| `AttributeQuery` | `attribute.py` | Attribute value management |
| `DiffQuery` | `diff.py` | Change detection between branches/times |
| `StandardNodeQuery` | `standard_node.py` | Simple non-graph node CRUD |

### Design Decisions

**Database Object in Initialization:** The `InfrahubDatabase` object is passed during initialization for:

1. **Schema access via database proxy:** Enables temporal queries using previous schema versions

   ```python
   schema = db.schema.get(name="MyNode", branch=branch)  # Good
   schema = registry.schema.get(name="MyNode")  # Avoid: loses temporal flexibility
   ```

2. **Database type abstraction:** Contains database-specific functions

   ```python
   id_func = db.get_id_function_name()  # Returns "elementId" for Neo4j
   ```

## Key Locations

| Component | Location |
|-----------|----------|
| Base classes | `backend/infrahub/core/query/__init__.py` |
| Node queries | `backend/infrahub/core/query/node.py` |
| Relationship queries | `backend/infrahub/core/query/relationship.py` |
| Attribute queries | `backend/infrahub/core/query/attribute.py` |
| Diff queries | `backend/infrahub/core/query/diff.py` |
| Subquery filters | `backend/infrahub/core/query/subquery.py` |
| IPAM queries | `backend/infrahub/core/query/ipam.py` |
| Branch queries | `backend/infrahub/core/query/branch.py` |
| Standard node queries | `backend/infrahub/core/query/standard_node.py` |

## See Also

- [Database Schema](database-schema.md) - Neo4j vertex/edge structure and temporal branching rules
- [Backend Architecture](architecture.md) - Overall backend structure
- [Testing](testing.md) - Query testing patterns
- [Python Coding Standards](../../guidelines/backend/python.md) - Dataclass conventions
