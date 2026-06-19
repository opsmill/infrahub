The GraphQL `order` argument now uses a single, structured interface for ordering results:

- `order: {by: [{field: "name__value", direction: ASC}, {field: "node_metadata__created_at", direction: DESC}]}`
- `field` is an attribute (`name__value`), a relationship attribute (`owner__name__value`), or node metadata (`node_metadata__created_at` / `node_metadata__updated_at`). It no longer carries a trailing `__asc`/`__desc` suffix.
- `direction` is an enum (`ASC` / `DESC`) and defaults to `ASC` when omitted.
- When provided, `by` fully replaces the schema's `order_by` default. It works at the root level, on many-relationship fields, and on hierarchical (`ancestors` / `descendants`) relationships.

The `node_metadata` field on the `order` argument is deprecated; order by metadata through `by` using the `node_metadata__created_at` / `node_metadata__updated_at` fields instead. `node_metadata` cannot be combined with `by` in the same input.

Schema-level `order_by` entries are unchanged and still reference object-level metadata (`node_metadata__created_at`) with an optional `__asc`/`__desc` suffix. A UUID tiebreaker is always appended so ordering is stable across paths.

Breaking change: `node_metadata` is a reserved attribute and relationship name. Schemas that literally use `node_metadata` as an attribute or relationship name will fail to load and must rename the offending element.
