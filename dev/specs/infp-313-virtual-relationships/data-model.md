# Data Model: Virtual Relationships

**Feature**: infp-313-virtual-relationships
**Date**: 2026-03-17

## Entities

### VirtualRelationshipSchema

A schema-level definition that lives on a `NodeSchema` or `GenericSchema`. It is **not** stored as edges in Neo4j — it is metadata that instructs the query layer how to traverse existing relationships to collect target nodes.

**Fields**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Unique name within the node (e.g., `all_interfaces`). Must be lowercase, 3-64 chars, no conflicts with attributes or relationships. |
| `label` | string | no | Auto-generated from name | Human-friendly display label |
| `description` | string | no | null | Short description (max 128 chars) |
| `path` | string | yes | — | Double-underscore-separated traversal path (e.g., `bays__line_cards__modules__interfaces`). Each segment is a relationship name. Min 2 segments, max 10 segments. |
| `peer` | string | yes (derived) | — | The kind of target nodes at the end of the path. Derived and validated from the path during schema processing, but can be explicitly specified for validation. |
| `order_weight` | int | no | null | Frontend ordering (lowest first), consistent with `RelationshipSchema.order_weight` |

**Validation Rules**:
1. `name` must be unique across attributes, relationships, AND virtual relationships on the same node
2. Each segment of `path` must be a valid relationship name on the node kind at that position in the chain
3. Path must have >= 2 segments (single-hop should use regular relationships)
4. Path must have <= 10 segments (bounded traversal depth)
5. Path must not create a circular reference (same node kind visited twice)
6. The final kind resolved from the path must exist in the schema

**State Transitions**: None — virtual relationships are immutable schema metadata. They change only through schema updates (load new schema version).

### Relationship to Existing Entities

```
NodeSchema / GenericSchema
├── attributes: list[AttributeSchema]
├── relationships: list[RelationshipSchema]
└── virtual_relationships: list[VirtualRelationshipSchema]   ← NEW

SchemaRoot
├── nodes: list[NodeSchema]
├── generics: list[GenericSchema]
└── extensions: SchemaExtension
    └── nodes: list[NodeExtensionSchema]
        ├── attributes: list[AttributeSchema]
        ├── relationships: list[RelationshipSchema]
        └── virtual_relationships: list[VirtualRelationshipSchema]   ← NEW
```

### GraphQL Type Mapping

Virtual relationships produce the same GraphQL types as many-cardinality relationships:

```
VirtualRelationshipSchema(name="all_interfaces", path="bays__line_cards__modules__interfaces")
    ↓ generates
GraphQL Field: all_interfaces: NestedPaginatedInfraInterface!
    ↓ with resolver
VirtualRelationshipResolver (multi-hop Cypher query)
```

The response structure is identical to regular many-cardinality relationships:

```graphql
type NestedPaginatedInfraInterface {
  count: Int!
  edges: [NestedEdgedInfraInterface!]!
}

type NestedEdgedInfraInterface {
  node: InfraInterface
  node_metadata: InfrahubNodeMetadata
  # Note: no "properties" field — virtual relationships have no relationship metadata
}
```

**Key difference from regular relationships**: Virtual relationship edges do NOT include `properties` (is_protected, owner, source) or `relationship_metadata` because there is no stored relationship node to carry this metadata.

## Schema YAML Definition Format

### Inline Definition

```yaml
nodes:
  - name: Device
    namespace: Infra
    attributes:
      - name: hostname
        kind: Text
        unique: true
    relationships:
      - name: interfaces
        peer: InfraInterface
        cardinality: many
        kind: Component
    virtual_relationships:
      - name: all_interfaces
        label: "All Interfaces"
        description: "All interfaces across all modules, line cards, and bays"
        path: bays__line_cards__modules__interfaces
      - name: affected_services
        label: "Affected Services"
        description: "All services reachable through this device's connections"
        path: interfaces__circuits__containers__services
```

### Extension Definition

```yaml
extensions:
  nodes:
    - kind: InfraDevice
      virtual_relationships:
        - name: all_interfaces
          path: bays__line_cards__modules__interfaces
```

## Neo4j Query Pattern

Virtual relationships do NOT create any new data in Neo4j. They generate Cypher traversal queries at query time.

### Single Virtual Relationship Resolution

For path `bays__line_cards__modules__interfaces` on a Device:

```cypher
MATCH (source:Node { uuid: $source_id })
WHERE "InfraDevice" IN LABELS(source)
MATCH path = (source)
  -[r1:IS_RELATED]->(:Relationship { name: $seg0_id })
  -[r2:IS_RELATED]->(hop1:Node)
  -[r3:IS_RELATED]->(:Relationship { name: $seg1_id })
  -[r4:IS_RELATED]->(hop2:Node)
  -[r5:IS_RELATED]->(:Relationship { name: $seg2_id })
  -[r6:IS_RELATED]->(hop3:Node)
  -[r7:IS_RELATED]->(:Relationship { name: $seg3_id })
  -[r8:IS_RELATED]->(target:Node)
WHERE $target_kind IN LABELS(target)
  AND all(r IN relationships(path) WHERE (branch_filter))
WITH DISTINCT target,
     reduce(br_lvl = 0, r in relationships(path) |
       CASE WHEN r.branch_level > br_lvl THEN r.branch_level ELSE br_lvl END
     ) AS branch_level
ORDER BY branch_level DESC
RETURN target.uuid AS target_id
```

Parameters:
- `$seg0_id` through `$seg3_id`: The relationship identifiers for each path segment
- `$target_kind`: The expected target node kind label
- Branch filter: Standard Infrahub branch/temporal filter applied to all edges

### Count Query

Same traversal with `RETURN count(DISTINCT target) AS count` instead of returning target IDs.

### Pagination

Add `SKIP $offset LIMIT $limit` before the final RETURN.
