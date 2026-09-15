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

All imports must be at the top of the file. Never import inside functions, methods, or classes (ruff
`PLC0415`). The only function-local imports we keep defer an optional or heavy dependency that must
not load on every import, each marked `# noqa: PLC0415` with the reason:

```python
# ✅ Good - imports at module level
from infrahub.exceptions import ValidationError

# ❌ Bad - import inside function
class NodeManager:
    def validate(self, node: Node) -> None:
        from infrahub.exceptions import ValidationError
        if not node.name:
            raise ValidationError("Node name is required")
```

All backend modules use `from __future__ import annotations`, so an import used **only** in
parameter types, return types, or variable annotations has no runtime effect. Put it under
`TYPE_CHECKING`, especially when it causes or risks a circular import chain:

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

### An import cycle is a layering defect, not a reason for a function-local import

A cycle means the module reaches into a layer above it, and hiding the import inside a function only
hides that. Map the cycle first: a hub package such as `infrahub.services` reaches low-level modules
by several routes, so cutting one edge rarely frees it. Then fix the dependency itself:

- Depend on the narrower interface the code actually uses: a lock that only calls `service.cache`
  takes the cache adapter, not the services container that owns it.
- When the import only served a runtime `isinstance`, give each accepted type its own parameter so
  the branches narrow on `None` and the type stays a `TYPE_CHECKING` import.
- Move a helper next to its only caller when that module already sits at the right layer.

```python
# ❌ Bad - the check needs a type from the layer above, so the import hides in the function
def _require_service(connection: redis.Redis | InfrahubServices | None) -> InfrahubServices:
    from infrahub.services import InfrahubServices  # noqa: PLC0415  # avoid circular import
    if not isinstance(connection, InfrahubServices):
        raise TypeError(...)
    return connection

# ✅ Good - one typed slot per driver; the branch narrows on None and imports nothing above this layer
def __init__(self, name: str, connection: redis.Redis | None = None, cache: InfrahubCache | None = None) -> None:
    if cache is None:
        raise TypeError(f"Lock {name!r} requires a cache adapter")
    self.cache: InfrahubCache = cache
```

**Exception — `tasks/*.py`:** keep `infrahub.*` and other heavy imports function-local there.
`tasks/__init__.py` eagerly imports every task submodule into the Invoke `Collection`, so a top-level
backend import in any task file would load the full backend on every `invoke` command, and
`pyproject.toml`'s `"tasks/**.py"` per-file-ignore disables the rule for exactly this reason. Keep
stdlib, `invoke` and sibling `.shared`/`.utils` imports at the top and defer the rest. The exception
covers a thin task wrapper: a task body needing a dozen deferred imports belongs in a module of its
own, which the task imports once.

Import a singleton from the module that defines it, not from a package `__init__.py` that re-exports
it under the same name as its submodule. `from infrahub.core import registry` names two things — the
`infrahub.core.registry` module and the object it re-exports — and mypy binds whichever it resolves
first. That order shifts when an import cycle elsewhere changes, so the errors (`Name "registry"
already defined`, `Module has no attribute "schema"`) appear in files the change never touched
(see [Package `__init__.py` files](../../knowledge/backend/package-init-files.md)):

```python
# ❌ Bad - names the submodule and the re-exported object at once
from infrahub.core import registry

# ✅ Good - one object, whatever order the cycle resolves in
from infrahub.core.registry import registry
```

