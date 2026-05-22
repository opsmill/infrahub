# Contract: `order_by` application across the three list paths

This contract pins the observable ordering behavior at each place where Infrahub returns a list of nodes. All three paths must produce identical orderings for the same schema (FR-008).

## The three paths

| Path | Cypher source | Caller examples |
|---|---|---|
| Top-level node list | `NodeGetListQuery` (`backend/infrahub/core/query/node.py`) | GraphQL `query { DocumentationNote { ... } }`; REST list endpoint; SDK `client.all()`. |
| Relationship-peer list | `RelationshipGetListQuery` (`backend/infrahub/core/query/relationship.py`) | GraphQL nested field on a parent: `parent { documentation_notes { ... } }`. |
| Hierarchy list | `NodeGetHierarchyQuery` (`backend/infrahub/core/query/node.py`) | Hierarchy traversal: parent → children of a hierarchical kind. |

## Ordering rules (uniform across the three paths)

When `schema.order_by` is non-empty and no query-time ordering argument is provided:

1. Parse each entry into `ParsedOrderByEntry` (see [grammar.md](grammar.md) and `data-model.md`).
2. Emit each parsed entry into the outer `ORDER BY` clause, in declaration order, with its parsed direction. Each subsequent entry is a secondary sort relative to the prior entries.
3. After all parsed entries, append the node UUID as a final ascending tiebreaker (FR-013):
   - Top-level path: `n.uuid ASC`.
   - Relationship-peer path: `peer.uuid ASC`.
   - Hierarchy path: `peer.uuid ASC`.

When `schema.order_by` is empty or absent and no query-time ordering argument is provided:

- Top-level path: behavior unchanged from today (UUID ascending).
- Relationship-peer + hierarchy paths: behavior unchanged from today (`peer.uuid` fallback).

## Query-time precedence (FR-009)

When a caller passes an explicit ordering argument:

- The schema's `order_by` is **ignored entirely**. No stacking, no tiebreaker fallback to schema entries.
- The query-time ordering becomes the primary ordering source; the implicit UUID tiebreaker is still appended after it.
- This is a behavior change from today (today the two stacked). Changelog must call this out.

## Metadata entries on each path

| Path | Metadata cypher source |
|---|---|
| Top-level | Reuse existing `_get_metadata_order_fields` / `_add_created_metadata_subquery` / `_add_updated_metadata_subquery` (`node.py:1699+`, `1742+`), driving them from the parsed schema entries rather than from `requested_order` alone. |
| Relationship-peer | New analogue helpers (or reuse with a `node_alias="peer"` parameter) that materialize `created_at` / `updated_at` for each peer and append the resulting alias to the outer `ORDER BY`. |
| Hierarchy | Same as relationship-peer with the same `peer` alias convention. |

## Examples

### Schema declares `order_by: ["node_metadata__created_at__desc"]`

| Path | Outer ORDER BY |
|---|---|
| Top-level | `created_at_value DESC, n.uuid ASC` |
| Relationship-peer | `peer_created_at_value DESC, peer.uuid ASC` |
| Hierarchy | `peer_created_at_value DESC, peer.uuid ASC` |

### Schema declares `order_by: ["status__value__desc", "name__value"]`

| Path | Outer ORDER BY |
|---|---|
| Top-level | `order1 DESC, order2 ASC, n.uuid ASC` |
| Relationship-peer | `order1 DESC, order2 ASC, peer.uuid ASC` |
| Hierarchy | `order1 DESC, order2 ASC, peer.uuid ASC` |

(`order1`, `order2` are the result aliases from `build_subquery_order`.)

### Schema declares `order_by: ["name__value"]`, caller passes `order: { node_metadata: { created_at: DESC } }`

All three paths: schema entries ignored; outer ORDER BY is `created_at_value DESC, <uuid alias> ASC`.

## Performance constraint

- No new query patterns. Each new direction suffix adds at most one Cypher keyword (`ASC`/`DESC`) to the outer `ORDER BY` clause. Each new metadata entry on relationship-peer / hierarchy adds one subquery comparable in cost to the existing top-level metadata subquery.
- UUID tiebreaker is appended once per query and is on a property already projected; no incremental traversal cost.
