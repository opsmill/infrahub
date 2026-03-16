# Feature Specification: Graph Path Traversal

**Feature Branch**: `infp-1991-graph-path-traversal`
**Created**: 2026-03-16
**Status**: Draft
**Input**: User description: "Build a feature that utilizes the neo4j concept of traversal to have two points and be able to see all the nodes that are between those two points."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query Path Between Two Nodes (Priority: P1)

As a network engineer, I want to select two infrastructure nodes (e.g., a server and a firewall) and see all the nodes and relationships that connect them, so I can understand the dependency chain and troubleshoot connectivity issues.

**Why this priority**: This is the core value proposition — without path discovery between two points, no other path-related features are meaningful. It enables users to understand how any two pieces of infrastructure relate to each other through the graph.

**Independent Test**: Can be fully tested by querying the path between any two known connected nodes and verifying the returned nodes match the expected chain. Delivers immediate value for dependency analysis and troubleshooting.

**Acceptance Scenarios**:

1. **Given** two nodes that are connected through one or more intermediate nodes, **When** a user requests the path between them, **Then** the system returns all intermediate nodes and the relationships connecting them in order.
2. **Given** two nodes with multiple possible paths between them, **When** a user requests paths, **Then** the system returns all distinct paths (up to a configurable limit) so the user can compare routes.
3. **Given** two nodes that have no connecting path, **When** a user requests the path between them, **Then** the system returns an empty result with a clear indication that no path exists.

---

### User Story 2 - Visualize Path Results (Priority: P2)

As an infrastructure operator, I want to see the path between two nodes displayed visually, so I can quickly understand the topology and identify potential bottlenecks or single points of failure.

**Why this priority**: Visual representation dramatically increases the usability of path data. Raw node lists are harder to interpret than a visual chain or graph view. However, the query capability (P1) must exist first.

**Independent Test**: Can be tested by requesting a path between two nodes and verifying the UI renders nodes and relationships as a readable visual chain. Delivers value by making path data immediately comprehensible.

**Acceptance Scenarios**:

1. **Given** a path query that returns results, **When** the results are displayed, **Then** nodes appear as labeled elements connected by relationship lines showing the traversal order.
2. **Given** a path with more than 10 intermediate nodes, **When** displayed visually, **Then** the visualization remains readable with scrolling or zooming capabilities.
3. **Given** multiple paths returned between two nodes, **When** displayed, **Then** each path is distinguishable and the user can select individual paths to highlight.

---

### User Story 3 - Filter Path Traversal by Node or Relationship Type (Priority: P3)

As a platform engineer, I want to constrain path traversal to specific node kinds or relationship types, so I can focus on relevant infrastructure layers (e.g., only network devices, only physical connections).

**Why this priority**: Filtering makes the feature practical for large, complex graphs where unfiltered traversal would return too many irrelevant paths. It builds on P1 and P2 to add precision.

**Independent Test**: Can be tested by querying a path with type filters applied and verifying that only nodes/relationships matching the filter appear in results. Delivers value by enabling focused infrastructure analysis.

**Acceptance Scenarios**:

1. **Given** a path query with a node kind filter (e.g., only "NetworkDevice" nodes), **When** executed, **Then** only paths that pass through nodes of the specified kind are returned.
2. **Given** a path query with a relationship type filter, **When** executed, **Then** only paths using the specified relationship types are traversed.
3. **Given** filters that exclude all possible paths, **When** executed, **Then** the system returns an empty result with a clear message.

---

### Edge Cases

- What happens when a user selects the same node as both start and end point? The system should return an informative message that start and end nodes must be different.
- How does the system handle circular paths (cycles in the graph)? The system should detect cycles and avoid infinite traversal by enforcing a maximum depth.
- What happens when the graph is very large and there are thousands of possible paths? The system should enforce a configurable maximum number of paths returned (default: 10) and a maximum traversal depth (default: 20 hops).
- How does the feature behave across branches? Path traversal must respect the current branch context, only following relationships that are active on the selected branch at the queried point in time.
- What happens if one of the specified nodes does not exist? The system should return a clear error identifying which node was not found.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept two node identifiers (by ID or unique key) and return all paths connecting them through the graph.
- **FR-002**: System MUST return paths as ordered sequences of nodes and relationships from start to end.
- **FR-003**: System MUST enforce a configurable maximum traversal depth to prevent unbounded queries (default: 20 hops).
- **FR-004**: System MUST enforce a configurable maximum number of paths returned per query (default: 10).
- **FR-005**: System MUST respect branch context when traversing — only active relationships on the current branch at the current time are followed.
- **FR-006**: System MUST return an empty result set with appropriate messaging when no path exists between the two nodes.
- **FR-007**: System MUST return an error when either the start or end node does not exist.
- **FR-008**: System MUST support filtering traversal by node kind (only traverse through nodes of specified kinds).
- **FR-009**: System MUST support filtering traversal by relationship type (only follow specified relationship types).
- **FR-010**: System MUST detect and handle cycles to prevent infinite traversal loops.
- **FR-011**: System MUST expose path traversal through the existing query interface so it is accessible programmatically.
- **FR-012**: System MUST provide a visual representation of path results in the user interface showing nodes and their connecting relationships.
- **FR-013**: System MUST allow users to select start and end nodes from the UI to initiate a path query.
- **FR-014**: System MUST return metadata for each node and relationship in the path (kind, display label, key attributes).

### Key Entities

- **Path**: An ordered sequence of alternating nodes and relationships connecting a start node to an end node. A single query may return multiple paths.
- **Path Node**: A node encountered during traversal, including its kind, display label, and identifying attributes.
- **Path Relationship**: A relationship traversed between two nodes in the path, including its type and direction.
- **Traversal Configuration**: The set of constraints governing a path query — maximum depth, maximum paths, node kind filters, and relationship type filters.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can discover the path between any two connected nodes in under 5 seconds for graphs with up to 100,000 nodes.
- **SC-002**: Path results accurately reflect all valid routes between two nodes, with no false paths (paths that don't actually exist in the graph at the queried branch/time).
- **SC-003**: Users can visually trace the path between two nodes without needing to manually query intermediate relationships.
- **SC-004**: Filtered path queries return only paths matching the specified constraints, with zero false positives.
- **SC-005**: The feature handles edge cases (no path, same node, cycles, missing nodes) gracefully with clear user-facing feedback in 100% of cases.

## Assumptions

- The existing Infrahub graph model (Node → IS_RELATED → Relationship → IS_RELATED → Node) is the traversal substrate; no changes to the core graph schema are required.
- Path traversal operates as a read-only query; it does not modify the graph.
- The feature builds on the existing branch-aware query infrastructure, reusing temporal and branch filtering patterns already established in the codebase.
- Performance is acceptable for typical infrastructure graphs (thousands to tens of thousands of nodes); optimization for graphs exceeding 100,000 nodes is a future concern.
- The visual representation will integrate into the existing Infrahub web UI rather than requiring a separate application.
