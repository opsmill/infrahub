# AGENTS.md - Backend

> See [root AGENTS.md](../AGENTS.md) for project-wide commands and guidelines.

## Overview

FastAPI backend with GraphQL API, Neo4j database, and async-first architecture.

## File Structure

- `infrahub/` – Main application
  - `api/` – REST endpoints
  - `graphql/` – GraphQL schema, mutations, resolvers
  - `core/` – Domain logic (nodes, schemas, branches, diff)
  - `database/` – Database utilities
  - `workers/` – Background tasks
- `tests/` – Test suites (unit, integration, functional, benchmark)
- `templates/` – Jinja2 code generation templates

## Commands

```bash
uv run invoke backend.test-unit        # Unit tests
uv run invoke backend.test-integration # Integration tests (needs Neo4j)
uv run invoke backend.format           # Format with ruff
uv run invoke backend.lint             # Lint with ruff + mypy
uv run invoke backend.generate         # Regenerate schemas/protocols
```

## Code Style

### Async-First

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

### Pydantic Models

```python
# ✅ Good
from pydantic import BaseModel, Field

class BranchCreateInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=250, description="name of the branch")
    description: str | None = Field(default=None, description="Description of the branch")

# ❌ Bad
branch_data = {"name": "feature-x", "description": None}
```

### Docstrings (Google-style)

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

### Naming Conventions

- **Functions/variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Test files:** `test_<module>.py`

### Query Pattern

```python
from infrahub.core.query import Query

class MyQuery(Query):
    name: str = "my_query"

    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:
        self.params["node_id"] = kwargs["node_id"]
        self.add_to_query("MATCH (n:Node {uuid: $node_id}) RETURN n")
```

### Neo4j/Cypher Queries

When writing or modifying Cypher queries, **read `DATABASE.md`** first. It documents:

- Vertex types (Root, Branch, Node, Relationship, Attribute, AttributeValue)
- Edge types and properties (branch, from, to, status)
- Temporal branching rules and valid path patterns
- Example queries for common operations

## Testing

- Unit tests: no external dependencies except database
- Integration tests: require Neo4j via testcontainers
- Test files mirror source: `infrahub/core/node.py` → `tests/unit/core/test_node.py`
- Async tests auto-configured via pytest-asyncio

## Boundaries

### Always Do

- Use async/await for all I/O
- Type hint all function parameters and returns
- Use Pydantic models for data structures
- Use Query class pattern for database operations

### Ask First

- New database indexes
- Core schema definition changes
- New GraphQL mutations/queries

### Never Do

- Unparameterized Cypher queries
- Block event loop with sync I/O
- Edit files in `infrahub/core/schema/generated/`
