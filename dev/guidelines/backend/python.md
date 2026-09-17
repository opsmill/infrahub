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

**Exception — `tasks/*.py`:** keep `infrahub.*` and other heavy/optional imports function-local
here. `tasks/__init__.py` eagerly imports every task submodule into the Invoke `Collection`, so a
top-level backend import in any `tasks/*.py` file would load the full backend package on every
`invoke` command, even unrelated ones (`invoke --list`, `invoke docs.*`, ...). This is a
deliberate, documented exception: `pyproject.toml`'s `"tasks/**.py"` per-file-ignore disables the
"import not at top level" lint rule for exactly this reason. Keep lightweight, always-needed
imports (stdlib, `invoke`, sibling `.shared`/`.utils` modules) at the top; defer the rest into the
function that needs them.

The exception covers a thin task wrapper, not logic that happens to live in `tasks/`. A task body
needing a dozen deferred imports is telling you the logic belongs in a module of its own, which the
task then imports once — put it there and the deferred imports mostly disappear with it.

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

**Document an attribute with an inline docstring below it**, not in the class docstring, and only
when the name does not already say what the field holds:

```python
# ✅ Good - a docstring only where the name leaves a question
@dataclass(frozen=True)
class RelationshipPeerData:
    branch: str
    source_id: UUID
    peer_kind: str
    rel_node_db_id: str | None = None

    rels: list[RelData] | None = None
    """Both relationships pointing at this Relationship Node."""

# ❌ Bad - the docstring restates the field name
@dataclass(frozen=True)
class RelationshipPeerData:
    source_id: UUID
    """UUID of the Source Node."""

    peer_kind: str
    """Kind of the Peer Node."""

# ❌ Bad - attributes documented in the class docstring
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

## Docstrings

A docstring states the contract in one line. Add a Google-style `Args`, `Returns` or `Raises`
section only for what the signature does not already say. Write one on a public function or class
that other modules call; a private helper whose name says what it does gets none. What belongs in
a comment at all is in `.agents/rules/code-doc-style.md`.

```python
# ✅ Good - one line; the signature already documents the parameters
async def create_branch(db: InfrahubDatabase, name: str, description: str | None = None) -> Branch:
    """Create a branch, raising BranchExistsError when the name is already taken."""


# ✅ Good - a section for the one parameter the name does not explain
def load_nodes(db: InfrahubDatabase, ids: list[str], *, strict: bool = False) -> list[Node]:
    """Load the nodes behind the given ids.

    Args:
        strict: Raise on an unknown id instead of dropping it from the result.

    """


# ❌ Bad - every section restates the signature
async def create_branch(db: InfrahubDatabase, name: str, description: str | None = None) -> Branch:
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
