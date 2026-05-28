# Phase 1 Data Model

This feature does not introduce persistent entities. The data model captures the parsed representation of an `order_by` entry — the in-process value used by the schema validator and the three list-query paths.

## Entity: `OrderDirection` (existing enum, reused)

Defined in `backend/infrahub/constants/enums.py`. Values: `ASC`, `DESC`. Already used by `OrderModel` and `FieldAttributeRequirement`.

No change.

## Entity: `OrderByTargetKind`

New string enum in the new module `backend/infrahub/core/schema/order_by.py`.

| Variant | Meaning |
|---|---|
| `ATTRIBUTE` | A regular schema attribute property path, e.g. `name__value`. |
| `RELATIONSHIP_ATTRIBUTE` | A traversal into a cardinality-one peer attribute, e.g. `account__name__value`. |
| `METADATA` | A node-level metadata field, e.g. `node_metadata__created_at`. |

## Entity: `OrderByMetadataField`

New string enum, same module.

| Variant | Literal | Source |
|---|---|---|
| `CREATED_AT` | `created_at` | `METADATA_CREATED_AT` constant (existing) |
| `UPDATED_AT` | `updated_at` | `METADATA_UPDATED_AT` constant (existing) |

The supported field set is identical to the GraphQL `InfrahubNodeMetadataOrder` input (FR-010): `created_at`, `updated_at`. No user-reference fields (`created_by`, `updated_by`).

## Entity: `ParsedOrderByEntry` (discriminated union of frozen dataclasses)

`ParsedOrderByEntry` is a type alias for a three-variant union; each variant carries only the fields it actually needs. `kind` is a `ClassVar[Literal[...]]` so callers narrow via `isinstance` or `parsed.kind is OrderByTargetKind.<...>` without runtime assertions.

```python
@dataclass(frozen=True, slots=True)
class _ParsedOrderByBase:
    raw: str                          # the original string from order_by
    direction: OrderDirection         # always set; defaults to ASC when no suffix


@dataclass(frozen=True, slots=True)
class ParsedAttributeOrderBy(_ParsedOrderByBase):
    attribute_name: str
    property_name: str
    kind: ClassVar[Literal[OrderByTargetKind.ATTRIBUTE]] = OrderByTargetKind.ATTRIBUTE


@dataclass(frozen=True, slots=True)
class ParsedRelationshipAttributeOrderBy(_ParsedOrderByBase):
    relationship_name: str
    attribute_name: str
    property_name: str
    kind: ClassVar[Literal[OrderByTargetKind.RELATIONSHIP_ATTRIBUTE]] = OrderByTargetKind.RELATIONSHIP_ATTRIBUTE


@dataclass(frozen=True, slots=True)
class ParsedMetadataOrderBy(_ParsedOrderByBase):
    metadata_field: OrderByMetadataField
    kind: ClassVar[Literal[OrderByTargetKind.METADATA]] = OrderByTargetKind.METADATA


type ParsedOrderByEntry = (
    ParsedAttributeOrderBy | ParsedRelationshipAttributeOrderBy | ParsedMetadataOrderBy
)
```

Each variant exposes a `target_key` property used for duplicate detection (see below).

Invariants:

- `direction` is always set (defaulted to `ASC` when no suffix is provided).
- `raw` is preserved so error messages and `__repr__` can echo what the author wrote.
- Path resolution (verifying that a relationship's peer schema actually has the named attribute, checking cardinality, etc.) is **not** the parser's job — it stays in `validate_schema_path` at schema-load time. The parser is a pure classifier + direction extractor and needs only `node_schema.attribute_names` / `node_schema.relationship_names` (no `SchemaBranch`).

### `target_key` rules

For deduplication (FR-006):

| Kind | `target_key` shape | Example |
|---|---|---|
| `ATTRIBUTE` | `("attribute", attr_name, prop_name)` | `("attribute", "name", "value")` |
| `RELATIONSHIP_ATTRIBUTE` | `("relationship_attribute", rel_name, attr_name, prop_name)` | `("relationship_attribute", "account", "name", "value")` |
| `METADATA` | `("metadata", field_name)` | `("metadata", "created_at")` |

Two `order_by` entries with the same `target_key` are a hard rejection regardless of whether their directions match.

## Grammar

```ebnf
order_by_entry  = metadata_entry | attribute_entry | relationship_attribute_entry ;

metadata_entry              = "node_metadata" "__" metadata_field [ "__" direction ] ;
attribute_entry             = attr_name "__" attr_prop [ "__" direction ] ;
relationship_attribute_entry = rel_name "__" attr_name "__" attr_prop [ "__" direction ] ;

metadata_field  = "created_at" | "updated_at" ;
direction       = "asc" | "desc" ;
attr_prop       = "value" ;                  (* current convention; reserved for future props *)
attr_name, rel_name = identifier from schema ;
```

The leading `node_metadata` prefix is the only disambiguator between metadata entries and regular paths. The author-facing literal `node_metadata` is reserved by FR-005, which guarantees no attribute or relationship can shadow it.

## Validation rules (all enforced at schema load)

| Rule | Source FR | Failure detail in error |
|---|---|---|
| Entry parses to one of the three valid grammar shapes | FR-001, FR-002 | Echo the raw entry; show the supported grammar. |
| If metadata, `metadata_field` ∈ `{created_at, updated_at}` | FR-004 | List supported metadata fields. |
| Direction token, if present, ∈ `{asc, desc}` | FR-007 | List the two valid tokens. |
| Attribute/relationship path resolves on the owning schema | (existing) | Echo node kind + offending segment. |
| No two entries share `target_key` | FR-006 | Echo both raw entries + the shared target. |
| No attribute or relationship is named `node_metadata` | FR-005 | Echo node kind + offending member name; instruct rename. |
| Every error names the offending node + entry + remediation hint | FR-011 | (cross-cuts the above) |

## Inheritance behavior

No new inheritance state. The concrete-kind inheritance handler copies `order_by` from a generic only when the concrete kind has not declared its own `order_by` (existing behavior, locked in by spec clarification).

The rename-tracking helper that rewrites attribute references when a generic's attribute is renamed must skip entries whose `kind == METADATA` (a metadata entry references a reserved field, not a renamable attribute). This is a pure guard, not new state.
