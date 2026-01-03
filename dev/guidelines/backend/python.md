# Python Coding Standards

> Part of: `dev/guidelines/backend/` | Related: [Backend Architecture](../../knowledge/backend/architecture.md)

Coding standards for the Python backend.

## Async-First

All I/O operations must be async:

```python
# ✅ Good
async def get_node(db: InfrahubDatabase, node_id: str) -> Node:
    query = await NodeGetQuery.init(db=db, node_id=node_id)
    await query.execute(db=db)
    return query.get_node()

# ❌ Bad - blocks event loop, no type hints
def get_node(db, node_id):
    return db.get(node_id)
```

## Data Structures

Use the appropriate data structure based on context. Do not use Pydantic everywhere.

### Pydantic Models (External APIs)

Use Pydantic for data structures that cross system boundaries (REST/GraphQL APIs, configuration files, external integrations):

```python
# ✅ Good - API input/output models
from pydantic import BaseModel, Field

class BranchCreateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=250, description="name of the branch")
    description: str | None = Field(default=None, description="Description of the branch")

class BranchResponse(BaseModel):
    id: str
    name: str
    is_default: bool
```

Pydantic is appropriate when you need:

- Input validation and serialization
- OpenAPI/JSON schema generation
- Data coming from or going to external systems

### Dataclasses (Internal Structures)

Use dataclasses for internal data structures that don't require validation or serialization.

**Prefer frozen dataclasses** (`frozen=True`) when instances don't need to be mutated after creation. Frozen dataclasses are immutable, memory efficient, hashable, and make code easier to reason about:

```python
# ✅ Good - Frozen dataclass for immutable data
from dataclasses import dataclass

@dataclass(frozen=True)
class QueryContext:
    branch_name: str
    at_time: str | None = None
    include_deleted: bool = False

# ✅ Good - Mutable dataclass only when mutation is required
@dataclass
class NodeDiffBuilder:
    node_id: str
    changed_attributes: list[str]  # Will be appended to during processing
```

**Document attributes with inline docstrings** below each attribute, not in the class docstring:

```python
# ✅ Good - Attribute docstrings below each field
@dataclass(frozen=True)
class RelationshipPeerData:
    branch: str

    source_id: UUID
    """UUID of the Source Node."""

    peer_kind: str
    """Kind of the Peer Node."""

    rel_node_db_id: str | None = None
    """Internal DB ID of the Relationship Node."""

# ❌ Bad - Attributes documented in class docstring
@dataclass(frozen=True)
class RelationshipPeerData:
    """Data about a relationship peer.

    Attributes:
        source_id: UUID of the Source Node.
        peer_id: UUID of the Peer Node.
    """
    source_id: UUID
    peer_id: UUID
```

Dataclasses are appropriate when you need:

- Simple internal data containers
- Lightweight objects without validation overhead
- Data passed between internal functions/classes

Use `frozen=True` unless you have a specific reason to mutate instances (e.g., builder pattern, accumulating results during iteration).

### Avoid Plain Dictionaries

Regardless of which approach you use, avoid untyped dictionaries for structured data:

```python
# ❌ Bad - no type safety
branch_data = {"name": "feature-x", "description": None}

# ✅ Good - use dataclass or Pydantic depending on context
branch_data = BranchCreateInput(name="feature-x")
```

## Docstrings (Google-style)

All public functions and classes must have Google-style docstrings:

```python
async def create_branch(
    db: InfrahubDatabase,
    name: str,
    description: str | None = None,
) -> Branch:
    """Create a new branch in the database.

    Args:
        db: Database connection instance.
        name: Name for the new branch.
        description: Optional description.

    Returns:
        The newly created Branch object.

    Raises:
        BranchExistsError: If branch name already exists.
    """
```

## Naming Conventions

- **Functions/variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Test files:** `test_<module>.py`

## Query Pattern

Use the Query class pattern for database operations:

```python
from infrahub.core.query import Query

class MyQuery(Query):
    name: str = "my_query"

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:
        self.params["node_id"] = kwargs["node_id"]
        self.add_to_query("MATCH (n:Node {uuid: $node_id}) RETURN n")
```

## Type Hints

- All function parameters and return types must be type-hinted
- Use `str | None` for optional strings (Python 3.10+)
- Use `list[Type]` instead of `List[Type]` (Python 3.9+)

## Function Call Style

Always use keyword arguments when calling functions and methods. This improves readability and makes code more resilient to parameter reordering:

```python
# ✅ Good - explicit keyword arguments
await query.execute(db=db)
node = await load_resource(db=db, resource_id=resource_id)
await perform_operation(db=db, resource=resource)

# ❌ Bad - positional arguments
await query.execute(db)
node = await load_resource(db, resource_id)
await perform_operation(db, resource)
```

Exceptions where positional arguments are acceptable:

- Single-argument functions: `len(items)`, `str(value)`
- Well-known stdlib patterns: `range(10)`, `print("message")`
- First argument when it's unambiguous: `log.info("message")`

## Testing

- Unit tests: no external dependencies except database
- Integration tests: require Neo4j via testcontainers
- Test files mirror source: `infrahub/core/node.py` → `tests/unit/core/test_node.py`
- Async tests auto-configured via pytest-asyncio

## See Also

- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
- [Git Workflow](../git-workflow.md) - Git workflow and commit conventions
