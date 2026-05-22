# Contract: `order_by` entry grammar

This is the author-facing contract for what may appear inside a schema's `order_by` list. The contract is enforced by the schema validator at load time; it does not change the wire shape (still `list[str] | None`).

## Accepted entry shapes

| Shape | Example | Notes |
|---|---|---|
| `<attr>__value` | `name__value` | Existing convention. Direction defaults to ascending. |
| `<attr>__value__<dir>` | `name__value__desc` | New: optional direction suffix. |
| `<rel>__<attr>__value` | `account__name__value` | Existing convention; `<rel>` must be cardinality-one. Direction defaults to ascending. |
| `<rel>__<attr>__value__<dir>` | `account__name__value__asc` | New: direction suffix. |
| `node_metadata__<field>` | `node_metadata__created_at` | New: metadata reference. Direction defaults to ascending. |
| `node_metadata__<field>__<dir>` | `node_metadata__updated_at__desc` | New: metadata reference with direction. |

Where:

- `<attr>` is the name of an `AttributeSchema` on the owning node.
- `<rel>` is the name of a cardinality-one `RelationshipSchema` on the owning node.
- `<field>` ∈ `{created_at, updated_at}` (the node-level metadata fields automatically tracked by Infrahub on every node).
- `<dir>` ∈ `{asc, desc}`.

## Rejected at schema load

All rejections produce a single error message that names the offending node kind, echoes the offending entry verbatim, and includes a remediation hint.

| Reject reason | Example bad entry | Remediation hint |
|---|---|---|
| Unsupported metadata field | `node_metadata__created_by` | "Supported metadata fields: `created_at`, `updated_at`." |
| Malformed direction token | `name__value__descending` | "Direction must be `asc` or `desc`." |
| Attribute path does not resolve | `nonexistent__value` | "Attribute `nonexistent` is not defined on `Documentation.Note`." |
| Cardinality-many relationship | `tags__name__value` | "Relationship `tags` is cardinality-many; only cardinality-one relationships may appear in `order_by`." |
| Duplicate target | `["name__value__asc", "name__value__desc"]` | "Target `name.value` appears in `order_by` more than once." |
| Reserved name conflict | An attribute literally named `node_metadata` | "`node_metadata` is a reserved name; rename the attribute or relationship." |
| Empty entry / non-string entry | `""` or `null` inside the list | "`order_by` entries must be non-empty strings." |

## Defaults and back-compat

- An entry with no direction suffix is ascending. This is identical to today's behavior for every `<attr>__value` and `<rel>__<attr>__value` entry, so existing schemas continue to behave as ascending without modification (FR-003, FR-012).
- An empty list and an absent `order_by` are equivalent (unchanged from today).
- Generic inheritance is unchanged: a concrete kind inherits the generic's `order_by` only when the concrete kind has not declared its own (locked in by spec clarification).
