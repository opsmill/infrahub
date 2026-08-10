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

## Read-only and Display Tier

Two `AttributeSchema` flags govern how a field is exposed, independent of what it stores.

`read_only=True` marks a field system-managed. Read-only attributes and relationships are excluded from the generated GraphQL `Create` / `Update` input types, so a mutation that supplies one fails at GraphQL **parse time** (`Field '<name>' is not defined by type '<Kind>UpdateInput'`) rather than at runtime; read-only relationships are additionally rejected at the relationship-mutation layer. A read-only field is therefore writable only by server-side code that constructs the node directly, never through GraphQL, REST, or a schema load. Pair it with `allow_override=AllowOverrideType.NONE` to stop an inheriting node from dropping the flag. Input-generation enforcement lives in `backend/infrahub/graphql/manager.py`; the relationship-mutation guard in `backend/infrahub/graphql/mutations/relationship.py`.

`display=SchemaAttributeDisplay.EXTRA` places a field in the UI's extra/advanced tier: the schema-driven UI hides it from the default detail view, but a user can reveal it via the extra-attributes toggle. It is independent of `read_only` and of API exposure; an `EXTRA` field is always queryable through GraphQL/REST. Use it for audit or provenance fields that should stay out of the default view yet remain machine-readable. `CoreAccountGroup.origin` combines all three: `read_only=True`, `allow_override=AllowOverrideType.NONE`, `display=SchemaAttributeDisplay.EXTRA`.

## Constraint Count Test

`backend/tests/component/message_bus/operations/requests/test_proposed_change.py::test_get_proposed_change_schema_integrity_constraints` contains hardcoded constraint counts. These counts change whenever schemas are added or removed because `ConstraintValidatorDeterminer` iterates all schemas in the registry and generates one `SchemaUpdateConstraintInfo` per validatable property. After schema changes, run the test to get actual counts and update the assertions. See `#2592` for planned improvements.

## Field Visibility and the Write / Read / Internal Models

Every schema field carries a `visibility` classification in its `extra` metadata, defined by
the `Visibility` enum in `backend/infrahub/core/constants/schema.py`. The three levels are
ordinal and nested — `write ⊆ read ⊆ internal`:

| Level | Who may see/set it | Examples |
|-------|--------------------|----------|
| `WRITE` | User may submit it on load | `name`, `namespace`, `attributes`, `relationships` |
| `READ` | Returned on `GET /api/schema` but not settable | `inherited`, `used_by`, `hierarchy`, derived `kind` |
| `INTERNAL` | Backend-only, never exposed | internal bookkeeping fields |

Fields default to `INTERNAL` unless their definition sets a higher `visibility`, so a new
field is hidden until it is deliberately classified.

### Model families

The `internal.py` definitions remain the single source of truth. `invoke backend.generate`
renders two model families from them by filtering each field on its visibility level (see
`SdkSchemaGenerator` in `tasks/backend.py`, entered through `_generate_schemas_sdk`):

- **write models** — include only `WRITE` fields and set `extra="ignore"`, so a read-only,
  internal, or unknown field in a submitted payload is dropped by pydantic itself instead of
  reaching the loaded schema. That holds at every nesting level, and the per-kind discriminated
  unions (attribute kinds, computed-attribute kinds) resolve first, so each variant keeps only
  the fields valid for it. Constrained values that *are* settable are still validated and
  rejected when out of range. No hand-written filtering step is needed at the boundary.
- **read models** — include `WRITE` and `READ` fields, describing the shape returned by
  `GET /api/schema`.

Because both families are generated from the same definitions, a field's classification is
declared once and both the write contract and the read shape follow automatically.

### Reporting the fields a payload sets but the contract drops

`extra="ignore"` decides that a non-write field has no effect; it does not decide whether the
user hears about it. That split is driven by a third generated artifact,
`python_sdk/infrahub_sdk/schema/generated/contract.py`, holding the non-settable field names of
each write class:

