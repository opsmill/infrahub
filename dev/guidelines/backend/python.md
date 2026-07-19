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

## Imports

All imports must be at the top of the file. Never import inside functions, methods, or classes:

```python
# ✅ Good - imports at module level
from infrahub.core.query import Query
from infrahub.exceptions import ValidationError

class NodeManager:
    def validate(self, node: Node) -> None:
        if not node.name:
            raise ValidationError("Node name is required")

# ❌ Bad - import inside function
class NodeManager:
    def validate(self, node: Node) -> None:
        from infrahub.exceptions import ValidationError
        if not node.name:
            raise ValidationError("Node name is required")
```

All backend modules use `from __future__ import annotations`, which turns annotations into strings at runtime. This means imports used **only** in type hints have no runtime effect and can be placed under `TYPE_CHECKING` to prevent circular imports:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
```

If an import is only referenced in parameter types, return types, or variable annotations, move it under `TYPE_CHECKING` — especially when it causes or risks a circular import chain:

```python
# ❌ Bad - top-level import only used in annotations; causes circular import
from infrahub.core.schema.schema_branch import SchemaBranch

def collect_filters(self, schema_branch: SchemaBranch) -> dict[str, set[str]]:
    ...

# ✅ Good - deferred under TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch

def collect_filters(self, schema_branch: SchemaBranch) -> dict[str, set[str]]:
    ...
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

### Type a closed value set as an enum, not `str`

When a field or argument accepts only a fixed set of values, don't type it as a bare `str` — a bare `str` lets a typo through silently and hides the valid set from readers and from the schema. Use one of:

- **`Literal["a", "b"]`** — the lighter option for a small closed set used in a **single file**. Still type-checked, no class to declare.
- **An enum** — when the set is shared across modules, needs a name, round-trips through the database, or is exposed over GraphQL. Subclass `str` so the value round-trips as text — `StrEnum` on the backend (Python 3.11+); use `class X(str, Enum)` for code shared with `python_testcontainers` (which targets 3.10).

```python
# ❌ Bad - any string is accepted; a typo silently bypasses downstream logic
origin: str | None = None

# ✅ Good - the valid set is discoverable and reusable; the owning model validates input
class NodeMutationOrigin(StrEnum):
    LIVE = "live"
    MERGE = "merge"
    REBASE = "rebase"

origin: NodeMutationOrigin | None = None
```

The annotation alone does not reject a bad value at runtime — a validation layer enforces it (a Pydantic model, or an explicit `NodeMutationOrigin(value)` conversion at the boundary for plain dataclasses/adapters). For a value exposed over GraphQL, reuse the existing Python-enum → GraphQL-enum conversion rather than re-declaring the values as strings in the GraphQL layer.

### Do not narrow a type in an override (Liskov / `ty`)

An override may not make a parameter type *narrower* (or a return type *wider*) than the base declaration — `ty` rejects it as a Liskov violation. When an abstract method and its implementations must accept a union, declare the full shared type on the abstract **and** on every implementation; do not tighten one adapter.

```python
# ❌ Bad - RedisCache narrows the abstract's `int` to `KVTTL`; ty errors
class InfrahubCache(ABC):
    async def set(self, key: str, value: str, expires: int | None = None) -> None: ...
class RedisCache(InfrahubCache):
    async def set(self, key: str, value: str, expires: KVTTL | None = None) -> None: ...

# ✅ Good - the shared union on the base and all adapters
async def set(self, key: str, value: str, expires: KVTTL | int | None = None) -> None: ...
```

### Prefer `isinstance` over `getattr` for narrowing

To branch on or read from a typed object, use `isinstance` so the type checker can narrow it; reaching for `getattr(obj, "attr", default)` defeats type analysis. When guarding a schema object, cover the whole family that carries the attribute — `isinstance(schema, (NodeSchema, ProfileSchema, TemplateSchema))` — since profiles and templates inherit node behavior and a `NodeSchema`-only check silently drops them.

### Deterministic serialization for hashes and cache keys

When a JSON string feeds a hash, fingerprint, or cache key, its output must be deterministic. Do **not** pass `default=str` to `json.dumps` there: it silently serializes unexpected types via `str()`, which can embed run-specific data (memory addresses) and break determinism. Serialize an explicit, canonical shape (sorted keys, known field types) and let unknown types raise instead of being coerced.

## Python Version Compatibility

The `python_testcontainers` package supports Python 3.10+, while the main backend requires Python 3.12+. When writing code that may be shared or used in `python_testcontainers`, be mindful of version-specific features.

### datetime.UTC (Python 3.11+)

The `datetime.UTC` constant was introduced in Python 3.11. For Python 3.10 compatibility, use `timezone.utc` instead:

```python
# ❌ Bad - Python 3.11+ only
from datetime import UTC, datetime
now = datetime.now(UTC)

# ✅ Good - Works in Python 3.10+
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

### Other Version-Specific Features

When using newer Python features, verify they're available in the minimum supported version:

| Feature | Minimum Version |
|---------|-----------------|
| `datetime.UTC` | 3.11 |
| `str \| None` union syntax | 3.10 |
| `list[Type]` generic syntax | 3.9 |
| `match` statements | 3.10 |
| `Self` type hint | 3.11 (use `typing_extensions.Self` for 3.10) |

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

## Exception Handling

Catch only the exceptions you expect and know how to handle. Do not use bare `except:` or a broad `except Exception` to wrap code you haven't verified can raise something you can recover from — it swallows `KeyboardInterrupt`/`SystemExit` intent, hides bugs (typos, `AttributeError`, misconfiguration) behind the same handler as the error you meant to catch, and makes failures silent.

```python
# ❌ Bad - swallows everything, including programming errors
try:
    node = await get_node(db=db, node_id=node_id)
except Exception:
    node = None

# ✅ Good - catch only what get_node is documented to raise
try:
    node = await get_node(db=db, node_id=node_id)
except NodeNotFoundError:
    node = None
```

Guidelines:

- **Name the exceptions.** Catch the narrowest type(s) that the called code actually raises. If several are handled the same way, group them: `except (NodeNotFoundError, BranchNotFoundError):`.
- **Keep the `try` body small.** Wrap only the statement that can raise, not a whole block, so an unexpected error elsewhere isn't caught by accident.
- **Never silence.** A bare `except Exception: pass` hides real failures. If there is genuinely nothing to do, comment why, and at minimum `log.debug(...)`.
- **Re-raise what you can't handle.** If you must catch broadly to add context or clean up, re-raise afterwards (`raise` to preserve the traceback, or `raise NewError(...) from exc` to chain).

```python
# ✅ Good - broad catch is acceptable only to add context, then re-raise
try:
    await run_migration(db=db)
except Exception as exc:
    log.error("Migration failed", error=str(exc))
    raise
```

A broad `except Exception` is justified only at a top-level boundary (a task worker loop, a request handler) whose job is to prevent one failure from taking down the process — and even there, log the exception and re-raise or record it, never discard it.

## Testing

- Unit tests: no external dependencies only file access
- Component tests: Similar to unit tests with regards to small testing scope but can require database access
- Integration tests: require Neo4j via testcontainers
- Test files mirror source: `infrahub/core/node.py` → `tests/unit/core/test_node.py`
- Async tests auto-configured via pytest-asyncio

For additional information around testing patterns refer to [./testing.md](./testing.md)

## See Also

- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
- [Git Workflow](../git-workflow.md) - Git workflow and commit conventions
