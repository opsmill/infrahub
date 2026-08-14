# Schema Definitions

> Part of: `dev/knowledge/backend/` | Related: [Database Schema](database-schema.md), [Code Generation](code-generation.md)

Infrahub's schema is defined in Python using Pydantic models in `backend/infrahub/core/schema/definitions/`. These definitions drive code generation, GraphQL schema export, and the runtime schema registry.

## Schema Types

| Class | Purpose | Example |
|-------|---------|---------|
| `GenericSchema` | Abstract base shared by multiple node types | `CoreWebhook` |
| `NodeSchema` | Concrete instantiable node type | `CoreStandardWebhook` |
| `AttributeSchema` | Attribute on a node (scalar value) | `name`, `url`, `active` |
| `RelationshipSchema` | Relationship between nodes | `headers`, `transformation` |

## Defining a Node

Schemas live in `backend/infrahub/core/schema/definitions/core/`. Each file typically exports one or more `GenericSchema` / `NodeSchema` instances.

```python
from infrahub.core.schema.definitions.core import GenericSchema, NodeSchema
from infrahub.core.schema.attribute_schema import AttributeSchema as Attr
from infrahub.core.schema.relationship_schema import RelationshipSchema as Rel
```

A `NodeSchema` can inherit from generics via `inherit_from`:

```python
core_standard_webhook = NodeSchema(
    name="StandardWebhook",
    namespace="Core",
    inherit_from=["CoreWebhook", "CoreTaskTarget"],
    ...
)
```

## RelationshipSchema Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | *required* | Relationship name (lowercase, 3-64 chars) |
| `peer` | `str` | *required* | Kind of the peer object (e.g., `InfrahubKind.KEYVALUE`) |
| `kind` | `RelationshipKind` | `GENERIC` | Relationship type (see below) |
| `identifier` | `str \| None` | `None` | Unique identifier; auto-generated if omitted |
| `cardinality` | `RelationshipCardinality` | `MANY` | `ONE` or `MANY` |
| `optional` | `bool` | `True` | Whether the relationship is mandatory |
| `order_weight` | `int \| None` | `None` | Frontend display ordering (lower = first) |
| `label` | `str \| None` | `None` | Human-friendly name (auto-generated if omitted) |
| `description` | `str \| None` | `None` | Short description (max 128 chars) |
| `min_count` | `int` | `0` | Minimum peers allowed |
| `max_count` | `int` | `0` | Maximum peers allowed (0 = unlimited) |
| `direction` | `RelationshipDirection` | `BIDIR` | `BIDIR`, `OUTBOUND`, or `INBOUND` |
| `branch` | `BranchSupportType \| None` | `None` | Branch support override (auto-determined from peers if omitted) |
| `on_delete` | `RelationshipDeleteBehavior \| None` | `None` | `None` (no-action) or `cascade` |
| `allow_override` | `AllowOverrideType` | `ANY` | Whether inheriting nodes can override this relationship |
| `read_only` | `bool` | `False` | Prevents user modification |
| `deprecation` | `str \| None` | `None` | Deprecation message shown to users |
| `common_parent` | `str \| None` | `None` | Constrains peer's parent to match this object's parent |
| `common_relatives` | `list[str] \| None` | `None` | Peer relationships that must share the same set of peers |

### Cascade deletes (`on_delete`)

A relationship marked `on_delete=cascade` deletes its peers when the owner is deleted. When you build a cascade to make a node deletable, the closure must reach **every** node that holds a *mandatory* relationship pointing **into** the deleted subtree — not just the direct children. Such a mandatory referrer lives on *another* schema (e.g. `CoreRepositoryGroup.repository` is mandatory and targets the repository); if that referrer is not itself in the cascade closure, the delete still fails, because Infrahub refuses to orphan a mandatory child — even though the top-level cascade looks complete.

When wiring a new cascade, inspect every schema for a mandatory relationship that *targets* each reachable node: any such inbound referrer must either be pulled into the cascade or be reconsidered. Assert the exact cascade closure in a test so a missing (or unexpected) edge is caught.

### Relationship Kinds

| Kind | Purpose |
|------|---------|
| `GENERIC` | Standard association between nodes |
| `ATTRIBUTE` | Peer is semantically part of the parent (e.g., headers on a webhook) |
| `COMPONENT` | Triggers template generation for the peer (see [Object Templates](templates.md)) |
| `PARENT` | Hierarchical parent-child relationship |
| `GROUP` | Group membership |

### Direction

- **`BIDIR`** (default) — traversable both ways. Use when peers are different kinds.
- **`OUTBOUND`** / **`INBOUND`** — needed when the same model appears on both sides (self-referencing relationships).

### Branch Support Auto-Determination

When `branch=None`, the branch support is resolved from both peers' settings. If both are `AGNOSTIC`, the relationship is `AGNOSTIC`. Only override when you need explicit control.

## Attribute Requirements

All `AttributeSchema` entries must include a `description` field. This is enforced by `backend/tests/component/core/schema/test_schema_documentation.py`. Omitting `description` will cause a test failure.

## Constraint Count Test

`backend/tests/component/message_bus/operations/requests/test_proposed_change.py::test_get_proposed_change_schema_integrity_constraints` contains hardcoded constraint counts. These counts change whenever schemas are added or removed because `ConstraintValidatorDeterminer` iterates all schemas in the registry and generates one `SchemaUpdateConstraintInfo` per validatable property. After schema changes, run the test to get actual counts and update the assertions. See `#2592` for planned improvements.

## Runtime schema registry cache

Each worker keeps per-branch `SchemaBranch` objects cached in `registry.schema`. The codebase relies on this cache being kept up-to-date, so read the current schema of a branch via `registry.schema.get_schema_branch(name=...)` — do not add defensive `load_schema_from_db` reloads "just in case". One caveat: `get_schema_branch` silently creates an *empty* `SchemaBranch` for a name it has never seen rather than raising, so it is only valid for branches the process has loaded or registered.

In branch merge/rebase tasks, schema loads needed only for migrations (common-ancestor baseline, pre-rebase rollback schema) belong inside the `obj.has_schema_changes` guard so data-only operations skip them.

## Key Locations

| Component | Path |
|-----------|------|
| Core schema definitions | `backend/infrahub/core/schema/definitions/core/` |
| Internal schema definitions | `backend/infrahub/core/schema/definitions/internal/` |
| Generated schemas (do not edit) | `backend/infrahub/core/schema/generated/` |
| RelationshipSchema class | `backend/infrahub/core/schema/relationship_schema.py` |
| AttributeSchema class | `backend/infrahub/core/schema/attribute_schema.py` |
| GenericSchema class | `backend/infrahub/core/schema/generic_schema.py` |
| NodeSchema class | `backend/infrahub/core/schema/node_schema.py` |

## See Also

- [Code Generation](code-generation.md) — How schema definitions become generated code
- [Database Schema](database-schema.md) — How schemas map to Neo4j graph structure
