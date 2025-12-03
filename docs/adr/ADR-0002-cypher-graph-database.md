# ADR-0002: Cypher Graph Database

## Status

Draft

## Context

Infrahub manages infrastructure data as a graph with complex relationships between entities. The data model requires efficient traversal of relationships, querying connected nodes, and maintaining referential integrity across a graph structure.

## Decision

We use Neo4j as the primary database, leveraging Cypher query language for graph operations. The database stores nodes, relationships, and attributes in a native graph structure, with branch-aware temporal properties on edges.

## Consequences

### Positive

- Native graph operations and traversal
- Efficient relationship queries
- Natural representation of infrastructure relationships
- Cypher provides expressive query language
- Strong consistency and ACID transactions

### Negative

- Learning curve for Cypher query language
- Requires careful query optimization
- Database-specific knowledge needed
- Less mature ecosystem compared to SQL databases

## Notes

- All queries use parameterized Cypher to prevent injection
- Custom Query class pattern wraps Cypher queries
- Branch-aware queries filter by branch properties on edges
- Temporal properties (from/to) enable time-travel queries
