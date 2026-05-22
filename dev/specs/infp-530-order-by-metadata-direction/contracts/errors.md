# Contract: Schema-load-time error messages

Every validation error raised by this feature MUST satisfy FR-011: cite the offending node, cite the offending entry, and include a remediation hint.

## Error shape

All errors are raised through the existing schema-validation error path so the standard `SchemaNotValidError` (or equivalent) wrapper is preserved. The message string follows this template:

```text
{node_kind}: {what_is_wrong} (entry: {offending_entry!r}). {remediation}
```

| Slot | Example values |
|---|---|
| `{node_kind}` | `Documentation.Note`, `Core.Account` |
| `{what_is_wrong}` | One of the rejection cases listed below. |
| `{offending_entry!r}` | The author's literal string, repr-quoted. For reserved-name errors this is the attribute or relationship name. |
| `{remediation}` | Concrete next step. Must be specific to the failure. |

## Rejection cases and message templates

| Case | Message |
|---|---|
| Unsupported metadata field | `{kind}: unknown metadata field (entry: 'node_metadata__foo'). Supported metadata fields: created_at, updated_at.` |
| Malformed direction token | `{kind}: invalid direction (entry: 'name__value__descending'). Direction must be 'asc' or 'desc'.` |
| Unresolvable attribute path | `{kind}: attribute 'nonexistent' not defined on this schema (entry: 'nonexistent__value').` |
| Cardinality-many relationship in order_by | `{kind}: relationship 'tags' is cardinality-many (entry: 'tags__name__value'). Only cardinality-one relationships are supported in order_by.` |
| Duplicate target across entries | `{kind}: target 'name.value' appears in order_by more than once (entries: 'name__value__asc', 'name__value__desc'). Each target may appear at most once.` |
| Reserved-name conflict | `{kind}: 'node_metadata' is a reserved name (attribute: 'node_metadata'). Rename this attribute or relationship.` |
| Empty / non-string entry | `{kind}: order_by entries must be non-empty strings (entry: '').` |

## Where errors surface

- Errors are raised during `SchemaBranch.validate_order_by()` and, for the reserved-name case, during the existing reserved-name pass at `schema_branch.py:1166-1174`.
- Errors are raised once per offending entry; do not coalesce multiple errors into a single string. The existing `SchemaNotValidError` aggregation surfaces them all when the loader runs to completion.

## What MUST NOT happen

- A malformed entry MUST NOT silently degrade to default ordering at query time. Spec User Story 3 motivates this: silent fallback hides typos.
- An error MUST NOT expose internal type names (e.g., `ParsedOrderByEntry`, `OrderByTargetKind`) — keep messages author-facing.
