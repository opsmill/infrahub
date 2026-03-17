# Feature Specification: Virtual Relationships

**Feature Branch**: `infp-313-virtual-relationships`
**Created**: 2026-03-17
**Status**: Draft
**Input**: User description: "Implement Virtual Relationships (computed relationships) on schema nodes that allow users to define higher-level, multi-hop relationship paths — enabling simplified access to downstream nodes without data duplication."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define a Virtual Relationship in Schema (Priority: P1)

A schema designer wants to define a virtual relationship on a parent node (e.g., "Device") that automatically collects all descendant nodes of a given kind (e.g., "Interface") by traversing intermediate relationships (bays → line cards → modules → interfaces). The designer specifies a traversal path in the schema definition, and the system resolves this path to present matching nodes as a first-class relationship on the parent node.

**Why this priority**: This is the foundational capability — without the ability to define virtual relationships, no other feature in this spec is possible. It directly eliminates the core pain point of choosing between schema correctness and query simplicity.

**Independent Test**: Can be fully tested by loading a schema with a virtual relationship definition, creating data that matches the traversal path, and verifying the virtual relationship returns the correct set of nodes.

**Acceptance Scenarios**:

1. **Given** a schema where "Device" has a virtual relationship defined to collect all "Interface" nodes via the path `bays__line_cards__modules__interfaces`, **When** a user queries the Device node, **Then** the virtual relationship field returns all Interface nodes reachable through that path.
2. **Given** a schema with a virtual relationship definition that references an invalid path (e.g., a relationship name that doesn't exist), **When** the schema is loaded, **Then** the system rejects the schema with a clear validation error indicating which path segment is invalid.
3. **Given** a schema with a virtual relationship, **When** the underlying data changes (e.g., a new module with interfaces is added to a line card), **Then** the virtual relationship on the parent Device reflects the updated set of interfaces.

---

### User Story 2 - Query Virtual Relationships via API (Priority: P1)

A network engineer or automation script queries a Device and wants to retrieve all its interfaces without knowing the intermediate schema structure. They query the virtual relationship field just like any other relationship, receiving a flat collection of the target nodes.

**Why this priority**: Query access is co-equal with definition — a virtual relationship that can't be queried has no value. This enables both human workflows and programmatic consumption (SDK, automation, AI/MCP).

**Independent Test**: Can be tested by issuing a query against a node with a virtual relationship and verifying the response contains the expected nodes with correct data.

**Acceptance Scenarios**:

1. **Given** a Device with a virtual relationship "all_interfaces" and the device has 12 interfaces spread across 3 modules in 2 bays, **When** a user queries `Device.all_interfaces`, **Then** all 12 interfaces are returned in the response.
2. **Given** a Device with a virtual relationship, **When** a user queries the virtual relationship with filters (e.g., only enabled interfaces), **Then** only the matching subset of target nodes is returned.
3. **Given** a Device with no downstream interfaces (empty bays), **When** a user queries the virtual relationship, **Then** an empty collection is returned (not an error).

---

### User Story 3 - Browse Virtual Relationships in UI (Priority: P2)

A network operations team member navigates to a Device in the Infrahub UI and sees virtual relationships displayed alongside regular relationships. They can click to expand and view all collected nodes (e.g., all interfaces) without manually clicking through bays, line cards, and modules.

**Why this priority**: The UI is critical for non-technical users (operations teams) but is a presentation layer on top of the query capability in P1. It delivers the "simplified access" promise for users who don't write queries.

**Independent Test**: Can be tested by navigating to a node with a virtual relationship in the UI and verifying all target nodes are displayed and navigable.

**Acceptance Scenarios**:

1. **Given** a Device with a virtual relationship to interfaces, **When** a user views the Device detail page in the UI, **Then** the virtual relationship is displayed with the count and list of collected interfaces.
2. **Given** a virtual relationship that resolves to more than 50 nodes, **When** a user views it in the UI, **Then** results are paginated and the total count is shown.
3. **Given** a user clicks on a node in the virtual relationship list, **When** they navigate to it, **Then** they land on that node's detail page (standard navigation behavior).

---

### User Story 4 - Cross-Domain Impact Analysis via Virtual Relationships (Priority: P2)

A service provider operations team needs to understand the impact of a device failure. A virtual relationship is defined on the Device node that traverses the path `interfaces__circuits__containers__services`. When a device has a problem, the team can immediately see all affected services without constructing complex queries or writing custom code.

**Why this priority**: This is a high-value use case that extends beyond simple parent-child traversal into cross-domain impact analysis. It validates that virtual relationships work across different node kinds and relationship types.

**Independent Test**: Can be tested by defining a virtual relationship that crosses domain boundaries (device → network → service) and verifying the collected nodes are correct.

**Acceptance Scenarios**:

1. **Given** a Device with a virtual relationship "affected_services" defined via path `interfaces__circuits__containers__services`, **When** the device has 4 interfaces connected to 3 circuits providing 2 services, **Then** querying the virtual relationship returns the 2 service nodes.
2. **Given** a virtual relationship path that traverses one-to-many relationships at each hop, **When** queried, **Then** all reachable target nodes are collected (no duplicates).

---

### User Story 5 - Bidirectional/Peer Traversal (e.g., Cable Connections) (Priority: P3)

A network engineer wants to find "what's on the other end" of a cable connection. A virtual relationship on an Interface traverses through the cable to the peer interface and its parent device (path: `connected_cable__peer_interface__device`). This supports peer-to-peer relationship traversal, not just hierarchical parent-child.

**Why this priority**: This extends virtual relationships beyond hierarchical traversal to peer/lateral relationships, which is a distinct and important pattern but builds on the same foundational mechanism.

**Independent Test**: Can be tested by defining a virtual relationship that traverses a peer relationship (cable) and verifying the correct remote node is returned.

**Acceptance Scenarios**:

1. **Given** Interface A connected to Interface B via a Cable, and a virtual relationship "remote_device" defined on Interface, **When** a user queries Interface A's virtual relationship, **Then** the device hosting Interface B is returned.
2. **Given** an Interface with no cable attached, **When** the virtual relationship is queried, **Then** an empty result is returned (not an error).

---

### Edge Cases

- What happens when a virtual relationship path contains a circular reference (e.g., device → interface → device)?
- How does the system handle a virtual relationship where intermediate nodes have been deleted but the path definition still exists?
- What happens when a virtual relationship traversal encounters a node the querying user does not have permission to view?
- How are virtual relationships handled across Infrahub branches (e.g., a virtual relationship defined on main but queried on a feature branch with different data)?
- What happens when the same target node is reachable via multiple paths in the traversal (deduplication)?
- How does the system behave when the schema changes and a previously valid path becomes invalid?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow schema designers to define virtual relationships on any node kind, specifying a traversal path through intermediate relationships to collect target nodes.
- **FR-002**: System MUST validate virtual relationship path definitions at schema load time, rejecting schemas where any segment of the path does not correspond to a valid relationship on the expected node kind. When the peer kind is a Generic, the system MUST also check relationships available on concrete nodes that implement that Generic (via other inherited Generics).
- **FR-003**: System MUST resolve virtual relationships at query time, returning all target nodes reachable via the defined traversal path from the source node.
- **FR-004**: System MUST deduplicate target nodes when the same node is reachable via multiple traversal paths.
- **FR-005**: System MUST support filtering on virtual relationship results (e.g., filter collected interfaces by status or name).
- **FR-006**: System MUST support pagination on virtual relationship results.
- **FR-007**: System MUST display virtual relationships in the UI alongside regular relationships, with the ability to browse and navigate to collected nodes.
- **FR-008**: System MUST respect existing access control and permissions when resolving virtual relationships — nodes the user cannot access MUST be excluded from results.
- **FR-009**: System MUST support virtual relationships across Infrahub branches, resolving the path using the data present in the queried branch.
- **FR-010**: System MUST support traversal paths of at least 5 hops (intermediate relationships).
- **FR-011**: System MUST return an empty collection (not an error) when a virtual relationship path resolves to zero target nodes.
- **FR-012**: Virtual relationships MUST be read-only (query and view only) in the initial release. Users cannot create, modify, or link target nodes through a virtual relationship. Write support may be considered in a future phase once usage patterns are established.

### Key Entities

- **Virtual Relationship Definition**: A schema-level construct on a node kind that specifies a name, a traversal path (ordered sequence of relationship names), and the expected target node kind. It is metadata — not stored as data edges in the graph.
- **Traversal Path**: An ordered sequence of relationship names (e.g., `bays__line_cards__modules__interfaces`) that the system follows from a source node to collect target nodes. Each segment must correspond to a valid relationship on the node kind at that position in the chain.
- **Source Node**: The node on which the virtual relationship is defined (e.g., Device).
- **Target Nodes**: The collection of nodes reached at the end of the traversal path (e.g., all Interfaces).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can retrieve all target nodes of a virtual relationship in a single query, without needing to know or specify intermediate nodes — reducing query complexity from N hops to 1 step.
- **SC-002**: Virtual relationship query results are returned within 2 seconds for traversal paths up to 5 hops with up to 1,000 target nodes.
- **SC-003**: Schema designers can define a virtual relationship in under 5 minutes using the standard schema definition workflow.
- **SC-004**: 100% of virtual relationship results are consistent with the actual data in the graph — no stale, missing, or duplicate nodes.
- **SC-005**: Non-technical operations team members can view virtual relationship data in the UI without writing any queries or code.
- **SC-006**: AI/MCP integrations can access virtual relationship data through the same query interface, reducing the context needed to interpret multi-hop relationships by at least 60%.

## Assumptions

- Virtual relationships are defined at the schema level (not per-instance). A virtual relationship on the "Device" kind applies to all Device instances.
- Traversal paths are unidirectional — defined from source toward target following named relationships.
- Virtual relationships are computed at query time (not materialized/cached), ensuring consistency with current data. Performance optimization (caching, materialization) may be added later but is not in initial scope.
- The path notation uses double-underscore separation (e.g., `bays__line_cards__modules__interfaces`), consistent with existing Infrahub query filter conventions.
- Virtual relationships do not create actual edges in the graph database — they are computed views.
- Users cannot create, update, or delete target nodes through a virtual relationship (read-only in initial release; write support deferred to a future phase).

## Scope Boundaries

### In Scope

- Schema-level virtual relationship definitions with path-based traversal
- Query resolution (API and UI) of virtual relationships
- Filtering and pagination on virtual relationship results
- Schema validation of path definitions
- Branch-aware resolution
- Deduplication of target nodes

### Out of Scope

- Write operations through virtual relationships (creating/linking nodes via the virtual path)
- Performance optimization via materialization or caching (future enhancement)
- Virtual relationships defined dynamically at query time (ad-hoc traversals)
- Reverse virtual relationships (automatically defining the inverse path)
- Virtual relationships with conditional/branching paths (e.g., "follow path A or path B depending on node type")
