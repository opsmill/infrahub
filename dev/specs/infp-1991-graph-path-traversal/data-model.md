# Data Model: Graph Path Traversal

## Overview

Path traversal is a **read-only query feature** — it does not introduce new persistent entities into the graph. The data model below describes the **query input** and **response structures** that flow through the system.

## Query Input

### PathTraversalRequest

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| source_id | string (UUID) | yes | — | UUID of the start node |
| destination_id | string (UUID) | yes | — | UUID of the end node |
| max_depth | integer | no | 20 | Maximum number of node hops (translates to max_depth * 2 edges in Neo4j) |
| max_paths | integer | no | 10 | Maximum number of paths to return |
| node_filter | list[string] | no | [] | Node kinds to include (empty = all kinds) |
| relationship_filter | list[string] | no | [] | Relationship names to include (empty = all) |

### Validation Rules

- `source_id` and `destination_id` must reference existing nodes
- `source_id` != `destination_id`
- `max_depth` must be between 1 and 50
- `max_paths` must be between 1 and 100
- `node_filter` values must be valid schema kinds
- `relationship_filter` values must be valid relationship names

## Query Response

### PathTraversalResponse

| Field | Type | Description |
|-------|------|-------------|
| paths | list[Path] | Ordered list of paths found, shortest first |
| source | PathNode | The start node |
| destination | PathNode | The end node |
| total_paths_found | integer | Total number of paths discovered (may exceed max_paths) |

### Path

| Field | Type | Description |
|-------|------|-------------|
| nodes | list[PathNode] | Ordered sequence of nodes from source to destination (inclusive) |
| relationships | list[PathRelationship] | Ordered sequence of relationships connecting the nodes |
| depth | integer | Number of node hops in this path |

**Invariant**: `len(relationships) == len(nodes) - 1`

### PathNode

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Node UUID |
| kind | string | Node schema kind (e.g., "InfraDevice", "InfraInterface") |
| display_label | string | Human-readable label for the node |
| db_id | string | Internal database element ID |

### PathRelationship

| Field | Type | Description |
|-------|------|-------------|
| id | string (UUID) | Relationship UUID |
| name | string | Relationship name (e.g., "interfaces", "connected_to") |
| direction | string | "outbound" or "inbound" relative to traversal direction |

## Relationship to Existing Graph Schema

This feature traverses the **existing** graph structure without modification:

```
(Node:source) -[:IS_RELATED]-> (Relationship) <-[:IS_RELATED]- (Node:intermediate)
     ↓                              ↓
  PathNode[0]                 PathRelationship[0]     PathNode[1]
```

- Each user-visible "hop" traverses 2 IS_RELATED edges through a Relationship vertex
- The Relationship vertex provides the `name` and metadata
- Branch/temporal filtering is applied to IS_RELATED edges via `get_query_filter_path()`
- Only edges with `status = "active"` on the queried branch at the queried time are followed
