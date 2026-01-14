# Neo4j Database Schema

> Part of: `dev/knowledge/backend/` | Related: [Query Pattern](query-pattern.md), [Architecture](architecture.md)

Infrahub uses a temporal graph database with branch support. All queries target a specific branch and point in time.

## Branches

Every Infrahub instance has at least two branches:

| Branch | Name | Description |
|--------|------|-------------|
| Default | typically `"main"` | Source for all user branches; target for all merges |
| Global | `"-global-"` | Branch-agnostic data (user accounts, tokens); no branching/merging |

**User branches** fork from the default branch and include all default branch data at creation time (tracked by `branched_from`). Maximum depth is 2 (default + user branch).

## Vertices

### Root

Single vertex anchoring the graph.

| Property | Type | Description |
|----------|------|-------------|
| `uuid` | string | UUID |
| `graph_version` | integer | Current graph version |
| `default_branch` | string | Name of default branch |

### Branch

Represents a branch. Linked to Root via `IS_PART_OF` edge.

| Property | Type | Description |
|----------|------|-------------|
| `name` | string | Branch name |
| `branched_from` | timestamp | When branch split from default (ISO format: `2025-05-07T12:47:40.208184Z`) |

### Node

Application data nodes. Labels: `Node`, `CoreNode`, `{kind}`, plus inherited schema kinds.

| Property | Type | Description |
|----------|------|-------------|
| `uuid` | string | UUID |
| `kind` | string | Node type (also in labels) |
| `branch_support` | string | `"aware"`, `"local"`, or `"agnostic"` |

### Relationship

Links two Node vertices. Label: `Relationship`.

| Property | Type | Description |
|----------|------|-------------|
| `uuid` | string | UUID |
| `name` | string | Relationship name |
| `branch_support` | string | `"aware"`, `"local"`, or `"agnostic"` |

### Attribute

Stores attribute metadata. Label: `Attribute`.

| Property | Type | Description |
|----------|------|-------------|
| `uuid` | string | UUID |
| `name` | string | Attribute name |
| `branch_support` | string | `"aware"`, `"local"`, or `"agnostic"` |

### Vertex Metadata

`Node`, `Relationship`, and `Attribute` vertices support optional metadata (set only on default/global branches):

| Property | Type | Description |
|----------|------|-------------|
| `created_by` | string? | UUID of creating user (or `"__system__"`) |
| `updated_by` | string? | UUID of last updating user (or `"__system__"`) |
| `created_at` | timestamp? | When added to default/global branch |
| `updated_at` | timestamp? | When last updated on default/global branch |

### AttributeValue / AttributeValueIndexed

Stores attribute values. Labels always include `AttributeValue`. Labels include `AttributeValueIndexed` if the value is indexed.

| Property | Type | Description |
|----------|------|-------------|
| `value` | any | The attribute value (`"NULL"` for null) |
| `is_default` | boolean | Whether this is a default value |

### Boolean

Stores boolean values for Boolean attributes and `IS_PROTECTED` metadata edges. Label: `Boolean`.

| Property | Type | Description |
|----------|------|-------------|
| `value` | boolean | `true` or `false` |

## Edges

### Common Edge Properties

All edges have:

| Property | Type | Description |
|----------|------|-------------|
| `branch` | string | Branch name |
| `branch_level` | integer | `1` = default/global, `2` = user branch |
| `from` | timestamp | When edge became valid |
| `to` | timestamp? | When edge became invalid (`NULL` if still valid) |
| `status` | string | `"active"` or `"deleted"` |
| `from_user_id` | string? | UUID of creating user (or `"__system__"`) |
| `to_user_id` | string? | UUID of deleting user (only if `to` is set) |

### Edge Types