- a name **in** the table is dropped and reported as a **warning** — a `READ`-level field, the
  `id`/`state` bookkeeping every internal schema model carries on the nested value models
  (parameters, choices, computed attribute, extensions), or a field belonging to a sibling
  variant of a discriminated union. These are all names a schema read back from Infrahub can
  carry, so accepting them is what keeps the read → edit → load round trip working.
- a name **not** in the table is an **error**, since the only ways to produce one are a typo and
  a field that no longer exists.

The table is built by `SdkSchemaGenerator._read_only_fields` from two diffs: the read variant of
a class against its write variant, and the internal pydantic counterpart of a value model against
its generated write model. Root-level keys that `GET /api/schema` adds over the write root
(`main`, `profiles`, `templates`, `namespaces`) are listed explicitly and pinned against
`SchemaReadAPI` by a test.

Applying the table means knowing which model governs each place in the payload.
`_collect_extra_fields` in `validate.py` walks the submitted payload alongside the *validated*
write document: the validated document resolves the model at every location — including which
union member an attribute matched — so the raw keys are compared against the fields that location
actually accepts. One consequence: extra fields are reported only once the payload validates,
so a payload rejected for another reason names them on the next run.

A field whose valid values are a closed set is generated as a dedicated `(str, Enum)` class in
`python_sdk/infrahub_sdk/schema/generated/enums.py` and referenced by both families, rather than
as a bare `str` or an inline `Literal`. The allowed values therefore travel with the model, so a
client — or an agent reading the contract — can enumerate them without consulting the server.

`version` is required on the write root. The load endpoint has always required it, so the
generated model requires it too; otherwise offline validation would accept a payload the server
rejects.

### Backend → SDK dependency

The generated write/read models are rendered **into the Python SDK**, at
`python_sdk/infrahub_sdk/schema/generated/{write,read}.py`. The output is self-contained
(only `pydantic` + `typing`) so it imports with just the SDK installed — no backend, no
server. This inverts the usual direction: the backend's schema definitions are the source,
and the generator writes the artifact into the SDK submodule, where it is committed and
shipped inside the published package.

`POST /api/schema/load` enforces the write contract at the boundary by calling the SDK's
`validate_schema()` (`python_sdk/infrahub_sdk/schema/validate.py`) from the
`validate_write_contract` validator on `SchemaLoadAPI` (`backend/infrahub/api/schema.py`).
The same validator runs offline in the SDK, so a client gets the identical field-level
verdict before submitting. After changing a field's `visibility` (or adding a field), run
`invoke backend.generate` and commit the regenerated SDK models alongside the backend
change; CI fails if the generated artifact is stale.

## Key Locations

| Component | Path |
|-----------|------|
| Core schema definitions | `backend/infrahub/core/schema/definitions/core/` |
| Internal schema definitions | `backend/infrahub/core/schema/definitions/internal/` |
| Generated schemas (do not edit) | `backend/infrahub/core/schema/generated/` |
| `Visibility` enum | `backend/infrahub/core/constants/schema.py` |
| SDK write/read generator | `SdkSchemaGenerator` in `tasks/backend.py` |
| Generated SDK write/read models (do not edit) | `python_sdk/infrahub_sdk/schema/generated/{write,read}.py` |
| Generated non-settable field table (do not edit) | `python_sdk/infrahub_sdk/schema/generated/contract.py` |
| Offline write-contract validator | `python_sdk/infrahub_sdk/schema/validate.py` |
| RelationshipSchema class | `backend/infrahub/core/schema/relationship_schema.py` |
| AttributeSchema class | `backend/infrahub/core/schema/attribute_schema.py` |
| GenericSchema class | `backend/infrahub/core/schema/generic_schema.py` |
| NodeSchema class | `backend/infrahub/core/schema/node_schema.py` |

## See Also

- [Code Generation](code-generation.md) — How schema definitions become generated code
- [Database Schema](database-schema.md) — How schemas map to Neo4j graph structure
- [ADR 0010](../../adr/0010-generated-user-facing-schema-contract.md) — Why the user-facing
  contract is generated into the SDK, and how submission reports the fields it does not apply
