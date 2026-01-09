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
    self.update_return_labels(["n"])
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

### Return Labels

The RETURN clause is automatically generated from `return_labels`. Call `update_return_labels()` to specify what to return:

```python
self.add_to_query("MATCH (n:Node)-[r:REL]->(p:Peer)")
self.update_return_labels(["n", "r", "p"])  # Generates: RETURN n, r, p
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
        self.add_to_query("RETURN n.uuid AS uuid, n.name AS name")  # Manual RETURN
```

### Pagination

Pagination (`LIMIT`/`OFFSET`) is automatically appended based on constructor parameters. To write pagination directly in your query, set `insert_limit = False`:

```python
class MyQuery(Query):
    name = "my-query"
    type = QueryType.READ
    insert_limit = False  # Disable automatic LIMIT/OFFSET

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_to_query("MATCH (n:Node)")
        self.add_to_query("RETURN n LIMIT 100")  # Manual pagination
```

## Result Dataclass Pattern

All queries must expose results through frozen dataclasses. This provides type safety, IDE autocompletion, and a clear API contract between queries and callers.

### Basic Structure

```python
from dataclasses import dataclass
from infrahub.core.query import Query, QueryResult, QueryType

@dataclass(frozen=True)
class MyQueryResult:
    """Result from MyQuery."""
    uuid: str
    name: str

    @classmethod
    def from_db(cls, result: QueryResult) -> MyQueryResult:
        """Convert raw QueryResult to typed dataclass."""
        node = result.get_node("n")
        return cls(uuid=node.get("uuid"), name=node.get("name"))

class MyQuery(Query):
    name = "my-query"
    type = QueryType.READ

    def __init__(self, node_id: str, **kwargs):
        super().__init__(**kwargs)
        self.params["node_id"] = node_id
        self.add_to_query("MATCH (n:Node { uuid: $node_id })")
        self.update_return_labels(["n"])

    def get_data(self) -> list[MyQueryResult]:
        """Return results as typed dataclass instances."""
        return [MyQueryResult.from_db(r) for r in self.get_results()]
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Result dataclass | `{QueryName}Result` | `NodeGetListQueryResult` |
| Factory method | `from_db(cls, result)` | `MyQueryResult.from_db(result)` |
| Query method | `get_data()` | Returns typed results |

### Pattern Examples

**Scalar values** (`RETURN n.uuid AS uuid, n.kind AS kind`):

```python
@dataclass(frozen=True)
class ScalarResult:
    uuid: str
    kind: str

    @classmethod
    def from_db(cls, result: QueryResult) -> ScalarResult:
        return cls(uuid=result.get_as_type("uuid", str), kind=result.get_as_type("kind", str))
```

**Single node** (`RETURN n`):

```python
@dataclass(frozen=True)
class SingleNodeResult:
    uuid: str
    kind: str
    db_id: str

    @classmethod
    def from_db(cls, result: QueryResult) -> SingleNodeResult:
        node = result.get_node("n")
        return cls(uuid=node.get("uuid"), kind=node.get("kind"), db_id=node.element_id)
```

**Node + relationship** (`RETURN n, r`):

```python
@dataclass(frozen=True)
class NodeWithRelResult:
    node_uuid: str
    rel_branch: str
    rel_status: str

    @classmethod
    def from_db(cls, result: QueryResult) -> NodeWithRelResult:
        node, rel = result.get_node("n"), result.get_rel("r")
        return cls(node_uuid=node.get("uuid"), rel_branch=rel.get("branch"), rel_status=rel.get("status"))
```

**Collection** (`RETURN n, collect(related) AS related`):

```python
@dataclass(frozen=True)
class CollectionResult:
    primary_uuid: str
    related_uuids: tuple[str, ...]  # tuple for frozen dataclass

    @classmethod
    def from_db(cls, result: QueryResult) -> CollectionResult:
        node = result.get_node("n")
        related = result.get_node_collection("related")
        return cls(primary_uuid=node.get("uuid"), related_uuids=tuple(r.get("uuid") for r in related))
```

**Optional values**:

```python
@dataclass(frozen=True)
class OptionalResult:
    uuid: str
    description: str | None

    @classmethod
    def from_db(cls, result: QueryResult) -> OptionalResult:
        return cls(uuid=result.get_as_type("uuid", str), description=result.get_as_optional_type("description", str))
```

### Query Method Patterns

```python
# Multiple results:
def get_data(self) -> list[MyQueryResult]:
    return [MyQueryResult.from_db(r) for r in self.get_results()]

# Large result sets (memory efficient):
def get_data_iterator(self) -> Iterator[MyQueryResult]:
    for result in self.get_results():
        yield MyQueryResult.from_db(result)

# Single result:
def get_data(self) -> MyQueryResult | None:
    result = self.get_result()
    return MyQueryResult.from_db(result) if result else None
```

### Guidelines

- Use `@dataclass(frozen=True)` for immutability and hashability (NOT Pydantic)
- Flatten aggressively: replace `node.get("prop")` chains with simple attributes
- Only include fields actually used by callers
- Use tuples instead of lists for collection fields (frozen dataclass requirement)
- Use `get_as_type()` for scalars, `get_as_optional_type()` for nullable values
- Use generators for large result sets to avoid memory issues

### Optimizing Cypher RETURN

When possible, return only needed properties instead of entire nodes:

```cypher
-- Before (returns entire nodes)
RETURN n, r, p

-- After (returns only needed properties)
RETURN n.uuid AS node_uuid, n.name AS node_name, r.branch AS rel_branch
```

This reduces data transfer and memory usage.

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

> **Note:** QueryResult is for internal query implementation. Use it only inside `from_db()` methods. External callers must use typed dataclass results.

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

- [Backend Architecture](architecture.md) - Overall backend structure
- [Testing](testing.md) - Query testing patterns
- [Python Coding Standards](../../guidelines/backend/python.md) - Dataclass conventions