| Type | Pattern | Description |
|------|---------|-------------|
| `IS_PART_OF` | `(:Node)-[:IS_PART_OF]->(:Root)` | Links Node to Root |
| `IS_RELATED` | `(:Node)-[:IS_RELATED]->(:Relationship)<-[:IS_RELATED]-(:Node)` | Links two Nodes via Relationship |
| `HAS_ATTRIBUTE` | `(:Node)-[:HAS_ATTRIBUTE]->(:Attribute)` | Links Node to Attribute (one per schema-defined attribute) |
| `HAS_VALUE` | `(:Attribute)-[:HAS_VALUE]->(:AttributeValue)` | Links Attribute to value (exactly one active per branch/time) |
| `IS_PROTECTED` | `(:Attribute)-[:IS_PROTECTED]->(:Boolean)` | Protection flag for Attribute or Relationship (default: `false`) |
| `HAS_SOURCE` | `(:Attribute)-[:HAS_SOURCE]->(:Node)` | Links Attribute or Relationship to its source Node (optional, for provenance) |
| `HAS_OWNER` | `(:Attribute)-[:HAS_OWNER]->(:Node)` | Links Attribute or Relationship to its owner Node (optional) |

### Attribute/Relationship Metadata Edges

`Attribute` and `Relationship` vertices have additional metadata edges:

```cypher
// Flag properties (link to Boolean vertices, mandatory)
(attr:Attribute)-[:IS_PROTECTED]->(protected:Boolean)

// Node properties (link to Node vertices, optional)
(attr:Attribute)-[:HAS_SOURCE]->(source:Node)
(attr:Attribute)-[:HAS_OWNER]->(owner:Node)
```

Same patterns apply to `Relationship` vertices:

```cypher
(rel:Relationship)-[:IS_PROTECTED]->(protected:Boolean)
(rel:Relationship)-[:HAS_SOURCE]->(source:Node)
(rel:Relationship)-[:HAS_OWNER]->(owner:Node)
```

| Edge | Target | Default | Purpose |
|------|--------|---------|---------|
| `IS_PROTECTED` | `Boolean` | `false` | Prevents modification when `true` |
| `HAS_SOURCE` | `Node` | none | Tracks data provenance (where data came from) |
| `HAS_OWNER` | `Node` | none | Tracks ownership (who is responsible for data) |

## Determining Edge Activity

An edge is **active** for a query (branch + timestamp) when ALL conditions are met:

### 1. Temporal Range

```cypher
r.from < $time AND (r.to IS NULL OR r.to >= $time)
```

### 2. Status

```cypher
r.status = "active"
```

### 3. Branch Scope

| Query Branch | Branches Included | Time Used |
|--------------|-------------------|-----------|
| Default | `{"-global-", default_branch}` | Query time |
| User | `{"-global-", default_branch}` | `branched_from` time |
| | `{"-global-", user_branch}` | Query time |

### 4. Priority Resolution

When multiple edges match, select winner then validate status:

```cypher
ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
LIMIT 1
```

1. Highest `branch_level` (user branch overrides default)
2. Most recent `from` timestamp
3. `status ASC` tiebreaker (`"active"` before `"deleted"`)

### Example Query

```cypher
MATCH (n:Node)-[r:IS_PART_OF]->(root:Root)
WHERE (
    (r.branch IN ["-global-", $default_branch]
     AND r.from < $branched_from_time
     AND (r.to IS NULL OR r.to >= $branched_from_time))
    OR
    (r.branch IN ["-global-", $user_branch]
     AND r.from < $time
     AND (r.to IS NULL OR r.to >= $time))
)
WITH n, r
ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
LIMIT 1
WITH n, r
WHERE r.status = "active"
RETURN n
```

Implementation: `Branch.get_query_filter_path()` in `backend/infrahub/core/branch/models.py`.

## Graph Patterns

### Node with Attributes

```cypher
(n:Node)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[:HAS_VALUE]->(val:AttributeValue)
```

### Relationships Between Nodes

**Bidirectional** (default for different node types):

```cypher
(n1:Node)-[:IS_RELATED]->(r:Relationship)<-[:IS_RELATED]-(n2:Node)
```

**Unidirectional** (required for same node type):

```cypher
(n1:Node)-[:IS_RELATED]->(r:Relationship)-[:IS_RELATED]->(n2:Node)
```

Outbound on `n1`, inbound on `n2`.

### Node Existence

```cypher
(n:Node)-[:IS_PART_OF]->(root:Root)
```

## Temporal and Branch Rules

### Soft Deletes

- **Same branch**: Set `to` property to deletion time
- **User branch deleting default branch data**: Add `status="deleted"` edge with `from` = deletion time

### Branch Deletion

Hard-deletes all edges on the branch and the `Branch` vertex.

