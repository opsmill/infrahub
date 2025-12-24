# Python Coding Standards

> Part of: `dev/guidelines/backend/` | Related: `dev/knowledge/backend/architecture.md`

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

## Pydantic Models

Use Pydantic models for all data structures:

```python
# ✅ Good
from pydantic import BaseModel, Field

class BranchCreateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=250, description="name of the branch")
    description: str | None = Field(default=None, description="Description of the branch")

# ❌ Bad
branch_data = {"name": "feature-x", "description": None}
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

## Testing

- Unit tests: no external dependencies except database
- Integration tests: require Neo4j via testcontainers
- Test files mirror source: `infrahub/core/node.py` → `tests/unit/core/test_node.py`
- Async tests auto-configured via pytest-asyncio

## See Also

- `dev/knowledge/backend/architecture.md` - Backend architecture overview
- `dev/guidelines/git-workflow.md` - Git workflow and commit conventions

