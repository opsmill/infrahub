# Research: Virtual Relationships

**Feature**: infp-313-virtual-relationships
**Date**: 2026-03-17

## Decision 1: Schema Definition Approach

**Decision**: Define virtual relationships as a new top-level list on `NodeSchema`/`GenericSchema`, using a path-based traversal specification with double-underscore notation.

**Rationale**:
- Infrahub already uses `__` notation for filter traversal in GraphQL queries (e.g., `location__name__value`), making it a natural fit for path definitions.
- A new schema-level construct (rather than extending `RelationshipSchema`) keeps concerns separated — virtual relationships are computed views, not stored graph edges.
- The existing `SchemaRoot` model supports `nodes`, `generics`, and `extensions` — adding a `virtual_relationships` list to node/generic definitions follows the established pattern.
- The existing `_virtual_relationship_names` set in `SchemaManager` (used for profiles/templates) proves that in-memory-only relationships are already a supported concept.

**Alternatives considered**:
- **Extend RelationshipSchema with a `virtual: bool` flag**: Rejected because virtual relationships have fundamentally different semantics (no stored edges, no write operations, no metadata properties). Mixing them into the same model creates ambiguity.
- **GraphQL-query-based definition**: Rejected because it couples schema definition to a specific query language and makes validation harder. Path notation is simpler and can be validated at schema load time.
- **Kind-based collection (collect all nodes of kind X under subtree)**: Rejected because it's too imprecise — a device might have Interface nodes in multiple relationship paths, and the user needs to control which path to follow.

## Decision 2: Query-Time Resolution (Not Materialized)

**Decision**: Resolve virtual relationships at query time by generating Cypher traversal queries. No materialized edges stored in Neo4j.

**Rationale**:
- Infrahub already has multi-hop traversal in Cypher using `[:IS_RELATED*2..N]` with branch-aware filtering (see `backend/infrahub/core/query/node.py` lines 2339-2376 for hierarchy queries). This pattern can be adapted for virtual relationships.
- Query-time resolution guarantees consistency with current data — no cache invalidation or materialization pipeline needed.
- The 3-node relationship pattern (source → Relationship node → peer) means a 5-hop virtual relationship = 10 Neo4j edges, which is within Neo4j's efficient traversal range.
- Branch-aware filtering via `reduce()` for branch_level scoring across multi-hop paths is already implemented and tested.
- Performance can be addressed later with optional materialization if query times exceed the 2-second SLA.

**Alternatives considered**:
- **Materialized edges (stored in DB)**: Rejected for initial release. Adds significant complexity: write triggers, cache invalidation on data changes, branch merge handling. Can be added later as optimization.
- **Hybrid (cache in Redis/memory)**: Rejected. Adds infrastructure dependency and cache coherence complexity without proven need.

## Decision 3: GraphQL Integration Approach

**Decision**: Generate virtual relationship fields on GraphQL types using the existing `NestedPaginated{Kind}` wrapper pattern, with a dedicated resolver that executes the traversal query.

**Rationale**:
- The GraphQL type generation pipeline (`GraphQLSchemaManager.generate_object_types()`) already dynamically adds relationship fields to types. Virtual relationships can be added in the same pass (Phase 4 of `generate_object_types`).
- Using `NestedPaginated{Kind}` for virtual relationships provides automatic pagination, count, and the standard `edges[].node` response structure — consistent with existing many-cardinality relationships.
- A dedicated resolver (e.g., `VirtualRelationshipResolver`) separates the multi-hop query logic from the standard `ManyRelationshipResolver`.
- Filters can be generated using the same `generate_filters()` method applied to the target kind.

**Alternatives considered**:
- **Reuse ManyRelationshipResolver**: Rejected because virtual relationships need a fundamentally different database query (multi-hop traversal vs. single-hop peer lookup). Trying to make one resolver handle both adds unneeded branching.
- **Separate GraphQL endpoint**: Rejected because it breaks the "virtual relationships look like regular relationships" UX goal.

## Decision 4: Schema Validation Strategy

**Decision**: Validate virtual relationship paths at schema load time by walking each segment against the schema graph.

**Rationale**:
- The schema loading pipeline (`SchemaBranch.process()`) already has pre-validation and validation phases. Virtual relationship path validation fits naturally in the validation phase.
- Each path segment (e.g., `bays` in `bays__line_cards__modules__interfaces`) must correspond to a valid relationship name on the node kind at that position. This can be validated by walking the schema graph without touching the database.
- The target kind (final node in the path) must be recorded for GraphQL type generation.