### Edge Constraints

For any vertex pair:

- One edge per `(edge_type, branch, status)` combination
- At least one `status="active"` edge required
- `status="deleted"` edge requires prior `status="active"` edge on same branch OR on default branch before `branched_from`

### Valid Path Rules

- Edges must be on same branch or deeper (`branch_level` >= preceding edges)
- If any edge has `status="deleted"`, all following edges must also be deleted

## Node Lifecycle

### Creation

```cypher
// Creates IS_PART_OF edge
{status: "active", from: $creation_time, to: NULL}
```

### Deletion

```cypher
// Adds IS_PART_OF edge (sets to on existing active edge if same branch)
{status: "deleted", from: $deletion_time, to: NULL}
```

## Attribute Updates

- Attributes are per-Node (not shared)
- Value updates modify only `(:Attribute)-[:HAS_VALUE]->(:AttributeValue)`
- `(:Node)-[:HAS_ATTRIBUTE]->(:Attribute)` changes only on Node deletion or schema updates
- Multiple Attributes can reference the same AttributeValue

## Schema Migration (Name/Namespace/Inheritance)

When a NodeSchema's `name`, `namespace`, or `inherit_from` changes, labels must be updated while preserving history.

**Node labels include:** `Node`, `CoreNode`, `{kind}`, plus all inherited GenericSchema kinds.

**Migration process:**

1. Create new Node vertices with same UUID but updated labels
2. Set all edges on old Node vertices to deleted
3. Create active edges on new Node vertices

**Result:** Multiple Node vertices with same UUID exist, but only one is active per branch/time.

**Important:** All UUID-based queries must account for duplicate-UUID nodes by filtering for the active one.

## Finding Active Nodes on Default/Global Branch

When querying for Node vertices that are active on the default or global branch (e.g., to update metadata), you must verify that the relevant edges are active. This is especially important when multiple Node vertices with the same UUID may exist due to schema migrations.

### Pattern: Active Node via Edge Path

To find Nodes that are currently active on `branch_level = 1`:

1. Filter edges by `branch_level = 1`
2. Order by `from DESC, status ASC` to get the latest edge
3. Take the first result with `LIMIT 1`
4. Verify the edge has `status = "active"` and `to IS NULL`

### Example: Active Peer Nodes for a Relationship

When a Relationship vertex may have IS_RELATED edges to more than 2 Node vertices (due to schema migrations), find only the active peer nodes:

```cypher
// Get distinct peer nodes connected via branch_level = 1 edges
CALL (rl) {
    MATCH (peer:Node)-[r_rel:IS_RELATED]-(rl)
    WHERE r_rel.branch_level = 1
    RETURN DISTINCT peer
}
WITH rl, peer
// For each peer, verify IS_RELATED edge is active
CALL (peer, rl) {
    MATCH (peer)-[r_rel:IS_RELATED]-(rl)
    WHERE r_rel.branch_level = 1
    ORDER BY r_rel.from DESC, r_rel.status ASC
    LIMIT 1
    WITH peer, r_rel
    WHERE r_rel.status = "active" AND r_rel.to IS NULL
    // Also verify IS_PART_OF edge is active (node exists)
    MATCH (peer)-[r_part:IS_PART_OF]->(:Root)
    WHERE r_part.branch_level = 1
    ORDER BY r_part.from DESC, r_part.status ASC
    LIMIT 1
    WITH peer, r_part
    WHERE r_part.status = "active" AND r_part.to IS NULL
    // Node is confirmed active, safe to update
    SET peer.updated_at = $at, peer.updated_by = $user_id
}
```

### Key Points

- **Two-edge validation**: Verify both the connecting edge (e.g., IS_RELATED) AND the IS_PART_OF edge to Root
- **DISTINCT first**: When multiple vertices may match, get DISTINCT nodes first, then validate each
- **Order then filter**: Always `ORDER BY ... LIMIT 1` first, then `WHERE status = "active"` to handle the case where the latest edge is a deletion
- **No `to` timestamp**: `to IS NULL` ensures the edge is currently valid (not expired)

## See Also

- [Query Pattern](query-pattern.md) - How to write database queries
- [Architecture](architecture.md) - Backend architecture overview