Fix the import where the checker flags it rather than sweeping existing call sites, and prefer not
importing the registry into a new component at all — see
[Accessing schema](../../knowledge/backend/query-pattern.md#accessing-schema-inject-schemamanager-else-dbschema-never-registry).

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

Regardless of which approach you use, avoid untyped dictionaries for structured data: write
`BranchCreateInput(name="feature-x")`, not `{"name": "feature-x", "description": None}`.

### Optional and default values

Prefer `dict.get(key, default)` over an `in` check or `try/except KeyError` for a possibly-missing
key (without a second argument `get()` returns `None`); use `setdefault()` when the default is a
mutable object you build up.

Zero is a value, not an absence. Test an optional numeric with `is not None` — a truthiness check
silently treats a legitimate `0` as unset:

```python
# ❌ Bad - offset=0 is dropped, so the first page renders a different query text
if offset:
    query += " SKIP $offset"

# ✅ Good - zero is bound like any other value
if offset is not None:
    query += " SKIP $offset"
```

When zero deliberately means "no bound" in the caller contract, keep that reading — and pin it with
a test, so the next pass at the line fails fast instead of shipping the inversion.

## Configuration Settings

`backend/infrahub/config.py` is the boundary where an operator's environment enters the process. Any value that gets past a `Field` is trusted by everything downstream, so constrain it here rather than defending against it in the logic that consumes it.

### Bound every numeric field

Give each numeric field the tightest bounds its *meaning* allows, not just `gt=0`. A multiplier that may only scale a value **up** is `ge=1`; one that may only scale it **down** is `gt=0, le=1`. A count that must leave room for at least one item is `ge=1`, not `ge=0`.

Every `float` field also needs `allow_inf_nan=False`. Pydantic accepts `inf` and `nan` for floats by default, and both slip past `gt`/`ge`: `inf` produces a threshold that can never be reached, and `nan` makes every comparison against it `False`, so the feature quietly stops working somewhere far from the config file.

```python
retry_backoff_multiplier: float = Field(
    default=2.0,
    ge=1,
    allow_inf_nan=False,
    description="Factor applied to the delay after each failed attempt.",
)
```

### Enforce cross-field invariants with a model validator

Per-field bounds cannot express a relationship *between* settings. When one setting is only meaningful relative to another — an ordering, a window that must contain another, a ceiling that must sit above its floor — assert it in a `@model_validator(mode="after")`. A contradictory configuration then fails at startup with an explanation, instead of silently inverting the feature's behavior at runtime.

```python
@model_validator(mode="after")
def validate_retry_delay_bounds_ordered(self) -> Self:
    """Require the initial retry delay to fall within the configured ceiling.

    Raises:
        ValueError: If the initial delay exceeds the maximum.

    """
    if self.retry_initial_delay_seconds > self.retry_max_delay_seconds:
        raise ValueError(
            "'retry_initial_delay_seconds' must not exceed 'retry_max_delay_seconds', "
            "otherwise the backoff ceiling is reached before the first retry"
        )
    return self
```

Name the validator after the invariant it enforces. Name the offending fields in full in the message so they are greppable, and state both the rule and its consequence — the operator reading it in a crash log has no other context.

Testing note: don't test that Pydantic enforces `ge`/`le` (see [Testing Standards](./testing.md#what-not-to-test)), but *do* test the model validator and the shipped defaults — the invariant and the defaults are ours.

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

Typing rules — enums over bare `str`, unions over flag structs, narrowing with `isinstance` rather
than `getattr` or `cast()`, clearing a suppression — live in [Python Typing](typing.md).

## Deterministic serialization for hashes and cache keys

When a JSON string feeds a hash, fingerprint, or cache key, its output must be deterministic. Do **not** pass `default=str` to `json.dumps` there: it silently serializes unexpected types via `str()`, which can embed run-specific data (memory addresses) and break determinism. Serialize an explicit, canonical shape (sorted keys, known field types) and let unknown types raise instead of being coerced.

## Path Matching

When matching a request path (or any string) against an exclusion or allow-list, never rely on
`path.startswith(prefix)` alone — it also matches unrelated paths that merely share the prefix as
a substring, e.g. `/healthcheck` incorrectly matches an excluded `/health`. Require the prefix to
be the whole path or a slash-delimited ancestor:

```python
# ❌ Bad - "/healthcheck" bypasses an exclusion meant for "/health"
if any(path.startswith(excluded) for excluded in excluded_paths):
    return True

# ✅ Good - exact match or a genuine descendant
if any(path == excluded or path.startswith(f"{excluded}/") for excluded in excluded_paths):
    return True
```

## Python Version Compatibility

The `python_testcontainers` package supports Python 3.10+, while the main backend requires Python 3.12+. When writing code that may be shared or used in `python_testcontainers`, be mindful of version-specific features.

### Version-specific features

The backend targets modern Python, but code shared with `python_testcontainers` must run on 3.10: there, avoid `datetime.UTC` (use `datetime.now(timezone.utc)`), and import `Self` from `typing_extensions`.

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

- Unit tests: no external dependencies only file access
- Component tests: Similar to unit tests with regards to small testing scope but can require database access
- Integration tests: require Neo4j via testcontainers
- Test files mirror source: `infrahub/core/node.py` → `tests/unit/core/test_node.py`
- Async tests auto-configured via pytest-asyncio

For additional information around testing patterns refer to [./testing.md](./testing.md)

## See Also

- [Python Typing](typing.md) - Type hints, narrowing without `cast()`, clearing suppressions
- [Exception Handling](exceptions.md) - Catching, scoping, and suppressing exceptions
- [ASGI Middleware](asgi-middleware.md) - Writing FastAPI/Starlette middleware
- [Backend Architecture](../../knowledge/backend/architecture.md) - Backend architecture overview
- [Git Workflow](../git-workflow.md) - Git workflow and commit conventions
