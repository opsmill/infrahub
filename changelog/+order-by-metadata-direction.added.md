Schema `order_by` entries can now reference object-level metadata and carry an explicit direction suffix:

- `node_metadata__created_at` and `node_metadata__updated_at` order by object-level timestamps.
- Any entry may end with `__asc` or `__desc` (e.g. `name__value__desc`, `node_metadata__created_at__desc`). Without a suffix, ascending order is assumed.
- The new grammar is honored consistently across top-level object listings, relationship-peer listings, and hierarchy listings. A UUID tiebreaker is always appended so ordering is stable across paths.

Behavior change: a query-time `order` argument now fully replaces the schema-level `order_by` default instead of being layered on top of it.

GraphQL `order` argument accepts an `order_by: [String!]` list using the same grammar as the schema's `order_by` field. This works at the root level, on many-relationship fields, and on hierarchical (`ancestors` / `descendants`) relationships. `order_by` cannot be combined with the legacy `node_metadata` form in the same argument.

Breaking change: `node_metadata` is now a reserved attribute and relationship name. Schemas that literally use `node_metadata` as an attribute or relationship name will fail to load and must rename the offending element.