**Validation rules**:
1. Each segment must be a valid relationship name on the current node kind
2. The path must have at least 2 segments (single-hop = use a regular relationship)
3. Maximum 10 segments (5 logical hops through 3-node relationship pattern)
4. No duplicate virtual relationship names on a single node
5. Virtual relationship names must not conflict with regular relationship names or attribute names

## Decision 5: Frontend Display Approach

**Decision**: Display virtual relationships as tabs on the node detail page, using the same `RelationshipTable` component with infinite-scroll pagination.

**Rationale**:
- Virtual relationships are always many-cardinality (they collect multiple target nodes). The existing tab pattern for many-cardinality relationships (`getRelationshipsVisibleInTab()`) is the natural fit.
- The `RelationshipTable` component already supports pagination, filtering, and navigation to target nodes.
- Virtual relationships should be visually distinguished from regular relationships (e.g., with a badge or icon) so users understand they are computed.
- The `useObjectRelationships` hook and `getObjectRelationshipsFromApi` query builder can be extended to handle virtual relationship queries.

**Key change**: Add a new visibility filter function or extend `getRelationshipsVisibleInTab()` to include virtual relationships. The tab should show a visual indicator that this is a virtual/computed relationship.

## Decision 6: Permission and Branch Handling

**Decision**: Apply permission filtering at the target node level (not intermediate nodes). Resolve virtual relationships using the queried branch context.

**Rationale**:
- Users querying a virtual relationship care about whether they can see the *target* nodes. Intermediate nodes are implementation details of the traversal path.
- Filtering intermediate nodes by permission could silently remove reachable target nodes that the user *should* see (if they have access to the target but not an intermediate node). This would be confusing.
- Branch resolution follows the existing pattern: `Branch.get_query_filter_relationships()` generates branch-aware Cypher filters that are applied to all edges in the traversal. The `reduce()` scoring pattern for multi-hop branch resolution is already tested in hierarchy queries.

## Decision 7: Circular Reference Protection

**Decision**: Detect and prevent circular paths at schema validation time. At query time, use bounded traversal depth as a safety net.

**Rationale**:
- Schema validation can detect obvious circular paths (e.g., `interfaces__device__interfaces`) by checking if the path revisits the same node kind.
- For paths that don't revisit the same kind but could create cycles through polymorphism, the bounded depth (max 10 segments) prevents infinite traversal.
- The existing hierarchy query pattern uses `*2..10` bounded traversal, establishing the precedent.

## Key Technical Findings

### Existing Multi-Hop Query Pattern
```cypher
-- From backend/infrahub/core/query/node.py:2339
MATCH path = (n:Node { uuid: $uuid })
    -[:IS_RELATED*2..10 { hierarchy: $hierarchy }]->(peer:Node)
WHERE $hierarchy IN LABELS(peer)
    AND all(r IN relationships(path) WHERE (branch_filter))
WITH peer, path,
     reduce(br_lvl = 0, r in relationships(path) |
        CASE WHEN r.branch_level > br_lvl THEN r.branch_level ELSE br_lvl END) AS branch_level
```

This pattern is directly adaptable for virtual relationship traversal by replacing the `hierarchy` constraint with relationship-name-based path matching.

### Existing Virtual Relationship Concept
```python
# From backend/infrahub/core/schema/manager.py:49
_virtual_relationship_names: set[str] = {
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,  # "object_template"
    PROFILES_RELATIONSHIP_NAME          # "profiles"
}
```

Virtual relationships already exist as a concept — they are added during schema processing but not persisted. The new feature extends this pattern with user-defined paths.

### 3-Node Relationship Pattern
```
(SourceNode)-[r1:IS_RELATED]->(Relationship { name: identifier })-[r2:IS_RELATED]->(PeerNode)
```

Each logical relationship hop = 2 Neo4j edges. A 5-hop virtual relationship = 10 Neo4j edges = `[:IS_RELATED*10..10]` for fixed-depth or `[:IS_RELATED*2..10]` for variable-depth traversal.

### Schema Extension Mechanism
```yaml
extensions:
  nodes:
    - kind: ExistingNodeKind
      virtual_relationships:
        - name: all_interfaces
          path: bays__line_cards__modules__interfaces
```

Virtual relationships can be added via the existing extension mechanism, allowing modular schema composition.
