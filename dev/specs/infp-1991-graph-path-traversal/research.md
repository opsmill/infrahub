# Research: Graph Path Traversal

## R1: Neo4j Path-Finding Approach

**Decision**: Use Neo4j's `allShortestPaths` with variable-length relationship matching and Infrahub's existing branch-aware filtering.

**Rationale**: Infrahub already has a proven pattern for variable-length path traversal in `NodeGetHierarchyQuery` using `[:IS_RELATED*2..N]`. The `allShortestPaths` function is a native Neo4j capability that efficiently finds all shortest paths between two nodes. Combined with the existing `Branch.get_query_filter_path()` for temporal/branch filtering and `all(r IN relationships(path) WHERE ...)` guards, this approach is both performant and branch-safe.

**Alternatives considered**:
- **Custom BFS/DFS in Python**: Rejected — would require multiple round-trips to the database and lose Neo4j's native graph traversal optimizations.
- **APOC path procedures**: Rejected — adds an external dependency; native Cypher is sufficient and already used throughout the codebase.
- **shortestPath (singular)**: Rejected — returns only one path; users need to see all shortest paths to compare routes.

## R2: Graph Traversal Substrate

**Decision**: Traverse through Node → IS_RELATED → Relationship → IS_RELATED → Node edges, skipping the intermediate Relationship vertex in results but using it for filtering.

**Rationale**: Infrahub's graph model interposes a `Relationship` vertex between every pair of connected `Node` vertices. A single "hop" in user terms is actually 2 edges in Neo4j (Node → IS_RELATED → Relationship → IS_RELATED → Node). The existing `NodeGetHierarchyQuery` uses `*2..N` (even numbers) for this reason. Path results should present only the `Node` vertices and the relationship metadata (from the `Relationship` vertex) to users, abstracting the internal graph structure.

**Alternatives considered**:
- **Expose Relationship vertices in results**: Rejected — adds noise; users care about the connected nodes and the type of connection, not the intermediary.
- **Traverse only direct relationships**: Rejected — would miss multi-hop paths, which is the entire point of the feature.

## R3: API Exposure

**Decision**: Expose path traversal as a custom top-level GraphQL query in `InfrahubBaseQuery`, following the pattern of `InfrahubSearchAnywhere` and `DiffTreeQuery`.

**Rationale**: Infrahub's GraphQL schema has two categories: auto-generated CRUD queries (from schema nodes) and custom utility queries (search, diff, status, IPAM). Path traversal is a utility query — it operates across node types and isn't tied to a single entity. The registration pattern is well-established: define a `Field()` in `graphql/queries/`, export in `__init__.py`, register in `schema.py`'s `InfrahubBaseQuery`.

**Alternatives considered**:
- **REST endpoint**: Rejected — Infrahub is GraphQL-first for data queries; REST is used only for non-data operations (file upload, schema management).
- **Extension of existing node queries**: Rejected — path traversal is a cross-entity operation, not a filter on a single node type.

## R4: Frontend Visualization

**Decision**: Use `@xyflow/react` (React Flow) with `dagre` for automatic hierarchical layout.

**Rationale**: React Flow is the dominant React graph visualization library (35K GitHub stars, 3.6M weekly npm downloads, actively maintained). At ~56 KB gzipped it's a reasonable addition. Its DOM-based rendering (SVG + HTML) means infrastructure nodes can be rendered as rich React components with icons, labels, and status badges. Automatic hierarchical layout via `dagre` (~7 KB) produces clean source-to-destination path layouts ideal for infrastructure topology. Path highlighting is straightforward — style nodes/edges based on which path is selected. React 19 and TypeScript are fully supported.

**Alternatives considered**:
- **Custom SVG**: Rejected — would require reimplementing zoom, pan, node interaction, and layout from scratch. React Flow provides all of this out of the box.
- **reagraph**: Built-in path highlighting but 375 KB gzipped (7x larger), smaller community (1K stars). Its built-in path-finding is redundant since Infrahub computes paths server-side.
- **cytoscape.js**: React wrapper (`react-cytoscapejs`) hasn't been published in 4 years, likely incompatible with React 19.
- **sigma.js**: Optimized for rendering 10K-100K+ node graphs; over-engineered for displaying specific paths.
- **react-force-graph**: Force-directed layout produces tangled, non-deterministic layouts unsuitable for infrastructure path visualization.

## R5: Branch-Aware Filtering Strategy

**Decision**: Reuse `Branch.get_query_filter_path()` applied to all relationships in the path via `all(r IN relationships(path) WHERE ...)`.

**Rationale**: This is the exact pattern used by `NodeGetHierarchyQuery` and all subquery filters in the codebase. It ensures paths only follow relationships that are active on the current branch at the queried point in time. The method handles both default and non-default branches, temporal filtering, and soft-delete semantics. No custom branch logic is needed.

**Alternatives considered**:
- **Post-query filtering in Python**: Rejected — would require fetching all paths regardless of branch and filtering after, wasting database resources.
- **Custom branch filter**: Rejected — the existing method is well-tested and handles all edge cases.

## R6: Cycle Detection and Depth Limits

**Decision**: Use Neo4j's built-in cycle prevention in `shortestPath`/`allShortestPaths` combined with an explicit max path length parameter.

**Rationale**: Neo4j's shortest path algorithms inherently avoid cycles (a shortest path never revisits a node). For general `allPaths`, the variable-length constraint `*2..N` with a configurable N provides an upper bound. The existing `max_depth_search_hierarchy` config pattern can be extended for path traversal. Default max depth of 20 hops (40 edges in Neo4j terms) balances usability with performance.

**Alternatives considered**:
- **Application-level cycle detection**: Rejected — unnecessary overhead when the database handles it natively.
- **No depth limit**: Rejected — unbounded traversal on large graphs could cause timeouts or memory issues.
